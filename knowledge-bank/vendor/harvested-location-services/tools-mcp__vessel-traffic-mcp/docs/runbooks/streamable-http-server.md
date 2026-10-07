# Streamable HTTP Server Runbook

## Scope

This runbook covers the F1.AC2 HTTP surface: a Streamable HTTP MCP endpoint at
`/mcp`, optional bearer-token authentication for MCP requests, and a public
`/health` endpoint for load balancers and uptime checks. The current tools are
fixture-backed and read-only. For end-to-end client wiring (Claude Desktop,
Claude Code, ChatGPT remote MCP, generic MCP Inspector) see
`docs/runbooks/clients.md`.

## Environment

Use Node.js 22 or newer.

```bash
npm ci
npm run build
```

Recommended local environment:

```bash
VESSEL_MCP_TRANSPORT=http
VESSEL_MCP_HTTP_HOST=127.0.0.1
VESSEL_MCP_HTTP_PORT=3000
VESSEL_MCP_AUTH_TOKEN=
```

Set `VESSEL_MCP_AUTH_TOKEN` only from a local ignored env file, process
environment, or deployment secret store. Do not paste production bearer tokens
into chat, committed config, logs, runbooks, or fixtures.

## Start

Run the HTTP server from a built checkout:

```bash
npm run start:http
```

The helper script builds first when `dist/index.js` is missing:

```bash
scripts/run-http-server.sh
```

Bind to all interfaces only behind a trusted HTTPS reverse proxy:

```bash
VESSEL_MCP_HTTP_HOST=0.0.0.0 VESSEL_MCP_HTTP_PORT=3000 scripts/run-http-server.sh
```

## Endpoints

- `GET /health`: public health check. It returns server name, status, transport,
  and MCP path. It does not expose bearer-token or provider credential state.
- `HEAD /health`: public health check with no response body.
- `GET /.well-known/mcp/server-card.json`: public directory metadata for MCP
  crawlers such as Smithery. It lists transport, package, tool, and provenance
  metadata without exposing bearer-token or provider credential material.
- `HEAD /.well-known/mcp/server-card.json`: public directory metadata check with
  no response body.
- `POST /mcp`: Streamable HTTP MCP JSON-RPC requests.
- `GET /mcp` and `DELETE /mcp`: Streamable HTTP session operations.
- `OPTIONS /mcp`: CORS preflight for browser-capable remote MCP clients.

When `VESSEL_MCP_AUTH_TOKEN` is non-empty, `/mcp` requires:

```text
Authorization: Bearer <configured token>
```

`/health` never requires the bearer token.

## Observability

HTTP startup, shutdown, and request events are written as JSON lines to stderr.
Request logs contain generated `requestId`, method, path, status, duration,
transport, and whether auth is required. They do not include headers, request
bodies, bearer tokens, provider query credentials, or raw provider responses.

Every HTTP response includes `X-Request-Id`. Use that value to correlate client
failures with server logs.

## Verification

Run the deterministic gates:

```bash
npm run lint
npm test
npm run build
```

`npm test` exercises the Streamable HTTP handler with fixture-backed MCP tools,
public `/health`, bearer-token rejection, authorized MCP calls, CORS preflight,
request IDs, and secret-safe log entries. Default verification does not call
paid or live vessel-data providers.

## Deployment Notes

Terminate TLS at a reverse proxy, load balancer, or platform edge before
exposing `/mcp` remotely. Keep `VESSEL_MCP_AUTH_TOKEN` in the deployment secret
manager and rotate it when client access changes.

For the full deployment contract — multi-stage `Dockerfile`,
`.dockerignore` secret boundary, nginx/Caddy/managed-platform HTTPS
topologies, token rotation, and the F6.AC2 verification gate — see
[`docs/runbooks/deployment-https.md`](./deployment-https.md).

Keep the server read-only: MCP tools must not mutate provider accounts, fleets,
billing settings, saved searches, or user profiles. Treat missing/stale AIS data
as a valid result state once live providers are added, not as an infrastructure
failure.
