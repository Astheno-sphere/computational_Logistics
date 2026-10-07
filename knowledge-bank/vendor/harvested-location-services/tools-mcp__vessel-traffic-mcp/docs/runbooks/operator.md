# Operator runbook (F6.AC3)

This runbook is the single entry point an operator needs to run
`vessel-traffic-mcp` against fixture data by default and, when explicitly
authorized, against real provider credentials. It covers four surfaces
that the rest of the runbook set assumes you already understand:

1. **Provider credentials** — how BYOK keys enter the process and how
   they stay out of logs.
2. **Rate limits** — what each provider declares and how the local
   limiter enforces those policies.
3. **Live-test toggles** — the `VESSEL_MCP_LIVE_TEST_*` flags that gate
   every paid or rate-limited call out of default verification.
4. **Client setup** — how Claude Desktop, Claude Code, ChatGPT remote
   MCP, and the generic MCP Inspector connect to the stdio and
   Streamable HTTP transports.

Cross-reference runbooks for details:

- `docs/runbooks/stdio-fixture-server.md` — stdio MCP transport.
- `docs/runbooks/streamable-http-server.md` — Streamable HTTP transport,
  `/health`, `/mcp`, bearer-token auth, request IDs.
- `docs/runbooks/credential-profiles.md` — BYOK profile loader and the
  labels-only contract exposed by the `credential_profiles` MCP tool.
- `docs/runbooks/capture-fixture-import.md` and
  `docs/runbooks/capture-traffic-ir.md` — authorized capture workflow
  (operator-only; never wired into default CI).

## Hard rules (must hold for every operator action)

- **Read-only.** MCP tools must not modify provider accounts, fleets,
  billing settings, saved searches, or user profiles. Do not call any
  endpoint that writes state.
- **Default verification must not call paid or live providers.**
  `npm run lint`, `npm test`, and `npm run build` use the fixture
  provider and sanitized fixtures only.
- **Never commit secrets.** API keys, bearer tokens, cookies, raw HAR
  files, `.env*`, and raw private captures are all gitignored. The
  `.env.example` template documents the env-var form without real
  values.
- **No bypass of authentication, paywalls, CAPTCHA, bot defenses, rate
  limits, or access controls.** Use official APIs, open-data feeds,
  user-provided credentials, or sanitized authorized capture fixtures.
- **MCP responses preserve provenance.** Every vessel-position payload
  must include `source`, `retrievedAt`, `observedAt` when available,
  freshness, coverage caveats, and confidence. Missing AIS coverage,
  stale positions, and no-data provider responses are valid states, not
  errors.

## Provider credentials

The credential profile loader is the only path raw keys take into the
process. See `docs/runbooks/credential-profiles.md` for the full
contract; the operator-facing summary is:

- **Env-var form** (preferred for ephemeral shells and CI secrets):

  ```
  VESSEL_MCP_PROFILE_<LABEL>__<FIELD>=<value>
  ```

  - `<LABEL>` is uppercased in the env var name; the loader normalizes
    it to lowercase with `_` replaced by `-`. Example:
    `VESSEL_MCP_PROFILE_MARINETRAFFIC__API_KEY=...` becomes profile
    label `marinetraffic`.
  - `<FIELD>` is one of `api_key`, `username`, `password`,
    `bearer_token`, `client_id`, `client_secret`, `subscription_key`.
    Unknown fields are silently ignored.
  - Empty values are treated as not set.

- **Local gitignored JSON form** at
  `config/credential-profiles.local.json`:

  ```json
  {
    "profiles": [
      { "label": "marinetraffic-prod", "provider": "marinetraffic", "fields": { "api_key": "..." } },
      { "label": "aisstream-dev",      "provider": "aisstream",     "fields": { "bearer_token": "..." } }
    ]
  }
  ```

  This file is in `.gitignore`. Do not commit it.

- **Merge rule.** When the same label appears in both sources, the
  environment value wins so operators can override a checked-in local
  profile without editing the file.

