# api-capture reference-only policy (F5.AC5)

The sibling project at `<api-capture-checkout>` is the
architecture reference for browser-based API capture (Playwright
control, XHR/fetch hooks, HAR backup, replay validation, traffic IR,
schema summaries, redaction worker, supervisor pacing). It is **not** a
runtime dependency of `vessel-traffic-mcp`, and none of its operator
artifacts may enter this repository.

This runbook owns the explicit contract that
`docs/maritime-capture-harness.md` §6 defers to: raw `api-capture`
sessions, `.env` files, cookies, and logs are reference-only and must
not be imported into this project or committed.

## 1. What "reference-only" means

`api-capture` contributes to `vessel-traffic-mcp` through **design and
documentation only**. Permitted use:

- Read `<api-capture-checkout>/README.md`,
  `<api-capture-checkout>/ARCHITECTURE.md`, and
  `<api-capture-checkout>/docs/LOCAL_AGENT_HARNESS.md` for
  architecture patterns (site profiles, capture worker, replay
  validator, traffic IR, redaction worker, supervisor pacing).
- Re-implement equivalent modules under `src/capture/` in this project.
- Cite the reference paths in design docs (`docs/PRD.md` §6.6 / §7.1,
  `docs/TDD.md` §9, `docs/maritime-capture-harness.md`,
  `AGENTS.md` "Implementation Preferences").

Forbidden use:

- Importing, copying, symlinking, vendoring, or `git subtree`-merging
  any `api-capture` source tree, fixture, or generated artifact into
  this repository.
- Reading `api-capture` operator outputs — raw HAR, session JSONL,
  cookies, `.env*`, `config/credential-profiles*.local*`,
  `state/`, `logs/`, `runs/`, `outputs/`, generated `openapi.json`,
  `api_log.jsonl`, `network.har`, `events.jsonl`, `traffic.ndjson`,
  `traffic_summary.json` — and feeding them into adapters, fixtures,
  tests, or commits in this project.
- Re-using `api-capture` credentials, tokens, cookies, or signed
  request bodies in any form, even after manual redaction.

If a future change needs a sanitized fixture for a maritime provider,
use this project's authorized capture path
(`docs/runbooks/capture-fixture-import.md`) against an operator-owned,
authorized session — never against an `api-capture` artifact.

## 2. Forbidden artifact list

The artifacts below originate inside `api-capture` operator runs. None
of them may be added to `vessel-traffic-mcp` under any path, even after
ad-hoc edits:

| Category                        | Examples                                                                                                      |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Raw browser captures            | `*.har`, `network.har`, `captures/raw/*`, `captures/private/*`, `runs/*/network.har`                          |
| Session/event logs              | `api_log.jsonl`, `events.jsonl`, `traffic.ndjson`, `*.log`, `logs/*`, supervisor stdout dumps                  |
| Credentials / env               | `.env`, `.env.local`, `.env.production`, any non-`.env.example` env file, `secrets.yaml`, profile JSON dumps  |
| Cookies                         | `cookies.json`, `cookies.txt`, Playwright `storageState.json`, browser profile dirs, `Set-Cookie`/`Cookie` headers |
| Generated reports               | `openapi.json` exports, `traffic_summary.json`, dashboard exports, replay reports tied to a real session       |
| State directories               | `state/`, `runs/`, `outputs/`, `cache/`, anything containing a live session id, account id, or billing id     |

The committed `.gitignore` already blocks the categories above for this
project (`.env`, `.env.*`, `*.log`, `*.har`, `captures/raw/`,
`captures/private/`, `state/`, `config/credential-profiles.local.json`,
`config/credential-profiles.*.local.json`, `fixtures/captures/raw/`,
`fixtures/captures/*.private.json`). Do not weaken those rules to make
room for an `api-capture` artifact — re-derive the value from a
sanitized fixture instead.

## 3. Why this contract exists

- **Credential safety.** `api-capture` is an autonomous capture agent
  that necessarily reads live cookies, bearer tokens, API keys, and
  session ids belonging to the operator running it. Re-publishing any
  fragment of those artifacts in this repository — even inside a test
  fixture — would compromise the operator and break the BYOK trust
  model that the rest of `vessel-traffic-mcp` is built on.
- **Provider terms.** `api-capture` runs against operator-authorized
  sessions on a per-site basis. Importing its artifacts into this
  project would transitively bind every contributor and downstream
  operator to whatever terms governed that session. Re-deriving
  sanitized fixtures here keeps the terms boundary local and auditable.
- **Determinism.** Default verification (`npm run lint`, `npm test`,
  `npm run build`) must remain network-free and credential-free. Any
  fixture that originated from `api-capture` would be opaque to the
  redaction tooling in this repo (`src/capture/redact.ts`,
  `src/capture/import.ts`), so determinism and the AC1 redaction
  guarantees could not be verified by this project's tests.
