#!/usr/bin/env node
/**
 * Guard the metadata that spans several files and can silently drift apart.
 *
 * Every rule here comes from a real failure: a lowercase registry namespace
 * (403 Forbidden), a server.json version that didn't match the npm package,
 * an over-long registry description (schema rejection), and an extension
 * manifest advertising a different tool count than the server returns.
 *
 *   node scripts/check-consistency.mjs
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (p) => JSON.parse(readFileSync(join(ROOT, p), "utf8"));

const pkg = read("package.json");
const mcpPkg = read("packages/mcp/package.json");
const server = read("server.json");
const manifest = read("extension/manifest.json");
const mcpSource = readFileSync(join(ROOT, "src/mcp.ts"), "utf8");

const problems = [];
const check = (ok, message) => {
  if (!ok) problems.push(message);
};

// The MCP server reports its own version in serverInfo — easy to forget.
const declaredVersion = mcpSource.match(/name:\s*"peckish",\s*version:\s*"([^"]+)"/)?.[1];
check(
  declaredVersion === pkg.version,
  `src/mcp.ts serverInfo version (${declaredVersion}) != package.json version (${pkg.version})`,
);

// Registry ownership: server.json name must equal the published mcpName.
check(
  server.name === mcpPkg.mcpName,
  `server.json name (${server.name}) != packages/mcp mcpName (${mcpPkg.mcpName})`,
);

// The registry preserves the GitHub login's casing; lowercasing it 403s.
check(
  server.name.startsWith("io.github.CydVilla/"),
  `server.json name must start with "io.github.CydVilla/" (exact GitHub username casing) — got ${server.name}`,
);

// The registry entry must point at a real npm version of the wrapper.
check(
  server.packages[0].version === mcpPkg.version,
  `server.json packages[0].version (${server.packages[0].version}) != packages/mcp version (${mcpPkg.version})`,
);
check(
  server.packages[0].identifier === mcpPkg.name,
  `server.json packages[0].identifier (${server.packages[0].identifier}) != ${mcpPkg.name}`,
);

// Schema limit — silently fatal at publish time.
check(
  server.description.length <= 100,
  `server.json description is ${server.description.length} chars (max 100)`,
);

// The extension advertises its tools; a stale list misleads the install UI.
check(
  manifest.version === pkg.version,
  `extension/manifest.json version (${manifest.version}) != package.json version (${pkg.version})`,
);
check(
  manifest.tools.some((t) => t.name === "get_session_context"),
  "extension/manifest.json is missing get_session_context (added by mcp.ts, not tools.ts)",
);

// dd-cli ships darwin-arm64 and linux-amd64 (Linux since v0.2.2) — claiming
// any other platform would strand users on an OS with no dd-cli build.
check(
  JSON.stringify(manifest.compatibility.platforms) === JSON.stringify(["darwin", "linux"]),
  `extension manifest platforms should be ["darwin", "linux"] — got ${JSON.stringify(manifest.compatibility.platforms)}`,
);

// Releases must ship with curated notes: the version being released needs its
// own CHANGELOG section (release.yml turns it into the GitHub release body).
const changelog = readFileSync(join(ROOT, "CHANGELOG.md"), "utf8");
check(
  new RegExp(`^## \\[${pkg.version.replace(/\./g, "\\.")}\\]`, "m").test(changelog),
  `CHANGELOG.md has no "## [${pkg.version}]" section — write the release notes before bumping/releasing`,
);

if (problems.length) {
  console.error("✗ metadata consistency check failed:\n");
  for (const p of problems) console.error("  • " + p);
  console.error("");
  process.exit(1);
}
console.log("✓ metadata is consistent across package.json, server.json, mcp.ts and the extension manifest");
