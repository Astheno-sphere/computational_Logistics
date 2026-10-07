# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-19

First public release.

### Added

- MCP server for the Zornade API v2, implemented as a Deno Supabase Edge
  Function (mcp-lite + Hono, streamable HTTP transport).
- Six tools:
  - `zornade_geocode_search` - forward geocoding on the ANNCSU street archive
    (18.7+ million Italian addresses).
  - `zornade_geocode_reverse` - reverse geocoding by WGS84 coordinates.
  - `zornade_parcel_by_id` - enriched cadastral parcel profile by FID or GML
    ID (risk, economics, solar, valuation and more, geometry omitted).
  - `zornade_parcel_locate` - parcels by point, multiple points or bounding
    box.
  - `zornade_parcel_search` - parcels by comune, foglio, label, sezione.
  - `zornade_admin_lists` - regions, provinces and municipalities.
- API key passthrough: the client key is accepted as `x-api-key` header,
  `Authorization: Bearer` header or `?api_key=` query parameter, with an
  optional `ZORNADE_API_KEY` environment fallback for self-hosting and
  automated checks.
- Public endpoint `https://mcp.zornade.com/mcp` via Netlify reverse proxy.
- Dockerfile and healthcheck for self-hosting: the HTTP server listens on
  port 8000 by default, or on a comma-separated list of ports via
  `ZORNADE_LISTEN_PORTS`.
- Stdio entrypoint (`functions/mcp/stdio.ts`) speaking JSON-RPC on
  stdin/stdout, used for local agent usage and automated directory checks.
- Shared tool definitions module (`functions/mcp/tools.ts`) so HTTP and stdio
  transports expose the exact same tools.
- MIT license and README with connection instructions for Claude Code,
  Claude Desktop and other MCP clients.

### Known limitations

- The HTTP transport is stateless: no persistent SSE sessions.
- Tool calls require a free Zornade API key (10,000 requests/hour per key).
