#!/usr/bin/env node
/**
 * Build the GitHub release body for a version:
 *   the version's CHANGELOG section
 *   + a standard install/upgrade block (all four channels)
 *   + artifact checksums (when a SHA256SUMS.txt path is supplied).
 *
 *   node scripts/release-notes.mjs <version> [path/to/SHA256SUMS.txt] > notes.md
 *
 * Used by release.yml; runnable locally to preview notes.
 */
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const version = (process.argv[2] ?? "").replace(/^v/, "");
if (!version) {
  console.error("usage: node scripts/release-notes.mjs <version> [SHA256SUMS.txt]");
  process.exit(1);
}

const changelog = readFileSync(join(ROOT, "CHANGELOG.md"), "utf8");
const escaped = version.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const sectionMatch = changelog.match(
  new RegExp(`^## \\[${escaped}\\][^\\n]*\\n([\\s\\S]*?)(?=^## \\[|\\Z)`, "m"),
);
if (!sectionMatch) {
  console.error(`✗ CHANGELOG.md has no "## [${version}]" section — write it before releasing.`);
  process.exit(1);
}

const lines = [];
lines.push(sectionMatch[1].trim(), "");

lines.push("## Install / upgrade", "");
lines.push("| Surface | Command |");
lines.push("|---|---|");
lines.push(`| Terminal + web | \`npm install -g peckish@${version}\` |`);
lines.push(
  `| Claude Code (MCP) | \`claude mcp add peckish -- npx -y peckish-mcp\` (upgrades pick up automatically on reconnect) |`,
);
lines.push(
  `| Claude Desktop | download \`peckish-${version}.mcpb\` below and double-click |`,
);
lines.push(`| Mac app | download \`Peckish-${version}-arm64.dmg\` below (unsigned — right-click → Open the first time) |`);
lines.push("");
lines.push(
  "Requires DoorDash's [dd-cli](https://github.com/doordash-oss/doordash-cli) signed in on your own machine — macOS (Apple Silicon) or Linux x86_64, which needs dd-cli ≥ 0.2.2. If dd-cli was upgraded, re-run `dd-cli login` (or `dd-cli export-token` for a headless host).",
  "",
);

const sumsPath = process.argv[3];
if (sumsPath && existsSync(sumsPath)) {
  const sums = readFileSync(sumsPath, "utf8").trim();
  if (sums) {
    lines.push("## Verify downloads", "");
    lines.push("`shasum -a 256 -c SHA256SUMS.txt` after downloading, or compare manually:", "");
    lines.push("```");
    lines.push(sums);
    lines.push("```", "");
  }
}

process.stdout.write(lines.join("\n"));
