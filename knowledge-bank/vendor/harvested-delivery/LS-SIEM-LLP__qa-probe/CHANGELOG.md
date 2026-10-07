# Changelog

All notable changes to qa-probe are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).  
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed

- Fixed the `npm test` command so it runs the full `src/**/*.test.js` suite
  instead of only the top-level `src` directory.
- Expanded GitHub Actions coverage to Node 18/20/22 across Linux, Windows, and
  macOS, and added an `npm pack --dry-run` packaging check.
- Added clearer public README guidance for first-time users, starter configs,
  limitations, and trademark/branding expectations.
- Hardened `fix --apply` so generated patches cannot write outside the project
  root.
- Updated npm dependency locks to resolve all current production audit findings.

---

## [2.12.1] - 2026-06-21

### Fixed — config keys for new features were being stripped (features dead via config file)

The config loader validates with a Zod schema that **strips unknown keys**, and the schema was missing every recently-added option. So `security`, `assertions`, `writeFlows`, `openApiFile`, `analyze.har`, and the probe/scoring/report tuning keys were silently dropped — the opt-in features only worked in unit tests, not from a real `qa-probe.config.js`. (Caught by a live run against a real app where `security: { enabled: true }` never executed.)

- Added schemas for top-level `security` (auth-bypass / privilege-escalation / PII, with `personas` + `policies` + `piiAllow`), `assertions`, `writeFlows`, `openApiFile`, `feedbackFile`, `analyze.har`, `probe.{idDiscovery,hardTimeoutMs,maxProbeMs,maxResponseBytes}`, `report.baselineRuns`, and `scoring.{securityIssue,assertionFailed,preconditionGate,unknown}`.
- Added a regression test pinning the full opt-in config surface so a feature can never again be silently stripped.

---

## [2.12.0] - 2026-06-21

### Added — Close the last two coverage gaps

- **HAR import** for dynamic frontends. Point qa-probe at a captured `.har` file (`analyze.har.enabled` + `harFile`) and it derives the call map from real observed requests — for GraphQL/tRPC/generated-SDK/custom-service-layer frontends that static parsing misses. Feeds the same `runtimeCalls` path as CDP tracing; static AST + runtime capture together give near-complete coverage.
- **OpenAPI spec auto-discovery + local file.** `fetchSpec` now tries common fallback paths (`/swagger.json`, `/v3/api-docs`, `/api-docs`, ...) when the configured URL 404s, and supports loading the spec from a local file via `openApiFile` — so far fewer apps fall into headless mode. (Headless already gets observed-shape drift detection via schema-history.)

---

## [2.11.0] - 2026-06-21

### Added — Render the new signals in the human + AI reports

Everything the recent releases produced lived only in `report.json` / MCP; the markdown and ai-context reports now surface it.

- **Markdown report:** a `Confidence` column on the diagnostics table; a security-findings / baselines / feedback / write-flows line in the Run Snapshot; and new **Feedback Applied** and **Write-Flows** sections.
- **ai-context report:** baselines / feedback / write-flows / security signals, plus an explicit note that `confidence: none` / `unknown` means UNVERIFIED (not a pass).

---

## [2.10.0] - 2026-06-21

### Added — Write-flow (CRUD-chain) testing (opt-in, mutating)

Exercises real create → read → update → delete chains to catch write-path and logic bugs a read-only smoke probe can't. **OFF by default — it mutates data.**

- New `writeFlows` config: `enabled` plus an explicit list of `flows`. Each flow defines `create` / `read` / `update` / `delete` steps; the created id is threaded into `{id}` placeholders.
- **Safety:** nothing is auto-discovered or auto-mutated — every flow is hand-defined. Every created resource is **deleted at the end of its flow, even if an earlier step fails or throws**, and the delete is verified. A loud warning prints when the pass runs. Intended for a disposable / test-tenant environment.
- Per-flow pass/fail + cleanup status surface in the report's `writeFlows` block.

---

## [2.9.0] - 2026-06-21

### Added — ID chaining (kills unseeded-DB noise)

