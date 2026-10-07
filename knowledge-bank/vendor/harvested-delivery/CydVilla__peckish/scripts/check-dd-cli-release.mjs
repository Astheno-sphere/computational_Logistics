#!/usr/bin/env node
/**
 * Compare the dd-cli release Peckish targets against the latest one published.
 *
 * Peckish once sat three dd-cli releases behind without anyone noticing, which
 * is how a pile of features goes unused. This runs on a schedule (see
 * .github/workflows/dd-cli-release-watch.yml) and exits non-zero when
 * DD_CLI_RECOMMENDED_VERSION in src/platform.ts falls behind the latest tag.
 *
 *   node scripts/check-dd-cli-release.mjs
 *
 * Exit codes: 0 up to date, 1 behind, 2 could not check (network/API).
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
// Overridable so the script itself can be exercised against a fixture.
const RELEASES =
  process.env.DD_CLI_RELEASES_URL ??
  "https://api.github.com/repos/doordash-oss/doordash-cli/releases/latest";

const platform = readFileSync(join(ROOT, "src/platform.ts"), "utf8");
const targeted = platform.match(/DD_CLI_RECOMMENDED_VERSION = "([^"]+)"/)?.[1];
if (!targeted) {
  console.error("✗ could not read DD_CLI_RECOMMENDED_VERSION from src/platform.ts");
  process.exit(2);
}

function compareVersions(a, b) {
  const pa = a.split(".").map(Number);
  const pb = b.split(".").map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const d = (pa[i] ?? 0) - (pb[i] ?? 0);
    if (d !== 0) return d;
  }
  return 0;
}

let latest;
let releaseUrl = "https://github.com/doordash-oss/doordash-cli/releases";
try {
  const headers = { accept: "application/vnd.github+json", "user-agent": "peckish-release-watch" };
  // GitHub Actions supplies a token; unauthenticated works too, just rate-limited.
  if (process.env.GITHUB_TOKEN) headers.authorization = `Bearer ${process.env.GITHUB_TOKEN}`;
  const res = await fetch(RELEASES, { headers });
  if (!res.ok) throw new Error(`GitHub API returned ${res.status}`);
  const body = await res.json();
  latest = String(body.tag_name ?? "").match(/v?(\d+\.\d+\.\d+)/)?.[1];
  if (body.html_url) releaseUrl = body.html_url;
  if (!latest) throw new Error(`could not parse a version from tag "${body.tag_name}"`);
} catch (err) {
  console.error(`✗ could not check for dd-cli releases: ${err.message}`);
  process.exit(2);
}

if (compareVersions(latest, targeted) <= 0) {
  console.log(`✓ Peckish targets dd-cli ${targeted}; latest published is ${latest}`);
  process.exit(0);
}

console.error(
  `✗ dd-cli ${latest} is out — Peckish still targets ${targeted}\n\n` +
    `  Release notes: ${releaseUrl}\n\n` +
    `  To catch up: read the notes for every release above ${targeted}, wire the new\n` +
    `  flags through src/tools.ts (handler argv AND the strict tool schema — a flag the\n` +
    `  schema can't express is a flag the model can't use), add any new response fields\n` +
    `  the trimmers would drop, update the prompts in src/agent.ts and src/mcp.ts, then\n` +
    `  bump DD_CLI_RECOMMENDED_VERSION and the table in README.md.\n`,
);
process.exit(1);
