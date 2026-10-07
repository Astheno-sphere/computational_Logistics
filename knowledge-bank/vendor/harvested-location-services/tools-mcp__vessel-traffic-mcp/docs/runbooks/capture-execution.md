# Capture execution runbook (F5A.AC3)

This runbook is the single operator-only entry point for performing an
authorized maritime capture against a real provider session and
promoting the resulting sanitized fixture into this repository.

It composes the surfaces that already exist in this project and links
out for the per-CLI detail; it does **not** restate the importer, IR,
or replay contracts (those live in their own runbooks) and it does
**not** redefine the `api-capture` reference-only boundary (that
contract is owned by `F5.AC5`).

## 1. Scope and threat model

- **Operator-only.** Every step below assumes a human operator with
  explicit, written authorization for the target site, account, and
  session being recorded. Autodev, CI, scheduled jobs, and shared
  service accounts are **not** authorized operators.
- **Default verification never runs this workflow.** `npm run lint`,
  `npm test`, and `npm run build` use the local fixture provider and
  sanitized fixtures only. Nothing in this runbook may be wired into
  default verification, autodev plans, or scheduled GitHub Actions.
- **Read-only contract is preserved.** The capture workflow exists to
  observe traffic shapes; it does not click destructive buttons, edit
  saved searches, fleets, billing, or user profile data. The site
  profile's `forbiddenActions` list enforces this at workflow time.
- **No bypass of authentication, paywalls, CAPTCHA, bot defenses, or
  rate limits.** If the target site blocks scripted access, that is
  the answer — do not work around it. Use an official API or stop.
- **B/L document workflows still apply.** When a captured response
  feeds vessel-name resolution, the same `needsConfirmation` and
  ranked-candidates contract from `AGENTS.md` must hold downstream.
- **Why the contract is strict.** A single committed raw HAR, `.env`,
  or unredacted cookie would compromise the operator who ran the
  capture and burn the BYOK trust model that the rest of the project
  is built on. The release checklist (`docs/runbooks/release-checklist.md`
  §3) and the deterministic redaction tests are the gates that catch a
  slip; this runbook is what keeps the operator from creating one in
  the first place.

## 2. Where raw private artifacts live

The capture workflow intentionally produces two kinds of output:
on-disk **raw** artifacts that stay with the operator, and a
**sanitized** fixture that is the only thing eligible for review and
commit.

- **Raw HAR backup.** `recordedExchangesToHar()`
  (`src/capture/har-writer.ts`) writes a HAR 1.2 log to
  `<out-dir>/captures/raw/<label>.har`. `assertHarOutputPath()`
  refuses any path outside a `captures/raw` segment, so a typo cannot
  drop the raw HAR into a tracked directory.
- **Local raw exports / logs.** Anything else the operator chooses to
  keep on disk (stderr logs, screenshots, Playwright traces) must live
  under one of the gitignored prefixes: `captures/raw/`,
  `captures/private/`, `state/`, `*.har`, `*.log`. Do not invent new
  paths that are not in `.gitignore`.
- **Credential profile overlay.** BYOK keys load from
  `config/credential-profiles.local.json` (gitignored) or
  `VESSEL_MCP_PROFILE_<LABEL>__<FIELD>` env vars. They do **not** get
  copied into capture artifacts. See
  `docs/runbooks/credential-profiles.md`.
- **`.env*`.** `.env`, `.env.local`, `.env.production`, and any
  non-`.env.example` env file are gitignored. They are never read by
  the capture workflow itself; they are only sourced into the operator
  shell that invokes `npm run capture:run`.

The committed `.gitignore` already blocks every category above
(`node_modules/`, `dist/`, `coverage/`, `.env`, `.env.*` with
`!.env.example`, `*.log`, `*.har`, `captures/raw/`, `captures/private/`,
`state/`, `config/credential-profiles.local.json`,
`config/credential-profiles.*.local.json`, `fixtures/captures/raw/`,
`fixtures/captures/*.private.json`). Do not weaken those rules to make
room for a raw artifact — re-derive the value from a sanitized fixture
instead. The release checklist
(`docs/runbooks/release-checklist.md` §3) verifies the rule set is
intact before every tag.

