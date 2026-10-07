#!/usr/bin/env node
/**
 * Entry point for the Peckish Claude Desktop extension (.mcpb).
 *
 * Claude Desktop launches this with its bundled Node runtime; `peckish` and
 * its deps are vendored into the bundle's node_modules, so there is nothing
 * for the user to install. Importing the module starts the stdio MCP server.
 *
 * stdout is the MCP transport — diagnostics must go to stderr only.
 */
import "peckish/dist/mcp.js";
