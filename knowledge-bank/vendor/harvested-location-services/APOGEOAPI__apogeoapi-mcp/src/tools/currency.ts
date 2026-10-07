import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { apiGet, asText, READ_ONLY, seg } from '../lib/api-client.js';

export function registerCurrencyTools(server: McpServer) {
  server.registerTool(
    'get_currency_rate',
    {
      title: 'Get currency rate',
      description: "Get the live USD exchange rate for a country's currency, refreshed every 4 hours. Requires the Basic plan or above; new accounts get it free for 14 days.",
      inputSchema: {
        country_code: z.string().min(2).max(3).describe('ISO2 or ISO3 country code (e.g. AR, BR, JP)'),
      },
      annotations: READ_ONLY,
    },
    async ({ country_code }) => asText(await apiGet(`/v1/api/geo/countries/${seg(country_code.toUpperCase())}/currency-rate`))
  );
}
