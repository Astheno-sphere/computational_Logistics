#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z, type ZodTypeAny } from "zod";
import { TOOLS, SERVER_INFO, toolAnnotations, type ToolArg } from "./core.js";

const server = new McpServer({ name: SERVER_INFO.name, version: SERVER_INFO.version });

function zodFor(a: ToolArg): ZodTypeAny {
  const s = (a.type === "number" ? z.number() : z.string()).describe(a.description);
  return a.optional ? s.optional() : s;
}

function json(data: unknown) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }],
    structuredContent: data as Record<string, unknown>,
  };
}

for (const t of TOOLS) {
  const shape: Record<string, ZodTypeAny> = {};
  for (const a of t.args) shape[a.name] = zodFor(a);
  server.tool(t.name, t.description, shape, toolAnnotations(t.name), async (args) => {
    try {
      return json(t.run(args as Record<string, unknown>));
    } catch (err) {
      return json({ error: (err as Error).message });
    }
  });
}

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error("floodwise MCP server failed to start:", err);
  process.exit(1);
});
