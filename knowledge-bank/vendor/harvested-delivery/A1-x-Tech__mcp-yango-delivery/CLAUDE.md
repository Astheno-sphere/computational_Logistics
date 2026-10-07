# CLAUDE.md — mcp-yango-delivery

MCP server for the Yango Delivery B2B API (TypeScript, stdio) — the
international brand of Yandex Delivery. A **write API**: tools create, accept
and cancel real deliveries. Only the express (claims) contour exists in the
international docs: `b2b.taxi.yandex.net`, `POST/GET /b2b/cargo/integration/v2/*`.
Auth is `Authorization: Bearer <YANGO_DELIVERY_TOKEN>` from the delivery cabinet
(Integration tab → "Get token"). The Russia-only `offers/calculate` method and
the platform (NDD / pickup-point) contour are deliberately excluded.
`raw_request` is the escape hatch for endpoints without a dedicated tool.

## Commands

```bash
npm run dev        # run from source (tsx watch)
npm test           # unit tests + dist smoke (incl. a real MCP handshake), no network
npm run typecheck  # types for src + tests
npm run build      # emit dist/
npm run smoke      # live READ-ONLY call (claims/search limit 1; needs YANGO_DELIVERY_TOKEN)
```

## Architecture

- `src/config.ts` — env → config. A missing `YANGO_DELIVERY_TOKEN` is NOT an error: the
  field stays `undefined`, the server starts degraded and the client raises
  `CredentialsError` (lives in `types.ts`) at call time. `ConfigError` (with a `reason`
  code) is reserved for malformed values, caught by `loadConfigOrDegraded` in `index.ts`
  (no such checks exist today). Optional: `YANGO_DELIVERY_BASE_URL`,
  `YANGO_DELIVERY_LANG` (default `en`), `YANGO_DELIVERY_TIMEOUT_MS`,
  `YANGO_DELIVERY_MAX_RETRIES`.
- `src/client.ts` — all HTTP. `request(method, path, {query, body, idempotent})` first
  rejects a missing token with `CredentialsError` (before building the request, the
  retries and fetch — the message is the product: it names the env variable to set and
  the needed restart), then builds the query string, sends `Authorization: Bearer` +
  `Accept-Language`, rejects paths that resolve to a foreign origin (SSRF guard),
  enforces an AbortController timeout that also covers reading the body, retries with
  backoff (honors `Retry-After`) and throws `DeliveryError(status, body)`. One typed
  method per endpoint; `claims/create` mints a UUID `request_id` (query param) when the
  caller omits one.
- `src/tools/claims.ts` — the seven claim-lifecycle tools; `src/tools/tracking.ts` —
  the five tracking/contact tools; `src/tools/raw.ts` — `raw_request` (path + query +
  body). `src/tools/util.ts` — `ok`/`fail`, the `READ_ONLY`/`WRITE`/`DESTRUCTIVE`
  annotation presets and shared zod schema factories.
- `src/index.ts` — wires every `register*` into the McpServer. `loadConfigOrDegraded`
  starts the server even on a config problem; without a token the initialize
  `instructions` open with the unconfigured prefix (set `YANGO_DELIVERY_TOKEN` and
  restart).
- `src/telemetry.ts` — anonymous usage pings (ids/names/versions only, never data or
  arguments; fire-and-forget, must never block or throw; opt-out `ASKADS_TELEMETRY=0`).
  `server_start` means "a usable install started"; an install without a token sends
  `unconfigured_start` instead. The `reason` is a closed vocabulary (`missing_token`) —
  never a variable's name or value. `startup_failed` remains for a config unusable at
  load time (malformed values), also fire-and-forget.

## Conventions (do not break)

- **Never exit because of configuration.** A server that dies before the MCP handshake
  leaves the user with a dead server and no reason — the sibling Metrica server's
  telemetry showed that state accounted for nearly every unconfigured install. A missing
  token is a survivable state: start, answer `initialize`/`tools/list` (with the
  unconfigured prefix in the instructions), and reject tool calls with
  `CredentialsError`. There are no login tools: the token comes only from the
  environment, so the fix is the operator setting `YANGO_DELIVERY_TOKEN` and restarting
  the server. `config.test.ts`, `client.test.ts` and `test/dist-smoke.test.js` pin this.
