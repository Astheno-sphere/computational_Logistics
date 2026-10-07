'use strict';

const FIX_GUIDES = {
  feature_flag_disabled: `
The backend router for this feature is not registered because a feature flag is disabled.

Steps to fix:
1. Check your environment variables or .env file for the HAS_* (or equivalent) flag
   that controls this path prefix.
2. Set it to true (or 1, depending on your config parser).
3. Restart your API server.
4. Re-run qa-probe probe to confirm the 404 is gone.

The flag name is shown in the root-cause detail. If it's missing, look for a conditional
router registration in your backend's main entry point (e.g. app/main.py or server.js).
`,
  missing_route: `
The frontend is calling a backend path that does not exist in the OpenAPI spec.

Steps to fix:
1. Check the frontend API call site (shown in qa_probe_explain_failure) for a typo.
2. Check your backend's router registration file to confirm the router is included.
3. Verify the router file itself exists and imports without errors.
4. If the route is intentionally new, add it to the correct router and register it
   in your backend's main entry point.
`,
  contract_mismatch: `
The frontend calls a path that is close to a backend route but not exactly matching.

Common causes:
- Trailing slash: frontend calls /alerts, backend has /alerts/ (or vice versa)
- Prefix mismatch: frontend includes /api prefix, backend expects /alerts directly
- Casing: /Users vs /users

Fix: align the frontend call path to exactly match the backend route key shown in the detail.
`,
  empty_db: `
The endpoint is working correctly (200 OK) but the database contains no records.

Steps to fix:
1. Run your project's seed or fixture script to populate demo data.
2. Verify the seed worked by calling the endpoint directly with your auth token.
3. If this is a production environment, this may be expected — empty tables are not bugs.
`,
  auth_scope_mismatch: `
The test user does not have the required scope or role for this endpoint.

Steps to fix:
1. Check the endpoint's required scopes (visible in the OpenAPI spec or backend decorator).
2. Configure qa-probe to authenticate as a user with admin or full-access role.
3. Alternatively, update the test user's permissions in your database or identity provider.
4. See auth configuration options in the qa-probe docs (type: bearer | cookie | api-key).
`,
  schema_mismatch: `
The endpoint returns 200 with data, but the response fields don't match what the frontend expects.

Common causes:
- A field was renamed (e.g., rule_name → name) in a backend refactor
- A field was removed from the response model
- A new required field was added that older records don't have

Fix: check the schemaErrors detail and align either the frontend component or the backend
response model so field names match across both sides.
`,
  stream_dead: `
The SSE or WebSocket endpoint is not delivering events.

Steps to fix:
1. Confirm the endpoint URL is correct and the server is running.
2. Check that your reverse proxy (nginx/traefik/caddy) is configured to allow streaming:
   - nginx: set proxy_buffering off; proxy_read_timeout 3600;
   - traefik: no special config needed by default
3. Check backend logs for errors in the event emitter or background task.
4. Confirm the auth token is accepted for streaming endpoints — some backends require
   separate WebSocket authentication (token in query string, not header).
`,
  server_error: `
The endpoint returned a 5xx error.

Steps to fix:
1. Check your backend logs for the traceback immediately before the error response.
2. Common causes: unhandled exception, database connection pool exhaustion, missing
   environment variable, or a third-party dependency timeout.
3. Re-run the failing endpoint in isolation to reproduce the error with full context.
`,
  slow_but_working: `
The endpoint is working but responding slowly (near the probe timeout threshold).

Suggested improvements:
1. Add a database index on the columns used in the query's WHERE / ORDER BY clause.
2. Add a result cache (Redis or in-memory LRU) for expensive aggregation queries.
3. Paginate large responses — return a page of 50 records instead of the full table.
4. Use EXPLAIN ANALYZE on the query to find the bottleneck.
`,
};

module.exports = {
  name: 'qa_probe_suggest_fix',
  description: 'Get a step-by-step fix guide for a root cause category. Ask: "What do I do about feature_flag_disabled issues?"',
  inputSchema: {
    type: 'object',
    properties: {
      rootCause: {
        type: 'string',
        enum: Object.keys(FIX_GUIDES),
        description: 'Root cause category to get a fix guide for.',
      },
    },
    required: ['rootCause'],
  },
  async execute({ rootCause } = {}) {
    const guide = FIX_GUIDES[rootCause];
    if (!guide) {
      return { error: `Unknown root cause: "${rootCause}". Known causes: ${Object.keys(FIX_GUIDES).join(', ')}` };
    }
    return { rootCause, guide: guide.trim() };
  },
};
