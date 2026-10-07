import { z } from 'zod';
import { poi, untrustedFields } from '../output-schema.js';
import type { McpServer } from '@modelcontextprotocol/server';
import {
  formatDistance,
  formatDuration,
  haversineMeters,
  roundCoord,
} from '../geo.js';

import { categoryList, resolveCategory } from '../categories.js';
import { READ_ONLY } from './annotations.js';
import type { Deps } from '../deps.js';
import type { Poi } from '../backends/overpass.js';
import { run, untrustedResult } from '../result.js';

const waypoint = z
  .string()
  .min(1)
  .max(300)
  .describe('Place name, address, or coordinates as "lat,lon"');

const language = z
  .string()
  .regex(/^[a-zA-Z-]{2,10}$/)
  .optional()
  .describe('Language used when geocoding place names, default "en"');

/** Tags worth showing in a list result; poi_details returns everything. */
const CORE_TAGS = [
  'amenity',
  'tourism',
  'shop',
  'leisure',
  'historic',
  'cuisine',
  'opening_hours',
  'website',
  'phone',
  'wheelchair',
] as const;

/**
 * The handful of tags a list entry shows. Values are already strings bounded
 * to `MAX_TAG_VALUE_LENGTH` — the Overpass backend shapes every tag set on
 * the way in, so this is a selection, not a second sanitiser.
 */
function coreTags(item: Poi): Record<string, string> {
  const entries: Array<[string, string]> = [];
  for (const key of CORE_TAGS) {
    const value = item.tags[key];
    if (value) entries.push([key, value]);
  }
  return Object.fromEntries(entries);
}

const OSM_ID = /^(node|way|relation)\/(\d{1,12})$/;

/** Response budget for poi_details: mega-relations carry hundreds of tags. */
const MAX_DETAIL_TAGS = 60;

function capTags(tags: Record<string, string>): {
  tags: Record<string, string>;
  tags_truncated?: string;
} {
  const entries = Object.entries(tags);
  const capped = Object.fromEntries(entries.slice(0, MAX_DETAIL_TAGS));
  return {
    tags: capped,
    ...(entries.length > MAX_DETAIL_TAGS
      ? {
          tags_truncated: `showing ${MAX_DETAIL_TAGS} of ${entries.length} tags`,
        }
      : {}),
  };
}