## 3. Triple-gated live capture

The `vessel-capture-runner` CLI defaults to a deterministic mock
driver. The live Playwright driver only runs when **all three** of the
following conditions hold (`gateRunner` in `src/capture/workflow.ts`):

1. **`VESSEL_CAPTURE_LIVE=1`** is exported in the operator shell.
2. **`--i-am-authorized`** is passed on the command line. This is a
   conscious, per-invocation acknowledgement; it cannot be stored in a
   config file.
3. **`siteProfile.termsReviewStatus === "allowed"`.** A profile that
   still says `needs-terms-review` or `blocked` is refused even if the
   other two gates pass.

If any one of the three is missing, the runner refuses with a
`WorkflowGateError` and exits non-zero. The mock driver never needs
any of these flags — that is what makes it safe for default
verification.

The same three-gate contract is exercised by
`test/capture-workflow.test.js` (`gateRunner blocks live driver…`), so
a future edit cannot quietly loosen any of the gates without breaking
a deterministic test.

## 4. Operator workflow (mock — the default)

Use the mock driver to validate a site profile and capture script
without touching the network. This is the only mode autodev or
CI-adjacent users should ever run.

```sh
npm install
npm run build

# Replace with a script you authored from a previously authorized
# session (see §5 for the live capture path that produces one).
npm run capture:run -- \
  --site-profile config/capture-sites.example.json \
  --script path/to/script.json \
  --driver mock \
  --label marinetraffic-search
```

Outputs go to the current working directory by default:

- `captures/raw/<label>.har` — raw HAR backup (gitignored).
- `fixtures/captures/<label>.private.json` — sanitized fixture
  (`.private` suffix, gitignored until `--promote`).
- `fixtures/captures/<label>.ir.private.json` — traffic IR alongside
  the fixture.

The mock driver never opens a browser and never makes a network call.
It is what `test/capture-workflow.test.js` uses to assert the
end-to-end pipeline behaves correctly under all the gate conditions.

## 5. Operator workflow (live — authorized only)

Run this **only** with explicit authorization for the target session,
on a workstation that is **not** a CI runner, **not** a shared agent,
and **not** otherwise tied to autodev.

```sh
# 1. Confirm the site profile termsReviewStatus is "allowed".
#    Do not edit the example file — copy it and fill in the field
#    after a human review of the provider terms.

# 2. Export the gates for this shell only (do not check these into
#    a dotfile or a CI config).
export VESSEL_CAPTURE_LIVE=1

# 3. If the workflow needs paid-provider credentials, source them
#    through the BYOK credential profile loader, never inline:
#    export VESSEL_MCP_PROFILE_MARINETRAFFIC__API_KEY="$(cat ~/.config/vessel-mcp/marinetraffic.key)"
#    (the file lives outside the repo; do not commit it)

# 4. Run the live capture against an authorized session you own.
npm run capture:run -- \
  --site-profile path/to/profile.allowed.json \
  --driver playwright \
  --label marinetraffic-search \
  --i-am-authorized \
  --validate-replay
```

The live driver is intentionally a stub in this build —
`createPlaywrightRecorderDriver()` dynamically `import('playwright')`
and the bundled stub throws
`"live playwright driver requires an operator-provided implementation"`.
Operators replace the stub with a vetted Playwright implementation
out-of-tree; the project never ships the live browser code.

What the workflow guarantees once the gates pass:

- `forbiddenActions` and `allowedOrigins` are enforced before each
  step reaches the driver. A step that targets a destructive endpoint
  or an off-profile host is refused with `WorkflowGateError`.
