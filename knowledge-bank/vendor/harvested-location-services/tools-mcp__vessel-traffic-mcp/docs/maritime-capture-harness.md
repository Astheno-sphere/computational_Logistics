# Maritime capture harness design (F5.AC4)

This document is the architecture-level synthesis for the maritime
capture harness. It maps the seven `<api-capture-checkout>`
patterns required by `F5.AC4` (site profiles, Playwright capture, HAR
backup, replay validation, traffic IR, supervisor pacing, redaction
worker) onto the modules that already exist in this repository, so a
reviewer can audit how each pattern is implemented and what the safety
boundaries are.

It does **not** restate per-CLI usage — those live in the runbooks
linked below. It does **not** define the `api-capture` reference-only
boundary either; that contract is owned by `F5.AC5` and lives in
`docs/runbooks/api-capture-reference-only.md`.

## 1. Sources and scope

- Reference (read-only architecture): `<api-capture-checkout>/README.md`,
  `<api-capture-checkout>/ARCHITECTURE.md`,
  `<api-capture-checkout>/docs/LOCAL_AGENT_HARNESS.md`.
- Project authority docs: `docs/PRD.md` §6.6 and §7.1, `docs/TDD.md`
  §9, `AGENTS.md` "Implementation Preferences".
- Implementation surface: `src/capture/` plus the runbooks under
  `docs/runbooks/capture-*`.

The harness is operator-only. Default verification
(`npm run lint && npm test && npm run build`) never calls a live or
paid provider; the live Playwright driver is gated behind
`VESSEL_CAPTURE_LIVE=1` and `--i-am-authorized` in
`src/capture/workflow.ts` (`gateRunner`).

## 2. Worker / module separation

`api-capture` separates exploration into capture, replay, schema,
redaction, and report workers under a supervisor loop. This project
keeps the same role split but realizes it as composable TypeScript
modules driven by a single CLI runner. The intent is that each role
remains testable in isolation:

| api-capture role  | This project's module                   | Role                                                                            |
| ----------------- | --------------------------------------- | ------------------------------------------------------------------------------- |
| Site profile      | `src/capture/site-profile.ts`           | Validate origins, forbidden actions, session-loss indicators, pacing policy.    |
| Capture worker    | `src/capture/recorder.ts`               | Mock or Playwright recorder driver that produces `RecordedExchange[]`.          |
| HAR backup        | `src/capture/har-writer.ts`             | Convert exchanges to HAR 1.2 and write under `captures/raw/` (gitignored).      |
| Redaction worker  | `src/capture/redact.ts`, `import.ts`    | Strip credential headers, cookies, query params, body fields, token patterns.  |
| Schema / IR       | `src/capture/schema.ts`, `traffic-ir.ts`, `fingerprint.ts` | Build endpoint fingerprints, schema summaries, and traffic IR. |
| Replay validator  | `src/capture/replay-validator.ts`       | Structural diff between two IRs (identical / added / removed / changed).        |
| Supervisor        | `src/capture/workflow.ts`               | Compose the loop, enforce gates, apply pacing caps, persist sanitized output.   |
| Operator entry    | `src/capture/runner-cli.ts`             | `vessel-capture-runner` CLI. Mock by default; live Playwright is double-gated.  |

The capture queue (`src/capture/capture-queue.ts`) plus the catalog
example files (`config/capture-sites.example.json`,
`config/capture-queue.example.json`) carry F5A.AC1's site-profile
inventory; this design doc only describes how the runtime *consumes*
those profiles.

## 3. Component-by-component mapping (F5.AC4 checklist)

### 3.1 Site profiles

- Type: `SiteProfile` (`src/capture/site-profile.ts`) with
  `SITE_PROFILE_FORMAT_VERSION = 1`.
- Required fields: `id`, `displayName`, `termsReviewStatus`
  (`allowed | needs-terms-review | blocked`), `baseUrl`,
  `allowedOrigins`, `forbiddenActions`, `sessionLossIndicators`,
  `pacing` (see §3.6), `notes`.
- Enforcement entry points:
  - `validateSiteProfile()` rejects malformed profiles before any
    network call.
  - `assertOriginAllowed()` and `assertActionAllowed()` are called for
    every `goto` step in `runCaptureWorkflow()` (see
    `src/capture/workflow.ts:163-168`) so a typo cannot reach an
    off-profile origin or hit a forbidden destructive endpoint.
