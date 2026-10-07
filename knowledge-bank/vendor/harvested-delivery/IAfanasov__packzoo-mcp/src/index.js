#!/usr/bin/env node
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { ListToolsRequestSchema, CallToolRequestSchema } from '@modelcontextprotocol/sdk/types.js';

const REMOTE_URL = process.env.PACKZOO_MCP_URL ?? 'https://packzoo.com/api/mcp';

async function main() {
  const client = new Client({ name: 'packzoo-mcp-proxy', version: '1.0.0' });
  await client.connect(new StreamableHTTPClientTransport(new URL(REMOTE_URL)));

  const server = new Server(
    { name: 'packzoo', version: '1.0.0' },
    { capabilities: { tools: {} } }
  );

  server.setRequestHandler(ListToolsRequestSchema, () => client.listTools());
  server.setRequestHandler(CallToolRequestSchema, (request) =>
    client.callTool(request.params)
  );

  await server.connect(new StdioServerTransport());
}

main().catch((err) => {
  console.error('packzoo-mcp failed to start:', err);
  process.exit(1);
});
