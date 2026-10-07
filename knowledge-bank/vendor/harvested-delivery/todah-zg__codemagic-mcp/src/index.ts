#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { execFile } from "node:child_process";
import { readFileSync } from "node:fs";
import { promisify } from "node:util";
import { registerCodemagicTools } from "./tools/codemagic.js";
import { registerAscTools } from "./tools/asc.js";
import { registerGooglePlayTools } from "./tools/googleplay.js";
import { registerYamlTools } from "./tools/yaml.js";
import { registerPrompts } from "./prompts.js";
import { registerReleaseNotesTools } from "./tools/releasenotes.js";
import { registerReadinessTools } from "./tools/readiness.js";
import { registerTestingTools } from "./tools/testing.js";

const execFileAsync = promisify(execFile);
const { version } = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as { version: string };

async function binaryVersion(cmd: string): Promise<string | null> {
  try {
    const { stdout } = await execFileAsync(cmd, ["--version"], { timeout: 5_000 });
    return stdout.trim().split(/\r?\n/)[0];
  } catch {
    return null;
  }
}

// Validate required credentials
const apiToken = process.env.CODEMAGIC_API_TOKEN ?? "";
if (!apiToken) {
  console.error("Warning: CODEMAGIC_API_TOKEN is not set. Codemagic tools will fail when called.");
}

// ASC credentials — optional, but warn if partial or missing
const ascVars = ["ASC_KEY_ID", "ASC_ISSUER_ID", "ASC_PRIVATE_KEY_B64", "ASC_BYPASS_KEYCHAIN"];
const missingAsc = ascVars.filter(v => !process.env[v]);
if (missingAsc.length > 0 && missingAsc.length < ascVars.length) {
  console.error(`Warning: partial ASC configuration — missing: ${missingAsc.join(", ")}. App Store Connect tools will fail.`);
} else if (missingAsc.length === ascVars.length) {
  console.error(`Warning: ${ascVars.join(", ")} are not set. App Store Connect tools will not work.`);
}

// Google Play credentials — optional, warn if missing
if (!process.env.GOOGLE_PLAY_SERVICE_ACCOUNT_CREDENTIALS) {
  console.error("Warning: GOOGLE_PLAY_SERVICE_ACCOUNT_CREDENTIALS is not set. Google Play tools will not work.");
}

// Preflight external CLIs — one line each so users (and support) can spot missing binaries immediately
const [ascVersion, gpVersion] = await Promise.all([binaryVersion("asc"), binaryVersion("google-play")]);
console.error(`asc: ${ascVersion ? `found ${ascVersion}` : "NOT FOUND — App Store Connect tools will fail"}`);
console.error(`google-play: ${gpVersion ? `found ${gpVersion}` : "NOT FOUND — Google Play tools will fail"}`);

// Server setup
const server = new McpServer({
  name: "codemagic-mcp",
  description: "MCP server for Codemagic CI/CD, App Store Connect, and Google Play",
  version,
});

// Register tools by domain
registerCodemagicTools(server, apiToken, version);
registerAscTools(server, apiToken);
registerGooglePlayTools(server, apiToken);
registerYamlTools(server);
registerPrompts(server);
registerReleaseNotesTools(server);
registerReadinessTools(server);
registerTestingTools(server, apiToken);


// Start
const transport = new StdioServerTransport();
await server.connect(transport);