- Inventory: committed site-profile examples live in
  `config/capture-sites.example.json`; the deterministic test
  `test/capture-sites-queue.test.js` requires entries for at least
  MarineTraffic, VesselFinder, MyShipTracking, FleetMon.

This is the project's analogue of `api-capture`'s `config/sites/*`
profiles. The "destructive action / account management blocked" rule
from `LOCAL_AGENT_HARNESS.md` is the `forbiddenActions` list; the
"`/cm/lgn` redirect = session loss" heuristic is one of the supported
`sessionLossIndicators` (`url-redirect`, `status-code`,
`response-header`, `response-body`).

### 3.2 Playwright capture

- Interface: `RecorderDriver` and `RecorderSession`
  (`src/capture/recorder.ts`) so every driver returns the same
  `RecordedExchange[]` shape regardless of how it was captured.
- Drivers:
  - `createMockRecorderDriver()` — the default. Pure-JS, deterministic,
    used by `test/capture-workflow.test.js` and the
    `vessel-capture-runner --driver mock` mode.
  - `createPlaywrightRecorderDriver()` — stub on purpose. Playwright is
    *not* a `package.json` dependency. The factory dynamically
    `import('playwright')` only when the operator opts in; if the
    module is absent it throws
    `"playwright is not installed"` (`src/capture/recorder.ts:142-145`).
    The bundled stub then throws
    `"live playwright driver requires an operator-provided implementation"`
    so this build cannot accidentally drive a real browser.
