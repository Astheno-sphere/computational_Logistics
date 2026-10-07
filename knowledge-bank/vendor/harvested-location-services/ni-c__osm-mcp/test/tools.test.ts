import { afterEach, describe, expect, it, vi } from 'vitest';
import { Client, InMemoryTransport } from '@modelcontextprotocol/client';

import { loadConfig } from '../src/config.js';
import { jsonResult, untrustedResult } from '../src/result.js';
import { createServer } from '../src/server.js';

async function connect(env: Record<string, string> = {}): Promise<Client> {
  const server = createServer(loadConfig(env as NodeJS.ProcessEnv));
  const [clientTransport, serverTransport] =
    InMemoryTransport.createLinkedPair();
  const client = new Client({ name: 'test', version: '0.0.0' });
  await Promise.all([
    client.connect(clientTransport),
    server.connect(serverTransport),
  ]);
  // Listing loads every output schema into the client, so each success-path
  // call below is validated on the client side too, not only by the server.
  await client.listTools();
  return client;
}

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

function stubFetch(handler: (url: string, init?: RequestInit) => Response) {
  const mock = vi.fn(async (url: string | URL | Request, init?: RequestInit) =>
    handler(String(url), init)
  );
  vi.stubGlobal('fetch', mock);
  return mock;
}

function firstText(result: Awaited<ReturnType<Client['callTool']>>): string {
  const content = result.content as Array<{ type: string; text?: string }>;
  return content[0]?.text ?? '';
}

function parseJson<T>(result: Awaited<ReturnType<Client['callTool']>>): T {
  const text = firstText(result);
  return JSON.parse(text.slice(text.indexOf('{'))) as T;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('route', () => {
  it('geocodes waypoint names through Nominatim before routing', async () => {
    const urls: string[] = [];
    stubFetch((url) => {
      urls.push(url);
      if (url.includes('nominatim')) {
        return jsonResponse([
          { lat: '49.7596', lon: '6.6439', display_name: 'Trier, Germany' },
        ]);
      }
      return jsonResponse({
        code: 'Ok',
        routes: [{ distance: 44_000, duration: 2400, legs: [] }],
      });
    });
    const client = await connect();
    const result = await client.callTool({
      name: 'route',
      arguments: { waypoints: ['Trier', '49.6116,6.1319'], profile: 'car' },
    });
    expect(result.isError).toBeFalsy();
    expect(urls[0]).toContain('nominatim.openstreetmap.org/search');
    expect(urls[1]).toContain('/routed-car/');
    const data = parseJson<{ waypoints: string[] }>(result);
    expect(data.waypoints[0]).toBe('Trier, Germany');
  });

  it('fails with a clear message when a waypoint cannot be geocoded', async () => {
    stubFetch(() => jsonResponse([]));
    const client = await connect();
    const result = await client.callTool({
      name: 'route',
      arguments: {
        waypoints: ['Nowhereville-XYZ', '49.6,6.1'],
        profile: 'foot',
      },
    });
    expect(result.isError).toBe(true);
    expect(firstText(result)).toContain('no location found');
  });

  it('returns turn-by-turn steps when requested', async () => {
    stubFetch(() =>
      jsonResponse({
        code: 'Ok',
        routes: [
          {
            distance: 1200,
            duration: 900,
            legs: [
              {
                distance: 1200,
                duration: 900,
                steps: [
                  {
                    distance: 700,
                    name: 'Simeonstraße',
                    maneuver: { type: 'depart' },
                  },
                  {
                    distance: 500,
                    name: 'Hauptmarkt',
                    maneuver: { type: 'turn', modifier: 'left' },
                  },
                  { distance: 0, name: '', maneuver: { type: 'arrive' } },
                ],
              },
            ],
          },
        ],
      })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'route',
      arguments: {
        waypoints: ['49.75,6.64', '49.76,6.65'],
        profile: 'foot',
        include_steps: true,
      },
    });
    const data = parseJson<{ steps: Array<{ instruction: string }> }>(result);
    expect(data.steps).toHaveLength(2);
    expect(data.steps[1]!.instruction).toBe('turn left onto Hauptmarkt');
  });

  it('adds a rate-limit hint on HTTP 429 from the routing service', async () => {
    stubFetch(() => new Response('rate limited', { status: 429 }));
    const client = await connect();
    const result = await client.callTool({
      name: 'route',
      arguments: { waypoints: ['49.75,6.64', '49.76,6.65'], profile: 'foot' },
    });
    expect(result.isError).toBe(true);
    expect(firstText(result)).toContain('wait ~30 seconds');
  });
});

