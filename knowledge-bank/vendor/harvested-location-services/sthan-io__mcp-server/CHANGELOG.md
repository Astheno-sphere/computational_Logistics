# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.9] - 2026-10-02

(0.1.8 was staged on npm but never released; 0.1.9 is the same content.)

- `sthan_ip_geolocation` / `sthan ip`: the API now also returns the network behind the address (`asn`, `asName`, `isp`, `organization`), `isMobile` / `isProxy` / `isHosting` flags, `reverseDns`, a 0-1 `confidence` score and country facts (flag, currency, calling code, local time). Tool description, README and the CLI summary show them. No breaking changes.

## [0.1.7] - 2026-09-26

### Added
- One-click install: "Install in VS Code" (prompts for the API key and stores it
  securely), "Install in VS Code Insiders", and "Add to Cursor" buttons.
- Claude Desktop extension (`sthan.mcpb`, attached to each GitHub release): double-click
  to install; Claude asks for the API key and keeps it in the system keychain. The server
  is bundled into one file, so nothing else needs installing. Build with
  `npm run build:mcpb`.

### Fixed
- Setup instructions: correct Claude Code command (`claude mcp add`, with `cmd /c` on
  Windows), real Claude Desktop config paths, VS Code `.vscode/mcp.json`, Windsurf, and
  `npx -y` everywhere (without `-y`, npx waits for an install prompt no AI client can
  answer). Added an MCP Inspector test command and troubleshooting notes.

## [0.1.6] - 2026-09-26

### Fixed
- Address verification and parsing no longer time out at 30 seconds. When sthan.io
  cannot match an address from its own data it falls through to a live postal
  lookup, which can take 70+ seconds. `verifyAddress` and `parseAddress` now wait up
  to 150 seconds (the same limit sthan.io's website uses); every other call keeps
  the 30-second limit. Configurable via the new `postalLookupTimeout` client option.

## [0.1.5] - 2026-06-27

### Fixed
- `@sthan/core` now calls the **V2** endpoints for address verification
  (`/v2/address-verification/usa/{address}`) and parsing
  (`/v2/address-parser/usa/{address}`). It was pointing at the older V1 routes,
  which omit `unitType`/`unitNumber` and the match metadata (`matchMode`,
  `matchTier`, `confidence`, `matchCode`). Verify and parse now return the full
  model in both the CLI and the MCP server. Geocode, autocomplete, and IP
  geolocation are unchanged (no V2 routes exist for those).

## [0.1.4] - 2026-06-27

### Changed
- Rewrote all 8 MCP tool descriptions for clarity and tool-definition quality:
  each now states its purpose, when to use it and when not (pointing to the
  right sibling tool), the response fields it returns, and behavioral notes
  (read-only, requires `STHAN_API_KEY`, counts toward the plan rate limit, and
  how errors are surfaced).
- Migrated MCP tool registration to `registerTool` and added read-only tool
  annotations (`readOnlyHint`, `idempotentHint`, `openWorldHint`,
  non-destructive) plus a human-readable `title` per tool.
- `@sthan/core` and `@sthan/cli` republished at 0.1.4 to keep the monorepo in
  lockstep (no functional changes in those two packages).

## [0.1.3] - 2026-06-27

### Added
- `@sthan/cli` package: a command-line tool with `login`, `whoami`, `verify`,
  `parse`, `geocode` (and reverse), and `ip`. Single lookups print a summary or
  `--json`. `verify`, `parse`, and `geocode` support batch `--input`/`--output`
  over CSV, TSV, XLSX, and TXT files, with bounded concurrency, automatic 429
  backoff, and per-row error capture.
- `mapWithConcurrency` in `@sthan/core`: a dependency-free concurrency runner
  with per-item retry and exponential backoff.

### Fixed
- `@sthan/core` `request()` read the response body as JSON unconditionally,
  which crashed on empty or non-JSON error responses (for example a 401 with no
  body). It now reads the body as text first and surfaces the HTTP status as a
  `SthanApiError`. This also fixes the auth-error message in `@sthan/mcp-server`.

### Changed
- `@sthan/core` and `@sthan/mcp-server` updated to 0.1.3.

## [0.1.2] - 2026-04-27

### Changed
- `STHAN_API_KEY` is no longer required at server startup. The check is deferred
  to per-tool invocation, so MCP introspection (`tools/list`) succeeds without
  an API key and tool calls return a clear error message if the key is missing.
- Expanded root README with a "why use it" section, multi-client setup snippets
  (Claude Desktop, Cursor, VS Code), example prompts, and links to the OpenAPI
  spec and `llms-full.txt` AI reference.
- `@sthan/core` updated to 0.1.2.

### Fixed
- Resolved 2 moderate transitive vulnerabilities reported by `npm audit`
  (in `hono`, via `@modelcontextprotocol/sdk`) by updating the lockfile.

### Added
- `LICENSE` file at the repository root (MIT).
- `glama.json` declaring the repository maintainer.
- `CHANGELOG.md` (this file).
- Continuous integration: build + type-check on Node 20 and 22.

## [0.1.1] - 2026-04-05

### Added
- `mcpName` field in `package.json` and `server.json` for the GitHub MCP Registry.
- `smithery.yaml` for the Smithery MCP directory.

## [0.1.0] - 2026-04-04

### Added
- Initial release.
- 8 MCP tools: `sthan_verify_address`, `sthan_parse_address`,
  `sthan_autocomplete_address`, `sthan_autocomplete_city`,
  `sthan_autocomplete_zipcode`, `sthan_geocode`, `sthan_reverse_geocode`,
  `sthan_ip_geolocation`.
- `@sthan/core` TypeScript SDK package.
- `@sthan/mcp-server` MCP server package, stdio transport.
