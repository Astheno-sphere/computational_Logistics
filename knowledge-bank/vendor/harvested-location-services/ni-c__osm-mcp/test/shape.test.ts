import fc from 'fast-check';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Client, InMemoryTransport } from '@modelcontextprotocol/client';

import { loadConfig } from '../src/config.js';
import { createServer } from '../src/server.js';
import {
  arrayOf,
  finiteNumber,
  finiteNumberFromText,
  measure,
  nonNegativeInteger,
  numberMatrix,
  objectOf,
  stringTags,
  text as shapeText,
  textOrPrimitive,
  MAX_TAG_KEY_LENGTH,
  MAX_TAG_VALUE_LENGTH,
} from '../src/shape.js';

/*
 * The shaping helpers, and the property they exist for: whatever a backend
 * answers, a tool never fails its own output schema. The SDK turns a schema
 * violation into an error result for the whole call — "Output validation
 * error: …" — which tells the model nothing and, for a listing, throws away
 * every good element because of one bad one. Before these helpers, nine
 * fields across six tools could be reached that way from any of the public
 * services this server talks to.
 */

describe('finiteNumber', () => {
  it('accepts only finite numbers and folds -0', () => {
    expect(finiteNumber(1.5)).toBe(1.5);
    expect(Object.is(finiteNumber(-0), 0)).toBe(true);
    for (const bad of [Infinity, -Infinity, NaN, '1', null, undefined, {}]) {
      expect(finiteNumber(bad)).toBeUndefined();
    }
  });

  it('parses a number a backend wrote as text, within a length bound', () => {
    expect(finiteNumberFromText('49.7596')).toBe(49.7596);
    expect(finiteNumberFromText(6.6)).toBe(6.6);
    expect(finiteNumberFromText('')).toBeUndefined();
    expect(finiteNumberFromText('abc')).toBeUndefined();
    expect(finiteNumberFromText('1e999')).toBeUndefined();
    expect(finiteNumberFromText('1'.repeat(41))).toBeUndefined();
    expect(finiteNumberFromText(null)).toBeUndefined();
  });

  it('takes an id only as a safe non-negative integer', () => {
    expect(nonNegativeInteger(42)).toBe(42);
    expect(nonNegativeInteger(0)).toBe(0);
    for (const bad of [-1, 1.5, 2 ** 53, '42', Infinity]) {
      expect(nonNegativeInteger(bad)).toBeUndefined();
    }
  });
});

describe('text', () => {
  it('takes strings only, cut with a visible mark', () => {
    expect(shapeText('Trier', 10)).toBe('Trier');
    expect(shapeText('x'.repeat(20), 10)).toBe(
      `${'x'.repeat(10)}… (truncated)`
    );
    for (const bad of [5, true, null, undefined, {}, []]) {
      expect(shapeText(bad, 10)).toBeUndefined();
    }
  });

  it('spells a number or boolean as a tag value would be', () => {
    expect(textOrPrimitive(250, 10)).toBe('250');
    expect(textOrPrimitive(true, 10)).toBe('true');
    expect(textOrPrimitive({ a: 1 }, 10)).toBeUndefined();
    expect(textOrPrimitive(null, 10)).toBeUndefined();
  });
});

describe('containers', () => {
  it('answers an empty array or nothing for the wrong kind', () => {
    expect(arrayOf([1])).toEqual([1]);
    expect(arrayOf({ length: 1 })).toEqual([]);
    expect(arrayOf('abc')).toEqual([]);
    expect(objectOf({ a: 1 })).toEqual({ a: 1 });
    expect(objectOf([1])).toBeUndefined();
    expect(objectOf(null)).toBeUndefined();
    expect(objectOf('x')).toBeUndefined();
  });

  it('makes a matrix of finite numbers or nulls out of anything', () => {
    expect(numberMatrix([[600, null, 'abc', Infinity], 'row'])).toEqual([
      [600, null, null, null],
      [],
    ]);
    expect(numberMatrix('nothing')).toEqual([]);
  });
});