describe('route_matrix', () => {
  it('returns rounded minutes and kilometers', async () => {
    stubFetch(() =>
      jsonResponse({
        code: 'Ok',
        durations: [[600, null]],
        distances: [[1500, null]],
      })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'route_matrix',
      arguments: {
        origins: ['49.75,6.64'],
        destinations: ['49.76,6.65', '49.77,6.66'],
        profile: 'foot',
      },
    });
    const data = parseJson<{
      durations_minutes: (number | null)[][];
      distances_km: (number | null)[][];
    }>(result);
    expect(data.durations_minutes).toEqual([[10, null]]);
    expect(data.distances_km).toEqual([[1.5, null]]);
  });
});

describe('optimize_route', () => {
  it('returns the optimized visiting order with legs', async () => {
    const mock = stubFetch(() =>
      jsonResponse({
        code: 'Ok',
        trips: [
          {
            distance: 9000,
            duration: 7200,
            legs: [
              { distance: 3000, duration: 2400 },
              { distance: 3000, duration: 2400 },
              { distance: 3000, duration: 2400 },
            ],
          },
        ],
        waypoints: [
          { waypoint_index: 0 },
          { waypoint_index: 2 },
          { waypoint_index: 1 },
        ],
      })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'optimize_route',
      arguments: {
        stops: ['49.75,6.64', '49.76,6.65', '49.77,6.66'],
        profile: 'bike',
      },
    });
    const url = new URL(String(mock.mock.calls[0]![0]));
    expect(url.pathname).toContain('/routed-bike/trip/v1/driving/');
    expect(url.searchParams.get('roundtrip')).toBe('true');
    expect(url.searchParams.get('source')).toBe('first');
    const data = parseJson<{
      optimized_order: string[];
      legs: unknown[];
    }>(result);
    expect(data.optimized_order).toEqual([
      '49.75,6.64',
      '49.77,6.66',
      '49.76,6.65',
      '49.75,6.64 (back to start)',
    ]);
    expect(data.legs).toHaveLength(3);
  });
});

describe('isochrone', () => {
  it('summarizes a Valhalla contour as bounding box and reach', async () => {
    const mock = stubFetch(() =>
      jsonResponse({
        features: [
          {
            properties: { contour: 15 },
            geometry: {
              type: 'LineString',
              coordinates: [
                [6.62, 49.74],
                [6.66, 49.76],
                [6.64, 49.77],
              ],
            },
          },
        ],
      })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'isochrone',
      arguments: { center: '49.75,6.64', profile: 'foot', minutes: 15 },
    });
    expect(String(mock.mock.calls[0]![0])).toContain(
      'valhalla1.openstreetmap.de/isochrone'
    );
    const data = parseJson<{
      engine: string;
      budget: string;
      bounding_box: { north: number };
      reach: { north: string };
    }>(result);
    expect(data.engine).toBe('valhalla');
    expect(data.budget).toBe('15 min');
    expect(data.bounding_box.north).toBe(49.77);
    expect(data.reach.north).toMatch(/km|m/);
  });

  it('summarizes a contour with more points than an argument list holds', async () => {
    /*
     * End to end, because the fold in geo.ts only helps if the tool actually
     * uses it. 200 000 points is past the ~150 000 argument ceiling of this
     * runtime and well inside the 8 MB response cap, so it is a shape a
     * barely-generalizing Valhalla instance really produces.
     */
    const coordinates = Array.from({ length: 200_000 }, (_, index) => [
      6.6 + (index % 1000) / 100_000,
      49.7 + (index % 997) / 100_000,
    ]);
    coordinates.push([6.5, 49.9]);
    stubFetch(() =>
      jsonResponse({
        features: [
          {
            properties: { contour: 120 },
            geometry: { type: 'LineString', coordinates },
          },
        ],
      })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'isochrone',
      arguments: { center: '49.75,6.64', profile: 'car', minutes: 120 },
    });
    expect(result.isError).toBeFalsy();
    const data = parseJson<{ bounding_box: { north: number; west: number } }>(
      result
    );
    expect(data.bounding_box.north).toBe(49.9);
    expect(data.bounding_box.west).toBe(6.5);
  });

  it('uses ORS isochrones when a key is configured', async () => {
    const mock = stubFetch(() =>
      jsonResponse({
        features: [
          {
            properties: { value: 900 },
            geometry: { coordinates: [[[6.62, 49.74]]] },
          },
        ],
      })
    );
    const client = await connect({ ORS_API_KEY: 'test-key-0123456789' });
    const result = await client.callTool({
      name: 'isochrone',
      arguments: { center: '49.75,6.64', profile: 'car', kilometers: 5 },
    });
    expect(result.isError).toBeFalsy();
    const url = String(mock.mock.calls[0]![0]);
    expect(url).toContain('/v2/isochrones/driving-car');
    const data = parseJson<{ engine: string; budget: string }>(result);
    expect(data.engine).toBe('openrouteservice');
    expect(data.budget).toBe('5 km');
  });
});

