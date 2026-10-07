# Codex Setup and Distribution Runbook (F7.AC3)

This runbook covers connecting `vessel-traffic-mcp` to the OpenAI
**Codex CLI** as an MCP server, and documents the current state of
Codex plugin manifest / marketplace metadata.

It closes F7.AC3 of the discoverability/release feature: *"Add Claude
Desktop, Claude Code, ChatGPT remote MCP, generic MCP Inspector, and
Codex setup/distribution docs, including Codex plugin manifest or
marketplace metadata when ready."*

The Claude Desktop, Claude Code, ChatGPT remote MCP, and generic MCP
Inspector wirings are covered by the F1.AC3
[client setup runbook](./clients.md). This file extends that contract
to Codex specifically. Read it together with `clients.md` — the hard
rules, env-var contract, and read-only tool surface are identical.

## Hard rules (must hold for the Codex wiring too)

- **Read-only.** The registered tools — `provider_status`,
  `data_sources`, `credential_profiles`, `provider_onboarding`,
  `vessel_search`, `vessel_name_resolve`, `document_vessel_lookup`,
  `vessel_position`, `vessel_area`, `vessel_track`, `port_calls`,
  `carrier_schedule_search`, `vessel_schedule`, and
  `schedule_delay_predict`, plus the connector-style `search` and
  `fetch` wrappers — all declare `readOnlyHint: true`. Codex
  must not be wired to a tool surface that mutates provider accounts,
  fleets, billing settings, saved searches, or user profiles.
- **Default verification stays fixture-only.** `npm run lint`,
  `npm test`, and `npm run build` exercise the fixture provider; the
  Codex wiring documented here never implies a paid or live call by
  default.
- **Never paste secrets into chat.** `VESSEL_MCP_AUTH_TOKEN` and any
  BYOK provider key must come from the operator's secret store or a
  gitignored config file — not from a Codex chat message.
- **stdout is the MCP protocol stream.** When Codex spawns the stdio
  binary, the server writes only MCP JSON-RPC frames to stdout.
  Diagnostics go to stderr with credentials redacted.

## Prerequisites

Use Node.js 22 or newer. From a clean checkout:

```bash
npm ci
npm run build
```

After `npm run build` succeeds, the binary is available at
`dist/index.js`. Default transport is stdio; set
`VESSEL_MCP_TRANSPORT=http` to start the Streamable HTTP server
instead. The full registered tool surface is read-only and listed
above.

## Codex CLI (stdio) — `~/.codex/config.toml`

The OpenAI Codex CLI registers MCP servers through TOML configuration
at `~/.codex/config.toml`. Add a `[mcp_servers.vessel-traffic-mcp]`
table that runs the built binary with `VESSEL_MCP_TRANSPORT=stdio`.
Use an absolute path; Codex does not run inside the repository
checkout.

```toml
[mcp_servers.vessel-traffic-mcp]
command = "node"
args = ["/absolute/path/to/vessel-traffic-mcp/dist/index.js"]

[mcp_servers.vessel-traffic-mcp.env]
VESSEL_MCP_TRANSPORT = "stdio"
```

Restart the Codex CLI after editing `~/.codex/config.toml`. In a new
session, the `vessel-traffic-mcp` server should appear in the tool
listing with the read-only tools enumerated above.

To opt in to the reviewed public MyShipTracking candidate for local
ship-name/MMSI lookup and bounding-box map positions, add the public
provider gate. This does not require credentials, and every result must
still expose the source service and URL through `source.provider` and
`source.landingUrl`.

```toml
[mcp_servers.vessel-traffic-mcp]
command = "node"
args = ["/absolute/path/to/vessel-traffic-mcp/dist/index.js"]

[mcp_servers.vessel-traffic-mcp.env]
VESSEL_MCP_TRANSPORT = "stdio"
VESSEL_MCP_ENABLE_PUBLIC_PROVIDERS = "myshiptracking,tradlinx,aisfriends"
```

BYOK profile env vars (only when you have explicit authorization for
that provider and account) go in the same `env` table:

```toml
[mcp_servers.vessel-traffic-mcp.env]
VESSEL_MCP_TRANSPORT = "stdio"
VESSEL_MCP_ENABLE_BYOK_PROVIDERS = "marinetraffic"
VESSEL_MCP_PROFILE_MARINETRAFFIC__API_KEY = "<your key>"
```

The MarineTraffic adapter is BYOK-only and implements the documented
`shipsearch`, `exportvessel`, `exportvesseltrack`, and `portcalls`
endpoints. Route calls with provider `marinetraffic` and credential
profile label `marinetraffic` when you want the official API instead of
the fixture or public MyShipTracking candidate. If the profile label is
exactly `marinetraffic`, the router can infer it when provider
`marinetraffic` is explicitly requested.

