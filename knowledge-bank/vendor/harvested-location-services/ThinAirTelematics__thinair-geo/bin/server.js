#!/usr/bin/env node
/**
 * @thinairtelematics/geo — local stdio reference adapter.
 *
 * Production runtime is hosted at
 * https://geo.thinair.co/mcp (streamable-http transport, OAuth 2.0 + Bearer).
 *
 * This file is a tool-catalog adapter that satisfies stdio-only
 * MCP runners (e.g. Glama's automated quality check, sandboxed CI) without
 * proxying to the hosted endpoint. tools/list returns the real tool catalog
 * so the runner indexes capabilities accurately; tools/call returns a
 * redirect message pointing the caller at the hosted endpoint for execution.
 *
 * Real users should configure their MCP client with the hosted URL directly
 * (printed by `bin/start.js`). This file exists for the quality-check gate.
 */

import { readFileSync } from "node:fs";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const REDIRECT_MESSAGE =
  "This is the local reference adapter for ThinAir Geo. " +
  "Tool execution requires the hosted MCP server at https://geo.thinair.co/mcp. " +
  "Configure your MCP client with that URL (and a Bearer token from " +
  "https://geo.thinair.co/connect — free 7-day trial, no signup) to execute tools.";

// The catalog is generated from the live tool registrations and shipped as
// tools.json (see package.json "files"). Resolved relative to this file so it
// works from any working directory and from the published tarball.
const TOOLS = JSON.parse(
  readFileSync(new URL("../tools.json", import.meta.url), "utf8"),
);
const { version: PACKAGE_VERSION } = JSON.parse(
  readFileSync(new URL("../package.json", import.meta.url), "utf8"),
);

const server = new Server(
  {
    name: "thinair-geo",
    version: PACKAGE_VERSION,
  },
  {
    capabilities: { tools: {} },
    instructions:
      "This is the local reference adapter. The production server is hosted at https://geo.thinair.co/mcp — connect there for real tool execution. tools/list reflects the live tool catalog.",
  },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

server.setRequestHandler(CallToolRequestSchema, async () => ({
  content: [{ type: "text", text: REDIRECT_MESSAGE }],
  isError: false,
}));

const transport = new StdioServerTransport();
await server.connect(transport);
