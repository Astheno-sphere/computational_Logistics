// qa-probe config for a typical FastAPI + React app
// Run from the repo root: npx qa-probe run --config qa-probe.config.js

module.exports = {
  // ── Target ────────────────────────────────────────────────────────────────
  // Backend API base URL. If you proxy through nginx and strip a prefix,
  // set frontendApiPrefix to that prefix so frontend `/api/...` calls map
  // correctly to backend routes.
  baseUrl: 'http://localhost:8000',
  frontendApiPrefix: '/api',
  framework: 'fastapi',
  openApiUrl: '/openapi.json',
  // FastAPI-specific: a /health/features endpoint listing HAS_* router flags.
  // Set to null if you don't expose one — feature_flag_disabled detection is skipped.
  featureStatusUrl: '/health/features',

  // ── Frontend Source ────────────────────────────────────────────────────────
  frontendSrc: './frontend/src',
  routerFile: './frontend/src/App.tsx',
  apiClientFile: './frontend/src/utils/api.js',

  // ── Auth ──────────────────────────────────────────────────────────────────
  auth: {
    type: 'bearer',
    loginUrl: '/auth/login',
    credentials: {
      // Set QA_PROBE_USER / QA_PROBE_PASS in your environment or CI secrets.
      // Never commit real credentials to source control.
      username: process.env.QA_PROBE_USER,
      password: process.env.QA_PROBE_PASS,
    },
    tokenPath: 'access_token',
  },

  // ── Probe Behavior ────────────────────────────────────────────────────────
  probe: {
    concurrency: 5,
    delayMs: 50,
    timeoutMs: 10000,
    // Set true if your dev/staging API uses a self-signed TLS cert.
    ignoreHTTPSErrors: false,
    skipPaths: ['^/auth/', '^/health', '^/openapi', '^/docs', '^/redoc'],
    // POST endpoints that are safe reads (search/query, not writes).
    // Everything else with method != GET is skipped to avoid mutating data.
    safePosts: [
      '/search',
      '/query',
    ],
    pathParamValues: {
      id: '1',
      user_id: '1',
    },
    sse: {
      enabled: true,
      firstEventTimeoutMs: 5000,
      paths: [],  // e.g. ['/events/stream']
    },
    ws: {
      enabled: true,
      firstFrameTimeoutMs: 5000,
      paths: [],  // e.g. ['/ws']
    },
  },

  // ── Scoring Weights (negative = penalty applied to a route's 0-100 score) ─
  scoring: {
    missingRoute: -50,
    emptyResponse: -20,
    authError: -30,
    serverError: -40,
    slowResponse: -10,
    disabledFeature: -15,
    schemaMismatch: -25,
    streamDead: -35,
  },

  // ── Output ────────────────────────────────────────────────────────────────
  output: {
    dir: '.qaprobe',
    keepHistory: 10,
    formats: ['json', 'markdown', 'ai-context'],
  },

  // Optional: shell command to seed your test database.
  // Shown in empty_db fix hints. Examples:
  //   'docker exec api python scripts/seed.py'
  //   'npm run db:seed'
  //   'make seed'
  // seedCommand: 'npm run db:seed',

  // Optional: override auto-derived feature flag names.
  // By default `/some-feature` → `HAS_SOME_FEATURE`. Use this when your
  // backend's flag name doesn't follow that convention.
  // featureFlagMap: { '/billing': 'HAS_BILLING_V2' },
};
