# AGENTS.md

## Project Goal

Build `vessel-traffic-mcp`: a read-only Model Context Protocol server that lets ChatGPT, Claude, Claude Code, and other MCP clients query vessel identity, position, track, and port-call data from authorized AIS/maritime data sources.

## Hard Rules

- Do not bypass authentication, paywalls, CAPTCHA, bot defenses, rate limits, or access controls.
- Do not implement credential harvesting, session hijacking, account sharing, or hidden scraping.
- Prefer official APIs and open-data feeds before any browser-network capture workflow.
- Browser/HAR capture support is for operator-owned, authorized sessions only, and only when the service terms allow that use.
- Paid/commercial providers are supported through BYOK credential profiles. Users may use their own provider subscriptions, but raw keys must be redacted and should not be pasted into normal chat unless a one-time in-memory mode is explicitly enabled.
- Never commit API keys, cookies, bearer tokens, CSRF tokens, session IDs, HAR files, `.env*`, or raw private captures.
- Sanitize all captured samples before storing fixtures. Strip `Authorization`, `Cookie`, `Set-Cookie`, API keys, tokens, personal account IDs, and precise billing identifiers.
- Keep MCP tools read-only. No tool may modify a provider account, fleet, billing setting, saved search, or user profile.
- Include source, timestamp, freshness, coverage caveats, and confidence in every vessel-position response.
- For B/L and shipping-document workflows, vessel-name resolution must return ranked MMSI/IMO candidates with evidence and must request confirmation when ambiguous.
- Treat missing AIS coverage, stale positions, and no-data responses as valid states, not implementation errors.
- Do not present AIS data as safety-critical navigation data.

## Implementation Preferences

- Runtime: Node.js 22+, TypeScript, ESM.
- MCP SDK: `@modelcontextprotocol/sdk`.
- Primary transports: stdio for local Claude Desktop/Claude Code use, Streamable HTTP for remote ChatGPT/Claude connector use. SSE can be added only as compatibility fallback.
- Provider integrations must use adapter interfaces. Avoid provider-specific logic leaking into MCP tool handlers.
- For browser-only API capture, reference `<api-capture-checkout>` architecture and docs, especially Playwright network capture, HAR backup, replay validation, traffic IR, supervisor pacing, and redaction. Do not read or copy its `.env`, raw sessions, raw logs, cookies, or credentials. The reference-only boundary is formalized in `docs/runbooks/api-capture-reference-only.md` (F5.AC5): raw api-capture sessions, `.env` files, cookies, and logs must never be imported into this project or committed. The operator-only execution workflow — triple-gated live driver, raw/sanitized artifact split, fixture promotion, and the rationale for excluding autodev/CI — is documented in `docs/runbooks/capture-execution.md` (F5A.AC3).
- Tests should use sanitized fixtures and local fake providers. Do not call paid or live providers in default CI.
- Live-provider tests must be opt-in through environment variables and skipped by default.
