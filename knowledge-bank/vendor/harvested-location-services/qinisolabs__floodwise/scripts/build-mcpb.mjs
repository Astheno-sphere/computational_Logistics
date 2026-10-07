// Build a one-click MCP Bundle (.mcpb) from the compiled server.
//
// An .mcpb is a self-contained zip (server + bundled prod deps + manifest.json) that installs
// into Claude Desktop in one click — no hand-edited JSON config. It's an EXTRA install option;
// the npm package, npx config and (where present) hosted endpoint are unchanged.
//
// Usage: npm run build && node scripts/build-mcpb.mjs
// Output: dist-mcpb/<name>-<version>.mcpb   (a release asset; not committed)
import { execSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync, cpSync, writeFileSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
const stage = join(tmpdir(), `mcpb-${pkg.name}-${process.pid}`);
const outDir = join(root, "dist-mcpb");
const safeName = pkg.name.replace(/^@[^/]+\//, ""); // drop npm scope (@qinisolabs/) so the file isn't nested
const out = join(outDir, `${safeName}.mcpb`); // stable, scope-stripped name (version lives in the manifest)

if (!existsSync(join(root, "dist"))) {
  console.error("dist/ not found — run `npm run build` first.");
  process.exit(1);
}

// Fresh staging dir.
rmSync(stage, { recursive: true, force: true });
mkdirSync(join(stage, "server"), { recursive: true });
mkdirSync(outDir, { recursive: true });

// manifest + compiled server.
cpSync(join(root, "manifest.json"), join(stage, "manifest.json"));
cpSync(join(root, "dist"), join(stage, "server"), { recursive: true });

// Minimal package.json carrying ONLY the production deps, then install them into the bundle.
writeFileSync(
  join(stage, "package.json"),
  JSON.stringify({ name: pkg.name, version: pkg.version, type: "module", dependencies: pkg.dependencies || {} }, null, 2),
);
console.error("Installing production dependencies into the bundle…");
execSync("npm install --omit=dev --no-audit --no-fund --silent", { cwd: stage, stdio: "inherit" });

// Pack + validate.
rmSync(out, { force: true });
execSync(`npx -y @anthropic-ai/mcpb@latest pack "${stage}" "${out}"`, { cwd: root, stdio: "inherit" });
rmSync(stage, { recursive: true, force: true });
console.error(`\n✓ Built ${out}`);
