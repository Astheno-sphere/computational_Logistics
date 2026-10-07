# CLAUDE.md — mcp-yandex-dostavka

MCP server for the Yandex Delivery B2B API (TypeScript, stdio). A **write API**:
tools create, accept and cancel real deliveries. Two independent contours behind
one server: **express** (same-day claims — `b2b.taxi.yandex.net`,
`POST/GET /b2b/cargo/integration/v2/*`) and **platform** (NDD / pickup points —
`b2b-authproxy.taxi.yandex.net`, `/api/b2b/platform/*`). Auth on both is
`Authorization: Bearer <token>` from the dostavka.yandex.ru cabinet; the shared
`YANDEX_DELIVERY_TOKEN` can be overridden per contour. `raw_request` is the
escape hatch for the ~30 endpoints without a dedicated tool.

## Commands

```bash
npm run dev        # run from source (tsx watch)
npm test           # unit tests + dist smoke (incl. a real MCP handshake), no network
npm run typecheck  # types for src + tests
npm run build      # emit dist/
npm run smoke      # live READ-ONLY call (claims/search limit 1; needs YANDEX_DELIVERY_TOKEN)
```

## Architecture

- `src/config.ts` — env → config. Tokens: `YANDEX_DELIVERY_TOKEN` fills both contours,
  `YANDEX_DELIVERY_EXPRESS_TOKEN` / `YANDEX_DELIVERY_PLATFORM_TOKEN` override it. A missing
  token is NOT an error: the field stays `undefined` (an empty string reads as absent), the
  server starts degraded and the client raises `CredentialsError` (lives in `types.ts`) when
  a call needs that contour. `ConfigError` (with a `reason` code) is reserved for malformed
  values, caught by `loadConfigOrDegraded` in `index.ts` (no such checks exist today).
  Optional: `*_BASE_URL` per contour (platform test contour: `b2b.taxi.tst.yandex.net`),
  `YANDEX_DELIVERY_LANG`, `YANDEX_DELIVERY_TIMEOUT_MS`, `YANDEX_DELIVERY_MAX_RETRIES`.
- `src/client.ts` — all HTTP. `request(contour, method, path, {query, body, idempotent})`
  picks the base + Bearer token by contour (a bare contour throws `CredentialsError` right
  there — before the request is built, retried or sent; the message opens with the historical
  startup text verbatim and ends with the env-and-restart fix), builds the query string,
  sends `Accept-Language`, rejects paths that resolve to a foreign origin (SSRF guard),
  enforces an AbortController timeout that also covers reading the body, retries with
  backoff (honors `Retry-After`) and throws `DeliveryError(status, body)`. One typed
  method per endpoint; `claims/create` mints a UUID `request_id` (query param) when the
  caller omits one.
- `src/tools/express.ts` — the nine `express_*` tools; `src/tools/platform.ts` — the six
  `platform_*` tools; `src/tools/raw.ts` — `raw_request` (contour + path + query + body).
  `src/tools/util.ts` — `ok`/`fail`, the `READ_ONLY`/`WRITE`/`DESTRUCTIVE` annotation
  presets and shared zod schema factories.
- `src/index.ts` — wires every `register*` into the McpServer. `loadConfigOrDegraded()`
  catches `ConfigError`, pings `startup_failed` (fire-and-forget) and degrades the config to
  "no tokens"; a start with a missing token prepends the per-contour unconfigured prefix —
  plus `Проблема конфигурации: <message>` when a ConfigError was caught — to the initialize
  `instructions`, and `oninitialized` sends `server_start` for a fully configured install or
  `unconfigured_start` otherwise (reason in the old check order: with both contours bare it
  is `missing_token`, never a contour-specific code).
- `src/telemetry.ts` — anonymous usage pings (ids/names/versions only, never data or
  arguments; fire-and-forget, must never block or throw; opt-out `ASKADS_TELEMETRY=0`).
  `server_start` means "a usable install started"; an install missing a token sends
  `unconfigured_start` instead, and `startup_failed` remains for a config unusable at load
  time (malformed values). Every `reason` is a closed vocabulary (`missing_token`,
  `missing_express_token`, `missing_platform_token`) — never a variable's name or value.

## Conventions (do not break)

- **Never exit because of configuration.** A server that dies before the MCP handshake
  leaves the user with a red cross and no reason — telemetry across this line of servers
  showed that state accounted for nearly every unconfigured install, and almost none of them
  recovered. A missing token is a survivable state: start, answer `initialize`/`tools/list`
  (with the unconfigured prefix in the instructions), and let the call fail with
  `CredentialsError` — per contour, so a half-configured server keeps serving the contour it
  has a token for. There are no login tools: tokens come only from the environment, so the
  fix is the operator setting the variables and restarting the server. `config.test.ts`,
  `client.test.ts` and `test/dist-smoke.test.js` pin this.
- **Credential failures are not transport failures.** `CredentialsError` is thrown where
  `request()` selects the contour's Bearer token — before the request is built, the
  retry/backoff branch and fetch: retrying it burns seconds of backoff before the user sees
  the one message that helps. Pinned by "fetch must not be called" assertions in
  `client.test.ts`.
- **This is a write API — gate the retries.** 429 is always retried; 5xx and network
  errors are retried ONLY when `idempotent` is set (GETs, side-effect-free POST reads,
  and claims/create thanks to its `request_id` token). Never mark `claims/accept`,
  `claims/cancel`, `offers/confirm` or `request/cancel` idempotent: a 502 after the
  write commits would duplicate the write.
- **Annotations are per-tool, not global.** Reads carry `READ_ONLY`, state-changing
  calls `WRITE`, cancellations and `raw_request` `DESTRUCTIVE` — all four hints set
  explicitly. `annotations.test.ts` pins the full map; extend it with every new tool.
- **Contour routing lives in the client, not the tools.** Tools never know hosts,
  tokens or whether a parameter rides in the query or the body — that mapping (incl.
  `claim_id` as a query param and `request_id` injection) is `client.ts`'s job.
- **Validate inputs with zod** in `inputSchema`; tool descriptions are in Russian (the
  audience is a Russian-speaking operator's LLM). Use the shared schema **factories**
  in `util.ts` (a fresh schema per field avoids `$ref` dedup in the JSON schema). Keep
  nested objects `.passthrough()` — the spec has known gaps and the API evolves.
- **Output compact JSON via `ok`** — the consumer is an LLM; pretty-printing burns
  tokens. Responses pass through verbatim (describe the fields in the tool
  `description`, the only place the external model reads).
- **Express money is decimal strings, platform money is integer kopecks.** Express
  dimensions are meters/kg, platform dimensions are cm/grams. Don't "fix" either.
- **Express errors come in two shapes:** non-2xx `{code, message}` AND an
  `error_messages` array inside 200 responses of claims/info. Both must keep reaching
  the caller.

## Adding a tool

Before adding or materially changing a public tool, read
`docs/a1-mcp-capability-documentation-contract.md` in full. It owns the
human-facing page structure, the private NMT-to-public-language boundary and the
state-change wording for `docs/capabilities/`.

1. Add (or extend) `src/tools/<contour>.ts` with the `server.registerTool` call.
2. If it hits a new endpoint, add a typed method to `src/client.ts` — decide its
   `idempotent` flag consciously (see Conventions).
3. Import and call the register fn in `src/index.ts` (new modules only).
4. Add it to the `EXPECTED` annotations map in `annotations.test.ts`, to the tool lists
   in `express.test.ts`/`platform.test.ts` and `test/dist-smoke.test.js`, to
   `docs/TOOLS.md`, and to `docs/capabilities/`.
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
