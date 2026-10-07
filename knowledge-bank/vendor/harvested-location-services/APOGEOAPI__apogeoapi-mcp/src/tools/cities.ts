import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { apiGet, asText, READ_ONLY } from '../lib/api-client.js';

export function registerCityTools(server: McpServer) {
  server.registerTool(
    'get_cities',
    {
      title: 'Get cities',
      description: 'Get all cities for a state/province by state ID (from get_states). Requires the Basic plan or above; new accounts get it free for 14 days.',
      inputSchema: {
        state_id: z.number().int().positive().describe('Numeric state ID (from get_states response)'),
        page: z.number().int().positive().optional(),
        limit: z.number().int().min(1).max(100).optional(),
        fields: z.enum(['basic', 'standard', 'full']).optional(),
      },
      annotations: READ_ONLY,
    },
    async ({ state_id, page, limit, fields }) => {
      const params = new URLSearchParams();
      if (page) params.set('page', String(page));
      if (limit) params.set('limit', String(limit));
      if (fields) params.set('fields', fields);
      const qs = params.toString() ? `?${params}` : '';
      return asText(await apiGet(`/v1/api/geo/states/${state_id}/cities${qs}`));
    }
  );
}
