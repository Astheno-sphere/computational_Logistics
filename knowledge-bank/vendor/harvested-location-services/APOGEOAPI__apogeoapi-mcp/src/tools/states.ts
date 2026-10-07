import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { apiGet, asText, READ_ONLY, seg } from '../lib/api-client.js';

export function registerStateTools(server: McpServer) {
  server.registerTool(
    'get_states',
    {
      title: 'Get states',
      description: 'Get all states/provinces for a country, with the numeric IDs that get_cities needs. Available on every plan, including Free.',
      inputSchema: {
        country_code: z.string().min(2).max(3).describe('ISO2 or ISO3 country code'),
        page: z.number().int().positive().optional(),
        limit: z.number().int().min(1).max(100).optional(),
        fields: z.enum(['basic', 'standard', 'full']).optional(),
      },
      annotations: READ_ONLY,
    },
    async ({ country_code, page, limit, fields }) => {
      const params = new URLSearchParams();
      if (page) params.set('page', String(page));
      if (limit) params.set('limit', String(limit));
      if (fields) params.set('fields', fields);
      const qs = params.toString() ? `?${params}` : '';
      return asText(await apiGet(`/v1/api/geo/countries/${seg(country_code.toUpperCase())}/states${qs}`));
    }
  );
}
