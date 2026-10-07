#!/usr/bin/env node

/**
 * Bamwor MCP Server — World Geographic Data for AI Agents
 *
 * Provides structured access to 261 countries and 13.4M cities
 * through the Model Context Protocol (MCP).
 *
 * Transport: stdio (standard for Claude Desktop, Cursor, etc.)
 * Data source: Bamwor REST API (https://bamwor.com/api/v1)
 *
 * Environment variables:
 *   BAMWOR_API_KEY  — Your Bamwor API key (register free at bamwor.com)
 *   BAMWOR_API_URL  — Override API base URL (optional)
 */

import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { createServer } from './server.js';

async function main(): Promise<void> {
  const server = createServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);

  // Log to stderr (stdout is reserved for MCP protocol messages)
  process.stderr.write('Bamwor MCP Server started (stdio transport)\n');
}

main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  const stack = error instanceof Error ? error.stack : '';
  process.stderr.write(`Fatal error: ${message}\n`);
  if (stack) process.stderr.write(`${stack}\n`);
  process.exit(1);
});

/**
 * Smithery sandbox entry point — allows Smithery to scan
 * server capabilities without real credentials.
 */
export function createSandboxServer() {
  return createServer();
}
