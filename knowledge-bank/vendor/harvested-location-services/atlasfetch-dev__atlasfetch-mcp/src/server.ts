import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js'
import { z } from 'zod'
import {
  ApiError, DEMO_KEY_NOTICE, request, usingDemoKey,
  type BoundarySet, type LookupResponse, type StreetAnswer,
} from './api.js'
import { VERSION } from './version.js'

/**
 * The AtlasFetch tools.
 *
 * Kept apart from any transport so the same definitions serve the stdio entry
 * point (`npx atlasfetch-mcp`, the published package) and, later, a hosted
 * Streamable HTTP endpoint. A transport decides who is connected; it does not
 * change what the tools do.
 *
 * Descriptions carry the caveats the API itself documents, because a model
 * choosing a tool reads only these. The two that cause real mistakes:
 * `municipal` is not always a city, and grid codes are output only.
 */

type ToolResult = {
  content: Array<{ type: 'text'; text: string }>
  isError?: boolean
  [key: string]: unknown
}

/** Every successful result carries the demo-key warning while one is in use. */
function ok(text: string): ToolResult {
  const body = usingDemoKey() ? `${text}\n\n${DEMO_KEY_NOTICE}` : text
  return { content: [{ type: 'text', text: body }] }
}

function fail(error: unknown): ToolResult {
  const message = error instanceof ApiError
    ? error.message
    : error instanceof Error
      ? `Could not reach AtlasFetch: ${error.message}`
      : 'Unknown error.'
  return { content: [{ type: 'text', text: message }], isError: true }
}

const json = (value: unknown) => JSON.stringify(value, null, 2)

/**
 * The widest street answer worth showing: the unlimited entry if it found
 * anything, else the first entry that did.
 */
function summariseStreet(answers: StreetAnswer[]): string {
  const best = [...answers].reverse().find(a => a.streetName) ?? answers.find(a => a.streetName)
  if (!best) return 'street: covered, but nothing nearby'
  const number = best.streetNumber ? `${best.streetNumber} ` : ''
  const distance = best.distanceMeters === null ? '' : ` (${best.distanceMeters} m)`
  return `street: ${number}${best.streetName}${distance}`
}

/** `{ country: {...}, region: null }` becomes "country: United Kingdom (GB) · region: no match". */
function summarise(result: LookupResponse): string {
  const parts = Object.entries(result.base).map(([layer, hit]) => {
    // street is three answers, not one hit, and its null means "no data for
    // this country" rather than "nothing matched here".
    if (Array.isArray(hit)) return summariseStreet(hit)
    if (layer === 'street') return 'street: no street data for this area'
    return hit ? `${layer}: ${hit.name}${hit.code ? ` (${hit.code})` : ''}` : `${layer}: no match`
  })
  const setNames = Object.entries(result.sets)
    .filter(([, matches]) => matches.length > 0)
    .map(([name, matches]) => `${name} -> ${matches.map(m => m.name).join(', ')}`)
  if (setNames.length > 0) parts.push(`sets: ${setNames.join('; ')}`)
  return parts.join(' · ')
}