- **Auditability.** The release checklist
  (`docs/runbooks/release-checklist.md` §3) scans the tracked tree for
  exactly the artifact shapes `api-capture` produces. Importing one
  would either bypass that gate or trip it — both outcomes are
  release-blockers, not bugs to work around.

## 4. Where the contract is enforced

The contract is enforced by a layered set of mechanisms — no single
control is load-bearing:

1. **Hard rules.** `AGENTS.md` "Implementation Preferences" and
   `CONTRIBUTING.md` "Project Hard Rules" both state that
   `<api-capture-checkout>` is referenced for architecture
   patterns only and that its raw sessions, `.env`, cookies, and logs
   must not be imported or committed.
2. **PRD scope.** `docs/PRD.md` §6.6 states "The implementation must
   not import or expose `api-capture` raw sessions, logs, `.env`
   files, cookies, or provider credentials."
3. **Capture harness design.** `docs/maritime-capture-harness.md` §1
   and §6 cite this runbook as the owner of the reference-only
   boundary.
4. **`.gitignore`.** Blocks every artifact category in §2 of this
   runbook so a slip cannot land via `git add .`. The release checklist
   §3 verifies the rule set is intact on every release.
5. **Release checklist.** `docs/runbooks/release-checklist.md` §3
   includes an explicit "`<api-capture-checkout>` raw
   sessions, `.env`, cookies, and logs are **not** present in this
   tree" line item.
6. **Security policy.** `SECURITY.md` requires reporters not to paste
   raw API keys, bearer tokens, cookies, raw HAR files, or private
   capture sessions into vulnerability reports — sanitize them with
   `npm run capture:import` first.
7. **Deterministic test.** `test/api-capture-reference-only.test.js`
   loads this runbook, the source docs that reference it, and the
   `.gitignore`, and asserts every required statement is present so a
   future edit cannot quietly weaken the contract.

## 5. Reviewer checklist (PR-time)

Before merging any change that touches `src/capture/`,
`docs/maritime-capture-harness.md`, `docs/PRD.md`,
`docs/runbooks/capture-*.md`, `AGENTS.md`, `CONTRIBUTING.md`, or
`.gitignore`:

- [ ] The PR does **not** add a path that contains `api-capture` raw
      session data, `.env*`, cookies, logs, generated `openapi.json`,
      or any artifact in §2.
- [ ] Any new doc reference to `<api-capture-checkout>`
      describes architecture patterns only and does not instruct the
      reader to copy or import operator output.
- [ ] Any new test fixture under `fixtures/captures/` was produced by
      `npm run capture:import` against an operator-owned authorized
      session in **this** project, not lifted from `api-capture`.
- [ ] The `.gitignore` rules listed in §2 are unchanged or
      strengthened. If a contributor proposes weakening them, treat the
      PR as a security review and escalate per `SECURITY.md`.
- [ ] If the change adds a new `api-capture` design citation, add the
      corresponding line to the deterministic test
      (`test/api-capture-reference-only.test.js`) so future drift gets
      caught.

## 6. Operator checklist (machine-time)

Operators running this project on the same workstation that hosts
`<api-capture-checkout>` must keep the two trees disjoint:

- [ ] Do not `cp`, `rsync`, `ln`, or `git checkout` from
      `<api-capture-checkout>` into the `vessel-traffic-mcp`
      working tree.
- [ ] Do not point `vessel-capture-import --in` at any file under
      `<api-capture-checkout>/**`. The importer only accepts
      operator-authorized HAR/JSON for **maritime** providers.
- [ ] Do not source an `api-capture` `.env` into a shell that will run
      `vessel-traffic-mcp` — that would expose unrelated credentials to
      the BYOK profile loader scan path.
- [ ] If the workstation has a shared clipboard or notebook, do not
      paste `api-capture` `Authorization`, `Cookie`, or `Set-Cookie`
      values into any `vessel-traffic-mcp` config, test, or chat.
- [ ] Before committing, run the release-checklist §3 searches even
      for non-release commits when you are not sure where a file came
      from.

## 7. Related documents

- `AGENTS.md` — project hard rules, including the implementation
  preference that names `api-capture` as a reference only.
- `CONTRIBUTING.md` — contributor hard rules and capture-fixture
  workflow.
- `SECURITY.md` — private reporting and "do not paste real secrets"
  rules.
- `.gitignore` — committed allow/deny list for capture artifacts.
- `docs/PRD.md` §6.6 / §7.1 — product-level scope for capture reuse.
- `docs/TDD.md` §9 / §9.1 — technical-design requirements for capture
  tooling and discovery.
- `docs/maritime-capture-harness.md` — F5.AC4 architecture synthesis
  that defers the reference-only boundary to this runbook.
- `docs/runbooks/capture-fixture-import.md` — F5.AC1 importer (the
  sanctioned way to produce a committable fixture).
- `docs/runbooks/capture-traffic-ir.md` — F5.AC2 IR/fingerprint CLI.
- `docs/runbooks/capture-fixture-replay.md` — F5.AC3 replay provider.
- `docs/runbooks/release-checklist.md` — release-time enforcement.
