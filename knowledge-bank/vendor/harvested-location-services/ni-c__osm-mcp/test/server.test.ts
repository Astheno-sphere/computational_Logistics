import { readFileSync } from 'node:fs';

import { afterEach, describe, expect, it, vi } from 'vitest';
import { Client, InMemoryTransport } from '@modelcontextprotocol/client';

import { loadConfig } from '../src/config.js';
import { run } from '../src/result.js';
import { createServer } from '../src/server.js';

const TOOLS = [
  'geocode',
  'reverse_geocode',
  'route',
  'route_matrix',
  'optimize_route',
  'isochrone',
  'find_nearby_pois',
  'poi_details',
  'suggest_meeting_point',
  'straight_line_distance',
  'map_link',
];

async function connect(env: Record<string, string> = {}): Promise<Client> {
  const server = createServer(loadConfig(env as NodeJS.ProcessEnv));
  const [clientTransport, serverTransport] =
    InMemoryTransport.createLinkedPair();
  const client = new Client({ name: 'test', version: '0.0.0' });
  await Promise.all([
    client.connect(clientTransport),
    server.connect(serverTransport),
  ]);
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

describe('server', () => {
  it('introduces itself in full, and the profile matches server.json', async () => {
    // What a client puts in front of a person comes from the handshake, not from
    // server.json — that file is not in the npm tarball. Both carry the same
    // profile, and this is what keeps the two from drifting apart.
    const registry = JSON.parse(
      readFileSync(new URL('../server.json', import.meta.url), 'utf8')
    ) as { title: string; description: string; websiteUrl: string };

    const info = (await connect()).getServerVersion();

    expect(info?.title).toBe(registry.title);
    expect(info?.description).toBe(registry.description);
    expect(info?.websiteUrl).toBe(registry.websiteUrl);
    // The registry enforces this limit; failing here beats failing on publish.
    expect(registry.description.length).toBeLessThanOrEqual(100);

    // Icons are URLs on the documentation site. A data: URI would be legal and
    // would ride along on every single handshake.
    expect(info?.icons?.length ?? 0).toBeGreaterThan(0);
    for (const icon of info?.icons ?? []) {
      expect(icon.src, 'icon src').toMatch(/^https:\/\//);
    }
  });

  it('warns about untrusted content where a model reads it first', async () => {
    // The untrusted marker on a result is read after the fact. This is the only
    // channel that arrives before the first tool call.
    const instructions = (await connect()).getInstructions();
    expect(instructions).toBeTruthy();
    expect(instructions).toMatch(/never\s+(?:follow|as)\s+instructions/i);
  });

  it('registers all eleven tools with an empty environment', async () => {
    const client = await connect();
    const names = (await client.listTools()).tools
      .map((t) => t.name)
      .toSorted();
    expect(names).toEqual([...TOOLS].toSorted());
  });

  it('declares an output schema on every tool', async () => {
    // The same argument as the annotations below, one field along. A tool that
    // says nothing about its result forces a client to parse prose to find out
    // what it got, and the SDK sends no `structuredContent` at all for a tool
    // that declared no schema.
    const client = await connect();
    const { tools } = await client.listTools();
    expect(tools.length).toBeGreaterThan(0);
    for (const tool of tools) {
      expect(tool.outputSchema, tool.name).toBeDefined();
      // An object root, not merely a schema. SEP-2106 allows an array or a
      // scalar, but a 2025-era client is served that same tool with the schema
      // rewritten to `{result: …}` — so it would answer in two shapes
      // depending on who asked.
      expect(tool.outputSchema?.type, tool.name).toBe('object');
    }
  });

  it('marks every result as untrusted, because all of it is', async () => {
    // OpenStreetMap is editable by anyone on earth. There is no tool here that
    // answers with anything else, so the list of exceptions is empty — and
    // saying so is what keeps the next tool from being the first one to forget.
    const client = await connect();
    const { tools } = await client.listTools();
    const plain = tools
      .filter((tool) => {
        const properties = tool.outputSchema?.properties as
          Record<string, unknown> | undefined;
        return properties?.untrusted === undefined;
      })
      .map((tool) => tool.name);
    expect(plain).toEqual([]);
  });

  it('declares all four annotation hints on every tool', async () => {
    // Not a style rule. Two of the four default to a *stronger* claim than
    // silence suggests: the specification gives destructiveHint and
    // openWorldHint a default of true, so a tool that omits them announces
    // itself as destructive and open-world. Leaving them out is a statement,
    // not an abstention — so every tool states all four.
    const client = await connect();
    const { tools } = await client.listTools();
    const hints = [
      'readOnlyHint',
      'destructiveHint',
      'idempotentHint',
      'openWorldHint',
    ] as const;
    for (const tool of tools) {
      for (const hint of hints) {
        expect(typeof tool.annotations?.[hint], `${tool.name}.${hint}`).toBe(
          'boolean'
        );
      }
    }
  });

  it('is the one server that really is open-world, and says so', async () => {
    // Everywhere else in this family openWorldHint is false, because those
    // servers talk to one configured instance. Here it is true and true is
    // correct — public geocoders and routers over the whole planet. Stated
    // rather than inherited from the default, so that it reads as a decision.
    const client = await connect();
    const { tools } = await client.listTools();
    for (const tool of tools) {
      expect(tool.annotations?.openWorldHint, tool.name).toBe(true);
      expect(tool.annotations?.readOnlyHint, tool.name).toBe(true);
    }
  });

  it('routes on foot via the routed-foot prefix and formats compactly', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse({
        code: 'Ok',
        routes: [
          {
            distance: 44_000,
            duration: 31_680,
            legs: [{ distance: 44_000, duration: 31_680, summary: 'B49' }],
          },
        ],
      })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'route',
      arguments: {
        waypoints: ['49.7596,6.6439', '49.6116,6.1319'],
        profile: 'foot',
      },
    });
    expect(result.isError).toBeFalsy();
    expect(String(fetchMock.mock.calls[0]![0])).toContain('/routed-foot/');
    const data = parseJson<Record<string, unknown>>(result);
    expect(data.distance).toBe('44 km');
    expect(data.duration).toBe('8 h 48 min');
    expect(data.engine).toBe('osrm');
  });

  it('uses ORS for routing when a key is configured', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse({
        routes: [{ summary: { distance: 44_000, duration: 31_680 } }],
      })
    );
    const client = await connect({ ORS_API_KEY: 'test-key-0123456789' });
    const result = await client.callTool({
      name: 'route',
      arguments: {
        waypoints: ['49.7596,6.6439', '49.6116,6.1319'],
        profile: 'car',
      },
    });
    expect(result.isError).toBeFalsy();
    expect(String(fetchMock.mock.calls[0]![0])).toContain(
      '/v2/directions/driving-car'
    );
    const data = parseJson<Record<string, unknown>>(result);
    expect(data.engine).toBe('openrouteservice');
  });

  it('rejects an oversized matrix without calling any API', async () => {
    const fetchMock = stubFetch(() => jsonResponse({}));
    const client = await connect();
    const many = Array.from({ length: 13 }, (_, i) => `49.${i},6.0`);
    const result = await client.callTool({
      name: 'route_matrix',
      arguments: { origins: many, destinations: many, profile: 'car' },
    });
    expect(result.isError).toBe(true);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('requires exactly one isochrone budget', async () => {
    const fetchMock = stubFetch(() => jsonResponse({}));
    const client = await connect();
    const result = await client.callTool({
      name: 'isochrone',
      arguments: {
        center: '49.75,6.64',
        profile: 'foot',
        minutes: 15,
        kilometers: 2,
      },
    });
    expect(result.isError).toBe(true);
    expect(firstText(result)).toContain('exactly one');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('marks OSM-sourced content as untrusted data', async () => {
    stubFetch(() =>
      jsonResponse([
        {
          lat: '49.75',
          lon: '6.64',
          display_name: 'Trier',
          osm_type: 'relation',
          osm_id: 1,
        },
      ])
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'geocode',
      arguments: { query: 'Trier' },
    });
    expect(firstText(result)).toMatch(/^The following is user-contributed/);
  });

  it('rejects malformed OSM ids before any request', async () => {
    const fetchMock = stubFetch(() => jsonResponse({}));
    const client = await connect();
    const result = await client.callTool({
      name: 'poi_details',
      arguments: { osm_id: 'node/../secrets' },
    });
    expect(result.isError).toBe(true);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('computes straight-line distances fully offline for coordinates', async () => {
    const fetchMock = stubFetch(() => jsonResponse({}));
    const client = await connect();
    const result = await client.callTool({
      name: 'straight_line_distance',
      arguments: { from: '49.7596,6.6439', to: '49.6116,6.1319' },
    });
    expect(result.isError).toBeFalsy();
    const data = parseJson<{ distance_m: number }>(result);
    expect(data.distance_m).toBeGreaterThan(38_000);
    expect(data.distance_m).toBeLessThan(43_000);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('builds marker and directions links offline for coordinates', async () => {
    const fetchMock = stubFetch(() => jsonResponse({}));
    const client = await connect();
    const marker = await client.callTool({
      name: 'map_link',
      arguments: { place: '49.75,6.64' },
    });
    expect(firstText(marker)).toContain(
      'https://www.openstreetmap.org/?mlat=49.75&mlon=6.64'
    );
    const directions = await client.callTool({
      name: 'map_link',
      arguments: { from: '49.75,6.64', to: '49.61,6.13', profile: 'car' },
    });
    expect(firstText(directions)).toContain('engine=fossgis_osrm_car');
    expect(fetchMock).not.toHaveBeenCalled();

    const invalid = await client.callTool({
      name: 'map_link',
      arguments: { place: '49.75,6.64', from: '49.75,6.64', to: '49.61,6.13' },
    });
    expect(invalid.isError).toBe(true);
  });

  it('finds nearby POIs, sorts by distance and keeps core tags only', async () => {
    stubFetch(() =>
      jsonResponse({
        elements: [
          {
            type: 'node',
            id: 2,
            lat: 49.76,
            lon: 6.65,
            tags: { name: 'Far Cafe', amenity: 'cafe', internal_junk: 'x' },
          },
          {
            type: 'node',
            id: 1,
            lat: 49.7501,
            lon: 6.6401,
            tags: {
              name: 'Near Cafe',
              amenity: 'cafe',
              opening_hours: 'Mo-Su 08:00-18:00',
            },
          },
        ],
      })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'find_nearby_pois',
      arguments: { near: '49.75,6.64', category: 'cafe' },
    });
    const text = firstText(result);
    const data = JSON.parse(text.slice(text.indexOf('{'))) as {
      results: Array<Record<string, unknown>>;
    };
    expect(data.results[0]!.name).toBe('Near Cafe');
    expect(data.results[0]!.opening_hours).toBe('Mo-Su 08:00-18:00');
    expect(data.results[1]!.name).toBe('Far Cafe');
    expect(data.results[1]!.internal_junk).toBeUndefined();
  });

  it('suggests the fairest meeting venue from the matrix', async () => {
    stubFetch((url) => {
      if (url.includes('interpreter') || url.includes('overpass')) {
        return jsonResponse({
          elements: [
            {
              type: 'node',
              id: 10,
              lat: 49.75,
              lon: 6.64,
              tags: { name: 'Cafe Mitte', amenity: 'cafe' },
            },
            {
              type: 'node',
              id: 11,
              lat: 49.751,
              lon: 6.641,
              tags: { name: 'Cafe Schief', amenity: 'cafe' },
            },
          ],
        });
      }
      // durations: venue 0 balanced (10/12 min), venue 1 lopsided (2/40 min)
      return jsonResponse({
        code: 'Ok',
        durations: [
          [600, 120],
          [720, 2400],
        ],
        distances: [
          [800, 200],
          [900, 3000],
        ],
      });
    });
    const client = await connect();
    const result = await client.callTool({
      name: 'suggest_meeting_point',
      arguments: { locations: ['49.74,6.63', '49.76,6.65'] },
    });
    const text = firstText(result);
    const data = JSON.parse(text.slice(text.indexOf('{'))) as {
      suggestion: { name: string };
      travel_times: Array<{ duration: string }>;
    };
    expect(data.suggestion.name).toBe('Cafe Mitte');
    expect(data.travel_times).toHaveLength(2);
  });
});

describe('secret redaction', () => {
  it('never echoes the ORS key, even when an upstream error body contains it', async () => {
    const KEY = 'sekret-ors-key-12345678';
    stubFetch(
      () =>
        new Response(`upstream echo: Authorization: Bearer ${KEY}`, {
          status: 500,
        })
    );
    const client = await connect({ ORS_API_KEY: KEY });
    const result = await client.callTool({
      name: 'route',
      arguments: {
        waypoints: ['49.7596,6.6439', '49.6116,6.1319'],
        profile: 'car',
      },
    });
    expect(result.isError).toBe(true);
    const text = firstText(result);
    expect(text).not.toContain(KEY);
    expect(text).toContain('[redacted]');
  });
});

describe('control characters and BiDi overrides', () => {
  // Written as escapes because they are invisible in a source file.
  const RLO = '\u202e';
  const CSI = '\u009b';
  const DEL = '\u007f';
  const RLM = '\u200f';

  it('strips them from OpenStreetMap data without touching RTL marks', async () => {
    /*
     * OSM is editable by anyone: a mapper can set `name=Caf\u00e9<RLO>...` on a
     * venue and `find_nearby_pois` hands the tag to the model verbatim.
     * `JSON.stringify` escapes everything below U+0020 and nothing above it, so
     * U+007F, the C1 block and U+202A-U+202E travelled straight through.
     *
     * U+200F is the domain exception and the reason there are two classes here:
     * a right-to-left mark is *legitimate* in an OSM name — an Arabic name with
     * a Latin fragment needs it to render in the intended order — and it cannot
     * reorder the text around it the way an override can. Stripping it would
     * corrupt the name of a real place.
     */
    stubFetch(() =>
      jsonResponse({
        elements: [
          {
            type: 'node',
            id: 1,
            lat: 49.75,
            lon: 6.64,
            tags: {
              name: `Caf\u00e9${RLO}evil${CSI}[31m${DEL}${RLM} \u0645\u0642\u0647\u0649`,
              amenity: 'cafe',
            },
          },
        ],
      })
    );
    const client = await connect();
    const text = firstText(
      await client.callTool({
        name: 'find_nearby_pois',
        arguments: { near: '49.75,6.64', category: 'cafe' },
      })
    );
    for (const unsafe of [RLO, CSI, DEL]) {
      expect(text).not.toContain(unsafe);
    }
    expect(text).toContain('Caf\u00e9');
    expect(text).toContain(RLM);
  });

  it('strips them from an upstream error body', async () => {
    /*
     * The sharper of the two paths: an error body is concatenated into the text
     * block with no JSON encoding anywhere, so an ANSI escape here is an ANSI
     * escape in whatever renders the result. None of these endpoints is run by
     * this project — the default OVERPASS_BASE_URL is a community mirror — and
     * the body is entirely theirs to choose.
     */
    stubFetch(
      () =>
        new Response(`routing engine says: ${CSI}[2J${RLO}denied${DEL}`, {
          status: 500,
        })
    );
    const client = await connect();
    const result = await client.callTool({
      name: 'route',
      arguments: {
        waypoints: ['49.7596,6.6439', '49.6116,6.1319'],
        profile: 'car',
      },
    });
    expect(result.isError).toBe(true);
    const text = firstText(result);
    for (const unsafe of [RLO, CSI, DEL]) {
      expect(text).not.toContain(unsafe);
    }
    expect(text).toContain('routing engine says:');
  });
});

describe('schema strip invariant', () => {
  it('drops unknown caller-supplied fields before anything reaches upstream', async () => {
    const fetchMock = stubFetch(() => jsonResponse({ elements: [] }));
    const client = await connect();
    await client.callTool({
      name: 'find_nearby_pois',
      arguments: {
        near: '49.75,6.64',
        category: 'cafe',
        format: 'evil-format',
        out: 'evil-out',
        data: 'evil-data',
      },
    });
    expect(fetchMock).toHaveBeenCalled();
    for (const call of fetchMock.mock.calls) {
      const url = String(call[0]);
      const body = String((call[1] as RequestInit | undefined)?.body ?? '');
      expect(url + body).not.toContain('evil-');
    }
  });
});

describe('tool call deadline', () => {
  it('aborts a stuck call at the deadline with an actionable error', async () => {
    const result = await run(() => new Promise(() => {}), 20);
    expect(result.isError).toBe(true);
    const content = result.content as Array<{ text?: string }>;
    expect(content[0]?.text).toContain('deadline');
  });
});