- Gates: `gateRunner()` in `src/capture/workflow.ts` refuses the
  `playwright` driver unless `VESSEL_CAPTURE_LIVE=1` is set,
  `--i-am-authorized` is passed, and the site profile's
  `termsReviewStatus === "allowed"`. All four constraints are
  exercised by `test/capture-workflow.test.js` ("gateRunner blocks
  live driver…").

In `api-capture` terms, the driver interface is the boundary that lets
the local agent harness (deterministic core) stay separate from the
LLM-driven actor. The mock driver replaces the actor for tests; the
Playwright driver is the place where an operator-supplied
implementation would re-attach the real browser when authorized.

### 3.3 HAR backup

- Builder: `recordedExchangesToHar()` (`src/capture/har-writer.ts`)
  produces HAR `version: '1.2'` logs with one `entry` per recorded
  exchange.
- Path safety: `assertHarOutputPath()` requires the raw output
  directory to be absolute *and* under a `captures/raw` segment, and
  the output file to be inside that directory. Relative paths and
  escape attempts are rejected with `HarPathError`.
- Default path: `defaultRawDir(cwd)` resolves to
  `<cwd>/captures/raw/<label>.har`. `captures/raw/` is gitignored at
  the repository level so the unredacted HAR cannot be committed by
  accident.
- Note: the HAR backup is intentionally **raw** — it still contains
  cookies, bearer tokens, and any other session secrets. That is what
  makes it useful for re-replay and re-import. Anything that leaves
  `captures/raw/` must come from §3.5 (sanitized fixture) or §3.6
  (traffic IR), not directly from the HAR.

This is the equivalent of the `network.har` produced by `api-capture`
sessions; the project keeps it on disk for the operator but does not
treat it as a publishable artifact.

### 3.4 Redaction worker

`src/capture/redact.ts` is the single redaction surface for the whole
workflow. The runbook at `docs/runbooks/capture-fixture-import.md`
enumerates the exact tokens — this design doc intentionally does not
duplicate that list so the two cannot drift; refer to
`src/capture/redact.ts` for the authoritative `SENSITIVE_HEADER_NAMES`,
`SENSITIVE_QUERY_PARAM_NAMES`, sensitive body fields, and
value-pattern matchers (JWT, AWS, GitHub PAT, `sk-`-style keys, etc.).

Key properties:

- Same module is reused by the HAR-to-fixture importer
  (`src/capture/import.ts`), the traffic-IR builder
  (`src/capture/traffic-ir.ts`), and the workflow runner
  (`src/capture/workflow.ts`). There is no second copy of the redaction
  list.
- `REDACTED_PLACEHOLDER = '[REDACTED]'` is the only allowed substitute
  for credential-bearing material. The traffic IR and replay validator
  treat surviving placeholders as a distinct schema kind
  (`{ "kind": "redacted" }`) so downstream tooling cannot mistake them
  for real values.
- Defense in depth: after the IR is rendered to text, the AC1
  token-pattern scrubber re-runs over the serialized output and adds a
  warning if anything that looks like a secret slipped through.
- Verified by: `test/capture-workflow.test.js` (`assertNoSecrets` over
  sanitized fixture and IR contents), `test/capture-import.test.js`,
  `test/capture-traffic-ir.test.js`.

This is the project's "secret scanner / redactor before any backup,
dashboard export, fixture generation, or commit" listed in PRD §6.6.

### 3.5 Sanitized fixture pipeline (importer)

Although F5.AC1 owns the sanitized-fixture format, the harness design
must record where the sanitized fixture sits in the workflow:

1. The supervisor (`runCaptureWorkflow`) writes the raw HAR (§3.3).
2. It immediately feeds the HAR through `importCapture()` from
   `src/capture/import.ts` to produce a `CaptureFixture` (`version: 1`).
3. The supervisor stamps `provenance.liveReplayDisabled = true`,
   `recorderDriver`, `siteProfileId`, `siteProfileVersion`,
   `capturedAt`. F5.AC3's `CaptureFixtureProvider` refuses to load any
   fixture where `liveReplayDisabled !== true`.
4. The fixture is written to
   `fixtures/captures/<label>.private.json` by default. `--promote`
   drops the `.private` suffix once the operator has reviewed it.
5. Fixture files are written with mode `0o600`.

`fixtureToJson()` and `trafficIRToJson()` provide deterministic
serialization so re-running the same input yields byte-identical
output.

### 3.6 Traffic IR

- Builder: `buildTrafficIR()` (`src/capture/traffic-ir.ts`).
  `TRAFFIC_IR_FORMAT_VERSION = 1`. Input must be a sanitized fixture
  (raw HAR rejected so the IR cannot inherit credentials).
- Endpoint identity: method + origin + path template, with
  parameterized segments collapsed via `breakdownPath()` in
  `src/capture/fingerprint.ts`. Identical sample paths get the same
  endpoint id so endpoint counts are stable across captures.
- Shape only: the IR retains header *names* (with credential headers
  surfaced separately as `redactedHeaderNames`), request cookie
  *count* (no names, no values), status codes, MIME types, and JSON
  schemas produced by `summarizeBody()` (`src/capture/schema.ts`).
- Bounded: `MAX_STATUS_PER_ENDPOINT = 8`; schema summarizer has depth,
  breadth, and union caps so pathological captures cannot blow up the
  output.
- Tooling: `vessel-capture-ir` CLI (`src/capture/ir-cli.ts`) renders
  an IR file from a sanitized fixture; the workflow also writes the IR
  next to the fixture (`<label>.ir.private.json` /
  `<label>.ir.json`).

### 3.7 Replay validation

- Comparator: `compareTrafficIR(baseline, candidate)` in
  `src/capture/replay-validator.ts` returns a
  `ReplayValidationReport` with `identical`, `addedEndpointIds`,
  `removedEndpointIds`, and per-endpoint `changes`. It compares IR
  structure only (id, status set, MIME types, redacted-header set,
  query keys, schema signature) and never compares raw values, since
  both inputs are sanitized.
- Inline use: when `runCaptureWorkflow({ validateReplay: true })` is
  set, the supervisor builds the IR twice from the same fixture and
  asserts the two are identical; a non-deterministic IR becomes a
  workflow warning rather than a silent ship. The mock test
  (`buildTrafficIR built from workflow output round-trips identically`
  in `test/capture-workflow.test.js`) is the deterministic guard.
- Operator use: re-importing a later HAR and running the comparator
  against the stored baseline IR detects endpoint drift (added /
  removed / changed schema) without re-issuing a single network
  request.

This is the analogue of the `api-capture` replay worker, with the key
difference that this project's "replay" is IR-against-IR (no live
session is ever re-issued by default verification).

### 3.8 Supervisor pacing

- Source of truth: `SiteProfile.pacing` (`src/capture/site-profile.ts`)
  carries `minStepIntervalMs`, `maxStepsPerRun`, `maxConcurrent`.
- Validation: `validateSiteProfile()` rejects pacing values that are
  not finite, non-negative, or positive integers.
- Enforcement in the supervisor (`src/capture/workflow.ts`):
  - `maxStepsPerRun` is enforced before the run starts; over-long
    scripts are rejected with a `WorkflowGateError("pacing", …)`.
  - `minStepIntervalMs` is consumed by the live recorder driver
    between operator steps; the mock driver is deterministic and does
    not need real time, but its session contract still surfaces the
    field so the live implementation can honour it.
  - `maxConcurrent` is informational for the current single-run CLI
    and is the constraint a future parallel queue runner must respect.
