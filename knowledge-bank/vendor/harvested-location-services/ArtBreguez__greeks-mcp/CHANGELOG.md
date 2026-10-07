# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [0.2.0] — 2026-08-10

### Added
- Five new analytics tools wrapping the new commercial endpoints:
  - `get_vex` (`/api/analytics/vex`, Pro) — Vanna & Charm exposure, the
    second-order dealer Greeks behind OPEX and end-of-day drift.
  - `get_vol_structure` (`/api/analytics/vol-structure`, Trader) — IV skew and
    term structure with plain-English reads (contango/backwardation).
  - `get_zero_dte` (`/api/analytics/zero-dte`, Pro) — 0DTE focus panel: pin risk,
    gamma flip, max pain and expected move from today's expiring contracts.
    Honestly reports `isTrue0DTE=false` (pinRisk "n/a") when nothing expires.
  - `get_gex_intraday` (`/api/analytics/gex-intraday`, Pro) — intraday
    gamma-regime time-series plus the timing of the last regime flip. Takes
    `date="YYYY-MM-DD"` instead of `expiration`.
  - `get_track_record_detail` (`/api/analytics/track-record`, Pro) — the
    authenticated day-by-day level report card behind the public accuracy
    headline. Takes an optional `symbol`.
- Server now exposes **17 tools** (was 12). Tests, CI/publish tool-count checks,
  and the README tool table were updated accordingly.

## [0.1.1] — 2026-07-30

### Fixed
- Pin `mcp[cli]` to `<2`. The unbounded `>=1.2.0` constraint let installs resolve
  to `mcp` 2.0.0, which restructured the package and removed
  `mcp.server.fastmcp` — breaking `uvx greeks-mcp` at startup with
  `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`.

### Added
- `Dockerfile` (+ `.dockerignore`) so the server can be built and run as a
  container. Starts and answers MCP introspection (initialize + tools/list) with
  no API key — enough for Glama to evaluate it. Public tools work keyless; the
  authenticated analytics tools use `GREEKS_API_KEY` at runtime when present.

## [0.1.0] — 2026-07-25

Initial release.

### Added
- MCP server exposing the Greeks options-analytics API as 12 tools:
  - Analytics: `get_max_pain`, `get_greeks`, `get_gex`, `get_flow`,
    `get_overview`, `get_snapshot`, `get_levels`.
  - Public data: `screener`, `gex_heatmap`, `track_record`.
  - Utility: `list_plans`, `health`.
- API-key auth via `GREEKS_API_KEY` (only required for `/api/analytics/*`;
  public tools work without a key).
- Configurable base URL (`GREEKS_BASE_URL`), timeout (`GREEKS_TIMEOUT`), and
  transport (`MCP_TRANSPORT`: stdio or http).
- Actionable error mapping for 401/402/403/404/429/timeouts.
- `greeks-mcp` console script and `python -m greeks_mcp` entry points.
- Ready-to-copy client configs for Claude Desktop and Cursor.
- Smoke test (tool wiring) and end-to-end test (spawns the server over stdio and
  exercises all 12 tools through the MCP protocol).
