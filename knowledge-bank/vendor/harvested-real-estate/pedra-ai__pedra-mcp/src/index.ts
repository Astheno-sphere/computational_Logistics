#!/usr/bin/env node
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { Pedra } from "@pedra-ai/sdk";
import { createServer, SERVER_NAME, SERVER_VERSION } from "./server";

async function main(): Promise<void> {
  const apiKey = process.env.PEDRA_API_KEY?.trim();
  if (!apiKey) {
    // Start anyway: the agent can get a key for the user with
    // pedra_request_access (they confirm by email). It's kept in memory only.
    process.stderr.write(
      "PEDRA_API_KEY is not set: starting without an account. The assistant can get one with " +
        "pedra_request_access (the user confirms by email), or add PEDRA_API_KEY to this server's " +
        "`env` block in your MCP client config (key in Settings at https://app.pedra.ai).\n",
    );
  }

  const server = createServer(apiKey ? new Pedra(apiKey) : null);
  const transport = new StdioServerTransport();
  await server.connect(transport);

  // stdio carries the MCP protocol on stdout — only log to stderr.
  process.stderr.write(
    `${SERVER_NAME} MCP server v${SERVER_VERSION} running on stdio.\n`,
  );
}

main().catch((err: unknown) => {
  const message = err instanceof Error ? err.message : String(err);
  process.stderr.write(`Fatal: ${message}\n`);
  process.exit(1);
});