Detail routes were probed with a guessed id (`/cases/1`), which 404s on an unseeded database and produced most of the `sample_not_found` / `invalid_sample_params` noise. qa-probe now discovers real ids.

- The HTTP probe runs in two phases: param-less **collections** first, then **detail routes**. A real id is harvested from each collection response and used for the matching detail route (`/cases/{id}` → `/cases/<real id>`).
- Pure read, **no extra requests** (collections are already in the probe set). Falls back to `pathParamValues` when nothing is discovered.
- On by default; disable with `probe.idDiscovery: false`. The run summary reports how many detail routes used a discovered id.

---

## [2.8.0] - 2026-06-21

### Added — Read-only response assertions (catch logic bugs)

A smoke probe checks that an endpoint responds; assertions check that the response is *correct*. Declare invariants per endpoint and qa-probe verifies them on every 2xx response — catching enum drift, bad counts, broken pagination, and missing/renamed fields. Purely inspects the response body; **no writes.**

- New `assertions` config keyed by `"METHOD path"`. Checks: `present`, `type`, `in`, `pattern`, `gte`/`lte`/`gt`/`lt`, `nonEmpty`, `minItems`/`maxItems`. Field paths support dot notation and array wildcards (`items[].user.id`).
- Violations classify as `assertion_failed` (high confidence, high severity, `scoring.assertionFailed` default −30) with the exact field + value that failed.

---

## [2.7.0] - 2026-06-21

### Added — Security checks (auth-bypass, privilege escalation, PII)

qa-probe knows every endpoint your app calls, so it can now verify *access*, not just data. Opt in with a `security: { enabled: true }` config block. Previously-written but unwired persona/security modules are now connected to the probe pipeline.

- **`auth_bypass`** (zero config) — re-probes every authed-`200` GET with no credentials; a still-`200` response means the endpoint is missing its auth guard.
- **`privilege_escalation`** — runs a per-persona access matrix and flags any role that reached a route your `policies` forbid.
- **`pii_leak`** — scans response bodies for SSN / credit-card / phone / email patterns not on `piiAllow`.
- All security re-probing is **GET-only — it never issues a write.**
- Findings surface as high-severity diagnostics, penalize the score (`scoring.securityIssue`, default −50), and carry calibrated confidence (auth_bypass / privilege_escalation = high; pii_leak = medium).

---

## [2.6.0] - 2026-06-21

### Added — Adaptive baselines (deviation-from-itself)

qa-probe now learns each endpoint's normal from recent history and flags this run's deviations — completing the learning loop without any model.

- **Baseline anomaly detection wired into the report pipeline.** Latency and row-count (cardinality) baselines are computed from recent runs; an endpoint that deviates >3σ from its own history is flagged as `anomaly_vs_baseline`.
- **`endpointMetrics`** is now recorded for *every* probed endpoint (status, ms, itemCount), so baselines cover healthy endpoints — not just ones that were already failing.
- **Never masks a real failure** — anomalies attach only to otherwise-healthy responses (2xx, non-empty, schema-clean). A `500` keeps `server_error`; an empty result keeps `empty_db`.
- **Honest confidence** — anomalies are `medium` confidence (could be load or a data change, not a confirmed defect). The report gains a `baselines` block (runs analyzed, endpoints with a baseline, anomalies flagged). Tunable via `report.baselineRuns` (default 20).

---

## [2.5.0] - 2026-06-21

### Added — Feedback writeback (first piece of the learning loop)

Humans and AIs can label a diagnosis; qa-probe persists it and reapplies it on future runs, so it improves the more it is used — without any model or black box.

- **`qa-probe label <endpoint> <verdict>`** CLI command and **`qa_probe_label`** MCP tool. Suppress verdicts (`expected`/`ignore`/`known_gate`/`ok`) reclassify a finding as `acknowledged` (a non-issue); confirm verdicts (`bug`/`real_bug`/`confirm`) keep it flagged at high confidence.
- **Honesty guard** — a label can be scoped to a rootCause (`signal`); it auto-revokes if the observed rootCause changes, so a stale "expected" can never hide a regression.
- **Transparent** — the report gains a `feedback` block listing every label applied this run (endpoint, verdict, by, reason). Suppression is never silent.
- Feedback persists in `<output.dir>/feedback.json` (override with `feedbackFile` to commit/share it).