describe('stringTags', () => {
  it('keeps string values, spells primitives and drops the rest', () => {
    expect(
      stringTags({
        name: 'Porta Nigra',
        ele: 137,
        wheelchair: true,
        broken: null,
        nested: { a: 1 },
        list: [1],
        '': 'empty key',
      })
    ).toEqual({ name: 'Porta Nigra', ele: '137', wheelchair: 'true' });
  });

  it('bounds keys and values', () => {
    const tags = stringTags({
      ['k'.repeat(300)]: 'v'.repeat(600),
    });
    const [key, value] = Object.entries(tags)[0]!;
    expect(key).toBe(`${'k'.repeat(MAX_TAG_KEY_LENGTH)}… (truncated)`);
    expect(value).toBe(`${'v'.repeat(MAX_TAG_VALUE_LENGTH)}… (truncated)`);
  });

  it('keeps a tag named __proto__ as an own property', () => {
    // Legal JSON, and a tag name any mapper can type. `tags[key] = value`
    // would set the prototype instead and lose the tag in silence. This is an
    // internal shaper; `clean()` in result.ts drops the key from every answer.
    const tags = stringTags(JSON.parse('{"__proto__": "x", "name": "a"}'));
    expect(Object.hasOwn(tags, '__proto__')).toBe(true);
    expect(Object.getPrototypeOf(tags)).toBe(Object.prototype);
    expect(tags.name).toBe('a');
  });

  it('answers an empty map for anything that is not an object', () => {
    for (const bad of [null, 'tags', [1], 5]) {
      expect(stringTags(bad)).toEqual({});
    }
  });
});

/*
 * The end-to-end property. Every tool is called through the SDK with a valid
 * argument set, against a fetch that answers arbitrary JSON — both random
 * documents and documents with the *right envelope* and random leaves, which
 * is how a real service misbehaves. Coordinates are given as "lat,lon" so no
 * geocoding stands between the tool and the answer under test.
 */

