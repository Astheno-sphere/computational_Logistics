import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { apiGet, asText, READ_ONLY, seg } from '../lib/api-client.js';

export function registerIpTools(server: McpServer) {
  server.registerTool(
    'geolocate_ip',
    {
      title: 'Geolocate IP',
      description: 'Geolocate an IPv4 or IPv6 address: country, region, city, coordinates, timezone and EU membership. Requires the Basic plan or above; new accounts get it free for 14 days.',
      inputSchema: {
        address: z.string().min(2).max(45).describe('IPv4 or IPv6 address to geolocate (e.g. 8.8.8.8 or 2001:4860:4860::8888)'),
      },
      annotations: READ_ONLY,
    },
    async ({ address }) => asText(await apiGet(`/v1/api/geo/ip/${seg(address)}`))
  );
}
