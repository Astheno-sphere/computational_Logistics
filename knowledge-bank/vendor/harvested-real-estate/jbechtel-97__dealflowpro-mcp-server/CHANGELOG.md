# Changelog

All notable changes to this project will be documented in this file.

## [1.2.7] - 2026-10-06

### Changed
- README: DealFlowPro is now listed in the Claude Connectors Directory (published 2026-10-06 as a community connector); the README links the listing and keeps the custom-connector path.
- README: dropped the "first real estate underwriting tool in the MCP ecosystem" claim, which could not be verified.
- README: corrected three stale statements. Auth is a Bearer key or, on the remote endpoint, an OAuth sign-in; the four saved-pipeline tools on the remote server are MCP-only; the `~$0.01/call` eval figure contradicted the pay-as-you-go price and was removed.

No functional change to the stdio server. This release exists so npmjs.com and the MCP Registry serve the corrected README, which only refresh on publish.

## [1.2.6] - 2026-08-24

### Changed
- README: corrected the claude.ai connection path. It named `Settings → Integrations → Add Custom Connector`, which no longer exists; the current path is `Customize → Connectors → "Add custom connector"`.
- README: documented the Team/Enterprise variant, which was missing entirely. Members on those plans cannot add a custom connector themselves — an organization Owner adds it once under `Organization settings → Connectors → Add → Custom`, after which each member connects their own DealFlowPro account.
- README: added the pre-filled install link (`claude.ai/customize/connectors?modal=add-custom-connector&...`) as an "Add DealFlowPro to Claude" button, and stated plainly that DealFlowPro is a custom connector rather than a Connectors Directory listing.

No functional change — this release exists so npmjs.com serves the corrected README, which only refreshes on publish.

## [1.2.5] - 2026-06-25

### Changed
- `score_deal` tool description aligned with the DFP-served MCP endpoint (`mcp_tools.php`). Both now read "Quick screening — returns the 0-100 DFP Score with quality grade." Previous npm description ("Quick DFP Score (0-100) and key metrics") was accurate but less detailed.
- Bumped `server-card.json` version (was stale at `1.2.2`).

## [1.2.4] - 2026-06-25

### Changed
- Bumped `@modelcontextprotocol/sdk` from `^1.12.0` to `^1.29.0` (17 minor versions of SDK improvements)
- Bumped `zod` from `^4.0.0` to `^4.4.3`

### Fixed
- Declared `zod` as an explicit dependency (was transitive-only through SDK; now pinned in `package.json` for stable version resolution)

## [1.2.3] - 2026-05-29

### Added
- Sends `User-Agent: dealflowpro-mcp/1.2.3` on every API call so MCP-originated traffic can be distinguished from direct API use in server-side audit logs

## [1.2.2] - 2026-05-28

### Improved
- Added npm keywords for better discoverability: `claude`, `anthropic`, `mcp-server`, `mcp-tools`, `commercial-real-estate`, `cap-rate`, `investment-analysis`
- Updated server-card.json version (was stale at 1.0.1)
- Added demo screenshot to README

## [1.2.1] - 2025-05-25

### Fixed
- market_data: flood zone null values no longer incorrectly display as "Not in flood zone"

## [1.2.0] - 2025-05-25

### Removed
- Removed fabricated `verdict` field from analyze and score API responses — the app uses manual pipeline stages, not auto-verdicts

### Fixed
- Server version in MCP handshake now matches package.json
- Header comment lists all 4 tools and both environment variables
- API: removed unused `property_address` from reverse-calc endpoint (data minimization)

### Changed
- Added Glama badge to README
- Fixed reverse_calc example prompt in README to include required monthly_income

## [1.0.1] - 2025-05-21

### Added
- `market_data` tool — flood zone, neighborhood income, job growth for any address
- Smithery registry support (`smithery.yaml`)
- MCP Registry support (`server.json` with `mcpName`)
- Dockerfile for Glama introspection checks
- `.well-known/mcp/server-card.json` for Smithery scanning

## [1.0.0] - 2025-05-20

### Added
- Initial release
- `analyze_deal` tool — full multifamily deal analysis with DFP Score, cap rate, DSCR, cash-on-cash, IRR, max offer price, and yearly cashflows
- `score_deal` tool — quick screening with DFP Score and verdict (Quick Review / Lead Underwriting / Closed Leads)
- `reverse_calc` tool — back-solve max offer price from target return metrics
- Formatted markdown output for all tools
- Published to npm as `dealflowpro-mcp`