- `sessionLossIndicators` (`url-redirect`, `status-code`,
  `response-header`, `response-body`) abort the workflow with
  `WorkflowAbortedError` as soon as one trips.
- `pacing.minStepIntervalMs` / `pacing.maxStepsPerRun` /
  `pacing.maxConcurrent` from the site profile are honoured by the
  supervisor. Do not edit them mid-run to "go faster".
- Off-profile exchanges captured incidentally by the browser
  (third-party CDNs, trackers) are dropped with a warning rather than
  persisted into the HAR or fixture.

## 6. Promoting a sanitized fixture

A sanitized fixture is the **only** capture artifact eligible for
review and commit. Promotion is a deliberate operator step, never an
automated one.

1. **Re-run the workflow with `--promote`.** This drops the
   `.private` suffix from the output filenames so the operator can
   review the fixture before staging it:

   ```sh
   npm run capture:run -- \
     --site-profile path/to/profile.allowed.json \
     --script path/to/script.json \
     --driver mock \
     --label marinetraffic-search \
     --promote
   ```

   `--promote` does **not** change `provenance.liveReplayDisabled`,
   which stays `true` so the replay provider refuses live use.
2. **Diff against the raw capture.** Open
   `fixtures/captures/<label>.fixture.json` and confirm none of the
   raw values from `captures/raw/<label>.har` survived — no
   `Authorization`, `Cookie`, `Set-Cookie`, `api_key`, `apikey`,
   `token`, or `session` strings with non-redacted values. The
   redaction surface is enumerated in
   `docs/runbooks/capture-fixture-import.md`.
3. **Confirm the IR is clean.** Re-render the IR with
   `npm run capture:ir -- --in fixtures/captures/<label>.fixture.json`
   and confirm `redactedHeaderNames` contains every credential-bearing
   header and `warnings` is empty. The IR file is also safe to commit
   under `fixtures/captures/`.
4. **Re-run `npm test`.** The deterministic redaction tests
   (`test/capture-import.test.js`, `test/capture-workflow.test.js`,
   `test/capture-traffic-ir.test.js`,
   `test/provider-capture-fixture.test.js`) must pass against the new
   fixture and IR shape.
5. **Stage only the sanitized artifacts.**
   `git add fixtures/captures/<label>.fixture.json
   fixtures/captures/<label>.ir.json`. Confirm with
   `git status` that the raw HAR is **not** staged. The `.gitignore`
   prevents it from being added under `captures/raw/`, but spot-check
   anyway.
6. **Review by a second operator.** Capture promotion is a
   security-sensitive step. Follow the release-checklist convention
   of two-person review (`docs/runbooks/release-checklist.md` §7) for
   any commit that lands a new fixture.

## 7. Why default autodev / CI must never run this

Default verification must not call paid or live providers and must not capture private sessions. That includes `npm run lint`, `npm test`, `npm run build`, every autodev plan, every scheduled GitHub Action, and every CI runner. The reasons stack:

- **Authorization is per-operator.** Provider terms typically grant
  access to a specific human and account, not to an automated agent.
  Running a live capture under an autodev or CI identity is a terms
  violation even if the credentials technically work.
- **Cost.** Paid providers bill per request. Wiring `vessel-capture-runner`
  with the live driver into a scheduled run would silently spend the
  operator's budget every iteration.
- **Rate-limit safety.** Site profiles cap `maxStepsPerRun` and
  `minStepIntervalMs` per session, but those caps protect a *single*
  authorized run. A concurrent autodev fleet would multiply load on
  the provider and could trip bot defenses, get the operator banned,
  or starve real users.
- **Credential exposure.** A CI job that runs Playwright would need
  the operator's session cookies or BYOK key in its environment. The
  BYOK contract explicitly forbids that path — keys belong on the
  operator's workstation, redacted at every boundary, and never in a
  shared CI secret store.
- **Reproducibility.** Live captures are non-deterministic by
  definition. Default verification must be deterministic so that test
  failures point at code, not at the upstream site's mood. The mock
  driver and sanitized fixtures are what give us that determinism.
