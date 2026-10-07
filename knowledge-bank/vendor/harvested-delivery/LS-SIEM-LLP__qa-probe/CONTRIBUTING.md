# Contributing to qa-probe

Thank you for considering a contribution. This document covers how to report bugs, propose features, and submit pull requests.

---

## Quick orientation

```
qa-probe/
├── bin/qa-probe.js          CLI entry point (#!/usr/bin/env node)
├── src/
│   ├── analyze/             Phase 1 — AST parsing + OpenAPI fetch
│   │   ├── adapters/        Framework-specific adapters (fastapi, express, nextjs, generic)
│   │   ├── frontend-parser.js
│   │   ├── route-extractor.js
│   │   ├── graph-builder.js
│   │   └── backend-fetcher.js
│   ├── probe/               Phase 2 — Live HTTP + SSE + WS probing
│   │   ├── authenticator.js
│   │   ├── endpoint-runner.js
│   │   ├── sse-checker.js
│   │   ├── ws-checker.js
│   │   ├── schema-validator.js
│   │   └── rate-limiter.js
│   ├── report/              Phase 3 — Root cause + scoring + output
│   │   ├── root-cause.js    The 9-rule classifier — most contributions land here
│   │   ├── scorer.js
│   │   ├── blast-radius.js
│   │   ├── regression.js
│   │   └── formatters/
│   ├── mcp/                 MCP server + 7 tools
│   ├── config/              Zod schema + loader
│   └── cache/               .qaprobe/ read/write
└── examples/                One config per supported framework
```

The three phases are intentionally decoupled. Phase 1 reads source files and writes `graph.json`. Phase 2 reads `graph.json` and writes `probe-results.json`. Phase 3 reads both and writes reports. You can work on any phase independently.

---

## Reporting bugs

Before opening an issue, run with the verbose flag and include the output:

```bash
qa-probe run 2>&1 | tee qa-probe-debug.log
```

A good bug report includes:
- The command you ran and the config (with credentials removed)
- The full terminal output including any errors
- Node.js version (`node --version`)
- OS and whether you are running against Docker, a remote server, or localhost

---

## Proposing features

Open an issue before writing code for anything non-trivial. Describe:
- What problem it solves and for whom
- How it fits into the existing phase structure
- Any config changes required (changes to the Zod schema need a migration note)

Features most likely to be accepted:
- New framework adapters (Hono, tRPC, NestJS) following the existing adapter interface in `src/analyze/adapters/interface.js`
- New root-cause rules with clear detection logic and a concrete fix hint
- New MCP tools backed by existing cached data
- Better path parameter detection for common patterns

Features that are out of scope:
- Visual regression testing (use Percy, Chromatic, or Playwright visual comparisons)
- Load testing (use k6 or Locust)
- Mutation testing of write endpoints (by design — qa-probe is read-only)

---

## Development setup

```bash
git clone https://github.com/LS-SIEM-LLP/qa-probe.git
cd qa-probe
npm install

# Run against your own project
QA_USER=testuser QA_PASS=testpass node bin/qa-probe.js run --config /path/to/your/qa-probe.config.js

# Lint (if you have eslint configured)
npx eslint src/
```

**Node.js requirement**: 18 or later. The codebase is CommonJS (`"type": "commonjs"`) so all requires use `require()`, not `import`.

---

## Adding a framework adapter

Create `src/analyze/adapters/<framework>.js` implementing the interface in `src/analyze/adapters/interface.js`:

```js
// Required exports:
module.exports = {
  // Fetch OpenAPI spec and optional feature flags
  async fetchSpec(config, http) {
    // Returns: { routes, featureFlags, specUrl, framework, headless, rawSpec }
  },

  // Check if a path requires auth
  isAuthRequired(path, spec) {
    // Returns: boolean
  },

  // Build the login request config
  buildAuthRequest(config) {
    // Returns: { method, url, data } or null
  },

  // Extract auth headers from the login response
  extractToken(loginResponse, config) {
    // Returns: { Authorization: 'Bearer ...' } or { Cookie: '...' } or {}
  },
};
```

Register your adapter in `src/analyze/backend-fetcher.js` and add an example config in `examples/<framework>/`.

---

## Adding a root-cause rule

The classifier lives in `src/report/root-cause.js`. Rules run in priority order — **first match wins**. When adding a rule:

1. Add a new numbered comment block inside `classifyEndpoint()`
2. Return `{ rootCause: 'your_category', rootCauseDetail: '...', fixHint: '...' }`
3. Add a corresponding entry to `FIX_GUIDES` in `src/mcp/tools/suggest-fix.js`
4. Add the new category to the scoring schema in `src/config/schema.js` if it needs a configurable weight
5. Document it in the comparison table in README.md

**Rule guidelines:**
- Detection must be deterministic — no network calls, only the data already in `probeResult` and `graph`
- Fix hints should be generic enough to work for any project, not a specific codebase
- If a rule only applies in certain conditions (e.g. when a feature flag endpoint is configured), check for the data first before returning a match

---

## Submitting a pull request

1. Fork the repo and create a feature branch: `git checkout -b feature/your-feature`
2. Make your changes
3. Run `node bin/qa-probe.js run` against a real project to verify the change works end-to-end
4. Update `CHANGELOG.md` under an `[Unreleased]` section
5. Update `README.md` if you changed any config options, CLI flags, or added capabilities
6. Open a PR against `main` with a description of what changed and why

**PR checklist:**
- [ ] No hardcoded credentials, URLs, or project-specific strings
- [ ] Config changes validated by the Zod schema in `src/config/schema.js`
- [ ] Fix hints in `suggest-fix.js` are generic (no container names, no specific paths)
- [ ] CHANGELOG.md updated
- [ ] README.md updated if user-facing behavior changed

---

## Code style

- CommonJS (`require`/`module.exports`) throughout — no ESM
- `'use strict';` at the top of every file
- 2-space indent, single quotes
- No external linter config is currently enforced, but follow the style of the file you're editing
- Prefer early returns over deeply nested conditionals
- Error messages should tell you what failed AND what to check next

---

## Developer Certificate of Origin (DCO)

To keep the project's IP clean, every contribution must be signed off under the
[Developer Certificate of Origin](https://developercertificate.org/). This is a
lightweight statement that you wrote the contribution (or otherwise have the
right to submit it under the project's license).

Add a `Signed-off-by` line to each commit by committing with `-s`:

```bash
git commit -s -m "fix: ..."
```

This appends, using your real name and email:

```
Signed-off-by: Jane Doe <jane@example.com>
```

Pull requests whose commits are not signed off will be asked to amend them
(`git commit --amend -s`, or `git rebase --signoff` for multiple commits).

## License

By contributing, you agree that your contributions will be licensed under the
Apache License, Version 2.0 that covers this project, and that LS-SIEM LLP may
distribute them as part of qa-probe. You retain the copyright to your contributions.
