# Release Checklist (F7.AC1)

This checklist is the gate every `vessel-traffic-mcp` release (tag or
published artifact) must pass. It exists to make secret-safety
violations impossible to miss before they ship.

Run from a clean checkout of the commit you intend to release.

## 1. Branch and working tree are clean

- [ ] `git status` is empty (no uncommitted or untracked files).
- [ ] You are on the commit you intend to tag. Record the SHA:
      `git rev-parse HEAD`.

## 2. Default verification gate passes (no live providers)

These must run green against the fixture provider and sanitized
fixtures only. Default verification must not call paid or live
providers.

- [ ] `npm run lint` (TypeScript type-check) passes.
- [ ] `npm test` passes. All `VESSEL_MCP_LIVE_TEST_*` flags remain
      unset; tests that depend on them must report `skipped`, not
      `failed`.
- [ ] `npm run build` produces `dist/` cleanly.

## 3. No secrets or private captures are committed

Run each search against the tracked tree (not the working tree) and
confirm every hit is intentional and safe (e.g., env-var *names*,
documentation examples). No real values.

- [ ] `.gitignore` still blocks: `node_modules/`, `dist/`, `coverage/`,
      `.env`, `.env.*` (with `!.env.example` allowlist), `*.log`,
      `*.har`, `captures/raw/`, `captures/private/`, `state/`,
      `config/credential-profiles.local.json`,
      `config/credential-profiles.*.local.json`,
      `fixtures/captures/raw/`, and `fixtures/captures/*.private.json`.
- [ ] `git ls-files` does **not** list any of the following:
  - `.env`, `.env.local`, `.env.production`, or any non-`.env.example`
    env file.
  - `*.har` files.
  - `config/credential-profiles.local.json` or any
    `config/credential-profiles.*.local.json` file.
  - Files under `captures/raw/`, `captures/private/`,
    `fixtures/captures/raw/`, or matching
    `fixtures/captures/*.private.json`.
  - Files under `state/`.
- [ ] Credential-shape grep against tracked files reports no hits.
      Suggested searches (rg/grep):
  - `Authorization:\s*Bearer\s+\S` (real bearer tokens, not docs)
  - `eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}` (JWTs)
  - `\b(AKIA|ASIA)[A-Z0-9]{16}\b` (AWS access key IDs)
  - `\bghp_[A-Za-z0-9]{20,}\b` (GitHub PATs)
  - `\bsk-[A-Za-z0-9]{20,}\b` (sk- secrets)
  - `Cookie:\s+\S` and `Set-Cookie:\s+\S` (raw cookie headers)
  - `"cookie"\s*:\s*"[^"]+"` (cookie strings in JSON fixtures)
- [ ] Spot-check any committed file under `fixtures/captures/` for
      `Authorization`, `Cookie`, `Set-Cookie`, `api_key`, `apikey`,
      `token`, `session` keys with non-redacted values. The
      capture-import CLI is the only sanctioned way to produce these
      fixtures (`npm run capture:import`).
- [ ] `<api-capture-checkout>` raw sessions, `.env`, cookies,
      and logs are **not** present in this tree. The api-capture path
      is a reference for architecture only — see
      `docs/runbooks/api-capture-reference-only.md` (F5.AC5) for the
      forbidden artifact list and reviewer checklist.

## 4. Release assets are in place

- [ ] `LICENSE` exists at the repo root and is MIT.
- [ ] `SECURITY.md` exists, with a private-reporting channel and an
      explicit "do not paste real keys / HAR / cookies in reports"
      instruction.
- [ ] `CONTRIBUTING.md` exists and restates the project hard rules
      (no bypasses, BYOK redaction, read-only tools, sanitized
      captures only, default verification does not call live
      providers).
- [ ] `README.md` carries the open-source positioning, MIT badge or
      link, and links to `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`,
      `AGENTS.md`, and the operator runbook.