- **What the MCP surface exposes.** The `credential_profiles` MCP tool
  returns labels, provider hint, source, declared fields, and status
  only — never the secret material. Internal log lines route through
  `redactForLog` and `redactStructured`, which scrub
  `VESSEL_MCP_PROFILE_*` values along with `Authorization: Bearer ...`,
  cookies, `api_key=...`, JWTs (`eyJ...`), AWS access-key IDs, `sk-...`
  tokens, and GitHub `ghp_` tokens.

- **Per-provider env vars (live-test only).** The provider catalog
  (`config/provider-catalog.example.json`) records the env vars each
  provider expects. Examples — none of these are called by default:

  | Provider | Auth profile field(s) | Env var(s) |
  | --- | --- | --- |
  | `marinetraffic` | `api_key` | `VESSEL_MCP_PROFILE_MARINETRAFFIC__API_KEY` |
  | `vesselfinder` | `api_key` | `VESSEL_MCP_PROFILE_VESSELFINDER__API_KEY` |
  | `aisstream` | `api_key` | `VESSEL_MCP_PROFILE_AISSTREAM__API_KEY` |
  | `aishub` | `username` | `VESSEL_MCP_PROFILE_AISHUB__USERNAME` |
  | `barentswatch` | `client_id`, `client_secret` | `VESSEL_MCP_PROFILE_BARENTSWATCH__CLIENT_ID`, `VESSEL_MCP_PROFILE_BARENTSWATCH__CLIENT_SECRET` |
  | `searates-schedules` | `api_key` | `VESSEL_MCP_PROFILE_SEARATES_SCHEDULES__API_KEY` |
  | `routescanner-connect` | `api_key` | `VESSEL_MCP_PROFILE_ROUTESCANNER_CONNECT__API_KEY` |
  | `vesselapi` | `api_key` | `VESSEL_MCP_PROFILE_VESSELAPI__API_KEY` |
  | `datadocked` | `api_key` | `VESSEL_MCP_PROFILE_DATADOCKED__API_KEY` |
  | `datalastic` | `api_key` | `VESSEL_MCP_PROFILE_DATALASTIC__API_KEY` |
  | `globalfishingwatch` | `bearer_token` | `VESSEL_MCP_PROFILE_GLOBALFISHINGWATCH__BEARER_TOKEN` |
  | `spire-maritime` | `api_key` | `VESSEL_MCP_PROFILE_SPIRE__API_KEY` |

  Treat this table as a cheat sheet; the catalog file is authoritative.

## Rate limits

Every adapter declares a `RateLimitPolicy` via
`VesselDataProvider.rateLimitPolicy()`
(`src/providers/types.ts`). The shared limiter in
`src/util/rate-limit.ts` turns that policy into a token bucket with
`requestsPerInterval`, `intervalMs`, optional `burst`, and a `scope`
of `per-credential`, `per-instance`, or `global`.

Operator obligations:

- **Honour the declared policy.** Do not raise `requestsPerInterval`,
  shorten `intervalMs`, or remove `scope` to "go faster". Provider terms
  override convenience.
- **Strict community quotas.** AISHub is documented at one request per minute per member username (`config/provider-catalog.example.json` `aishub.cost.quotaNote`); the eventual adapter must keep this throttle exactly. Live-test runs that violate the quota are not allowed.
- **Fixture provider has no effective rate limit.** The fixture
  provider returns `requestsPerInterval: Number.MAX_SAFE_INTEGER` only
  so routing parity holds; nothing real is being called.
- **Quota state surfaces through `provider_status`.** The
  `ProviderStatus.quota.state` enum
  (`not_applicable | unknown | available | limited | exhausted`) is the
  read-only signal MCP clients see. Do not invent quota numbers in
  logs.
- **Backoff is the limiter's job.** When `RateLimiter.consume()`
  returns `allowed: false`, respect `retryAfterMs` — do not retry
  immediately.

## Live-test toggles

Default verification (`npm run lint && npm test && npm run build`) must
not call paid or live providers. Each catalog entry declares its
opt-in flags so operators can enable a single provider explicitly:

- **`liveTest.enabledFlagEnvVar`** — every provider has an opt-in
  flag named `VESSEL_MCP_LIVE_TEST_<PROVIDER>` (validator in
  `src/providers/catalog.ts` enforces the prefix).
- **`liveTest.requiredEnvVars`** — the BYOK env vars that must also be
  set; if any of them are missing the live test must be skipped, not
  failed.
