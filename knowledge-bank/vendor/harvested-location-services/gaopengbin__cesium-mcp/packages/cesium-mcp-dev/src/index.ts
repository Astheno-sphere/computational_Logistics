#!/usr/bin/env node

import { serveStdio } from '@modelcontextprotocol/server/stdio'
import { buildDevMcpServer } from './server.js'

serveStdio(() => buildDevMcpServer())
console.error('[cesium-mcp-dev] MCP Server running (stdio), 3 tools registered')
