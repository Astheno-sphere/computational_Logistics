# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.5] - 2026-04-26

### Changed

- **`check_grass_conditions` description condensed** to push TDQS Conciseness from 4/5 → 5/5. Removed redundant repetition of "cached 24h", "no auth required", and "reads state.json" across multiple sections; folded the data-freshness paragraph into the leading summary. All distinct facts retained; word count down ~40%.

## [0.1.4] - 2026-04-25

### Changed

- **TDQS refinements** based on Glama's per-dimension feedback on v0.1.0:
  - `check_grass_conditions`: added explicit data-freshness block (location 24h cache vs. live weather/sunset, ~200–600ms latency, no permissions beyond outbound HTTPS + local file read).
  - `log_touch_grass`: tightened the `activity` parameter description to explicitly link it to the recording action (stored verbatim as the entry's `activity` field, descriptive only, no effect on streak math), and added error-handling disclosure (failures surface as `isError=true` without partial streak updates).

## [0.1.3] - 2026-04-25

### Changed

- **Tool definitions upgraded for Glama TDQS**: every MCP tool now ships MCP-spec `annotations` (`title`, `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) and rewritten descriptions covering side effects (file writes, outbound HTTPS), auth requirements, rate-limit behavior, and explicit when-to-use vs. when-not-to-use guidance. Addresses Glama's "Behavior" and "Usage Guidelines" findings.

## [0.1.2] - 2026-04-25

### Fixed

- **Glama hosting**: added a root `index.js` shim that delegates to `plugin/mcp-server/index.mjs`, and pulled `@modelcontextprotocol/sdk` into the root `package.json`. Glama's auto-runner invokes `node index.js` from the repo root, which previously failed with `MODULE_NOT_FOUND`.

## [0.1.1] - 2026-04-25

### Added

- **Dockerfile** at the repo root for running the MCP server as a container (used by the Glama directory listing).
- **glama.json** claiming maintainership of the Glama MCP server listing.

## [0.1.0] - 2026-04-11

First public release. 🌿

### Added

- **Claude Code plugin** (`plugin/.claude-plugin/plugin.json`) bundling a SessionStart hook, MCP server, and agent skill.
- **SessionStart hook** (`plugin/hooks/session-start.mjs`) that fetches live weather, sunset timing, and streak state, then injects a decision-ready context block into every Claude Code session.
- **MCP server** (`plugin/mcp-server/index.mjs`) exposing four tools:
  - `check_grass_conditions` — weather, temperature, minutes until sunset, streak state
  - `suggest_activity` — random activity recommendation (golden-hour-aware)
  - `log_touch_grass` — records that the user went outside, updates streak
  - `get_stats` — raw session telemetry and streak history
- **Agent skill** (`plugin/skills/touch-grass/SKILL.md`) teaching the agent when to nudge, when to stay quiet, and what tone to use.
- **Local state management** at `~/.touch-grass/state.json` for streak and session tracking.
- **IP-based location detection** via `ip-api.com` (cached 24h).
- **Weather + sunset** via `open-meteo.com` (no API key, no account).
- **Next.js marketing site** at [touch-grass-xi.vercel.app](https://touch-grass-xi.vercel.app) with copyable install command, nudge demo, MCP tools reference, and a PWA manifest.
- **GitHub Actions CI** — syntax checks, hook smoke test, MCP `tools/list` smoke test, Next.js typecheck/lint/build.
- **VHS demo tape** at `plugin/docs/demo.tape` for reproducible README recordings.

### Privacy

- All state stored locally in `~/.touch-grass/`.
- Only two external calls: `ip-api.com` for city coordinates (cached 24h) and `api.open-meteo.com` for weather and sunset.
- No accounts, no API keys, no telemetry.

[0.1.0]: https://github.com/nalediym/touch-grass/releases/tag/v0.1.0
