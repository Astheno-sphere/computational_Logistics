# Changelog

All notable changes to this project are documented here. This project follows [Semantic Versioning](https://semver.org).

## [1.0.0] - Initial release

### Added
- Built against Ambee's `/v3` API endpoints (`/v3/aq/*`, `/v3/weather/*`, `/v3/pollen/*`)
- All tools accept `place` or `lat` and `lng` natively at the API level allowing the client-side geocoding to be optional.
- Added `aqiStandard` (air quality), `units` (weather), and `speciesRisk` (pollen) parameters.
- Full error-code handling for every status documented at [docs.ambeedata.com/apis/overview#error-codes](https://docs.ambeedata.com/apis/overview#error-codes) (200, 206, 299, 400, 401, 403, 404, 422, 429, 500), each surfaced as a clear MCP tool error with actionable guidance.
- Client configuration examples for Claude Code, Claude Desktop, Cursor, VS Code, Windsurf, Cline, Zed, Ollama (via `mcp-use`), ChatGPT, and generic MCP clients.