describe('geocode', () => {
  it('uses Photon when requested', async () => {
    const mock = stubFetch(() =>
      jsonResponse({
        features: [
          {
            geometry: { coordinates: [6.64, 49.75] },
            properties: { name: 'Porta Nigra', city: 'Trier' },
          },
        ],
      })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'geocode',
      arguments: { query: 'porta ngira', provider: 'photon' },
    });
    expect(String(mock.mock.calls[0]![0])).toContain('photon.komoot.io/api');
    const data = parseJson<{ provider: string; results: unknown[] }>(result);
    expect(data.provider).toBe('photon');
    expect(data.results).toHaveLength(1);
  });

  it('returns an explanatory note when nothing matches', async () => {
    stubFetch(() => jsonResponse([]));
    const client = await connect();
    const result = await client.callTool({
      name: 'geocode',
      arguments: { query: 'zzzz-does-not-exist' },
    });
    const data = parseJson<{ results: unknown[]; note: string }>(result);
    expect(data.results).toEqual([]);
    expect(data.note).toContain('No match');
  });
});

describe('reverse_geocode', () => {
  it('returns the nearest address', async () => {
    stubFetch(() =>
      jsonResponse({
        lat: '49.7546',
        lon: '6.6424',
        display_name: 'Hauptmarkt, Trier, Germany',
        osm_type: 'node',
        osm_id: 42,
      })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'reverse_geocode',
      arguments: { latitude: 49.7546, longitude: 6.6424 },
    });
    const data = parseJson<{ result: { label: string } }>(result);
    expect(data.result.label).toBe('Hauptmarkt, Trier, Germany');
  });

  it('reports when nothing is found', async () => {
    stubFetch(() => jsonResponse({ error: 'Unable to geocode' }));
    const client = await connect();
    const result = await client.callTool({
      name: 'reverse_geocode',
      arguments: { latitude: 0, longitude: 0 },
    });
    const data = parseJson<{ result: null; note: string }>(result);
    expect(data.result).toBeNull();
  });
});

describe('poi_details', () => {
  it('returns the full tag set with a map link', async () => {
    stubFetch(() =>
      jsonResponse({
        elements: [
          {
            type: 'node',
            id: 240109189,
            lat: 49.7596,
            lon: 6.6439,
            tags: {
              name: 'Porta Nigra',
              historic: 'city_gate',
              opening_hours: 'Mo-Su 09:00-18:00',
              website: 'https://example.com',
            },
          },
        ],
      })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'poi_details',
      arguments: { osm_id: 'node/240109189' },
    });
    const data = parseJson<{
      name: string;
      map: string;
      tags: Record<string, string>;
    }>(result);
    expect(data.name).toBe('Porta Nigra');
    expect(data.map).toBe('https://www.openstreetmap.org/node/240109189');
    expect(data.tags.opening_hours).toBe('Mo-Su 09:00-18:00');
  });

  it('errors on an unknown element', async () => {
    stubFetch(() => jsonResponse({ elements: [] }));
    const client = await connect();
    const result = await client.callTool({
      name: 'poi_details',
      arguments: { osm_id: 'way/1' },
    });
    expect(result.isError).toBe(true);
    expect(firstText(result)).toContain('no OSM element found');
  });
});

