#!/usr/bin/env node
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { createServer } from './server.js'

/**
 * The published entry point: `npx atlasfetch-mcp`, launched by the MCP client
 * as a child process and spoken to over stdin/stdout.
 *
 * NOTHING may be written to stdout except protocol messages — a stray
 * console.log corrupts the stream and the client drops the connection. Logging
 * goes to stderr, which clients surface as server logs.
 */
async function main(): Promise<void> {
  const server = createServer()
  await server.connect(new StdioServerTransport())
  console.error('atlasfetch-mcp ready on stdio')
}

main().catch(error => {
  console.error('atlasfetch-mcp failed to start:', error)
  process.exit(1)
})
