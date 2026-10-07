// Builds the Claude Desktop extension at dist-mcpb/sthan.mcpb.
//
// The server and its dependencies are bundled into a single file, so the extension ships
// without node_modules and users need nothing installed beyond Claude Desktop. The manifest
// version is stamped from packages/mcp-server/package.json so the two never drift.
//
// Run after `npm run build --workspaces`:  node scripts/build-mcpb.js
const { buildSync } = require("esbuild");
const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const serverDist = path.join(root, "packages/mcp-server/dist/index.js");
const stage = path.join(root, "mcpb/build");
const outDir = path.join(root, "dist-mcpb");
const outFile = path.join(outDir, "sthan.mcpb");

if (!fs.existsSync(serverDist)) {
  console.error("packages/mcp-server/dist/index.js not found. Run `npm run build --workspaces` first.");
  process.exit(1);
}

fs.rmSync(stage, { recursive: true, force: true });
fs.mkdirSync(path.join(stage, "server"), { recursive: true });
fs.mkdirSync(outDir, { recursive: true });

buildSync({
  entryPoints: [serverDist],
  outfile: path.join(stage, "server/index.js"),
  bundle: true,
  platform: "node",
  target: "node20",
  format: "cjs",
  legalComments: "none",
});

const { version } = JSON.parse(fs.readFileSync(path.join(root, "packages/mcp-server/package.json"), "utf8"));
const manifest = JSON.parse(fs.readFileSync(path.join(root, "mcpb/manifest.json"), "utf8"));
manifest.version = version;
fs.writeFileSync(path.join(stage, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
fs.copyFileSync(path.join(root, "mcpb/icon.png"), path.join(stage, "icon.png"));
fs.copyFileSync(path.join(root, "LICENSE"), path.join(stage, "LICENSE"));

const mcpb = "npx -y @anthropic-ai/mcpb";
execSync(`${mcpb} validate "${path.join(stage, "manifest.json")}"`, { stdio: "inherit" });
execSync(`${mcpb} pack "${stage}" "${outFile}"`, { stdio: "inherit" });

console.log(`Built ${path.relative(root, outFile)} (version ${version})`);
