import { z } from 'zod';
import { place, untrustedFields } from '../output-schema.js';
import type { McpServer } from '@modelcontextprotocol/server';

import type { Deps } from '../deps.js';
import { READ_ONLY } from './annotations.js';
import { run, untrustedResult } from '../result.js';

const language = z
  .string()
  .regex(/^[a-zA-Z-]{2,10}$/)
  .optional()
  .describe(
    'Language for place names (IETF code like "en" or "de"), default "en"'
  );

export function registerGeocodingTools(server: McpServer, deps: Deps): void {
  server.registerTool(
    'geocode',
    {
      title: 'Geocode a place or address',
      description:
        'Converts a place name or address into coordinates using OpenStreetMap. ' +
        'Returns matching places with lat/lon, a display label and the OSM id. ' +
        'Provider "nominatim" (default) is best for addresses; "photon" is ' +
        'typo-tolerant and better for fuzzy place names.',
      inputSchema: z.object({
        query: z.string().min(1).max(300).describe('Place name or address'),
        provider: z
          .enum(['nominatim', 'photon'])
          .optional()
          .describe('Geocoder to use, default nominatim'),
        limit: z
          .number()
          .int()
          .min(1)
          .max(10)
          .optional()
          .describe('Maximum number of results, default 3'),
        language,
        countrycodes: z
          .string()
          .max(200)
          .regex(/^[a-zA-Z]{2}(,[a-zA-Z]{2})*$/)
          .optional()
          .describe(
            'Restrict to countries: comma-separated ISO 3166-1 alpha-2 codes, e.g. "de,lu" (Nominatim only)'
          ),
      }),
      annotations: READ_ONLY,
      outputSchema: z.object({
        ...untrustedFields,
        provider: z.enum(['nominatim', 'photon']).optional(),
        note: z.string().optional().describe('Present when nothing matched.'),
        results: z.array(place),
      }),
    },
    async ({ query, provider, limit, language: lang, countrycodes }) =>
      run(async () => {
        const results = await deps.resolver.search(query, {
          ...(provider ? { provider } : {}),
          ...(limit !== undefined ? { limit } : {}),
          ...(lang ? { language: lang } : {}),
          ...(countrycodes ? { countrycodes } : {}),
        });
        if (results.length === 0) {
          return untrustedResult({
            results: [],
            note: `No match for "${query}". Try the other provider or a broader query.`,
          });
        }
        return untrustedResult({ provider: provider ?? 'nominatim', results });
      })
  );

  server.registerTool(
    'reverse_geocode',
    {
      title: 'Reverse geocode coordinates',
      description:
        'Converts coordinates into the nearest address or place name (Nominatim).',
      inputSchema: z.object({
        latitude: z.number().min(-90).max(90),
        longitude: z.number().min(-180).max(180),
        language,
      }),
      annotations: READ_ONLY,
      outputSchema: z.object({
        ...untrustedFields,
        result: place.nullable(),
        note: z.string().optional().describe('Present when nothing was found.'),
      }),
    },
    async ({ latitude, longitude, language: lang }) =>
      run(async () => {
        const result = await deps.nominatim.reverse(
          latitude,
          longitude,
          lang ?? 'en'
        );
        if (!result) {
          return untrustedResult({
            result: null,
            note: 'No address found near these coordinates.',
          });
        }
        return untrustedResult({ result });
      })
  );
}