export function createServer(): McpServer {
  const server = new McpServer(
    { name: 'atlasfetch', version: VERSION },
    {
      instructions:
        'AtlasFetch answers "which place is this coordinate in?" — the country, region and ' +
        'municipality containing a point, the nearest street and house number (opt-in), ' +
        'plus the boundaries the caller has uploaded themselves. It does not do forward ' +
        'geocoding or place search, routing or distances, and it does not return boundary geometry ' +
        'for the reference layers.',
    },
  )

  // ── The lookup ─────────────────────────────────────────────────────────────
  server.registerTool(
    'lookup_location',
    {
      title: 'Look up the boundaries containing a coordinate',
      description: [
        'Reverse geocode a coordinate to the administrative areas that contain it — country,',
        'region (state or province) and municipality — as names plus ISO 3166 codes, optionally the',
        'nearest street, and matches from boundary sets the account has uploaded: all in one call.',
        '',
        'Use for: which country, region or municipality a point is in; which street a point is on',
        '(add "street" to base); geofence checks against your own polygons; tagging data with region',
        'codes.',
        'Do NOT use for: forward geocoding or place search (an address to a coordinate), routing,',
        'distances, or fetching boundary geometry.',
        '',
        'Caveats worth repeating to the user: municipal is the finest unit AVAILABLE, not a',
        'consistent kind of thing — Los Angeles returns a city, rural Kansas returns a county, so',
        'do not assume it names a city. A layer that matched nothing comes back null. The errors',
        'array is always present: a boundary set that is unavailable or not granted to this key is',
        'skipped and reported there, while the call itself still succeeds.',
        '',
        'STREETS (opt-in via base, worldwide). base.street is ALWAYS three',
        'answers, for 5 m, 20 m and unlimited in that order,',
        'each with radiusMeters, streetNumber, streetName, postcode and distanceMeters. A numbered',
        'address within the radius wins over a nearer street (for the unlimited entry the address',
        'must still be within 20 m); otherwise the nearest named street; unnamed roads never answer.',
        'Two different nulls: base.street === null means there is no street data for the point’s',
        'country, while an entry whose fields are null means nothing was within that radius —',
        'never report them the same way. streetNumber and postcode are STRINGS (44A, 12-14, 0181),',
        'house numbers are rare outside well-mapped areas, and no street geometry is returned.',
        '',
        'One call is one billed lookup however many layers, sets or grid codes it touches, and a',
        'call that matches nothing still bills.',
      ].join('\n'),
      inputSchema: {
        lat: z.number().min(-90).max(90).describe('Latitude, -90 to 90.'),
        lng: z.number().min(-180).max(180).describe('Longitude, -180 to 180.'),
        base: z
          .array(z.enum(['country', 'region', 'municipal', 'street']))
          .optional()
          .describe(
            'Which reference layers to resolve. Defaults to country, region and municipal. ' +
              '"street" is opt-in: add it explicitly to get the nearest street.',
          ),
        sets: z
          .array(z.string().max(64))
          .optional()
          .describe('Names of the boundary sets on this account to match against. Defaults to none.'),
        encode: z
          .array(z.enum(['h3', 'pluscode']))
          .optional()
          .describe(
            'Also return the point as an H3 cell index and/or Google Plus Code. Output only — ' +
              'neither can be used AS a location, because both name areas rather than points.',
          ),
        h3res: z.number().int().min(0).max(15).optional().describe('H3 resolution 0-15. 9 is about 400 m across.'),
        pluslen: z
          .union([
            z.literal(2), z.literal(4), z.literal(6), z.literal(8), z.literal(10),
            z.literal(11), z.literal(12), z.literal(13), z.literal(14), z.literal(15),
          ])
          .optional()
          .describe('Plus Code length. 9 is not a valid length. 10 is about 14 m.'),
      },
      annotations: { readOnlyHint: true, openWorldHint: true },
    },
    async ({ lat, lng, base, sets, encode, h3res, pluslen }) => {
      try {
        const result = await request<LookupResponse>('/location/lookup', {
          query: {
            lat: String(lat),
            lng: String(lng),
            base: base?.join(','),
            set: sets?.join(','),
            encode: encode?.join(','),
            h3res: h3res === undefined ? undefined : String(h3res),
            pluslen: pluslen === undefined ? undefined : String(pluslen),
          },
        })

        const skipped = result.errors.length > 0
          ? `\n\nPartial problems (the lookup still succeeded):\n${
              result.errors.map(e => `- [${e.type}] ${e.message}`).join('\n')}`
          : ''

        return ok(`${summarise(result)}\n\n${json(result)}${skipped}`)
      } catch (error) {
        return fail(error)
      }
    },
  )

  // ── Boundary sets ──────────────────────────────────────────────────────────
  server.registerTool(
    'list_boundary_sets',
    {
      title: 'List the boundary sets on this account',
      description:
        'Lists the boundary sets on this account with their boundary counts and the API keys (id ' +
        'and label) each is granted to. A set only matches during a lookup when it is available AND ' +
        'granted to the key making the call.',
      inputSchema: {},
      annotations: { readOnlyHint: true, openWorldHint: true },
    },
    async () => {
      try {
        const result = await request<{ sets: BoundarySet[] }>('/boundaries/sets')
        if (result.sets.length === 0) {
          return ok('This account has no boundary sets yet. Create one with create_boundary_set.')
        }
        return ok(json(result.sets))
      } catch (error) {
        return fail(error)
      }
    },
  )

  server.registerTool(
    'create_boundary_set',
    {
      title: 'Create a boundary set',
      description: [
        'Creates an empty named set to hold your own polygons: delivery zones, service areas,',
        'sales territories.',
        '',
        'IMPORTANT, and not a bug: a new set is created unavailable and granted to no key, so it',
        'matches nothing until both are changed. Granting is addressed by API key id, and the only',
        'endpoint that lists key ids needs a browser session — which this server does not have. So',
        'this tool can create the set and add boundaries to it, but CANNOT make it queryable. Tell',
        'the user to finish that at https://atlasfetch.xyz/dashboard.',
      ].join('\n'),
      inputSchema: {
        name: z
          .string()
          .regex(/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,31}$/)
          .describe(
            'A short name, used to reference the set in lookups: 1-32 letters, digits, hyphens or ' +
              'underscores, starting with a letter or digit.',
          ),
      },
      annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    },
    async ({ name }) => {
      try {
        const set = await request<BoundarySet>('/boundaries/sets', { method: 'POST', body: { name } })
        return ok(
          `Created the set "${set.name}". It is not queryable yet: switch it on and grant it to an ` +
            'API key at https://atlasfetch.xyz/dashboard — that step needs a signed-in browser.' +
            `\n\n${json(set)}`,
        )
      } catch (error) {
        return fail(error)
      }
    },
  )

  // Rules transcribed from the API's boundaryService (validatePolygon,
  // validateProps, createBoundary) and plans.ts. The geometry schema is typed
  // rather than a free record, so a MultiPolygon or a whole Feature is refused
  // by the client before any request, and the schema itself tells the model
  // what shape to build.
  server.registerTool(
    'add_boundary',
    {
      title: 'Add a polygon to a boundary set',
      description: [
        'Adds ONE polygon to an existing boundary set on this account, so that lookup_location',
        'reports when a point falls inside it — delivery zones, service areas, sales territories.',
        'Each call creates a new boundary: calling twice with the same name stores two.',
        '',
        'Before calling: the set must already exist (create_boundary_set). A set matches nothing in',
        'lookups until it is switched on and granted to an API key in the dashboard at',
        'https://atlasfetch.xyz/dashboard, which this server cannot do.',
        '',
        'geometry must be a single GeoJSON Polygon — not a MultiPolygon, Feature or',
        'FeatureCollection. Positions are [longitude, latitude]. Each ring needs at least 4',
        'positions and must be closed (last position equals the first); extra rings are holes.',
        'Self-intersecting shapes are rejected. To store a MultiPolygon, add each part separately.',
        '',
        'Plan limits cap vertices per polygon (every position counts, including the closing one),',
        'properties per boundary and boundaries per set; a limit hit is refused with a message naming',
        'it. WITHOUT YOUR OWN KEY, the shared demo key is on the Public plan: at most 5 positions per',
        'polygon (a closed quadrilateral), properties only category (zone, area, route, place,',
        'other), color (green, blue, red, yellow, purple, orange) and priority (low, medium, high),',
        'and one set shared with every demo user, where adding to a full set silently deletes its',
        'oldest boundary. Never upload anything private with the demo key.',
        '',
        'Returns the stored boundary: id, set, name, properties, pointCount and createdAt.',
      ].join('\n'),
      inputSchema: {
        set: z
          .string()
          .regex(/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,31}$/)
          .describe('Name of an existing set on this account (see list_boundary_sets).'),
        name: z
          .string()
          .min(1)
          .max(100)
          .describe('Label returned when a looked-up point falls inside this polygon, e.g. "Zone A".'),
        geometry: z
          .object({
            type: z.literal('Polygon'),
            coordinates: z
              .array(z.array(z.array(z.number()).min(2).max(3)).min(4))
              .min(1)
              .describe(
                'Rings of [longitude, latitude] positions. The first ring is the outline; any further ' +
                  'rings are holes. Each ring is closed: its last position repeats its first.',
              ),
          })
          .describe(
            'A GeoJSON Polygon, e.g. {"type":"Polygon","coordinates":[[[18.40,-33.93],[18.40,-33.90],' +
              '[18.44,-33.90],[18.44,-33.93],[18.40,-33.93]]]}.',
          ),
        properties: z
          .record(z.string().max(32), z.union([z.string().max(256), z.number(), z.boolean()]))
          .optional()
          .describe(
            'Optional flat key/value pairs returned with every match: keys up to 32 characters, values ' +
              'a string (up to 256 characters), number or boolean. The demo key accepts only category, ' +
              'color and priority, from fixed lists.',
          ),
      },
      // destructiveHint is true because of the Public plan: adding to its full,
      // shared set deletes the oldest boundary, which may be someone else's.
      annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: true },
    },
    async ({ set, name, geometry, properties }) => {
      try {
        const created = await request<unknown>('/boundaries', {
          method: 'POST',
          body: { set, name, geometry, properties },
        })
        return ok(`Added "${name}" to set "${set}".\n\n${json(created)}`)
      } catch (error) {
        return fail(error)
      }
    },
  )

  return server
}
