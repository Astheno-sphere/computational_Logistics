# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and the project adheres to [Semantic Versioning](https://semver.org/).

## [1.1.0] — 2026-08-19

### Changed

- **The server no longer exits because of configuration.** A missing `YANGO_DELIVERY_TOKEN`
  is a survivable state: the server starts, completes the MCP handshake, serves the full
  tool list and opens the `initialize` instructions with the fix (set the variable and
  restart the server — it is read only at startup). A tool call then fails with that same
  actionable message (`CredentialsError`, an `isError` response) — without retries and
  without touching the network — instead of the client showing a dead server with no reason.

### Added

- Telemetry event `unconfigured_start` (with the historical `missing_token` reason code):
  a server without a token now survives to the MCP handshake, so a degraded start is
  counted separately instead of inflating `server_start` or dying as `startup_failed`.

## [1.0.1] — 2026-08-12

### Added

- Server instructions. The MCP `initialize` response now carries a short briefing for the calling
  model: what this API is and is not, what it cannot do, and the quotas, retry rules and misleading
  failures that should change how it is used. That knowledge previously lived only in the README,
  which a model never reads.

## [1.0.0] — 2026-08-11

### Changed

- Declared stable. The tool surface, input schemas and environment variables of 0.1.x carry over
  unchanged — this release marks API stability, not new behaviour.

## [0.1.0] — 2026-08-09

First full release (version 0.0.1 was a stub reserving the npm name).

### Added

- 13 MCP tools for the Yango Delivery claims B2B API (`b2b.taxi.yandex.net`,
  the express contour — the only one documented for countries outside Russia):
  - **Claim lifecycle:** `check_price`, `create_claim` (idempotent `request_id`),
    `accept_claim`, `get_claim`, `get_cancel_info`, `cancel_claim`, `search_claims`.
  - **Tracking & contact:** `get_performer_position`, `get_tracking_links`,
    `get_points_eta`, `get_courier_phone`, `get_confirmation_code`.
  - `raw_request` — a direct call to any method of the claims API.
- HTTP client: Bearer auth (`YANGO_DELIVERY_TOKEN`), `Accept-Language`
  (`YANGO_DELIVERY_LANG`, default `en`), AbortController timeout, retries with
  backoff (429 always; 5xx/network only for idempotent calls), an SSRF guard on
  `raw_request` paths, decoding of both API error shapes (`{code, message}` and
  `error_messages[]` inside 200 responses).
- Annotations on every tool (`READ_ONLY`/`WRITE`/`DESTRUCTIVE`) — the server is
  a writing one; cancellation is marked destructive.
- Anonymous usage telemetry (opt-out `ASKADS_TELEMETRY=0`).
- Tests: offline unit suite + 3 smoke tests of the built `dist/` (including a
  real MCP handshake over stdio); CI on Node 20/22/24.
