import { afterEach, describe, expect, it, vi } from 'vitest';

import { NominatimBackend } from '../src/backends/nominatim.js';
import { OrsBackend } from '../src/backends/ors.js';
import { OsrmBackend } from '../src/backends/osrm.js';
import { OverpassBackend, parseTagSelector } from '../src/backends/overpass.js';
import { PhotonBackend } from '../src/backends/photon.js';
import { ValhallaBackend } from '../src/backends/valhalla.js';
import { loadConfig } from '../src/config.js';
import { HttpClient, RateLimiter } from '../src/http.js';

const config = loadConfig({} as NodeJS.ProcessEnv);
const noWait = () => new RateLimiter(0);

function http(): HttpClient {
  return new HttpClient('test/1.0', 0);
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

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('NominatimBackend', () => {
  it('builds a policy-compliant search request and maps results', async () => {
    const mock = stubFetch(() =>
      jsonResponse([
        {
          lat: '49.7596208',
          lon: '6.6439115',
          display_name: 'Trier, Rheinland-Pfalz, Germany',
          osm_type: 'relation',
          osm_id: 172679,
          category: 'boundary',
          type: 'administrative',
        },
      ])
    );
    const backend = new NominatimBackend(http(), config, noWait());
    const results = await backend.search('Trier', {
      language: 'de',
      countrycodes: 'DE',
    });
    const url = new URL(String(mock.mock.calls[0]![0]));
    expect(url.origin + url.pathname).toBe(
      'https://nominatim.openstreetmap.org/search'
    );
    expect(url.searchParams.get('format')).toBe('jsonv2');
    expect(url.searchParams.get('accept-language')).toBe('de');
    expect(url.searchParams.get('countrycodes')).toBe('de');
    expect(results).toEqual([
      {
        lat: 49.75962,
        lon: 6.64391,
        label: 'Trier, Rheinland-Pfalz, Germany',
        osm: 'relation/172679',
        kind: 'boundary/administrative',
      },
    ]);
  });

  it('returns null when reverse finds nothing', async () => {
    stubFetch(() => jsonResponse({ error: 'Unable to geocode' }));
    const backend = new NominatimBackend(http(), config, noWait());
    expect(await backend.reverse(0, 0)).toBeNull();
  });
});

describe('PhotonBackend', () => {
  it('maps GeoJSON features and falls back to the default language', async () => {
    const mock = stubFetch(() =>
      jsonResponse({
        features: [
          {
            geometry: { coordinates: [6.6439, 49.7596] },
            properties: {
              name: 'Porta Nigra',
              city: 'Trier',
              country: 'Germany',
              osm_type: 'W',
              osm_id: 24526783,
              osm_key: 'historic',
              osm_value: 'city_gate',
            },
          },
        ],
      })
    );
    const backend = new PhotonBackend(http(), config, noWait());
    const results = await backend.search('porta nigra', { language: 'es' });
    const url = new URL(String(mock.mock.calls[0]![0]));
    expect(url.searchParams.get('lang')).toBe('default');
    expect(results[0]).toMatchObject({
      lat: 49.7596,
      lon: 6.6439,
      label: 'Porta Nigra, Trier, Germany',
      osm: 'way/24526783',
      kind: 'historic/city_gate',
    });
  });
});

describe('OsrmBackend', () => {
  const trier = { lat: 49.7596, lon: 6.6439 };
  const lux = { lat: 49.6116, lon: 6.1319 };

  it('selects the profile via the routed-* path prefix, not the inner segment', async () => {
    const mock = stubFetch(() =>
      jsonResponse({
        code: 'Ok',
        routes: [{ distance: 44000, duration: 31000, legs: [] }],
      })
    );
    const backend = new OsrmBackend(http(), config, noWait());
    await backend.route('foot', [trier, lux]);
    const url = String(mock.mock.calls[0]![0]);
    // The FOSSGIS demo servers ignore the profile inside the OSRM path — the
    // routed-foot prefix is the only thing that actually selects walking.
    expect(url).toContain(
      'routing.openstreetmap.de/routed-foot/route/v1/driving/'
    );
    expect(url).toContain('6.6439,49.7596;6.1319,49.6116');
  });

  it('throws on a non-Ok response code', async () => {
    stubFetch(() => jsonResponse({ code: 'NoRoute', message: 'nope' }));
    const backend = new OsrmBackend(http(), config, noWait());
    await expect(backend.route('car', [trier, lux])).rejects.toThrow(
      /code: .*NoRoute.*message: .*nope/
    );
  });

  it('requests a table with sources/destinations split', async () => {
    const mock = stubFetch(() =>
      jsonResponse({
        code: 'Ok',
        durations: [[100, 200]],
        distances: [[1000, 2000]],
      })
    );
    const backend = new OsrmBackend(http(), config, noWait());
    const matrix = await backend.table('car', [trier], [lux, trier]);
    const url = new URL(String(mock.mock.calls[0]![0]));
    expect(url.pathname).toContain('/routed-car/table/v1/driving/');
    expect(url.searchParams.get('sources')).toBe('0');
    expect(url.searchParams.get('destinations')).toBe('1;2');
    expect(url.searchParams.get('annotations')).toBe('duration,distance');
    expect(matrix.durations).toEqual([[100, 200]]);
  });

  it('inverts the trip waypoint order correctly', async () => {
    stubFetch(() =>
      jsonResponse({
        code: 'Ok',
        trips: [{ distance: 5000, duration: 3600, legs: [] }],
        // input 0 is visited 2nd, input 1 first, input 2 third
        waypoints: [
          { waypoint_index: 1 },
          { waypoint_index: 0 },
          { waypoint_index: 2 },
        ],
      })
    );
    const backend = new OsrmBackend(http(), config, noWait());
    const trip = await backend.trip('bike', [trier, lux, trier], true);
    expect(trip.order).toEqual([1, 0, 2]);
  });
});

describe('OverpassBackend', () => {
  it('fails over to the mirror on 429', async () => {
    const urls: string[] = [];
    stubFetch((url) => {
      urls.push(url);
      if (new URL(url).hostname === 'overpass-api.de') {
        return new Response('too many', { status: 429 });
      }
      return jsonResponse({
        elements: [
          { type: 'node', id: 1, lat: 49.75, lon: 6.64, tags: { name: 'X' } },
        ],
      });
    });
    const backend = new OverpassBackend(http(), config, noWait(), () =>
      Promise.resolve()
    );
    const pois = await backend.findNearby(
      { lat: 49.75, lon: 6.64 },
      { key: 'amenity', value: 'cafe' },
      500,
      10
    );
    expect(urls).toEqual([
      'https://overpass-api.de/api/interpreter',
      'https://lz4.overpass-api.de/api/interpreter',
    ]);
    expect(pois[0]).toMatchObject({ name: 'X', osm: 'node/1' });
  });

  it('fails over to the mirror when an endpoint times out', async () => {
    const urls: string[] = [];
    stubFetch((url) => {
      urls.push(url);
      if (new URL(url).hostname === 'overpass-api.de') {
        throw new DOMException(
          'The operation was aborted due to timeout',
          'TimeoutError'
        );
      }
      return jsonResponse({
        elements: [
          { type: 'node', id: 1, lat: 49.75, lon: 6.64, tags: { name: 'X' } },
        ],
      });
    });
    const backend = new OverpassBackend(http(), config, noWait(), () =>
      Promise.resolve()
    );
    const elements = await backend.query('[out:json];node(1);out;');
    expect(urls).toEqual([
      'https://overpass-api.de/api/interpreter',
      'https://lz4.overpass-api.de/api/interpreter',
    ]);
    expect(elements).toHaveLength(1);
  });

  it('names the timeout when every endpoint times out', async () => {
    const urls: string[] = [];
    stubFetch((url) => {
      urls.push(url);
      throw new DOMException(
        'The operation was aborted due to timeout',
        'TimeoutError'
      );
    });
    const backend = new OverpassBackend(http(), config, noWait(), () =>
      Promise.resolve()
    );
    await expect(backend.query('[out:json];node(1);out;')).rejects.toThrow(
      /all Overpass endpoints failed \(last: The operation was aborted due to timeout\)/
    );
    expect(urls).toHaveLength(2);
  });

  it('does not fail over on a network refusal', async () => {
    const urls: string[] = [];
    stubFetch((url) => {
      urls.push(url);
      throw new TypeError('fetch failed');
    });
    const backend = new OverpassBackend(http(), config, noWait(), () =>
      Promise.resolve()
    );
    await expect(backend.query('[out:json];node(1);out;')).rejects.toThrow(
      'fetch failed'
    );
    expect(urls).toHaveLength(1);
  });

  it('does not fail over on a client error', async () => {
    const urls: string[] = [];
    stubFetch((url) => {
      urls.push(url);
      return new Response('bad query', { status: 400 });
    });
    const backend = new OverpassBackend(http(), config, noWait(), () =>
      Promise.resolve()
    );
    await expect(backend.query('malformed')).rejects.toMatchObject({
      status: 400,
    });
    expect(urls).toHaveLength(1);
  });

  it('uses way/relation centers as coordinates', async () => {
    stubFetch(() =>
      jsonResponse({
        elements: [
          {
            type: 'way',
            id: 2,
            center: { lat: 49.7, lon: 6.6 },
            tags: { name: 'Museum' },
          },
        ],
      })
    );
    const backend = new OverpassBackend(http(), config, noWait(), () =>
      Promise.resolve()
    );
    const pois = await backend.findNearby(
      { lat: 49.7, lon: 6.6 },
      { key: 'tourism' },
      500,
      10
    );
    expect(pois[0]).toMatchObject({ lat: 49.7, lon: 6.6, osm: 'way/2' });
  });
});

describe('parseTagSelector', () => {
  it('accepts key and key=value', () => {
    expect(parseTagSelector('tourism')).toEqual({ key: 'tourism' });
    expect(parseTagSelector('diet:vegan=yes')).toEqual({
      key: 'diet:vegan',
      value: 'yes',
    });
  });

  it('rejects anything that could escape the Overpass QL string', () => {
    expect(() => parseTagSelector('amenity="]')).toThrow(/invalid tag filter/);
    expect(() => parseTagSelector('a=b=c')).toThrow(/invalid tag filter/);
    expect(() => parseTagSelector('name~"x"')).toThrow(/invalid tag filter/);
  });
});

describe('ValhallaBackend', () => {
  it('maps profiles to Valhalla costings and flattens contours', async () => {
    const mock = stubFetch(() =>
      jsonResponse({
        features: [
          {
            properties: { contour: 15 },
            geometry: {
              type: 'LineString',
              coordinates: [
                [6.6, 49.7],
                [6.7, 49.8],
              ],
            },
          },
        ],
      })
    );
    const backend = new ValhallaBackend(http(), config, noWait());
    const contours = await backend.isochrone(
      { lat: 49.75, lon: 6.65 },
      'foot',
      { minutes: 15 }
    );
    const url = new URL(String(mock.mock.calls[0]![0]));
    const request = JSON.parse(url.searchParams.get('json')!) as {
      costing: string;
      contours: unknown[];
    };
    expect(url.pathname).toBe('/isochrone');
    expect(request.costing).toBe('pedestrian');
    expect(request.contours).toEqual([{ time: 15 }]);
    expect(contours[0]).toEqual({
      value: 15,
      coordinates: [
        { lon: 6.6, lat: 49.7 },
        { lon: 6.7, lat: 49.8 },
      ],
    });
  });
});

describe('OrsBackend', () => {
  const withKey = loadConfig({
    ORS_API_KEY: 'test-key-0123456789',
  } as NodeJS.ProcessEnv);

  it('is disabled without a key', () => {
    expect(new OrsBackend(http(), config).enabled).toBe(false);
    expect(new OrsBackend(http(), withKey).enabled).toBe(true);
  });

  it('routes via the mapped profile with the key in the header', async () => {
    const mock = stubFetch(() =>
      jsonResponse({
        routes: [
          {
            summary: { distance: 44000, duration: 31000 },
            segments: [{ distance: 44000, duration: 31000 }],
          },
        ],
      })
    );
    const backend = new OrsBackend(http(), withKey, noWait());
    const route = await backend.route('foot', [
      { lat: 49.7596, lon: 6.6439 },
      { lat: 49.6116, lon: 6.1319 },
    ]);
    const url = String(mock.mock.calls[0]![0]);
    const init = mock.mock.calls[0]![1]!;
    expect(url).toBe(
      'https://api.openrouteservice.org/v2/directions/foot-walking'
    );
    expect((init.headers as Record<string, string>).Authorization).toBe(
      'test-key-0123456789'
    );
    expect(JSON.parse(String(init.body))).toEqual({
      coordinates: [
        [6.6439, 49.7596],
        [6.1319, 49.6116],
      ],
      instructions: false,
    });
    expect(route.distanceMeters).toBe(44000);
  });

  it('normalizes isochrone values back to minutes', async () => {
    stubFetch(() =>
      jsonResponse({
        features: [
          {
            properties: { value: 900 },
            geometry: { coordinates: [[[6.6, 49.7]]] },
          },
        ],
      })
    );
    const backend = new OrsBackend(http(), withKey, noWait());
    const contours = await backend.isochrone({ lat: 49.75, lon: 6.65 }, 'car', {
      minutes: 15,
    });
    expect(contours[0]!.value).toBe(15);
    expect(contours[0]!.coordinates).toEqual([{ lon: 6.6, lat: 49.7 }]);
  });
});

describe('audit regressions', () => {
  it('resolveCategory does not resolve prototype keys to functions', async () => {
    const { resolveCategory } = await import('../src/categories.js');
    for (const key of ['constructor', '__proto__', 'toString', 'valueOf']) {
      const selector = resolveCategory(key);
      expect(typeof selector.key).toBe('string');
    }
    expect(() => resolveCategory('hasOwnProperty()')).toThrow(
      /invalid tag filter/
    );
  });

  it('photon ignores prototype-key osm_type values from upstream', async () => {
    stubFetch(() =>
      jsonResponse({
        features: [
          {
            geometry: { coordinates: [6.64, 49.75] },
            properties: { name: 'X', osm_type: 'constructor', osm_id: 5 },
          },
        ],
      })
    );
    const backend = new PhotonBackend(http(), config, noWait());
    const results = await backend.search('x');
    expect(results[0]!.osm).toBeUndefined();
  });

  it('drops geocode results with non-finite coordinates', async () => {
    stubFetch(() =>
      jsonResponse([
        { lat: 'not-a-number', lon: '6.64', display_name: 'Broken' },
        { lat: '49.75', lon: '6.64', display_name: 'Fine' },
      ])
    );
    const backend = new NominatimBackend(http(), config, noWait());
    const results = await backend.search('x');
    expect(results).toHaveLength(1);
    expect(results[0]!.label).toBe('Fine');
  });
});
