# MCP Client Setup Runbook (F1.AC3)

This runbook is the single client-facing entry point for connecting an MCP
client to `vessel-traffic-mcp`. It covers these supported clients:

1. **Claude Desktop** (local stdio)
2. **Claude Code** (local stdio)
3. **ChatGPT remote MCP** (Streamable HTTP at `/mcp`)
4. **Gemini CLI / Gemini Code Assist** (`mcpServers` settings)
5. **Generic MCP Inspector** (`@modelcontextprotocol/inspector`)

Transport-level mechanics live in
[`stdio-fixture-server.md`](./stdio-fixture-server.md) and
[`streamable-http-server.md`](./streamable-http-server.md); BYOK credential
state lives in [`credential-profiles.md`](./credential-profiles.md). This
file documents the client wiring only.

## Hard rules (must hold for every client wiring)

- **Read-only.** MCP tools must not modify provider accounts, fleets,
  billing settings, saved searches, or user profiles. The registered
  tools — `provider_status`, `data_sources`, `credential_profiles`,
  `provider_onboarding`, and the vessel/schedule query tools — all
  declare `readOnlyHint: true`.
- **Default verification stays fixture-only.** `npm run lint`,
  `npm test`, and `npm run build` exercise the fixture provider; no
  client configuration in this runbook implies a paid or live call by
  default.
- **Never paste secrets into chat.** `VESSEL_MCP_AUTH_TOKEN` and any
  BYOK provider key must come from the deployment secret store, an OS
  keychain, a sourced shell file, or a gitignored env file — not from a
  pasted client message.
- **stdout is the MCP protocol stream.** When running stdio servers,
  the binary writes only the MCP JSON-RPC frames to stdout. Diagnostic
  output, when emitted at all, must go to stderr with credentials
  redacted.

## Prerequisites

Use Node.js 22 or newer. From a clean checkout:

```bash
npm ci
npm run build
```

After `npm run build` succeeds, the package binary is available at
`dist/index.js` and the symlink `node_modules/.bin/vessel-traffic-mcp`
(when installed as a dependency) or directly at `./dist/index.js`
(when running from the repo). The default transport is stdio; set
`VESSEL_MCP_TRANSPORT=http` to start the Streamable HTTP server
instead.

The current registered tool surface is fixture-backed and read-only:

- `provider_status`, `data_sources`, `credential_profiles`,
  `provider_onboarding`
- `vessel_search`, `vessel_name_resolve`, `document_vessel_lookup`,
  `vessel_position`, `vessel_area`, `vessel_track`, `port_calls`
- `carrier_schedule_search`, `vessel_schedule`, `schedule_delay_predict`

## Claude Desktop (stdio)

Claude Desktop launches MCP servers from its
`claude_desktop_config.json` file. Add a `vessel-traffic-mcp` entry
that runs the built binary with `VESSEL_MCP_TRANSPORT=stdio`. Use an
absolute path; Claude Desktop does not run inside the repository
checkout.

```json
{
  "mcpServers": {
    "vessel-traffic-mcp": {
      "command": "node",
      "args": ["/absolute/path/to/vessel-traffic-mcp/dist/index.js"],
      "env": {
        "VESSEL_MCP_TRANSPORT": "stdio",
        "VESSEL_MCP_ENABLE_PUBLIC_PROVIDERS": "myshiptracking,tradlinx,aisfriends"
      }
    }
  }
}
```

Restart Claude Desktop after editing the config. In a new chat, the
`vessel-traffic-mcp` server should appear in the tool listing with the
read-only tools enumerated above.

`tradlinx` enables the explicit opt-in FCL/LCL carrier schedule adapter for
`carrier_schedule_search`; the default verification path remains fixture-only.
Client displays may show the returned `source.landingUrl` as the source without
adding a vendor display label.

BYOK profile env vars (only when you have explicit authorization for
that provider and account) go in the same `env` block:

```json
"env": {
  "VESSEL_MCP_TRANSPORT": "stdio",
  "VESSEL_MCP_PROFILE_MARINETRAFFIC__API_KEY": "<your key>"
}
```

Do not paste real keys into chat. Keep them in this local config file
only; the config file lives outside this repository.

Reference: [`stdio-fixture-server.md`](./stdio-fixture-server.md).

## Claude Code (stdio)

Claude Code reads the same `claude_desktop_config.json`-style schema
through its CLI. To register the server for a single project, add a
`.mcp.json` file at the project root (or use `claude mcp add`):

