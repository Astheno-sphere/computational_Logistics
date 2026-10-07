import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { apiGet, asText, READ_ONLY } from '../lib/api-client.js';

export function registerSearchTools(server: McpServer) {
  server.registerTool(
    'global_search',
    {
      title: 'Global search',
      description: 'Search across countries, states and cities in a single query and return the best matches of every type. Matching is accent-sensitive, so use the local spelling with its accents (e.g. "Córdoba", not "Cordoba"). Requires the Basic plan or above; new accounts get it free for 14 days. On the Free plan, use search_countries.',
      inputSchema: {
        q: z.string().min(1).describe('Search term in its local spelling (e.g. "Buenos Aires", "La Pampa", "Córdoba", "São Paulo")'),
        limit: z.number().int().min(1).max(20).optional().describe('Max results (default: 10)'),
      },
      annotations: READ_ONLY,
    },
    async ({ q, limit }) => {
      const params = new URLSearchParams({ q });
      if (limit) params.set('limit', String(limit));
      return asText(await apiGet(`/v1/api/geo/search?${params}`));
    }
  );
}