- Per-site overrides: capture queue entries
  (`src/capture/capture-queue.ts`) can pin a stricter pacing policy
  for a provider that has explicit terms-of-service caps.

This mirrors `api-capture`'s supervisor pacing: deterministic, capped
by the site profile, and refuses to "hammer providers or repeat
low-yield actions" (PRD §6.6).

## 4. Safety invariants the design must preserve

The harness only honours the F5.AC4 requirement if these invariants
hold every time a new capture-related change is reviewed. They are
each backed by code and at least one deterministic test:

- The default driver is `mock`. The live Playwright driver requires
  three concurrent conditions: `VESSEL_CAPTURE_LIVE=1`, operator
  `--i-am-authorized`, and `termsReviewStatus === "allowed"`. Verified
  by `test/capture-workflow.test.js` (`gateRunner blocks live
  driver…`).
- Steps that target an off-profile origin or a forbidden action are
  refused before they reach the driver. Verified by
  `test/capture-workflow.test.js` (`refuses steps that target
  disallowed origins`, `refuses forbidden destructive actions`).
- A session-loss indicator aborts the workflow with
  `WorkflowAbortedError`. Verified by `test/capture-workflow.test.js`
  (`aborts when a session-loss indicator triggers`).
- Off-profile exchanges captured by a noisy driver (third-party
  trackers, CDNs) are dropped with a warning rather than persisted.
  Verified by `test/capture-workflow.test.js` (`drops exchanges with
  origins outside the profile`).
- Sanitized fixtures and IRs never contain any of the secrets that
  appear in the raw HAR. Verified by `assertNoSecrets()` over the
  on-disk artifacts in `test/capture-workflow.test.js`.
- `provenance.liveReplayDisabled === true` is stamped on every
  sanitized fixture the workflow emits, including after `--promote`.
  Verified by the same test (`runCaptureWorkflow promote=true…`).
- `captures/raw/` is gitignored at the repository level; raw HARs are
  never committed.

## 5. Default verification posture

- `npm run lint && npm test && npm run build` exercises the mock
  driver end-to-end (site profile → recorder → HAR → sanitization →
  fixture → IR → replay validator) and the supervisor gates. It must
  not require network access, paid credentials, or Playwright.
- Live Playwright capture, paid-provider calls, and any operator
  workflow that touches a real session are out of scope for default
  verification.
- The runbooks for individual CLIs are linked in §6; they are the
  authoritative source of step-by-step operator instructions.

## 6. Related runbooks and acceptance criteria

- `docs/runbooks/capture-fixture-import.md` — `F5.AC1` importer.
- `docs/runbooks/capture-traffic-ir.md` — `F5.AC2` IR/fingerprint CLI.
- `docs/runbooks/capture-fixture-replay.md` — `F5.AC3` capture-fixture
  provider.
- `docs/runbooks/api-capture-reference-only.md` — `F5.AC5` owns the
  explicit "raw api-capture sessions, `.env`, cookies, and logs are
  reference-only and must not be imported into this project or
  committed" contract, including forbidden artifact list, reviewer
  checklist, and operator checklist. This design document defers the
  boundary definition to that runbook.
- `docs/runbooks/capture-execution.md` — `F5A.AC3` operator runbook
  for performing authorized maritime captures, including raw artifact
  location, sanitized fixture promotion, and the rationale for keeping
  default autodev/CI off live paid providers.

Parent feature `F5` is now `implemented` because all five F5 ACs
(`F5.AC1`–`F5.AC5`) have shipped and are covered by deterministic
tests; the promotion lives in `docs/autodev/requirements.yaml` and is
guarded by `test/f5-feature-status.test.js`. `F5.AC4`'s scope is
satisfied by this design synthesis and the supporting code/tests
cited above. Parent feature `F5A` is now `implemented` as well —
after `F5A.FOLLOWUP`, the three F5A ACs (capture sites/queue, the
operator-only workflow that reuses api-capture patterns, and the
authorized-captures runbook) are all shipped and covered. The F5A
promotion is guarded by `test/f5a-feature-status.test.js` and
verified end-to-end by `test/capture-sites-queue.test.js`,
`test/capture-workflow.test.js`, and
`test/capture-execution-runbook.test.js`.
