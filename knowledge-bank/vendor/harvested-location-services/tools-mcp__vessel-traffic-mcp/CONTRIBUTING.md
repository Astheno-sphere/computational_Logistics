# Contributing to vessel-traffic-mcp

Thank you for considering a contribution. This project is a read-only
Model Context Protocol server that brokers authorized vessel/AIS data.
Because it sits in front of operator credentials and authorized capture
fixtures, contributions are governed by a small set of non-negotiable
safety rules in addition to the usual code-quality expectations.

This document covers F7.AC1.

## Project Hard Rules (please read first)

These rules come from `AGENTS.md` and apply to every contribution. PRs
that violate them will be closed.

- Do not bypass authentication, paywalls, CAPTCHA, bot defenses, rate
  limits, or access controls of any provider.
- Use official APIs, open-data feeds, user-provided credentials, or
  sanitized authorized capture fixtures only.
- Paid/commercial providers are supported through BYOK credential
  profiles. Raw keys must be redacted at all boundaries (logs, errors,
  MCP tool responses) and must never be committed.
- Never commit API keys, cookies, bearer tokens, CSRF tokens, session
  IDs, raw HAR files, `.env*`, or raw private captures. The
  `.gitignore` enforces this; do not weaken it.
- Keep MCP tools read-only. No tool may modify a provider account,
  fleet, billing setting, saved search, or user profile.
- Every vessel-position response must include `source`, `retrievedAt`,
  `observedAt` when available, freshness, coverage caveats, and
  confidence. Treat missing/stale data as valid states, not errors.
- Default verification (`npm run lint`, `npm test`, `npm run build`)
  must not call paid or live providers. Live-provider tests must be
  opt-in through `VESSEL_MCP_LIVE_TEST_*` env vars and skipped by
  default.
- `<api-capture-checkout>` is referenced for architecture
  patterns only. Do not import or commit its raw sessions, `.env`
  files, cookies, logs, or credentials. The full reference-only
  contract — including the forbidden artifact list and reviewer
  checklist — lives in
  `docs/runbooks/api-capture-reference-only.md` (F5.AC5).

## Getting Started

Prerequisites: Node.js 22+, npm.

```bash
git clone <your-fork>
cd vessel-traffic-mcp
npm install
npm run lint
npm test
npm run build
```

The default test suite uses the fixture provider and sanitized
fixtures; it does not need network access, API keys, or accounts.

## Development Workflow

1. **Open an issue first** for non-trivial changes (new provider,
   normalized-type changes, security-sensitive surfaces). This gives
   maintainers a chance to flag scope/compliance concerns before you
   write code. Use the issue forms for bugs, provider requests,
   documentation issues, and authorized capture reviews.
2. **Branch from `main`.** Keep branches focused; one acceptance
   criterion per PR is a good default.
3. **Add or update tests.** New behavior needs deterministic tests
   under `test/*.test.js`. Provider work should ship a fixture-backed
   test; do not rely on live-network calls in default verification.
4. **Run the full verification gate** before pushing:

   ```bash
   npm run lint    # tsc --noEmit
   npm test        # node --test test/*.test.js (builds first)
   npm run build   # tsc -p tsconfig.json
   ```

5. **Update docs.** If you change an operator-facing surface (env vars,
   transports, tools, runbooks), update `docs/runbooks/operator.md` and
   the relevant focused runbook in the same PR.
6. **Update `docs/autodev/requirements.yaml`** when you close an
   acceptance criterion. Flip `status:` to `implemented` and confirm
   the `verification:` value still matches reality.

## Commit and PR Style

- Commits: short imperative subject line. If the change closes a PRD
  acceptance criterion, reference it (e.g., `F7.AC1: …`).
- PR description: explain the *why*, the scope, and the verification
  evidence. Link any related issue.
- Keep PRs reviewable. Refactors and feature work should not be
  combined unless the refactor is strictly required by the feature.

## Adding a Provider Adapter

Providers must:

- Implement the adapter interface and register through the provider
  registry. Tool handlers must not contain provider-specific code.
- Declare credential requirements, landing/signup URL, rate-limit
  policy, cache TTL, and capabilities through metadata that the router
  can consume.
- Document the provider entry in `docs/provider-catalog.md` and the
  catalog JSON, including access class, auth mode, cost/quota model,
  capabilities, source docs, implementation status, live-test env
  vars, and capture eligibility.
- Default to disabled (`liveTest.defaultDisabled = true`) and require
  an explicit `VESSEL_MCP_LIVE_TEST_<PROVIDER>=1` opt-in for live
  calls. Tests skip cleanly when the flag and required env vars are
  not present.
- Redact credentials from every error path. The credential profile
  loader exposes labels/status only.

For paid providers, follow `docs/runbooks/credential-profiles.md` for
the BYOK contract (`VESSEL_MCP_PROFILE_<LABEL>__<FIELD>` env vars and
the gitignored `config/credential-profiles.local.json` overlay).

## Adding a Capture Fixture

Captures are operator-only and must be sanitized before they enter the
repository.

1. Use `npm run capture:import -- <input.har|input.json> <fixture-name>`
   to redact sensitive headers, cookies, tokens, query parameters, and
   body fields before writing the fixture.
2. Generate the traffic IR / schema summary with `npm run capture:ir`.
   Do not commit raw HAR or private session data — `.gitignore`
   already blocks `*.har`, `captures/raw/`, `captures/private/`,
   `fixtures/captures/raw/`, and `fixtures/captures/*.private.json`.
3. Verify with `git diff --cached` that the staged sanitized fixture
   contains no `Authorization`, `Cookie`, `Set-Cookie`, or API-key
   strings before committing.
4. Re-run `npm test` so the capture-importer redaction tests prove the
   fixture is safe.

See `docs/runbooks/capture-fixture-import.md` and
`docs/runbooks/capture-traffic-ir.md`. For the end-to-end authorized
capture workflow — including the triple-gated live driver, where raw
private artifacts live on the operator's disk, how sanitized fixtures
are promoted, and why default autodev/CI must never call live paid
providers or capture private sessions — see
`docs/runbooks/capture-execution.md` (F5A.AC3).

## Reporting Security Issues

Do not file a public GitHub issue for a suspected vulnerability. See
`SECURITY.md` for the private reporting channel (`smgu@futhing.com` or
GitHub private vulnerability reporting).

## Releasing

Maintainers follow the release checklist in
`docs/runbooks/release-checklist.md` to confirm no secrets or private
captures slip into a tag.

## License

By contributing, you agree that your contributions are licensed under
the project's MIT license (`LICENSE`).

## Code of Conduct

Project collaboration follows `CODE_OF_CONDUCT.md`.
