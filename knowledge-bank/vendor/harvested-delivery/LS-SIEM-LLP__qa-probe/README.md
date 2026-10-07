# qa-probe

**Find out exactly why your pages are blank - in under 5 minutes.**

qa-probe is a Node.js command-line tool that reads your React frontend, maps every
API call to its backend route, probes those endpoints live with real auth, and tells
you the **root cause** when something is wrong - not just a status code.

```
Overall score: 74/100

Root causes detected:
  empty_db:              5 route(s)   seed the database
  feature_flag_disabled: 3 route(s)   enable HAS_BILLING, HAS_REPORTS
  contract_mismatch:     1 route(s)   frontend calls /api/users/, backend serves /users

Route          Score   Status     Root cause
-----------    -----   --------   ----------------------
/dashboard     100     healthy
/users          80     healthy    empty_db
/billing         0     broken     feature_flag_disabled
/reports        50     degraded   empty_db
/settings       85     healthy
```

It works best on React apps backed by **FastAPI, Express, Next.js, GraphQL, or tRPC**
with an OpenAPI spec available. Built by the LightShield SIEM team and battle-tested
against a production SIEM.

---

## The problem it solves

Your dashboard loads. Nothing crashes. But every table is empty, every chart shows
zero, and you have no idea why. The cause is almost always one of:

- The frontend calls `/api/users/` but the backend route is `/api/users` (trailing slash)
- A feature flag (`HAS_BILLING=false`) silently disabled an entire router
- The database is connected but the table has no rows
- A backend refactor renamed a field and the frontend still reads the old name
- An endpoint is missing its auth guard, or leaks data without a token

qa-probe builds a source-aware map from frontend calls to live backend responses, then
explains each failure in one line with a fix hint. It complements Playwright (user
journeys) and Schemathesis (contract fuzzing) - it is the layer that answers
"why is this page blank?" first.

---

## Quick start

### 1. Install

```bash
npx qa-probe run        # use without installing
# or
npm install -g qa-probe
```

### 2. Create a config

`qa-probe.config.js` in your project root:

```js
module.exports = {
  baseUrl: 'http://localhost:8000',      // your backend
  frontendSrc: './frontend/src',          // your React source
  routerFile: './frontend/src/App.tsx',   // your router file

  auth: {
    type: 'bearer',
    loginUrl: '/auth/login',
    credentials: {
      username: process.env.QA_USER,       // never hardcode credentials
      password: process.env.QA_PASS,
    },
    tokenPath: 'access_token',
  },
};
```

### 3. Run it

```bash
QA_USER=tester QA_PASS=secret npx qa-probe run
```

qa-probe will parse your frontend, fetch `/openapi.json`, probe every endpoint with
real auth, and write a full report to `.qaprobe/` (`report.md`, `report.json`,
`ai-context.md`, `report.html`). A summary table prints to the terminal.

---

## Understanding the report

**Route status**

| Status   | Meaning |
|----------|---------|
| healthy  | endpoints respond, data present, schema valid |
| degraded | works but has an issue (empty data, slow response) |
| broken   | unreachable, 404, 5xx, or a security/logic failure |

**Common root causes**

| Root cause              | What happened | What to do |
|-------------------------|---------------|------------|
| `feature_flag_disabled` | router not registered (a `HAS_*` flag is false) | enable the flag and restart |
| `contract_mismatch`     | a similar route exists (slash/casing) | align the frontend path |
| `missing_route`         | 404, not in the OpenAPI spec | fix the typo or `include_router()` |
| `empty_db`              | 200 OK but empty array | seed the database |
| `precondition_required` | 428 - terms/onboarding/MFA gate not satisfied | clear the gate for the probe account |
| `auth_scope_mismatch`   | 401/403 - wrong role/scope | use a user with the required permissions |
| `schema_mismatch`       | a field was renamed/removed vs the spec | align frontend, backend, and spec |
| `auth_bypass`           | endpoint returns 200 without auth | add the missing auth guard |
| `assertion_failed`      | response violated a declared invariant | fix the response or the assertion |
| `server_error`          | 5xx | check backend logs |

**Every result is verifiable.** Each diagnosis carries its **evidence** (the request,
a snapshot of the response, timing) and a **confidence** level - `high`, `medium`, or
`none`. A `confidence: none` / `unknown` result is explicitly **not** a confirmed pass.

**Score:** each route is 0-100; the overall score is the average. Use
`--fail-under 80` to make CI fail when the score drops.

---

## Use cases

- **"Why is this page blank?"** - the everyday case. Get a root cause and a fix hint
  in one run instead of digging through network tabs and logs.