export function registerPoiTools(server: McpServer, deps: Deps): void {
  server.registerTool(
    'find_nearby_pois',
    {
      title: 'Find nearby places (POIs)',
      description:
        'Finds points of interest near a location, sorted by distance. ' +
        `Category shortcuts: ${categoryList()}. ` +
        'Any other OSM tag works as "key" or "key=value" (e.g. "diet:vegan=yes"). ' +
        'Use poi_details for the full record of one result.',
      inputSchema: z.object({
        near: waypoint,
        category: z
          .string()
          .min(1)
          .max(100)
          .describe('Category shortcut or OSM tag filter'),
        radius_m: z
          .number()
          .int()
          .min(50)
          .max(10_000)
          .optional()
          .describe('Search radius in meters, default 1000'),
        limit: z
          .number()
          .int()
          .min(1)
          .max(25)
          .optional()
          .describe('Maximum number of results, default 10'),
        language,
      }),
      annotations: READ_ONLY,
      outputSchema: z.object({
        ...untrustedFields,
        near: z.string().describe('The resolved centre, as OSM labels it.'),
        category: z.string(),
        count: z.number().int(),
        note: z.string().optional().describe('Present when nothing was found.'),
        results: z.array(poi),
      }),
    },
    async ({ near, category, radius_m, limit, language: lang }) =>
      run(async () => {
        const selector = resolveCategory(category);
        const center = await deps.resolver.resolve(near, lang);
        const max = limit ?? 10;
        // Overpass's own limit is applied before sorting, so fetch a few more
        // and cut after sorting by distance.
        const pois = await deps.overpass.findNearby(
          center,
          selector,
          radius_m ?? 1000,
          Math.min(100, max * 4)
        );
        const sorted = pois
          .map((found) => ({
            poi: found,
            meters: haversineMeters(center, found),
          }))
          .toSorted((a, b) => a.meters - b.meters)
          .slice(0, max);
        return untrustedResult({
          near: center.label,
          category,
          count: sorted.length,
          ...(sorted.length === 0
            ? {
                note: 'Nothing found — try a larger radius_m or another category.',
              }
            : {}),
          results: sorted.map(({ poi: found, meters }) => ({
            name: found.name,
            distance: formatDistance(meters),
            lat: found.lat,
            lon: found.lon,
            osm: found.osm,
            ...coreTags(found),
          })),
        });
      })
  );

  server.registerTool(
    'poi_details',
    {
      title: 'Get POI details',
      description:
        'Fetches the full OpenStreetMap record of one element — all tags ' +
        '(opening hours, website, phone, …), coordinates and a map link. ' +
        'Takes an OSM id as returned by find_nearby_pois or geocode, ' +
        'e.g. "node/240109189".',
      inputSchema: z.object({
        osm_id: z
          .string()
          .regex(OSM_ID, 'expected "node/<id>", "way/<id>" or "relation/<id>"'),
      }),
      annotations: READ_ONLY,
      // Loose, and deliberately: the body of this answer is the element's OSM
      // tags, and the tag namespace is open — anyone can invent a key. A strict
      // shape would turn a mapper adding `payment:bitcoin` into a tool that
      // fails outright, since the SDK validates a result against the schema
      // before it goes out.
      // The `meta` again: `extend` builds a new schema and does not carry the
      // parent's metadata over, so without it this one goes back to spelling
      // `additionalProperties` as `{}`.
      outputSchema: poi
        .extend({
          ...untrustedFields,
          map: z.string().optional(),
        })
        .meta({ additionalProperties: true }),
    },
    async ({ osm_id }) =>
      run(async () => {
        const [, type, id] = OSM_ID.exec(osm_id)!;
        const element = await deps.overpass.byId(
          type as 'node' | 'way' | 'relation',
          Number(id)
        );
        if (!element) {
          throw new Error(`no OSM element found for ${osm_id}`);
        }
        return untrustedResult({
          osm: osm_id,
          name: element.tags.name ?? '(unnamed)',
          ...(element.lat !== undefined && element.lon !== undefined
            ? {
                lat: element.lat,
                lon: element.lon,
                map: `https://www.openstreetmap.org/${osm_id}`,
              }
            : {}),
          ...capTags(element.tags),
        });
      })
  );

  server.registerTool(
    'suggest_meeting_point',
    {
      title: 'Suggest a meeting point',
      description:
        'Suggests a fair place to meet for people starting from different ' +
        'locations: finds venues around the geographic midpoint and picks the ' +
        'one with the most balanced travel times for everyone.',
      inputSchema: z.object({
        locations: z
          .array(waypoint)
          .min(2)
          .max(8)
          .describe('Starting points of all participants'),
        profile: z
          .enum(['foot', 'car', 'bike'])
          .optional()
          .describe('How everyone travels, default foot'),
        venue_category: z
          .string()
          .min(1)
          .max(100)
          .optional()
          .describe('What kind of venue to meet at, default "cafe"'),
        search_radius_m: z
          .number()
          .int()
          .min(100)
          .max(10_000)
          .optional()
          .describe('Venue search radius around the midpoint, default 1500'),
        language,
      }),
      annotations: READ_ONLY,
      outputSchema: z.object({
        ...untrustedFields,
        profile: z.enum(['foot', 'car', 'bike']).optional(),
        note: z
          .string()
          .optional()
          .describe('Present when no venue was found near the midpoint.'),
        midpoint: z
          .object({ lat: z.number(), lon: z.number() })
          .optional()
          .describe('Only reported when nothing was found near it.'),
        suggestion: poi.optional(),
        travel_times: z
          .array(z.object({ from: z.string(), duration: z.string() }))
          .optional(),
        alternatives: z
          .array(z.object({ name: z.string(), osm: z.string() }))
          .optional(),
      }),
    },
    async ({
      locations,
      profile,
      venue_category,
      search_radius_m,
      language: lang,
    }) =>
      run(async () => {
        const mode = profile ?? 'foot';
        const selector = resolveCategory(venue_category ?? 'cafe');
        const origins = await deps.resolver.resolveAll(locations, lang);
        const midpoint = {
          lat: origins.reduce((sum, p) => sum + p.lat, 0) / origins.length,
          lon: origins.reduce((sum, p) => sum + p.lon, 0) / origins.length,
        };
        const venues = (
          await deps.overpass.findNearby(
            midpoint,
            selector,
            search_radius_m ?? 1500,
            30
          )
        )
          .map((found) => ({
            poi: found,
            meters: haversineMeters(midpoint, found),
          }))
          .toSorted((a, b) => a.meters - b.meters)
          .slice(0, 8)
          .map((entry) => entry.poi);
        if (venues.length === 0) {
          return untrustedResult({
            note:
              'No matching venue near the midpoint — try a larger ' +
              'search_radius_m or another venue_category.',
            midpoint: {
              lat: roundCoord(midpoint.lat),
              lon: roundCoord(midpoint.lon),
            },
          });
        }
        const engine = deps.ors.enabled ? deps.ors : deps.osrm;
        const matrix = await engine.table(mode, origins, venues);
        // Fairness first (smallest worst-case travel time), then total time.
        let best = 0;
        let bestScore = [Infinity, Infinity];
        for (let v = 0; v < venues.length; v++) {
          const times = origins.map((_, o) => matrix.durations[o]?.[v] ?? null);
          if (times.some((t) => t === null)) continue;
          const score = [
            Math.max(...(times as number[])),
            (times as number[]).reduce((a, b) => a + b, 0),
          ];
          if (
            score[0]! < bestScore[0]! ||
            (score[0] === bestScore[0] && score[1]! < bestScore[1]!)
          ) {
            best = v;
            bestScore = score;
          }
        }
        const venue = venues[best]!;
        return untrustedResult({
          profile: mode,
          suggestion: {
            name: venue.name,
            lat: venue.lat,
            lon: venue.lon,
            osm: venue.osm,
            ...coreTags(venue),
          },
          travel_times: origins.map((origin, o) => {
            const seconds = matrix.durations[o]?.[best];
            return {
              from: origin.label,
              duration: seconds != null ? formatDuration(seconds) : 'unknown',
            };
          }),
          alternatives: venues
            .filter((_, v) => v !== best)
            .slice(0, 3)
            .map((alt) => ({ name: alt.name, osm: alt.osm })),
        });
      })
  );
}