---

## [2.4.0] - 2026-06-21

### Added — Trust contract (provenance + calibrated confidence)

Every result is now verifiable and honest about its certainty, so an AI (or human) consumer never has to trust a label blind. This is the foundation for the upcoming feedback/learning loop.

- **`evidence` on every probe result and diagnostic** — the request issued plus a bounded snapshot of what the server actually returned (status, content-type, body type, item count, truncated body sample, timing). Request auth headers are never captured.
- **Calibrated `confidence`** — a classifier rule may now set its own confidence; `unknown` is `confidence: none` (no rule matched), no longer a misleading `low`.
- **Self-explaining `unknown`** — an unclassified result now states it is *not a confirmed pass* and points the consumer at the captured evidence, instead of a bare `status=…`.
- **`trust` note in `qa_probe_explain_failure`** — the MCP tool flags when calls are unclassified and instructs the consumer not to report them as passing without checking the evidence. Each call also carries its `rootCause`, `confidence`, and `evidence`.

### Changed

- `unknown` confidence is now `none` instead of `low`.

---

## [2.3.2] - 2026-06-21

### Fixed

- **Probe can no longer hang indefinitely on a streaming/long-poll endpoint.** axios's `timeout` is socket-inactivity based, so a response that keeps trickling data (SSE-over-HTTP, LLM token streams, chunked keep-alive) never tripped it, and because the concurrency runner awaits each batch with `Promise.all`, a single hung request stalled the entire probe. Each request now has a **hard wall-clock abort** (`AbortController`) that fires regardless of socket activity.

### Added

- `probe.hardTimeoutMs` — hard per-request deadline (default `timeoutMs + 2000`). Cancels a request even if it is actively streaming.
- `probe.maxProbeMs` — optional overall run deadline; when set, in-flight requests are aborted and remaining endpoints are recorded as deadline-exceeded.
- `probe.maxResponseBytes` — cap on buffered response size (default 25 MB) so a flooding endpoint can't be read into memory unbounded.
- Hung/aborted requests are reported as the `timeout` root cause (the classifier now also recognizes `deadline`/`canceled`).

---

## [2.3.1] - 2026-06-21

### Added

- New `precondition_required` root cause for HTTP **428 Precondition Required**. Endpoints gated behind a one-time precondition (terms/license acceptance, an onboarding wizard, or MFA enrollment for the probe account) are now diagnosed explicitly instead of falling into the generic `unknown` bucket.
- Scorer now penalizes `precondition_required` (default −30, configurable via `scoring.preconditionGate`) and `unknown` (default −10, configurable via `scoring.unknown`). Previously these deducted nothing, which let large clusters of gated/odd-status endpoints hide behind a near-perfect score.

### Fixed

- Quiet-state QA reporting improvements.
- Parse-cache crash on some real-world frontends.

---

## [2.3.0] - 2026-05-09

### Added

- GraphQL introspection adapter that maps queries and mutations into QA Probe endpoints.
- tRPC router adapter that extracts query, mutation, and subscription procedures from router files.
- Config support for `framework: graphql` and `framework: trpc` with adapter-specific options.

---

## [2.2.0] - 2026-05-09

### Added

- Optional Schemathesis runner configuration for OpenAPI fuzz checks.
- Schemathesis JSON parser that maps failures into `validation_edge_case` findings.
- Root-cause classification for validation edge cases and offending payload hints.

---

## [2.1.0] - 2026-05-09

### Added

- HAR replay support for safe POST request bodies via `postBodyMode: har`.
- Deterministic HAR anonymization for SSN, email, phone, credit card, and UUID values.
- HAR endpoint matching with OpenAPI-style path parameters.

---

## [2.0.0] - 2026-05-09