```json
{
  "mcpServers": {
    "vessel-traffic-mcp": {
      "command": "node",
      "args": ["/absolute/path/to/vessel-traffic-mcp/dist/index.js"],
      "env": {
        "VESSEL_MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

Alternatively, run the binary inline for an ad-hoc session:

```bash
VESSEL_MCP_TRANSPORT=stdio /absolute/path/to/vessel-traffic-mcp/dist/index.js
```

Claude Code will surface the read-only tools and route tool calls
through stdio. The same secret rules as Claude Desktop apply: BYOK
keys go in the project-local `.mcp.json` env block (gitignored) or in
the operator shell — never pasted into chat.

## ChatGPT remote MCP (Streamable HTTP)

ChatGPT remote MCP connects over Streamable HTTP. The server must be
reachable over HTTPS from ChatGPT, so this client always runs against
the HTTP transport behind a trusted TLS reverse proxy. Local-only
testing is supported by tunnelling to `127.0.0.1`.

Server side, start the HTTP transport:

```bash
export VESSEL_MCP_TRANSPORT=http
export VESSEL_MCP_HTTP_HOST=127.0.0.1
export VESSEL_MCP_HTTP_PORT=3000
export VESSEL_MCP_AUTH_TOKEN="<a-strong-random-token-you-generated>"
npm run start:http
```

Endpoints:

- `GET /health` and `HEAD /health` — public, no bearer token required.
- `POST /mcp`, `GET /mcp`, `DELETE /mcp`, `OPTIONS /mcp` — Streamable
  HTTP MCP. Requires `Authorization: Bearer <token>` when
  `VESSEL_MCP_AUTH_TOKEN` is non-empty.

Every response includes an `X-Request-Id` header (UUID v4) for log
correlation. Request logs go to stderr as JSON and never include
request headers, request bodies, bearer tokens, provider query
credentials, or raw provider responses.

In the ChatGPT remote MCP connector UI, configure:

| Field | Value |
| --- | --- |
| Endpoint URL | `https://<your-public-host>/mcp` |
| Authentication | Bearer token: `<the same value as VESSEL_MCP_AUTH_TOKEN>` |
| Transport | Streamable HTTP |

For ChatGPT, OpenAI Responses API, and search-style connector flows,
`vessel-traffic-mcp` also exposes generic read-only `search` and
`fetch` wrappers. They map natural-language vessel queries to the
vessel identity and latest-position tools while preserving
`source.provider`, `source.landingUrl`, `retrievedAt`, freshness,
confidence, and no-navigation caveats. Keep the vessel-specific tools
enabled as well when the client supports full MCP tool selection.

Health probe (no auth):

```bash
curl -sf "https://<your-public-host>/health"
```

MCP probe (bearer auth):

```bash
curl -sS -X POST "https://<your-public-host>/mcp" \
  -H "Authorization: Bearer $VESSEL_MCP_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Bind to `0.0.0.0` only behind a trusted HTTPS reverse proxy that
terminates TLS. For the full deployment contract — multi-stage
`Dockerfile`, `.dockerignore` secret boundary, nginx/Caddy/managed-
platform HTTPS topologies, and token rotation — see
[`deployment-https.md`](./deployment-https.md).

Reference: [`streamable-http-server.md`](./streamable-http-server.md).

## Gemini CLI and Gemini Code Assist (stdio or HTTP)

Gemini CLI and Gemini Code Assist discover MCP servers from Gemini's
settings JSON. For a local stdio install using the published npm
package, add a server entry like this:

```jsonc
{
  "mcpServers": {
    "vessel-traffic-mcp": {
      "command": "npx",
      "args": ["-y", "@tools-mcp/vessel-traffic-mcp"],
      "env": {
        "VESSEL_MCP_TRANSPORT": "stdio",
        "VESSEL_MCP_ENABLE_PUBLIC_PROVIDERS": "myshiptracking,tradlinx,aisfriends"
      },
      "timeout": 30000
    }
  }
}
```

For a remote Streamable HTTP deployment, use Gemini's HTTP MCP shape
and keep credentials in local settings or the operator environment:

```jsonc
{
  "mcpServers": {
    "vessel-traffic-mcp": {
      "httpUrl": "https://<your-public-host>/mcp",
      "headers": {
        "Authorization": "Bearer <your-token>"
      },
      "timeout": 30000
    }
  }
}
```

Use the same smoke prompt as other agents:

```text
Use Vessel Traffic MCP. Search for EVER GIVEN, fetch the best result,
and include source.provider, source.landingUrl, observedAt, retrievedAt,
freshnessSeconds, confidence, coverage caveats, and a not-for-navigation note.
```

## Generic MCP Inspector

The generic [`@modelcontextprotocol/inspector`](https://www.npmjs.com/package/@modelcontextprotocol/inspector)
is the supported tool for ad-hoc exploration and tool-schema
inspection. It can drive either transport.

### Inspector against stdio

```bash
npx @modelcontextprotocol/inspector node dist/index.js
```

You should see the read-only tools list and be able to call
`provider_status`, `data_sources`, `credential_profiles`, and
`provider_onboarding` against the fixture provider.

### Inspector against Streamable HTTP

Start the HTTP server as in the ChatGPT section above, then point the
Inspector at the `/mcp` endpoint with the bearer token:

```bash
npx @modelcontextprotocol/inspector \
  --transport streamable-http \
  --server-url "http://127.0.0.1:3000/mcp" \
  --header "Authorization: Bearer $VESSEL_MCP_AUTH_TOKEN"