- **Credential failures are not transport failures.** `CredentialsError` is thrown
  before the retry/backoff branch (and before fetch) in `request()` — retrying it burns
  seconds of backoff before the user sees the one message that helps. Pinned by a
  "fetch must not be called" assertion in `client.test.ts`.
- **This is a write API — gate the retries.** 429 is always retried; 5xx and network
  errors are retried ONLY when `idempotent` is set (GETs, side-effect-free POST reads,
  and claims/create thanks to its `request_id` token). Never mark `claims/accept` or
  `claims/cancel` idempotent: a 502 after the write commits would duplicate the write.
- **Annotations are per-tool, not global.** Reads carry `READ_ONLY`, state-changing
  calls `WRITE`, `cancel_claim` and `raw_request` `DESTRUCTIVE` — all four hints set
  explicitly. `annotations.test.ts` pins the full map; extend it with every new tool.
- **Wire mapping lives in the client, not the tools.** Tools never know the host, the
  token or whether a parameter rides in the query or the body — that mapping (incl.
  `claim_id` as a query param vs body field and `request_id` injection) is `client.ts`'s
  job. Note the API's mixed contract: `claims/info`/`points-eta` take `claim_id` in the
  query, `driver-voiceforwarding`/`claims/confirmation_code` take it in the body.
- **Validate inputs with zod** in `inputSchema`; all user-facing text (tool
  descriptions, errors, docs) is in English. Use the shared schema **factories** in
  `util.ts` (a fresh schema per field avoids `$ref` dedup in the JSON schema). Keep
  nested objects `.passthrough()` — the spec has known gaps and the API evolves.
- **Output compact JSON via `ok`** — the consumer is an LLM; pretty-printing burns
  tokens. Responses pass through verbatim (describe the fields in the tool
  `description`, the only place the external model reads).
- **Money is decimal strings** (`"350.00"` + ISO 4217 currency), dimensions are meters,
  weights are kilograms. Don't "fix" any of it.
- **Errors come in two shapes:** non-2xx `{code, message}` AND an `error_messages`
  array inside 200 responses of claims/info and claims/create. Both must keep reaching
  the caller.
- **Do not add Russia-only endpoints** (`offers/calculate`, `api/b2b/platform/*`) —
  they are absent from the international docs on purpose.

## Adding a tool

Before changing the tool registry, read [the MCP capability documentation contract](docs/CAPABILITY-DOCUMENTATION.md). Every registered tool must have exactly one task-oriented page in `docs/capabilities/`; update that page, the index, and the coverage test in the same change.

1. Add (or extend) `src/tools/<module>.ts` with the `server.registerTool` call.
2. If it hits a new endpoint, add a typed method to `src/client.ts` — decide its
   `idempotent` flag consciously (see Conventions).
3. Import and call the register fn in `src/index.ts` (new modules only).
4. Add it to the `EXPECTED` annotations map in `annotations.test.ts`, to the tool lists
   in `claims.test.ts`/`tracking.test.ts` and `test/dist-smoke.test.js`, and to
   `docs/TOOLS.md`.
5. `npm run typecheck && npm test`.

## Releasing

Full walkthrough (incl. the MCP registry and its pitfalls): `docs/PUBLISHING.md`.

1. Bump `version` in **three places, byte-identical**: `package.json`,
   `server.json` (root) and `server.json` `packages[0]`; update `CHANGELOG.md`
   (move `[Unreleased]` into a dated section). Check: `grep -n '"version"' package.json server.json`.
2. `npm publish` (runs typecheck + tests + build via `prepublishOnly` / `prepare`).
3. `git commit`, `git tag -a vX.Y.Z -m vX.Y.Z`, `git push origin main --follow-tags`.
4. GitHub Release: `gh release create vX.Y.Z --title vX.Y.Z --generate-notes --verify-tag`.
5. MCP registry: `mcp-publisher logout && mcp-publisher login github --token "$(gh auth token)" && mcp-publisher publish`.