describe('suggest_meeting_point', () => {
  it('falls back to the midpoint when no venue is found', async () => {
    stubFetch(() => jsonResponse({ elements: [] }));
    const client = await connect();
    const result = await client.callTool({
      name: 'suggest_meeting_point',
      arguments: { locations: ['49.74,6.63', '49.76,6.65'] },
    });
    const data = parseJson<{ note: string; midpoint: { lat: number } }>(result);
    expect(data.note).toContain('No matching venue');
    expect(data.midpoint.lat).toBeCloseTo(49.75, 5);
  });
});

describe('response budgets', () => {
  it('truncates turn-by-turn steps beyond the cap', async () => {
    const steps = Array.from({ length: 150 }, (_, i) => ({
      distance: 10,
      name: `Street ${i}`,
      maneuver: { type: 'turn', modifier: 'left' },
    }));
    stubFetch(() =>
      jsonResponse({
        code: 'Ok',
        routes: [
          {
            distance: 1500,
            duration: 1200,
            legs: [{ distance: 1500, duration: 1200, steps }],
          },
        ],
      })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'route',
      arguments: {
        waypoints: ['49.75,6.64', '49.76,6.65'],
        profile: 'foot',
        include_steps: true,
      },
    });
    const data = parseJson<{ steps: unknown[]; steps_truncated: string }>(
      result
    );
    expect(data.steps).toHaveLength(100);
    expect(data.steps_truncated).toContain('first 100 of 150');
  });

  it('caps the tag count and value length in poi_details', async () => {
    const tags: Record<string, string> = { name: 'Big' };
    for (let i = 0; i < 80; i++) tags[`tag_${i}`] = 'v';
    tags.description = 'x'.repeat(2000);
    stubFetch(() =>
      jsonResponse({
        elements: [{ type: 'node', id: 1, lat: 49.75, lon: 6.64, tags }],
      })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'poi_details',
      arguments: { osm_id: 'node/1' },
    });
    const data = parseJson<{
      tags: Record<string, string>;
      tags_truncated: string;
    }>(result);
    expect(Object.keys(data.tags).length).toBeLessThanOrEqual(60);
    expect(data.tags_truncated).toContain('60 of 82');
    const description = data.tags.description ?? '';
    expect(description.length).toBeLessThanOrEqual(520);
  });
});

/*
 * Review 2026-09-07. What a backend answers reaches an output schema, and
 * the SDK answers a violation with an error result for the whole call. Each
 * test here is a payload a public service (or the community mirror the
 * default Overpass list falls back to) can send, and asserts the tool either
 * answers with the good part or with a sentence — never with
 * "Output validation error".
 */