- **`liveTest.defaultDisabled: true`** — every catalog entry must
  declare this. Without it the catalog parser rejects the entry, so
  the project cannot ship a provider that is on by default.

Operator workflow to run a single provider live (only when you have
explicit authorization for that provider and account):

```sh
export VESSEL_MCP_LIVE_TEST_MARINETRAFFIC=1
export VESSEL_MCP_PROFILE_MARINETRAFFIC__API_KEY=<your key>
npm test -- --test-name-pattern='live'   # only if/when live tests are added
```

If either the enable flag or any `requiredEnvVars` value is missing the
live test must skip; default `npm test` runs must continue to pass
without any of these variables set. Never paste keys into shell
history that is checked into version control; prefer a sourced shell
file under `~/.config/` or an OS keychain.

## Client setup

### Local stdio (Claude Desktop, Claude Code)

`vessel-traffic-mcp` is published as the `@tools-mcp/vessel-traffic-mcp`
package and exposes the `vessel-traffic-mcp` binary. After
`npm ci && npm run build`, register the local build with
your MCP client:

- **Claude Desktop / Claude Code**: configure an MCP server entry that
  runs the package binary with `VESSEL_MCP_TRANSPORT=stdio`. The
  binary must not write logs to stdout (stdout is the MCP protocol
  stream); only short, redacted stderr is allowed.
- **Generic MCP Inspector**: run

  ```sh
  npx @modelcontextprotocol/inspector node dist/index.js
  ```

  and list the `provider_status`, `data_sources`,
  `credential_profiles`, and `provider_onboarding` tools.

Reference: `docs/runbooks/stdio-fixture-server.md`.

### Remote Streamable HTTP (ChatGPT remote MCP, hosted Claude)

The Streamable HTTP transport binds to `127.0.0.1:3000` by default and
exposes:

- `GET /health`, `HEAD /health` — public, no bearer required.
- `POST /mcp`, `GET /mcp`, `DELETE /mcp`, `OPTIONS /mcp` — Streamable
  HTTP MCP. Requires `Authorization: Bearer <token>` when
  `VESSEL_MCP_AUTH_TOKEN` is non-empty.

Recommended local environment:

```sh
VESSEL_MCP_TRANSPORT=http
VESSEL_MCP_HTTP_HOST=127.0.0.1
VESSEL_MCP_HTTP_PORT=3000
VESSEL_MCP_AUTH_TOKEN=<rotate per client>
```

Start with `npm run start:http` (or `scripts/run-http-server.sh`). Bind
to `0.0.0.0` only behind a trusted HTTPS reverse proxy that terminates
TLS. Every response carries an `X-Request-Id` header (UUID v4) for
log correlation; request logs go to stderr as JSON and never include
headers, request bodies, bearer tokens, provider query credentials, or
raw provider responses.

Reference: `docs/runbooks/streamable-http-server.md`.

### Read-only contract for every client

Whichever transport you wire up, the tools registered on this server
are read-only and must remain read-only:

- `provider_status` and `data_sources` — fixture-backed diagnostics.
- `credential_profiles` — labels-only profile summary; never raw
  secrets.
- `provider_onboarding` — provider signup/API-doc URLs, required env
  vars, configured status, and manual validation steps. It never
  creates accounts, accepts terms, solves CAPTCHA, completes email
  verification, sets payment details, or issues API keys.

When live providers are added later, they must continue to honour the
read-only contract: no fleet edits, no saved-search mutations, no
account changes.

## Verifying this runbook

Run from the project root:

```sh
npm run lint
npm test
npm run build
```

The deterministic test `test/operator-runbook.test.js` asserts:

- this runbook covers all four required surfaces (credentials, rate
  limits, live-test toggles, client setup) and the read-only / no-paid
  defaults;
- the live-test cheat-sheet examples match the catalog
  (`config/provider-catalog.example.json`) for at least one BYOK
  provider — no stale provider IDs or env-var names;
- the runbook does not contain literal credential-shaped strings (JWT,
  AWS access key, `ghp_`, `sk-`);
- the README links to this runbook so operators can discover it.

Default verification does not call any paid or live vessel-data
provider; everything above is checked from local file contents only.