- **Audit.** Sanitized fixtures are human-reviewed before commit
  (§6). A CI-driven capture would skip the reviewer step and could
  ship a fixture that still contained credentials before the next
  deterministic test caught it.

Enforcement (no single control is load-bearing):

- `gateRunner` refuses the Playwright driver unless the operator
  passes `VESSEL_CAPTURE_LIVE=1`, `--i-am-authorized`, and a site
  profile with `termsReviewStatus === "allowed"` (§3).
- `package.json` scripts (`capture:run`, `capture:import`,
  `capture:ir`) are operator commands; `npm test` does **not** invoke
  them.
- Every catalog entry that supports live API calls declares
  `liveTest.defaultDisabled = true` and an
  `enabledFlagEnvVar` starting with `VESSEL_MCP_LIVE_TEST_`
  (`config/provider-catalog.example.json`). The provider catalog
  parser rejects an entry that omits either.
- `docs/runbooks/operator.md` documents the BYOK and live-test
  toggles; this runbook is the capture-specific complement, and both
  are required reading before an operator runs a live workflow.
- `docs/runbooks/release-checklist.md` §3 grep-scans the tracked tree
  for credential-shaped strings, raw HARs, and private-suffix
  fixtures before every release.

## 8. When something goes wrong

- **`WorkflowGateError("pacing"|"origin"|"action"|"driver"|"terms"…)`.**
  Read the message; the gate names the rule that fired. Do not
  override the gate. If the gate is wrong, the site profile is the
  thing to fix (after human review).
- **`WorkflowAbortedError`.** A session-loss indicator tripped. Stop
  the workflow, re-authenticate manually outside this tool, then
  decide whether to re-run. Do not loop on `WorkflowAbortedError`.
- **Suspected credential leak in a sanitized fixture.** Treat as a
  security incident: rotate the leaked credential at the provider
  first, then purge the artifact from `fixtures/captures/`, history,
  and any pushed branch. File a private report via `SECURITY.md`.
- **Suspected `api-capture` artifact in this tree.** Do not delete
  silently. The forbidden artifact list and reviewer checklist live
  in `docs/runbooks/api-capture-reference-only.md` (F5.AC5); follow
  its operator checklist before touching anything.

## 9. Related runbooks and acceptance criteria

- `docs/runbooks/capture-fixture-import.md` — `F5.AC1` HAR/JSON →
  sanitized fixture redactor.
- `docs/runbooks/capture-traffic-ir.md` — `F5.AC2` IR/fingerprint CLI.
- `docs/runbooks/capture-fixture-replay.md` — `F5.AC3` capture-fixture
  provider (router-level opt-in only).
- `docs/maritime-capture-harness.md` — `F5.AC4` harness architecture
  synthesis. This runbook implements the operator-facing usage of the
  modules cataloged there.
- `docs/runbooks/api-capture-reference-only.md` — `F5.AC5` contract
  for the `<api-capture-checkout>` reference boundary
  (forbidden artifact list, reviewer/operator checklists).
- `docs/runbooks/operator.md` — `F6.AC3` operator runbook (BYOK,
  rate limits, live-test toggles, client setup).
- `docs/runbooks/release-checklist.md` — `F7.AC1` release-time
  enforcement of every rule above.

## 10. Verifying this runbook

Run from the project root:

```sh
npm run lint
npm test
npm run build
```

The deterministic test `test/capture-execution-runbook.test.js`
asserts the structural invariants of this document: section headings,
the triple-gated live driver, the raw vs. sanitized artifact split,
the gitignore alignment, the operator CLI commands, the
default-autodev/CI exclusion rationale, the absence of credential-
shaped strings, and the cross-links into README, AGENTS, CONTRIBUTING,
the harness design, and the sibling capture runbooks. Default
verification does not call any live or paid provider; the test checks
local file contents only.