describe('shaping what the backends answer', () => {
  const nominatim = [
    { lat: '49.7596', lon: '6.6439', display_name: 'Trier, Germany' },
  ];
  const ESC = String.fromCharCode(27);

  it('answers a sentence when OSRM sends a route without a usable distance', async () => {
    stubFetch((url) =>
      url.includes('nominatim')
        ? jsonResponse(nominatim)
        : jsonResponse({ code: 'Ok', routes: [{ legs: [] }] })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'route',
      arguments: { waypoints: ['Trier', '49.6,6.1'], profile: 'car' },
    });
    expect(result.isError).toBe(true);
    expect(firstText(result)).toContain('without a usable distance');
    expect(firstText(result)).not.toContain('Output validation');
  });

  it('treats a distance of 1e999 (Infinity after JSON.parse) the same way', async () => {
    stubFetch(
      () =>
        new Response(
          '{"code":"Ok","routes":[{"distance":1e999,"duration":10,"legs":[]}]}',
          { status: 200, headers: { 'content-type': 'application/json' } }
        )
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'route',
      arguments: { waypoints: ['49.75,6.64', '49.76,6.65'], profile: 'car' },
    });
    expect(result.isError).toBe(true);
    expect(firstText(result)).toContain('without a usable distance');
  });

  it('drops a POI whose coordinate is not a number instead of the whole listing', async () => {
    stubFetch(() =>
      jsonResponse({
        elements: [
          { type: 'node', id: 1, lat: 'abc', lon: 6.64, tags: { name: 'bad' } },
          {
            type: 'node',
            id: 2,
            lat: 49.75,
            lon: 6.64,
            tags: { name: 'good' },
          },
          { type: 'node', id: 3, lat: 49.75, lon: 6.64, tags: { name: {} } },
          { type: 'thing', id: 4, lat: 49.75, lon: 6.64, tags: {} },
          { type: 'node', id: 'five', lat: 49.75, lon: 6.64, tags: {} },
        ],
      })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'find_nearby_pois',
      arguments: { near: '49.75,6.64', category: 'cafe' },
    });
    expect(result.isError).toBeFalsy();
    const data = parseJson<{ count: number; results: Array<{ name: string }> }>(
      result
    );
    expect(data.count).toBe(2);
    expect(data.results.map((r) => r.name)).toEqual(['good', '(unnamed)']);
  });

  it('spells or drops tag values that are not strings', async () => {
    stubFetch(() =>
      jsonResponse({
        elements: [
          {
            type: 'node',
            id: 1,
            lat: 49.75,
            lon: 6.64,
            tags: { name: 'a', ele: 137, foo: null, bar: { x: 1 } },
          },
        ],
      })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'poi_details',
      arguments: { osm_id: 'node/1' },
    });
    expect(result.isError).toBeFalsy();
    const data = parseJson<{ tags: Record<string, string> }>(result);
    expect(data.tags).toEqual({ name: 'a', ele: '137' });
  });

  it('drops a tag named __proto__ and answers the same in both channels', async () => {
    stubFetch(
      () =>
        new Response(
          '{"elements":[{"type":"node","id":1,"lat":49.75,"lon":6.64,"tags":{"__proto__":"x","__pro\\u0000to__":"y","name":"a"}}]}',
          { status: 200, headers: { 'content-type': 'application/json' } }
        )
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'poi_details',
      arguments: { osm_id: 'node/1' },
    });
    expect(result.isError).toBeFalsy();
    const tags = (result.structuredContent as { tags: Record<string, string> })
      .tags;
    expect(Object.hasOwn(tags, '__proto__')).toBe(false);
    expect(Object.getPrototypeOf(tags)).toBe(Object.prototype);
    expect(tags.name).toBe('a');
    const text = firstText(result);
    expect(text).not.toContain('__proto__');
    expect(parseJson(result)).toEqual(
      JSON.parse(JSON.stringify(result.structuredContent))
    );
  });

  it('caps a name the mirror made a megabyte long', async () => {
    stubFetch(() =>
      jsonResponse({
        elements: [
          {
            type: 'node',
            id: 1,
            lat: 49.75,
            lon: 6.64,
            tags: { name: 'n'.repeat(1_000_000) },
          },
        ],
      })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'poi_details',
      arguments: { osm_id: 'node/1' },
    });
    const data = parseJson<{ name: string }>(result);
    expect(data.name).toHaveLength(500 + '… (truncated)'.length);
    expect(firstText(result).length).toBeLessThan(2000);
  });

  it('drops a geocoding hit whose coordinate is not a number, keeps the rest', async () => {
    stubFetch(() =>
      jsonResponse([
        { lat: '49.7', lon: '6.6', display_name: 12345 },
        { lat: 'north', lon: '6.6', display_name: 'nowhere' },
        { lat: '49.7', lon: '6.6', display_name: 'Trier' },
      ])
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'geocode',
      arguments: { query: 'x' },
    });
    expect(result.isError).toBeFalsy();
    const data = parseJson<{ results: Array<{ label: string }> }>(result);
    expect(data.results.map((r) => r.label)).toEqual(['(unnamed)', 'Trier']);
  });

  it('leaves a contour point at 1e999 out of the bounding box', async () => {
    stubFetch(
      () =>
        new Response(
          '{"features":[{"properties":{"contour":15},"geometry":{"coordinates":[[6.62,49.74],[1e999,49.7],[6.66,49.76]]}}]}',
          { status: 200, headers: { 'content-type': 'application/json' } }
        )
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'isochrone',
      arguments: { center: '49.75,6.64', profile: 'foot', minutes: 15 },
    });
    expect(result.isError).toBeFalsy();
    const data = parseJson<{ bounding_box: { east: number } }>(result);
    expect(data.bounding_box.east).toBe(6.66);
  });

  it('reads a matrix cell that is not a number as "no route"', async () => {
    stubFetch(() =>
      jsonResponse({
        code: 'Ok',
        durations: [['abc', 600]],
        distances: [[5, null]],
      })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'route_matrix',
      arguments: {
        origins: ['49.75,6.64'],
        destinations: ['49.76,6.65', '49.77,6.66'],
        profile: 'car',
      },
    });
    expect(result.isError).toBeFalsy();
    const data = parseJson<{ durations_minutes: (number | null)[][] }>(result);
    expect(data.durations_minutes).toEqual([[null, 10]]);
  });

  it('omits a leg summary that is not text', async () => {
    stubFetch(() =>
      jsonResponse({
        code: 'Ok',
        routes: [
          {
            distance: 2,
            duration: 2,
            legs: [
              { distance: 1, duration: 1, summary: 7 },
              { distance: 1, duration: 1, summary: 'B51' },
            ],
          },
        ],
      })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'route',
      arguments: {
        waypoints: ['49.75,6.64', '49.76,6.65', '49.77,6.66'],
        profile: 'car',
      },
    });
    expect(result.isError).toBeFalsy();
    const data = parseJson<{ legs: Array<{ via?: string }> }>(result);
    expect(data.legs.map((l) => l.via)).toEqual([undefined, 'B51']);
  });

  it('refuses an optimized order that does not cover the stops', async () => {
    stubFetch(() =>
      jsonResponse({
        code: 'Ok',
        trips: [{ distance: 1, duration: 1, legs: [] }],
        waypoints: [{ waypoint_index: 0 }, { waypoint_index: 0 }, {}],
      })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'optimize_route',
      arguments: {
        stops: ['49.75,6.64', '49.76,6.65', '49.77,6.66'],
        profile: 'bike',
      },
    });
    expect(result.isError).toBe(true);
    expect(firstText(result)).toContain('does not cover the stops');
  });

  it('quotes an OSRM error as the service’s text, cut and labelled', async () => {
    stubFetch(() =>
      jsonResponse({
        code: 'NoRoute',
        message: `${ESC}[2J${'X'.repeat(100_000)}`,
      })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'route',
      arguments: { waypoints: ['49.75,6.64', '49.76,6.65'], profile: 'car' },
    });
    expect(result.isError).toBe(true);
    const text = firstText(result);
    expect(text).toContain('(untrusted text from the service) NoRoute');
    expect(text).toContain('… (truncated)');
    expect(text.length).toBeLessThan(500);
    expect(text).not.toContain(ESC);
  });

  it('fails over to the next Overpass mirror even when the error page is huge', async () => {
    // A 5xx whose body exceeds the data cap used to surface as a size error,
    // a plain Error with no status, and the failover keyed on the status never
    // saw it. Status first, then a bounded read of the error body.
    const mock = stubFetch(
      () => new Response('x'.repeat(9 * 1024 * 1024), { status: 502 })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'poi_details',
      arguments: { osm_id: 'node/1' },
    });
    expect(result.isError).toBe(true);
    expect(mock).toHaveBeenCalledTimes(2);
    expect(firstText(result)).toContain('all Overpass endpoints failed');
    expect(firstText(result)).toContain('HTTP 502');
  }, 30_000);
});

describe('a __proto__ key in a result', () => {
  it('is dropped at every depth and nothing else', () => {
    const parsed = JSON.parse(
      '{"__proto__": {"x": 1}, "__pro\\u0000to__": 2, "list": [{"__proto__": "x", "keep": 3}], "nest": {"__proto__": 4, "ok": 5}, "nil": {"__proto__": null}}'
    ) as Record<string, unknown>;
    for (const build of [jsonResult, untrustedResult]) {
      const out = build(parsed).structuredContent as Record<string, unknown>;
      expect(Object.hasOwn(out, '__proto__')).toBe(false);
      expect(Object.getPrototypeOf(out)).toBe(Object.prototype);
      expect(out).toMatchObject({
        list: [{ keep: 3 }],
        nest: { ok: 5 },
        nil: {},
      });
      expect(Object.getPrototypeOf(out.nil)).toBe(Object.prototype);
      expect(JSON.stringify(out)).not.toContain('__proto__');
    }
  });
});
