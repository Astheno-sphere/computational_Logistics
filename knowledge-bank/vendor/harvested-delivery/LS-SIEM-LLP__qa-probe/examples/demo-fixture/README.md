# qa-probe demo fixture

Use this fixture outline when you want a fast, honest demo of qa-probe's value:
it should show source-aware QA diagnosis, not a perfect replacement for
end-to-end tests.

## Demo app shape

- Frontend: React app with routes for `/dashboard`, `/alerts`, `/reports`,
  `/billing`, `/settings`, and `/live`.
- Backend: FastAPI or Express app with OpenAPI enabled.
- Auth: test-only user supplied through `QA_PROBE_USER` and `QA_PROBE_PASS`.
- Data: seed script that creates alerts/settings data but leaves reports empty.

## Failures to seed

1. `/dashboard` is healthy: expected 100 score.
2. `/alerts` calls `/api/alerts/` while backend exposes `/alerts`: contract mismatch.
3. `/reports` returns `200 []`: empty database.
4. `/billing` route is disabled by `HAS_BILLING=false`: feature flag disabled.
5. `/settings` returns `display_name` while the frontend expects `displayName`: schema mismatch.
6. `/live` opens SSE or WebSocket but receives no first event/frame: stream dead.

## Demo script

```bash
QA_PROBE_USER=demo-user QA_PROBE_PASS=demo-pass npx qa-probe run --fail-under 80
```

Expected outcome:

- Terminal summary shows one healthy route and five diagnosed failures.
- `.qaprobe/report.md` explains root causes and fix hints.
- `.qaprobe/report.json` can be consumed by CI.
- MCP tools can answer questions such as "why is /reports empty?" or
  "which frontend routes depend on GET /alerts?"

## What the demo should not claim

- It does not replace browser workflow tests.
- It does not infer every dynamic API call.
- It does not support GraphQL, tRPC, generated SDK clients, or Next server
  actions without custom adapters.
- It probes configured safe endpoints only; unsafe writes should stay skipped.