```

Use `127.0.0.1` for local-only inspection; do not expose the bearer
token over a non-TLS hop.

## Claude plugin manifest / installation metadata

PRD §8.1 says: *"Add Claude-oriented installation metadata if a
supported Claude MCP/plugin registry path is available; otherwise
keep documented local/remote MCP setup as the canonical integration."*

As of this runbook's last refresh on 2026-05-16, no stable, publicly
documented Claude plugin manifest schema or Claude MCP marketplace
publication API exists that `vessel-traffic-mcp` can target as a
first-party listing. The Claude Desktop and Claude Code wirings above
(via `claude_desktop_config.json` and `.mcp.json`) are the supported
distribution path until that changes. This is the concrete blocker
for shipping a real Claude manifest today.

The project tracks the forward-looking surface here so it can be
filled in without a schema redesign once a stable contract exists.
The scaffold parallels the Codex one in
[`./codex.md`](./codex.md) so a future manifest can be promoted into
either ecosystem without breaking the security model.

Sketch (illustrative; schema not yet finalized by Anthropic):

```jsonc
// claude-plugin.json — scaffold, not a published Anthropic schema.
{
  "name": "@tools-mcp/vessel-traffic-mcp",
  "displayName": "Vessel Traffic MCP",
  "description": "Read-only MCP server for vessel position and AIS-style maritime data (BYOK).",
  "license": "MIT",
  "homepage": "https://github.com/tools-mcp/vessel-traffic-mcp#readme",
  "repository": "https://github.com/tools-mcp/vessel-traffic-mcp",
  "transport": "stdio",
  "entrypoint": {
    "command": "node",
    "args": ["./dist/index.js"]
  },
  "env": {
    "VESSEL_MCP_TRANSPORT": "stdio"
  },
  "byok": {
    "envVarPrefix": "VESSEL_MCP_PROFILE_",
    "credentialPolicy": "redacted-labels-only"
  },
  "readOnly": true,
  "notForNavigation": true
}
```

This sketch is intentionally *not* shipped as a real manifest in
this repository: writing it as if Claude Desktop or Claude Code
consumed it today would encourage operators to install a file that
has no defined effect. When a stable Claude plugin/marketplace
schema lands, replace the sketch with a published manifest under
version control and update the release checklist
(`docs/runbooks/release-checklist.md`, section "Release assets are
in place") to validate it.

Cross-references:

- [`./codex.md`](./codex.md) — sibling Codex scaffold with the same
  invariants (read-only, BYOK redaction, env-var names only).
- [`../discoverability.md`](../discoverability.md) — F7.AC2
  discoverability surface (`claude-mcp` keyword and `Claude MCP`
  GitHub Topic) so operators can find the project under
  Claude-oriented search queries.
- [`./release-checklist.md`](./release-checklist.md) — release gate
  that locks the manifest invariants before any promotion.

## Read-only contract for every client

Whichever client you wire up, the registered tools must remain
read-only. When live providers are added later they continue to
honour the same contract: no fleet edits, no saved-search mutations,
no account changes. Missing AIS coverage, stale positions, and
no-data provider responses are valid result states, not infrastructure
errors.

## Verification matrix and claim boundary

The project verifies the MCP protocol contract locally; it does not claim that
an arbitrary user's authenticated Claude, ChatGPT, Codex, or Gemini account
has connected successfully. Keep those two levels of evidence separate.

| Surface | Reproducible evidence in this repository | What it proves | What it does not prove |
| --- | --- | --- | --- |
| Local stdio | `test/mcp-stdio.test.js` | A real SDK client can initialize the built stdio server, list its read-only tools, and call fixture-backed flows. | A user's desktop client configuration or account state. |
| Streamable HTTP | `test/mcp-http.test.js` | Health, server-card, bearer rejection/acceptance, CORS, request IDs, and tool discovery work through the HTTP handler. | A public HTTPS deployment; none is operated by the maintainers at this time. |
| Client configuration | This runbook and `test/client-setup.test.js` | The documented Claude, Claude Code, Codex, Gemini, and MCP Inspector settings use the package's actual binary and env-var contract. | A completed sign-in or connector approval in a third-party client. |

For a client-owned acceptance check, first run the deterministic test suite,
then use the applicable config in this runbook with the fixture-only default.
Record the client name, transport, tool-list result, and one source-attributed
query result. Do not record credentials, browser sessions, or raw provider
responses. A remote-client check additionally requires an operator-owned,
HTTPS-protected `/mcp` endpoint; see
[`deployment-https.md`](./deployment-https.md).

## Verifying this runbook

Run from the project root:

```bash
npm run lint
npm test
npm run build
```

The deterministic test `test/client-setup.test.js` asserts that this
runbook covers all four required clients, names the read-only tools,
points at both transports with the right env-var contract, parses
the Claude-oriented installation metadata scaffold above and locks
its read-only / BYOK / no-credentials invariants, and does not
contain credential-shaped strings. Default verification does not
call any paid or live vessel-data provider; everything above is
checked from local file contents only.
