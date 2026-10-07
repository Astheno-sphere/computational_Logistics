// Smoke test: start the built server over stdio and assert it advertises the
// tools we expect. Deliberately makes no API call, so it is deterministic in CI
// and cannot fail because addressintel.co is slow or down. For a live check
// against the real API, run test_mcp.mjs by hand instead.
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const EXPECTED = [
  "get_property_intelligence",
  "list_adu_leads",
  "list_market_signals",
  "list_redevelopment_leads",
  "list_sb9_inventory",
  "search_permits",
];

const transport = new StdioClientTransport({ command: "node", args: ["dist/index.js"] });
const client = new Client({ name: "smoke-test", version: "1.0.0" }, { capabilities: {} });

await client.connect(transport);

const found = (await client.listTools()).tools.map((t) => t.name).sort();
const missing = EXPECTED.filter((t) => !found.includes(t));
const extra = found.filter((t) => !EXPECTED.includes(t));

if (missing.length || extra.length) {
  console.error(`expected: ${EXPECTED.join(", ")}`);
  console.error(`found:    ${found.join(", ")}`);
  if (missing.length) console.error(`missing:  ${missing.join(", ")}`);
  if (extra.length) console.error(`extra:    ${extra.join(", ")}`);
  process.exit(1);
}

// Every tool needs a description and an input schema, or clients render it badly.
for (const tool of (await client.listTools()).tools) {
  if (!tool.description?.trim()) {
    console.error(`tool ${tool.name} has no description`);
    process.exit(1);
  }
  if (!tool.inputSchema) {
    console.error(`tool ${tool.name} has no inputSchema`);
    process.exit(1);
  }
}

console.log(`ok: ${found.length} tools advertised, all described`);
process.exit(0);
