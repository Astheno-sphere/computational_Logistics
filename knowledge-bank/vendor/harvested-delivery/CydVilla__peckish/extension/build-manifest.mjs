#!/usr/bin/env node
/**
 * Regenerate the extension manifest's tool list from the built tool layer, so
 * the .mcpb never advertises a stale set. Run from `extension/`:
 *
 *   node build-manifest.mjs        (after `npm run build` at the repo root)
 */
import { readFileSync, writeFileSync } from "node:fs";
// Relative import on purpose: the manifest must reflect the repo's freshly
// built tool layer, not whatever peckish version extension/node_modules holds.
import { tools } from "../dist/tools.js";

const { version } = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8"));

/**
 * The MCP surface exposes one tool beyond the shared tool layer (mcp.ts adds
 * it), so list it here too — the count must match what tools/list returns.
 */
const MCP_ONLY_TOOLS = [
  {
    name: "get_session_context",
    description:
      "Load the user's ordering context: default delivery address, saved dietary/budget preferences, and current local time.",
  },
];

/** First sentence of a tool description, trimmed for the install UI. */
function shortDesc(text) {
  const first = text.split(/(?<=\.)\s/)[0].trim();
  return first.length > 110 ? first.slice(0, 107).trimEnd() + "…" : first;
}

const manifest = {
  manifest_version: "0.3",
  name: "peckish",
  display_name: "Peckish — DoorDash ordering",
  version,
  description: "Order food on DoorDash from Claude — you approve every order.",
  long_description:
    "Peckish gives Claude real DoorDash ordering: it searches stores, compares " +
    "true fee-included totals from live quotes, builds carts, scans promos, and " +
    "handles groceries, pickup, scheduled delivery, reorders and spend questions.\n\n" +
    "Placing an order always requires an approval dialog you answer yourself — " +
    "Claude must first show the itemized quote, confirm the Dasher tip, and name " +
    "the card being charged. Submission never auto-retries, and every tool call " +
    "and confirmation is logged to ~/.peckish/logs/.\n\n" +
    "Requires DoorDash's dd-cli (waitlist-gated) on a Mac with Apple Silicon or " +
    "Linux x86_64, signed in via `dd-cli login`. No Anthropic API key needed — " +
    "your Claude subscription powers the model.",
  author: {
    name: "Cyd Villavicencio",
    url: "https://github.com/CydVilla",
  },
  homepage: "https://github.com/CydVilla/peckish",
  documentation: "https://github.com/CydVilla/peckish#readme",
  support: "https://github.com/CydVilla/peckish/issues",
  icon: "icon.png",
  license: "MIT",
  keywords: ["doordash", "food", "delivery", "ordering", "groceries", "agent"],
  repository: {
    type: "git",
    url: "https://github.com/CydVilla/peckish",
  },
  server: {
    type: "node",
    entry_point: "server/index.js",
    mcp_config: {
      command: "node",
      args: ["${__dirname}/server/index.js"],
      env: {
        DD_CLI_PATH: "${user_config.dd_cli_path}",
      },
    },
  },
  user_config: {
    dd_cli_path: {
      type: "file",
      title: "dd-cli location (optional)",
      description:
        "Leave blank if dd-cli is at ~/.local/bin/dd-cli. Set it if you installed the DoorDash CLI somewhere else — desktop apps don't inherit your shell PATH.",
      required: false,
    },
  },
  tools_generated: false,
  tools: [
    ...MCP_ONLY_TOOLS,
    ...tools.map((t) => ({ name: t.name, description: shortDesc(t.description) })),
  ],
  compatibility: {
    claude_desktop: ">=0.10.0",
    // dd-cli ships darwin-arm64 and linux-amd64 builds (Linux since v0.2.2).
    platforms: ["darwin", "linux"],
    runtimes: { node: ">=20.0.0" },
  },
};

writeFileSync(new URL("./manifest.json", import.meta.url), JSON.stringify(manifest, null, 2) + "\n");
console.error(`wrote manifest.json with ${manifest.tools.length} tools`);