- [ ] `package.json` declares `"license": "MIT"`.
- [ ] `package.json` discoverability metadata (F7.AC2) is current:
      non-empty `keywords` array covering vessel-ais-mcp,
      ship-tracking-mcp, marinetraffic-mcp, claude-mcp, chatgpt-mcp,
      and codex-plugin; `repository`, `homepage`, and `bugs` URLs
      point at the canonical GitHub repo; `author` is set; `mcpName`
      is `io.github.tools-mcp/vessel-traffic-mcp`; the `files`
      allowlist contains only safe publication artifacts such as
      `dist`, `README.md`, `server.json`, `glama.json`, `LICENSE`,
      `SECURITY.md`, `CONTRIBUTING.md`, `AGENTS.md`, and `docs`. See
      `docs/discoverability.md` for the full contract.
- [ ] `server.json` validates against the official MCP Registry
      schema, uses the `io.github.tools-mcp/vessel-traffic-mcp`
      namespace, points at the canonical GitHub repo, and does not
      contain credentials.
- [ ] `glama.json` includes a GitHub username that can authenticate as a
      maintainer for Glama organization-repository verification.
- [ ] GitHub Issues, Discussions, issue templates, PR template, and
      Topics are enabled according to
      `docs/runbooks/public-sharing.md`.
- [ ] `docs/runbooks/clients.md` (F1.AC3) and
      `docs/runbooks/codex.md` (F7.AC3) describe the same registered
      read-only tool surface as `src/server/create-server.ts`, and
      the env-var contract (`VESSEL_MCP_TRANSPORT`,
      `VESSEL_MCP_HTTP_*`, `VESSEL_MCP_AUTH_TOKEN`,
      `VESSEL_MCP_PROFILE_*`) is consistent across both. If a Codex
      plugin manifest or marketplace metadata file has been promoted
      out of the F7.AC3 scaffold, confirm it carries `readOnly`,
      `notForNavigation`, and only env-var *names* — no real
      credentials.
- [ ] `AGENTS.md` hard rules are unchanged or strengthened — never
      weakened.

## 5. Operator surfaces still match reality

- [ ] `docs/runbooks/operator.md` is current for the released commit:
      env vars, transports, `VESSEL_MCP_LIVE_TEST_*` flags, and
      provider IDs referenced in the live-test cheat sheet match
      `config/provider-catalog.example.json`.
- [ ] `docs/runbooks/credential-profiles.md`, `stdio-fixture-server.md`,
      and `streamable-http-server.md` are current.
- [ ] `docs/autodev/requirements.yaml` accurately reflects which
      acceptance criteria are `implemented`, `pending`, or
      `not_implemented`. Do not flip a parent feature to
      `implemented` unless every child criterion is.

## 6. Provider catalog and routing safety

- [ ] `docs/provider-catalog.md` and
      `config/provider-catalog.example.json` agree on provider IDs,
      access classes, and implementation status.
- [ ] Every catalog entry that supports live calls has
      `liveTest.defaultDisabled = true` and an
      `enabledFlagEnvVar` starting with `VESSEL_MCP_LIVE_TEST_`.
- [ ] No entry encourages bypassing authentication, paywalls,
      CAPTCHA, bot defenses, rate limits, or access controls.

## 7. Final sign-off

- [ ] Two-person review: at least one maintainer other than the
      release author has run sections 2–4 locally and confirmed the
      results.
- [ ] Tag is created from the verified commit. Release notes link to
      this checklist run and to `SECURITY.md` for vulnerability
      reports.
- [ ] If anything in section 3 surfaced a real secret, the release is
      **aborted**: rotate the leaked credential at the provider, purge
      the artifact from history, and re-run from the top.

## Why this exists

`vessel-traffic-mcp` sits in front of operator credentials (BYOK) and
authorized capture fixtures. A single committed `.env`, raw HAR, or
unredacted cookie would compromise the operator who shipped it and
break the trust model the entire project depends on. This checklist
turns the secret-safety contract from a habit into a deterministic
gate. Do not skip steps — failing a step is a release blocker, not a
nit.