- **CI gate** - `qa-probe run --fail-under 80` blocks a deploy when pages regress.
- **Demo / staging sign-off** - confirm an environment actually works before a customer
  call, not just that it returns 200s.
- **Catch contract drift** - a backend refactor renames a field or moves a route;
  qa-probe flags the exact endpoint and frontend call affected.
- **Security smoke** - find endpoints missing an auth guard or leaking PII (opt-in,
  read-only, see Security checks).
- **Logic checks** - assert response invariants (valid enum values, non-negative
  counts, required fields) without writing a test suite.
- **AI-assisted debugging** - let Claude, Cursor, or Codex query the QA state and
  explain failures in plain English (see below).

---

## Use it with an AI assistant (Claude Code, Cursor, Codex)

qa-probe ships a **Model Context Protocol (MCP) server**. Point your AI assistant at
it and the assistant can read your QA data and explain failures directly - no manual
report-reading.

### Setup

Run qa-probe once to populate the cache:

```bash
npx qa-probe run
```

Then add the MCP server. For **Claude Code** / **Cursor**, add to `.mcp.json` at your
repo root:

```json
{
  "mcpServers": {
    "qa-probe": {
      "command": "npx",
      "args": ["qa-probe", "mcp"]
    }
  }
}
```

Restart the assistant. Now you can ask in plain English:

- "Why is /reports showing no data?"
- "Which pages break if the users endpoint goes down?"
- "Show me all broken routes."
- "Mark the empty /alerts result as expected." (records feedback, reapplied next run)

### Available MCP tools

| Tool | Ask it |
|------|--------|
| `qa_probe_get_report`     | "Show me all broken routes and their scores" |
| `qa_probe_explain_failure`| "Why is /reports showing no data?" |
| `qa_probe_probe_endpoint` | "Is GET /users returning data right now?" |
| `qa_probe_get_graph`      | "Which backend routes does /dashboard call?" |
| `qa_probe_get_blast_radius`| "What pages break if the users endpoint goes down?" |
| `qa_probe_suggest_fix`    | "What should I do about feature_flag_disabled?" |
| `qa_probe_run_analysis`   | "Run a full QA check and give me the summary" |
| `qa_probe_label`          | "Mark this finding as expected / a real bug" |

MCP output is sanitized - SQL errors, stack traces, and table names are redacted
before they reach the assistant. Raw data stays on disk. Results carry their
evidence and confidence, and `explain_failure` returns a plain-English `trust` note
when a finding is unverified, so the assistant does not report guesses as passes.

You can also simply open the `qa-probe` folder (or your project with `.qaprobe/`) in
an AI coding tool and ask it to read `ai-context.md` - a compact, LLM-oriented summary
written on every run.

---

## CLI commands

```
qa-probe run       [--config <path>] [--fail-under <N>]   analyze + probe + report
qa-probe analyze   [--config <path>]                       build the dependency graph
qa-probe probe     [--config <path>]                       probe all endpoints
qa-probe report    [--config <path>] [--fail-under <N>]   score, classify, write reports
qa-probe label <endpoint> <verdict> [-r <reason>]          record feedback (reapplied later)
qa-probe fix       [--config <path>] [--apply] [--pr]      generate remediation diffs
qa-probe mcp       [--config <path>]                       start the MCP server (stdio)
```

`--fail-under <N>` exits non-zero when the overall score is below N (a CI gate).

---

## Capabilities

- **Source-aware mapping** - Babel parses your frontend; detects axios/fetch calls and
  common hook patterns; extracts routes from React Router (JSX and `createBrowserRouter`)
  and TanStack Router.
- **Live probing with real auth** - bearer, cookie, api-key, or none. Concurrency-limited,
  with a hard per-request deadline so a streaming endpoint can never hang the run.
- **Root-cause classification** - around 25 causes, each with a fix hint.
- **ID chaining** - probes collections first, harvests a real id, then probes detail
  routes with it instead of a guessed value (kills unseeded-DB noise). On by default.
- **Adaptive baselines** - learns each endpoint's normal latency and row counts from
  recent runs and flags deviation from itself. No model; fully inspectable.
- **Feedback** - `qa-probe label` (or the MCP tool) records a verdict that is reapplied
  on future runs. Scoped labels auto-revoke if behavior changes, so they cannot hide a
  regression.
- **Security checks (opt-in)** - anonymous auth-bypass re-probe, PII scan, and a
  per-persona privilege-escalation matrix. GET-only; never issues a write.
- **Response assertions** - declare invariants (`in`, `type`, `gte`, `pattern`,
  `present`, `minItems`, ...) and qa-probe verifies them on every 2xx response.
- **Write-flows (opt-in, mutating)** - full create/read/update/delete chains with
  guaranteed cleanup. Off by default; for a disposable / test-tenant environment only.
