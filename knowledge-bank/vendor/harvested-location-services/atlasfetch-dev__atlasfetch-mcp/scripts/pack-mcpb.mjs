// Build the MCPB bundles.
//
//   atlasfetch-<version>.mcpb           Spec-valid bundle. Claude Desktop installs
//                                       it with a double-click; attach it to
//                                       GitHub releases.
//   atlasfetch-<version>.smithery.mcpb  The same files, for `smithery mcp publish`.
//
// Why two: the formats disagree about tools. The MCPB manifest spec rejects an
// `inputSchema` on a tool ("Unrecognized key"), and `mcpb pack` enforces that.
// Smithery's CLI copies `manifest.tools` verbatim into its server card, and
// Smithery's API then rejects any tool WITHOUT `inputSchema` — our first publish
// failed with one "expected object, received undefined" per tool. No single
// manifest satisfies both, so the Smithery copy is produced after packing, by
// swapping in a manifest whose tools carry their real schemas.
//
// Those schemas are read from the built server itself (tools/list), never
// written by hand, so they cannot drift from the code.
//
// A bundle ships its own node_modules, so it is packed from a staging copy with
// PRODUCTION dependencies only — packing the working tree would drag TypeScript
// and the mcpb CLI into every user's download.
//
// Run: npm run pack:mcpb
import { cpSync, mkdirSync, readFileSync, rmSync, existsSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { join, resolve } from "node:path";
import { unzipSync, zipSync, strToU8, strFromU8 } from "fflate";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const STAGE = join("build", "mcpb");

function run(command, args, cwd = ".") {
  // A shell is needed so npm and npx resolve to their .cmd shims on Windows. The
  // command goes in as one string: passing an args array alongside shell:true
  // is deprecated (DEP0190), because the array is concatenated unescaped anyway.
  // Every argument here is a literal or a path this script built, never input.
  const line = [command, ...args.map(a => (/\s/.test(a) ? `"${a}"` : a))].join(" ");
  const result = spawnSync(line, { cwd, stdio: "inherit", shell: true });
  if (result.status !== 0) {
    console.error(`\nFailed: ${line}`);
    process.exit(result.status ?? 1);
  }
}

// Every place the version lives must agree, or the bundle, the npm package and
// the registry entry would describe different releases.
const pkg = JSON.parse(readFileSync("package.json", "utf8"));
const manifest = JSON.parse(readFileSync("manifest.json", "utf8"));
const serverJson = JSON.parse(readFileSync("server.json", "utf8"));
const versions = {
  "package.json": pkg.version,
  "manifest.json": manifest.version,
  "server.json": serverJson.version,
  "server.json packages[0]": serverJson.packages[0].version,
};
if (new Set(Object.values(versions)).size !== 1) {
  console.error("Versions disagree; refusing to pack:", versions);
  process.exit(1);
}
if (!existsSync(join("dist", "stdio.js"))) {
  console.error("dist/stdio.js is missing. Run npm run build first.");
  process.exit(1);
}

// ── Stage production files ───────────────────────────────────────────────────
rmSync(STAGE, { recursive: true, force: true });
mkdirSync(STAGE, { recursive: true });
for (const file of ["manifest.json", "icon.png", "LICENSE", "README.md", "package.json", "package-lock.json"]) {
  cpSync(file, join(STAGE, file));
}
cpSync("dist", join(STAGE, "dist"), { recursive: true });
run("npm", ["ci", "--omit=dev", "--ignore-scripts", "--no-audit", "--no-fund", "--silent"], STAGE);

// ── The spec-valid bundle ────────────────────────────────────────────────────
run("npx", ["mcpb", "validate", join(STAGE, "manifest.json")]);
const output = `atlasfetch-${pkg.version}.mcpb`;
rmSync(output, { force: true });
run("npx", ["mcpb", "pack", STAGE, output]);

// ── Ask the staged server what it actually exposes ───────────────────────────
// Run from the staging copy, so it resolves the bundle's own dependencies. No
// key is needed: listing tools makes no API call.
const transport = new StdioClientTransport({
  command: process.execPath,
  args: [resolve(STAGE, "dist", "stdio.js")],
  cwd: resolve(STAGE),
  env: { ...process.env, ATLASFETCH_API_KEY: "" },
  stderr: "ignore",
});
const client = new Client({ name: "pack-mcpb", version: pkg.version });
await client.connect(transport);
const { tools: liveTools } = await client.listTools();
await client.close();

const declared = manifest.tools.map(t => t.name).sort();
const live = liveTools.map(t => t.name).sort();
if (JSON.stringify(declared) !== JSON.stringify(live)) {
  console.error("manifest.json tools do not match the server:", { manifest: declared, server: live });
  process.exit(1);
}

// ── The Smithery bundle: same archive, tools with schemas ────────────────────
const smitheryManifest = {
  ...manifest,
  tools: liveTools.map(t => ({
    name: t.name,
    ...(t.title ? { title: t.title } : {}),
    description: t.description ?? "",
    inputSchema: t.inputSchema,
    ...(t.annotations ? { annotations: t.annotations } : {}),
  })),
};
for (const tool of smitheryManifest.tools) {
  if (tool.inputSchema?.type !== "object") {
    console.error(`Tool ${tool.name} has no object inputSchema; Smithery will reject it.`);
    process.exit(1);
  }
}

const entries = unzipSync(new Uint8Array(readFileSync(output)));
const packedManifest = JSON.parse(strFromU8(entries["manifest.json"]));
if (packedManifest.version !== pkg.version) {
  console.error("The packed manifest is not the one just built.");
  process.exit(1);
}
entries["manifest.json"] = strToU8(JSON.stringify(smitheryManifest, null, 2) + "\n");

const smitheryOutput = `atlasfetch-${pkg.version}.smithery.mcpb`;
writeFileSync(smitheryOutput, zipSync(entries, { level: 9 }));

console.log(`\nBuilt ${output}  (Claude Desktop, GitHub releases)`);
console.log(`Built ${smitheryOutput}  (smithery mcp publish) — ${smitheryManifest.tools.length} tools with input schemas`);
