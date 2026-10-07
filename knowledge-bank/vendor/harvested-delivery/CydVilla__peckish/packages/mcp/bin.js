#!/usr/bin/env node
/**
 * `peckish-mcp` — thin launcher so MCP clients can run the Peckish MCP server
 * with a plain `npx -y peckish-mcp`.
 *
 * The `peckish` package ships three binaries and npx resolves the one matching
 * the package name (the terminal REPL), so MCP clients need this dedicated
 * entry point. All logic lives in `peckish`; importing the module starts the
 * stdio server. stdout is the MCP transport — never write to it here.
 */
import "peckish/dist/mcp.js";