async function connect(env: Record<string, string> = {}): Promise<Client> {
  const server = createServer(loadConfig(env as NodeJS.ProcessEnv));
  const [clientTransport, serverTransport] =
    InMemoryTransport.createLinkedPair();
  const client = new Client({ name: 'test', version: '0.0.0' });
  await Promise.all([
    client.connect(clientTransport),
    server.connect(serverTransport),
  ]);
  // Listing loads the output schemas into the client, so the success path is
  // checked on the client side as well as the server's.
  await client.listTools();
  return client;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Serialises a value; the sentinel becomes the literal `1e999`, which JSON.parse reads as Infinity. */
function serialise(value: unknown): string {
  return JSON.stringify(value).replaceAll('"__INF__"', '1e999');
}

const leaf = fc.oneof(
  fc.jsonValue({ maxDepth: 2 }),
  fc.double({ noNaN: true }),
  fc.constant('__INF__'),
  fc.constant(1e300),
  fc.string({ maxLength: 700 }),
  fc.constant(null)
);

const overpassLike = fc.record({
  elements: fc.array(
    fc.record({
      type: fc.oneof(fc.constantFrom('node', 'way', 'relation'), leaf),
      id: leaf,
      lat: leaf,
      lon: leaf,
      center: fc.oneof(fc.record({ lat: leaf, lon: leaf }), leaf),
      tags: fc.oneof(
        fc.dictionary(fc.string({ maxLength: 40 }), leaf, { maxKeys: 8 }),
        leaf
      ),
    }),
    { maxLength: 6 }
  ),
});

const osrmLike = fc.record({
  code: fc.oneof(fc.constant('Ok'), leaf),
  message: leaf,
  routes: fc.array(
    fc.record({
      distance: leaf,
      duration: leaf,
      legs: fc.array(
        fc.record({
          distance: leaf,
          duration: leaf,
          summary: leaf,
          steps: fc.array(
            fc.record({
              distance: leaf,
              name: leaf,
              maneuver: fc.record({ type: leaf, modifier: leaf }),
            }),
            { maxLength: 4 }
          ),
        }),
        { maxLength: 4 }
      ),
    }),
    { maxLength: 2 }
  ),
  trips: fc.array(fc.record({ distance: leaf, duration: leaf, legs: leaf }), {
    maxLength: 2,
  }),
  waypoints: fc.array(fc.record({ waypoint_index: leaf }), { maxLength: 5 }),
  durations: fc.array(fc.array(leaf, { maxLength: 3 }), { maxLength: 3 }),
  distances: fc.array(fc.array(leaf, { maxLength: 3 }), { maxLength: 3 }),
});

const nominatimLike = fc.array(
  fc.record({
    lat: leaf,
    lon: leaf,
    display_name: leaf,
    osm_type: leaf,
    osm_id: leaf,
    category: leaf,
    type: leaf,
  }),
  { maxLength: 4 }
);

const geoJsonLike = fc.record({
  features: fc.array(
    fc.record({
      properties: fc.record({ contour: leaf, value: leaf }),
      geometry: fc.record({
        coordinates: fc.oneof(
          fc.array(fc.array(leaf, { maxLength: 3 }), { maxLength: 5 }),
          leaf
        ),
      }),
    }),
    { maxLength: 3 }
  ),
});

const anyAnswer = fc.oneof(
  fc.jsonValue({ maxDepth: 4 }),
  overpassLike,
  osrmLike,
  nominatimLike,
  geoJsonLike
);

const CALLS: Array<{ name: string; arguments: Record<string, unknown> }> = [
  { name: 'geocode', arguments: { query: 'Trier' } },
  { name: 'geocode', arguments: { query: 'Trier', provider: 'photon' } },
  { name: 'reverse_geocode', arguments: { latitude: 49.75, longitude: 6.64 } },
  {
    name: 'route',
    arguments: {
      waypoints: ['49.75,6.64', '49.76,6.65', '49.77,6.66'],
      profile: 'foot',
      include_steps: true,
    },
  },
  {
    name: 'route_matrix',
    arguments: {
      origins: ['49.75,6.64'],
      destinations: ['49.76,6.65', '49.77,6.66'],
      profile: 'car',
    },
  },
  {
    name: 'optimize_route',
    arguments: {
      stops: ['49.75,6.64', '49.76,6.65', '49.77,6.66'],
      profile: 'bike',
    },
  },
  {
    name: 'isochrone',
    arguments: { center: '49.75,6.64', profile: 'foot', minutes: 15 },
  },
  {
    name: 'find_nearby_pois',
    arguments: { near: '49.75,6.64', category: 'cafe' },
  },
  { name: 'poi_details', arguments: { osm_id: 'node/1' } },
  {
    name: 'suggest_meeting_point',
    arguments: { locations: ['49.74,6.63', '49.76,6.65'] },
  },
];

/** The largest honest answer: 25 POIs with ten bounded tags each, with room. */
const MAX_TEXT_LENGTH = 300_000;

describe('no backend answer fails a tool its own output schema', () => {
  for (const call of CALLS) {
    it(`${call.name}${'provider' in call.arguments ? ' (photon)' : ''}`, async () => {
      await fc.assert(
        fc.asyncProperty(anyAnswer, async (answer) => {
          const body = serialise(answer);
          vi.stubGlobal(
            'fetch',
            vi.fn(
              async () =>
                new Response(body, {
                  status: 200,
                  headers: { 'content-type': 'application/json' },
                })
            )
          );
          const client = await connect();
          const result = await client.callTool(call);
          const content = result.content as Array<{ text?: string }>;
          const text = content[0]?.text ?? '';
          expect(text).not.toContain('Output validation error');
          expect(text).not.toMatch(/Cannot read properties|is not a function/);
          expect(text.length).toBeLessThanOrEqual(MAX_TEXT_LENGTH);
        }),
        { numRuns: Number(process.env.SHAPE_RUNS ?? 60) }
      );
    }, 60_000);
  }

  it('also holds with an OpenRouteService key', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.oneof(fc.jsonValue({ maxDepth: 4 }), osrmLike, geoJsonLike),
        fc.constantFrom(...CALLS.filter((c) => /route|isochrone/.test(c.name))),
        async (answer, call) => {
          const body = serialise(answer);
          vi.stubGlobal(
            'fetch',
            vi.fn(
              async () =>
                new Response(body, {
                  status: 200,
                  headers: { 'content-type': 'application/json' },
                })
            )
          );
          const client = await connect({ ORS_API_KEY: 'test-key-0123456789' });
          const result = await client.callTool(call);
          const content = result.content as Array<{ text?: string }>;
          const text = content[0]?.text ?? '';
          expect(text).not.toContain('Output validation error');
          expect(text).not.toMatch(/Cannot read properties|is not a function/);
        }
      ),
      { numRuns: Number(process.env.SHAPE_RUNS ?? 60) }
    );
  }, 60_000);
});

describe('measure', () => {
  it('is a finite, non-negative number under the ceiling', () => {
    expect(measure(44_000)).toBe(44_000);
    expect(measure(0)).toBe(0);
    for (const bad of [-1, -9007199254740992, 1e300, Infinity, NaN, '5']) {
      expect(measure(bad)).toBeUndefined();
    }
  });
});
