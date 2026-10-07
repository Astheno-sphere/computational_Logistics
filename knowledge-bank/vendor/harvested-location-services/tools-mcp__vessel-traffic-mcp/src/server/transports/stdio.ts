import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';

import { createVesselMcpServer } from '../create-server.js';

export async function startStdioServer(): Promise<void> {
  const server = createVesselMcpServer();
  await server.connect(new StdioServerTransport());
}
