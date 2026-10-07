import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { apiGet, asText, READ_ONLY, seg } from '../lib/api-client.js';

export function registerCountryTools(server: McpServer) {
  server.registerTool(
    'get_country',
    {
      title: 'Get country',
      description:
        'Get data for a country by ISO2 or ISO3 code: name, capital, region, population, currency, timezones and phone code. Available on every plan, including Free. On the Basic plan and above (and during the 14-day trial) the response also includes the live USD exchange rate of its currency.',
      inputSchema: {
        code: z.string().min(2).max(3).describe('ISO2 (e.g. AR) or ISO3 (e.g. ARG) country code'),
        fields: z.enum(['basic', 'standard', 'full']).optional().describe('Detail level: basic (fast), standard (default), full (all fields)'),
      },
      annotations: READ_ONLY,
    },
    async ({ code, fields }) => {
      const qs = fields ? `?fields=${fields}` : '';
      return asText(await apiGet(`/v1/api/geo/countries/${seg(code.toUpperCase())}${qs}`));
    }
  );

  server.registerTool(
    'list_countries',
    {
      title: 'List countries',
      description: 'List all countries with pagination. Returns basic info by default; add fields=full for all data. Available on every plan, including Free.',
      inputSchema: {
        page: z.number().int().positive().optional().describe('Page number (default: 1)'),
        limit: z.number().int().min(1).max(100).optional().describe('Results per page (default: 50, max: 100)'),
        fields: z.enum(['basic', 'standard', 'full']).optional().describe('Detail level'),
      },
      annotations: READ_ONLY,
    },
    async ({ page, limit, fields }) => {
      const params = new URLSearchParams();
      if (page) params.set('page', String(page));
      if (limit) params.set('limit', String(limit));
      if (fields) params.set('fields', fields);
      const qs = params.toString() ? `?${params}` : '';
      return asText(await apiGet(`/v1/api/geo/countries${qs}`));
    }
  );

  server.registerTool(
    'search_countries',
    {
      title: 'Search countries',
      description: 'Search countries by name (e.g. "arg" finds Argentina). Returns paginated matches. Available on every plan, including Free.',
      inputSchema: {
        q: z.string().min(1).describe('Search query (partial name match)'),
        page: z.number().int().positive().optional(),
        limit: z.number().int().min(1).max(100).optional(),
      },
      annotations: READ_ONLY,
    },
    async ({ q, page, limit }) => {
      const params = new URLSearchParams({ q });
      if (page) params.set('page', String(page));
      if (limit) params.set('limit', String(limit));
      return asText(await apiGet(`/v1/api/geo/countries/search?${params}`));
    }
  );
}
