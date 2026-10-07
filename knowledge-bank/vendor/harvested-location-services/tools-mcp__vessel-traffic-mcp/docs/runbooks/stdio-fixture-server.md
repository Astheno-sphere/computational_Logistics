# Stdio Fixture Server Runbook

## Scope

This runbook covers the current F1.AC1 server surface: the package binary starts
a stdio MCP server and exposes `provider_status` and `data_sources` backed by
the local fixture provider. Streamable HTTP is covered separately in
`docs/runbooks/streamable-http-server.md`; live providers and credential
profiles are tracked by later acceptance criteria. For end-to-end client
wiring (Claude Desktop, Claude Code, ChatGPT remote MCP, generic MCP
Inspector) see `docs/runbooks/clients.md`.

## Environment

Use Node.js 22 or newer.

```bash
cp .env.example .env.local
npm ci
npm run build
```

Set `VESSEL_MCP_TRANSPORT=stdio` for local stdio operation. Do not put API keys,
cookies, bearer tokens, HAR files, or private captures in committed files.

## Local Verification

Run the required deterministic gates:

```bash
npm run lint
npm test
npm run build
```

`npm test` builds the package, starts `dist/index.js` through the configured
`vessel-traffic-mcp` package binary target, lists MCP tools over stdio, and
calls both fixture-backed tools.

## Expected Tool State

- `provider_status`: read-only provider diagnostics for the fixture provider.
- `data_sources`: read-only source catalogue entry for fixture data.

The fixture provider never calls live or paid providers and does not require
credentials. Its outputs are deterministic product evidence for transport and
tool-registry verification only; they are not live AIS or navigation data.

## Logging And Secrets

Normal stdio MCP operation must not write logs to stdout because stdout is the
MCP protocol stream. Startup failures write a short stderr message with common
secret patterns redacted. CI and local tests assert that the package-binary
smoke test does not emit credential-like stderr.