- **SSE and WebSocket checks**, schema-drift detection, blast radius, regression diff,
  coverage, and HAR import for dynamic frontends.
- **OpenAPI auto-discovery** - tries common spec paths and supports a local spec file,
  so fewer apps fall back to headless mode.

---

## Configuration

The example above is enough to start. Key options (all optional unless noted):

```js
module.exports = {
  baseUrl: 'http://localhost:8000',      // required
  frontendApiPrefix: '/api',              // stripped when matching calls to routes
  framework: 'fastapi',                   // fastapi | express | nextjs | graphql | trpc | generic
  openApiUrl: '/openapi.json',            // auto-discovers fallbacks if missing
  openApiFile: null,                      // or load the spec from a local file
  frontendSrc: './frontend/src',
  routerFile: './frontend/src/App.tsx',

  auth: { type: 'bearer', loginUrl: '/auth/login',
          credentials: { username: process.env.QA_USER, password: process.env.QA_PASS },
          tokenPath: 'access_token' },

  probe: {
    concurrency: 5,
    timeoutMs: 10000,
    idDiscovery: true,                    // ID chaining (on by default)
    safePosts: [],                        // POST endpoints that are safe reads
    pathParamValues: { id: '1' },         // fallback values for {id} etc.
    ignoreHTTPSErrors: false,             // dev/staging only
  },

  // Opt-in extras:
  security: { enabled: true, piiAllow: ['email'] },
  assertions: { 'GET /alerts': [{ field: 'items[].severity', in: ['low','high','critical'] }] },
  writeFlows: { enabled: false, flows: [] },
  analyze: { har: { enabled: false, harFile: './traffic.har' } },

  output: { dir: '.qaprobe', formats: ['json', 'markdown', 'ai-context', 'html'] },
  seedCommand: 'npm run db:seed',         // shown in the empty_db fix hint
};
```

`qa-probe.config.js` is executed as JavaScript (like ESLint or Jest configs). Never
hardcode credentials - use environment variables.

---

## How it works

Three phases, each cached so you can re-run them independently.

1. **Analyze** - parse the frontend AST, extract routes, fetch the OpenAPI spec (or
   import a HAR), and build a dependency graph with blast radius.
2. **Probe** - authenticate once, then probe every discovered endpoint live: HTTP,
   SSE, WebSocket, with hard deadlines and ID chaining.
3. **Report** - classify root causes, apply baselines and feedback, score routes
   0-100, and write JSON / Markdown / ai-context / HTML reports.

---

## vs other tools

| Capability | qa-probe | Schemathesis | Playwright | Postman |
|---|:---:|:---:|:---:|:---:|
| Frontend to backend route mapping | yes | no | no | no |
| Root-cause labels with fix hints | yes | no | no | no |
| Live probe with real auth | yes | yes | yes | yes |
| Property-based contract fuzzing | no | yes | no | no |
| User-journey E2E | no | no | yes | no |
| MCP server for AI assistants | yes | no | no | no |
| CI exit-code gate | yes | yes | yes | yes |

Use Schemathesis for thorough contract fuzzing and Playwright for user journeys.
qa-probe maps and explains; reach for the others to go deeper on what it surfaces.

---

## Security and safe use

- Credentials are held in memory for the run and never written to any report.
- Config is executed as JavaScript - only run qa-probe with a config you trust.
- `ignoreHTTPSErrors: true` disables TLS verification; dev/staging only.
- Security re-probing is GET-only and never writes. Write-flows are off by default
  and clean up after themselves; use them only against a disposable environment.

To report a vulnerability, see [SECURITY.md](SECURITY.md).

---

## Known limitations

- Detects visible HTTP calls and common hook patterns. Generated SDK clients, GraphQL
  clients, tRPC routers, and custom service layers may need an adapter - or use HAR
  import to discover them from real traffic.
- Dynamic URLs built by arbitrary factory functions are not detected.
- Best results need an OpenAPI spec; headless mode loses the spec-dependent rules but
  still detects observed-shape drift.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Contributions require a
[Developer Certificate of Origin](https://developercertificate.org/) sign-off
(`git commit -s`).

---

## Branding and trademarks

"qa-probe", "LightShield", and "LS-SIEM" are trademarks of LS-SIEM LLP. The Apache
License does not grant permission to use these names or logos.

---

## License

Copyright (c) 2026 LS-SIEM LLP - created and maintained by the LightShield SIEM team.

Licensed under the Apache License, Version 2.0 - see [LICENSE](LICENSE) and
[NOTICE](NOTICE). You may use, modify, and redistribute qa-probe under the Apache-2.0
terms; copyright and the trademarks above remain with LS-SIEM LLP.