Do not paste real keys into chat. Keep them in this local config file
only; `~/.codex/config.toml` lives outside this repository and must
never be committed.

Reference: [`stdio-fixture-server.md`](./stdio-fixture-server.md).

## Codex CLI against the Streamable HTTP transport

When the Codex CLI is configured to call a remote MCP endpoint over
Streamable HTTP, point it at the same `/mcp` endpoint that the
ChatGPT remote-MCP connector uses. Start the HTTP transport server
side:

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

The full deployment contract — multi-stage `Dockerfile`,
`.dockerignore` secret boundary, nginx/Caddy/managed-platform HTTPS
topologies, and token rotation — lives in
[`deployment-https.md`](./deployment-https.md).

Reference: [`streamable-http-server.md`](./streamable-http-server.md).

Current Codex builds also support URL-based MCP registration. For a
public HTTPS deployment, use the CLI form:

```bash
codex mcp add vesselTraffic --url https://<your-public-host>/mcp
codex mcp list
```

Or add the equivalent URL entry to `~/.codex/config.toml`:

```toml
[mcp_servers.vessel-traffic-mcp]
url = "https://<your-public-host>/mcp"
```

The remote endpoint must still enforce the same token/OAuth boundary
used by ChatGPT remote MCP. Do not place bearer tokens in this
repository; keep them in the local Codex config, an ignored profile
file, or the operator's secret store.

## Codex plugin manifest / marketplace metadata

Codex itself does not currently publish a stable plugin-manifest
schema or a public plugin marketplace API that
`vessel-traffic-mcp` can target as a first-party listing. The
project tracks this surface here so it can be filled in without a
schema redesign once a stable contract exists:

- **Distribution model today.** Operators install
  `vessel-traffic-mcp` from this open-source repository (clone +
  `npm ci` + `npm run build`) and register it through
  `~/.codex/config.toml` as documented above. The `package.json`
  `bin` entry exposes the `vessel-traffic-mcp` command for any future
  `npx`-style or registry install.
- **Discoverability today.** The discoverability metadata
  documented in [`../discoverability.md`](../discoverability.md)
  (F7.AC2) carries the `codex-plugin` keyword and the `Codex plugin`
  GitHub Topic so operators can find the project under
  Codex-oriented search queries.
- **Forward-looking scaffold.** When Codex publishes a stable
  plugin manifest or marketplace metadata schema, the manifest
  should declare the same read-only tool surface that the MCP
  server already registers, point at the same `dist/index.js`
  binary, and reuse the BYOK env-var contract. No manifest may
  contain real credentials; only env-var *names* are valid.

  Sketch (illustrative; schema not yet finalized by Codex):

  ```jsonc
  // codex-plugin.json — scaffold, not a published Codex schema.
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
  this repository: writing it as if Codex consumed it today would
  encourage operators to install a file that has no defined effect.
  When a stable Codex plugin/marketplace schema lands, replace the
  sketch with a published manifest under version control and update
  the release checklist (`docs/runbooks/release-checklist.md`,
  section "Release assets are in place") to validate it.
- **Blocker, dated.** As of this acceptance criterion landing on
  2026-05-15, no stable, publicly documented Codex plugin manifest
  schema or marketplace publication API exists that this project
  can target. This is the concrete blocker for shipping a real
  manifest; the Codex CLI MCP wiring above is the supported
  distribution path until that changes.

## Generic MCP Inspector against the same surface

The generic MCP Inspector verifies that the Codex wiring talks to the
same registered tools as Claude Desktop / Claude Code:

```bash
npx @modelcontextprotocol/inspector node dist/index.js
```

Streamable HTTP form:

```bash
npx @modelcontextprotocol/inspector \
  --transport streamable-http \
  --server-url "http://127.0.0.1:3000/mcp" \
  --header "Authorization: Bearer $VESSEL_MCP_AUTH_TOKEN"
```

Use `127.0.0.1` for local-only inspection; do not expose the bearer
token over a non-TLS hop.

## Read-only contract for the Codex wiring

The Codex wiring inherits the same read-only contract as every other
client. When live providers are added later they continue to honour
the contract: no fleet edits, no saved-search mutations, no account
changes. Missing AIS coverage, stale positions, and no-data provider
responses are valid result states, not infrastructure errors.

## Verifying this runbook

Run from the project root:

```bash
npm run lint
npm test
npm run build
```

The deterministic test `test/codex-setup.test.js` asserts that this
runbook covers the Codex CLI TOML wiring, names the read-only tool
surface, points at both transports with the right env-var contract,
mirrors the `clients.md` runbook for the other four clients, and
does not contain credential-shaped strings. The discoverability
contract in [`../discoverability.md`](../discoverability.md)
(F7.AC2) carries the `codex-plugin` keyword. Default verification
does not call any paid or live vessel-data provider; everything
above is checked from local file contents only.