### Added

- Opt-in LLM-assisted parser repair for analysis-only syntax recovery.
- Disabled, OpenAI, Anthropic, and Ollama provider slots with conservative guardrails.
- Route/API call metadata showing `parsedVia: llm-repair` and the configured provider.

---

## [1.8.0] - 2026-05-08

### Added

- Cross-run baseline computation for latency, response size, and response cardinality.
- Anomaly detection for current probe results outside historical ranges.
- `anomaly_vs_baseline` root-cause classification and historical fix suggestion helper.

---

## [1.7.0] - 2026-05-08

### Added

- Multi-persona probing helpers and role-by-route matrix support.
- Security overlay modules for IDOR checks, PII scanning, and auth-bypass detection.
- Root-cause classifications for `privilege_escalation`, `pii_leak`, and `auth_bypass`.

---

## [1.6.0] - 2026-05-08

### Added

- Optional OpenTelemetry trace correlation with W3C `traceparent` injection.
- Jaeger, Tempo, and Honeycomb trace fetcher modules.
- `slow_app` and `slow_dependency` root-cause classifications for slow successful probes.

---

## [1.5.0] - 2026-05-08

### Added

- `qa-probe fix` command for dry-run remediation diffs and high-confidence apply mode.
- Auto-remediation strategies for contract mismatches, disabled feature flags, and empty data findings.
- Contract mismatch trailing-slash fixes with confidence scoring.

---

## [1.4.0] - 2026-05-08

### Added

- Coverage analytics report generation via `coverage.md`.
- Dead endpoint detection for OpenAPI routes with no frontend references, with configurable ignore globs.
- Dead component and orphaned response-field analytics for frontend/API cleanup.

---

## [1.3.0] - 2026-05-08

### Added

- Opt-in visual probe via `probe.visual.enabled` with viewport and density threshold controls.
- Layout density analysis for rendered text, images, and non-empty containers.
- `data_received_not_rendered` diagnosis for healthy HTTP routes that render as blank or sparse pages.

---

## [1.2.0] - 2026-05-08

### Added

- Opt-in CDP runtime tracing during analyze via `analyze.runtime.enabled`.
- Playwright-backed runtime driver that observes browser network requests and captures DOM snapshots.
- Runtime-discovered API calls merged into `graph.json` with `source: runtime`; duplicate AST/runtime calls are tagged `source: both`.
- Runtime navigation failures are emitted as warnings without aborting analyze.

---

## [1.1.0] - 2026-05-08

### Added

- Self-healing parser warnings, parse-cache fallback, and Markdown parse warning reporting.
- Recursive `React.lazy(() => import(...))` route resolution with cycle/depth protection.
- Zod-backed OpenAPI response validation with type mismatch, missing required field, and field rename classifications.
- Schema history snapshots under `.qaprobe/history/schemas/` with additive vs. breaking drift reporting.
- Stratified safe POST body generation with `empty`, `minimal`, `realistic`, and `example` modes plus per-route overrides.

### Changed

- Safe POST probes now default to minimal schema-derived JSON bodies instead of empty bodies.
- Analyze output now carries parse warnings into `graph.json` and downstream reports.

---

## [1.0.0] — 2026-05-04

Initial public release under Apache 2.0.

### Added

**Phase 1 — Analyze**
- Babel AST parser walks React frontend source (`frontendSrc`) and extracts all API calls:
  - Direct axios/fetch calls: `api.get('/path')`, `axios.post('/path', data)`
  - Custom hook patterns: `useApiData('/path', opts)`, `useApiQuery(['key'], '/path', opts)`
  - Template literals: `` api.get(`/cases/${id}`) `` → normalized to `/cases/{id}`
  - String concatenation: `'/users/' + id` → `/users/{param}`
