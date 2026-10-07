// Installs the PUBLISHED package with npx into an empty temporary folder, then
// drives it with a real MCP client. Proves the release works for someone who
// has only the npm registry, not this checkout.
//
// Run: node scripts/registry-smoke.mjs [version]   (defaults to package.json)
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const version = process.argv[2] ?? JSON.parse(readFileSync("package.json", "utf8")).version;
const cwd = mkdtempSync(join(tmpdir(), "atlasfetch-smoke-"));

const transport = new StdioClientTransport({
  command: process.platform === "win32" ? "npx.cmd" : "npx",
  args: ["-y", `atlasfetch-mcp@${version}`],
  cwd,
  stderr: "pipe",
});
const client = new Client({ name: "registry-smoke", version: "0.0.0" });

try {
  await client.connect(transport);
  const served = client.getServerVersion()?.version;
  const { tools } = await client.listTools();
  console.log(`atlasfetch-mcp@${version} from npm reports version ${served}`);
  console.log("tools:", tools.map(t => t.name).join(", "));
  const res = await client.callTool({ name: "lookup_location", arguments: { lat: -33.9249, lng: 18.4241 } });
  console.log("lookup isError:", res.isError ?? false);
  console.log(res.content[0].text.split("\n")[0]);
  if (served !== version || res.isError) process.exitCode = 1;
} finally {
  await client.close().catch(() => {});
  rmSync(cwd, { recursive: true, force: true });
}
