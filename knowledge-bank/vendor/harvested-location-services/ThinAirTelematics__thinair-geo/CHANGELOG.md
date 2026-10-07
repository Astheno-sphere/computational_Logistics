# Changelog

All notable changes to `@thinairtelematics/geo` are documented here.
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
and the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

## [Unreleased]

## [2.2.3] — 2026-10-06

### Security
- **MCP SDK range tightened to `^1.31.0`.** The dependency was declared as
  `^1.0.0`, which still admitted `@modelcontextprotocol/sdk` 1.12.0 through
  1.30.1, the range affected by GHSA-6qxp-vccf-f47h. A fresh install now
  resolves a patched SDK (1.32.1 at the time of release). Transitive
  dependencies were refreshed in the lockfile so `npm audit --omit=dev` reports
  no known vulnerabilities.

### Notes
- The tool catalog (`tools.json`, 19 tools) is unchanged from 2.2.2 and matches
  the live catalog.

## [2.2.2] — 2026-09-29

### Changed
- `tools/list` from the local adapter now serves the full live tool catalog
  (complete input and output schemas, annotations) from the shipped
  `tools.json`.

## [2.2.1] — 2026-09-15

### Fixed
- **The README's headline example returned zero results.** It advertised
  `geocode "Port of Houston Bayport Terminal"` resolving to "Bayport Container
  Terminal, confidence 0.97, 29.6008 -95.0201". Live, that query returns
  `match_count: 0` — with and without `layers=venue`. The coordinates do
  reverse-geocode (12100 Port Road, Seabrook TX), so the location is indexed as
  an address; the venue name is what fails. The first example a prospect tries
  was one that could not work.

  Replaced with a live-verified query. Confirmed against production on
  2026-09-15: `geocode "Bayport Terminal"` → "Bayport Terminal, Harris County,
  TX, USA", confidence 1, 29.61345 / -95.00292.

  npm serves the README from the published tarball, so the broken example stayed
  visible on the package page for every release since it was written — this
  patch exists to get the corrected one published.

## [2.2.0] — 2026-09-14

### Fixed
- **Release pipeline unblocked.** `release.yml` has not run since 2026-05-02
  (v2.1.4 — no `v*` tag pushed since), so this was latent rather than observed on
  that workflow. It would fail on the next tag: `npm install -g npm@latest` now
  resolves to npm 12, whose engines are `^22.22.2 || ^24.15.0 || >=26.0.0`, a hard
  `EBADENGINE` exit 1 on the Node 20 runner. Not hypothetical — the identical step
  in `release-mcp.yml` failed exactly this way on 2026-07-14. Runners now use Node 22 and pin `npm@^11`, with an
  explicit assert that `npm --version` is at least 11.5.1 — the floor for Trusted
  Publisher OIDC auto-auth (OIDC publish landed in 11.5.0; 11.5.1 fixed provenance
  defaulting to OIDC). The assert fails the job rather than publishing unsigned.
- **Version gate unblocked.** `package.json` and `server.json` had drifted apart
  (2.1.4 vs 2.1.6), which the release workflow's own version-match check rejects
  with exit 1. Both now read 2.2.0, matching the version the hosted product
  already serves at `/.well-known/agent-card.json`.

### Changed
- `release-mcp.yml` no longer triggers on pushes to `main`. It previously fired on
  any commit touching `geo-mcp/**` *or the workflow file itself*, so an ordinary
  docs commit could start an unreviewed npm publish. It is now
  `workflow_dispatch` only.

### Added
- **Agent-discovery surfaces documented.** The README now points at the live
  `/.well-known/agent-card.json`, `/.well-known/skills.json`, and `/llms.txt`
  endpoints, which agents and directory crawlers can read without parsing prose.
- Generated-content markers (`TOOLCOUNT`, `TOOLS`, `AGENT-DISCOVERY`) in the
  README so a future generator can keep the tool list in sync with the live
  server instead of drifting by hand.

## [2.0.5] — 2026-04-26

### Added
- `repository` field in package.json pointing at https://github.com/ThinAirTelematics/thinair-geo — npmjs.com now surfaces a "Repository" link to this public release source.


## [2.0.4] — 2026-04-26

### Changed
- Release pipeline moved to a dedicated public repository
  (https://github.com/ThinAirTelematics/thinair-geo) — enables npm provenance
  attestation without exposing the source monorepo. First version published
  with `--provenance` from CI.

## [2.0.3] — 2026-04-26

### Removed
- Dropped `repository` and `bugs.url` fields that pointed to the source repo.
  Issues and source links route through https://geo.thinair.co/support and
  support@thinair.co instead.

## [2.0.2] — 2026-04-26

### Added
- `mcpName: "co.thinair/geo"` in `package.json` for MCP Registry ownership verification.

### Changed
- MCP Registry namespace updated to slash-separated format (`co.thinair/geo`).

## [2.0.1] — 2026-04-26

### Added
- Initial `mcpName` field for the MCP Registry (later corrected in 2.0.2).

## [2.0.0] — 2026-04-26

### Changed
- **Renamed package** from `thinair-geo` (unscoped) to `@thinairtelematics/geo` (scoped).
- Org namespace: now published under `thinairtelematics` org on npm.
- Bin name unchanged: `thinair-geo` for `npx` invocation.
- README, badges, and footer URLs updated for the new package name.

### Migration
The unscoped `thinair-geo@1.0.x` has been deprecated; npm will surface the
deprecation message pointing users at `@thinairtelematics/geo`. No code changes
needed in consumers — the printed config block is identical.

## [1.0.1] — 2026-04-25

### Added
- `LICENSE` file (MIT) shipped in tarball.
- Geist Mono `500` weight added to font preload list (eliminates a swap flash
  inside the typography of the printed config block).
- "Try with npx" pointer in the README now uses the canonical short form.

### Fixed
- README links section: removed dangling Discord/Enterprise lines, added
  `Main: https://geo.thinair.co` as first link.

## [1.0.0] — 2026-04-25

### Added
- Initial public release.
- `npx thinair-geo` prints a ready-to-paste MCP client config block for the
  hosted `https://geo.thinair.co/mcp` endpoint.
- Flags: `--api-key <key>`, `--transport sse`.
- Keyless OAuth 2.1 default; key-bearing variant for non-OAuth clients.
- Zero runtime dependencies.