- React Router v6 route extractor — parses `<Route>`, `<ScopeRoute>`, `<AdminRoute>`, `<PrivateRoute>` elements from `routerFile`; normalizes relative nested paths to absolute
- Backend spec fetcher — OpenAPI 3.0 via `openApiUrl`; optional feature flag status via `featureStatusUrl`
- FastAPI adapter — handles `/openapi.json` + `/health/features` router status endpoint
- Express adapter — handles `/api-docs/swagger.json` or `/swagger.json`
- Generic adapter — any OpenAPI 3.0 / Swagger 2.0 URL
- Graph builder — strips `frontendApiPrefix`, fuzzy-matches frontend calls to backend routes, computes blast radius (how many frontend routes call each backend endpoint)
- Headless mode fallback — when OpenAPI is unavailable, probes frontend-discovered URLs directly with HTTP status reporting only

**Phase 2 — Probe**
- Authenticator — bearer token (body + cookie-mode JWT fallback), API key header, none
- Concurrent HTTP endpoint runner — configurable concurrency, per-request timeout, inter-request delay, `ignoreHTTPSErrors` for self-signed TLS
- Safe POST whitelist — POST endpoints listed in `safePosts` are probed; all other write methods are skipped
- Path parameter sampler — substitutes `{id}`, `{name}`, and other path params from `pathParamValues` config
- SSE checker — opens Server-Sent Event streams, waits for first event within `firstEventTimeoutMs`
- WebSocket checker — performs upgrade handshake, waits for first frame within `firstFrameTimeoutMs`
- Schema validator — compares response field names against the OpenAPI response model for the probed endpoint

**Phase 3 — Report**
- 9-rule root-cause classifier (priority order, first match wins):
  1. `feature_flag_disabled` — 404 at <15ms + path in feature flags with `included: false`
  2. `missing_route` — 404 + not in OpenAPI spec
  3. `contract_mismatch` — 404 + fuzzy match finds a similar route (trailing slash, prefix, casing)
  4. `empty_db` — 200 + empty array or empty body
  5. `auth_scope_mismatch` — 401 or 403
  6. `schema_mismatch` — 200 + data present + response field names differ from spec
  7. `stream_dead` — SSE/WS connected but no events delivered within timeout
  8. `server_error` — 5xx response
  9. `slow_but_working` — 200 but response time exceeds 80% of configured timeout
- Cluster pass — groups 5+ failures sharing the same path prefix and root cause into one diagnosis
- Route scorer — computes a 0–100 score for each frontend route from the probe results; configurable penalty weights per root cause category
- Blast radius reporter — lists which frontend routes are affected by each backend endpoint failure
- Regression detector — diffs current run against `.qaprobe/history/`; reports newly broken and newly fixed endpoints
- Three output formatters:
  - `report.json` — machine-readable full report
  - `report.md` — human-readable Markdown with score table
  - `ai-context.md` — compact summary optimized for LLM context windows

**MCP Server**
- Stdio MCP server (`qa-probe mcp`) using `@modelcontextprotocol/sdk`
- 7 tools: `qa_probe_get_graph`, `qa_probe_get_report`, `qa_probe_probe_endpoint`, `qa_probe_explain_failure`, `qa_probe_suggest_fix`, `qa_probe_get_blast_radius`, `qa_probe_run_analysis`
- `.mcp.json` integration — Claude Code and Cursor pick up the server automatically

**CLI**
- `qa-probe analyze` — Phase 1 only
- `qa-probe probe` — Phase 2 only (requires graph from analyze)
- `qa-probe report [--fail-under N]` — Phase 3 only; exits 1 if overall score < N (CI gate)
- `qa-probe run [--fail-under N]` — All three phases in sequence
- `qa-probe mcp` — MCP server over stdio
- `--config <path>` flag on all commands

**Config**
- Zod-validated config schema with clear error messages for invalid values
- `qa-probe.config.js` convention — loaded from the working directory by default
- Environment variable support for credentials (`QA_USER`, `QA_PASS`, `QA_API_KEY`)

**Examples**
- `examples/fastapi-react/` — fully annotated FastAPI + React example
- `examples/express-app/` — Express + React minimal example

---

[1.0.0]: https://github.com/LS-SIEM-LLP/qa-probe/releases/tag/v1.0.0
