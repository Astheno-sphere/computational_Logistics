'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
const { classifyEndpoint, clusterRootCauses } = require('./root-cause.js');

// ---------------------------------------------------------------------------
// Helpers — build minimal probe results and graph objects
// ---------------------------------------------------------------------------

function probe(overrides) {
  return {
    status: 200,
    ms: 50,
    empty: false,
    schemaErrors: [],
    type: 'http',
    connected: null,
    error: null,
    emptyReason: null,
    ...overrides,
  };
}

function graph(overrides) {
  return {
    featureFlags: {},
    backendRoutes: {},
    config: {},
    ...overrides,
  };
}

const cfg = { probe: { timeoutMs: 10000 } };

// ---------------------------------------------------------------------------
// not_probed
// ---------------------------------------------------------------------------

describe('not_probed', () => {
  test('null probeResult returns not_probed', () => {
    const result = classifyEndpoint('GET /alerts', null, graph(), cfg);
    assert.equal(result.rootCause, 'not_probed');
    assert.equal(result.rootCauseDetail, null);
    assert.equal(result.fixHint, null);
  });
});

// ---------------------------------------------------------------------------
// Rule 1 — feature_flag_disabled
// ---------------------------------------------------------------------------

describe('feature_flag_disabled', () => {
  const flagGraph = graph({
    featureFlags: {
      '/billing': { included: false, enabled: false, message: 'HAS_BILLING=false' },
    },
  });

  test('404 at <15ms with disabled flag → feature_flag_disabled', () => {
    const result = classifyEndpoint('GET /billing/invoices', probe({ status: 404, ms: 5 }), flagGraph, cfg);
    assert.equal(result.rootCause, 'feature_flag_disabled');
    assert.ok(result.rootCauseDetail.includes('404 at 5ms'));
    assert.ok(result.fixHint.includes('HAS_BILLING'));
  });

  test('fix hint includes the auto-derived flag name', () => {
    const result = classifyEndpoint('GET /billing/invoices', probe({ status: 404, ms: 3 }), flagGraph, cfg);
    assert.ok(result.fixHint.includes('HAS_BILLING=true'));
  });

  test('404 at >=15ms with disabled flag → feature_flag_disabled', () => {
    const result = classifyEndpoint('GET /billing/invoices', probe({ status: 404, ms: 20 }), flagGraph, cfg);
    assert.equal(result.rootCause, 'feature_flag_disabled');
  });

  test('404 at <15ms with flag ENABLED → NOT feature_flag_disabled', () => {
    const enabledGraph = graph({
      featureFlags: { '/billing': { included: true, enabled: true } },
    });
    const result = classifyEndpoint('GET /billing/invoices', probe({ status: 404, ms: 5 }), enabledGraph, cfg);
    assert.notEqual(result.rootCause, 'feature_flag_disabled');
  });

  test('404 at <15ms with no feature flag entry → NOT feature_flag_disabled', () => {
    const result = classifyEndpoint('GET /unknown/path', probe({ status: 404, ms: 5 }), graph(), cfg);
    assert.notEqual(result.rootCause, 'feature_flag_disabled');
  });

  test('flag prefix matching works for sub-paths', () => {
    // /billing flag covers /billing/invoices, /billing/refunds, etc.
    const result = classifyEndpoint(
      'GET /billing/invoices/detail',
      probe({ status: 404, ms: 8 }),
      flagGraph,
      cfg,
    );
    assert.equal(result.rootCause, 'feature_flag_disabled');
  });

  test('featureFlagMap override provides custom flag name', () => {
    const overrideGraph = graph({
      featureFlags: { '/credential-scanner': { included: false, enabled: false } },
      config: { featureFlagMap: { '/credential-scanner': 'HAS_DEFAULT_CRED_SCANNER' } },
    });
    const result = classifyEndpoint(
      'GET /credential-scanner/results',
      probe({ status: 404, ms: 4 }),
      overrideGraph,
      cfg,
    );
    assert.equal(result.rootCause, 'feature_flag_disabled');
    assert.ok(result.fixHint.includes('HAS_DEFAULT_CRED_SCANNER'));
  });
});

// ---------------------------------------------------------------------------
// Rule 3 — contract_mismatch (must come BEFORE missing_route in priority)
// ---------------------------------------------------------------------------

describe('contract_mismatch', () => {
  test('404 with trailing-slash fuzzy match → contract_mismatch, not missing_route', () => {
    // Frontend calls GET /alerts, backend has GET /alerts/
    const g = graph({ backendRoutes: { 'GET /alerts/': {} } });
    const result = classifyEndpoint('GET /alerts', probe({ status: 404, ms: 50 }), g, cfg);
    assert.equal(result.rootCause, 'contract_mismatch');
    assert.ok(result.rootCauseDetail.includes('GET /alerts/'));
  });

  test('404 with reversed trailing-slash match → contract_mismatch', () => {
    // Frontend calls GET /rules/, backend has GET /rules
    const g = graph({ backendRoutes: { 'GET /rules': {} } });
    const result = classifyEndpoint('GET /rules/', probe({ status: 404, ms: 50 }), g, cfg);
    assert.equal(result.rootCause, 'contract_mismatch');
  });

  test('404 with casing mismatch → contract_mismatch', () => {
    const g = graph({ backendRoutes: { 'GET /Users': {} } });
    const result = classifyEndpoint('GET /users', probe({ status: 404, ms: 50 }), g, cfg);
    assert.equal(result.rootCause, 'contract_mismatch');
  });

  test('fix hint advises aligning the path', () => {
    const g = graph({ backendRoutes: { 'GET /alerts/': {} } });
    const result = classifyEndpoint('GET /alerts', probe({ status: 404, ms: 50 }), g, cfg);
    assert.ok(result.fixHint.toLowerCase().includes('trailing slash'));
  });
});

// ---------------------------------------------------------------------------
// Rule 2 — missing_route
// ---------------------------------------------------------------------------

describe('missing_route', () => {
  test('404 with no match in spec → missing_route', () => {
    const result = classifyEndpoint('GET /nonexistent', probe({ status: 404, ms: 50 }), graph(), cfg);
    assert.equal(result.rootCause, 'missing_route');
  });

  test('404 with no fuzzy match at all → missing_route (not contract_mismatch)', () => {
    // Completely unrelated backend routes
    const g = graph({ backendRoutes: { 'GET /totally/different': {} } });
    const result = classifyEndpoint('GET /nonexistent', probe({ status: 404, ms: 50 }), g, cfg);
    assert.equal(result.rootCause, 'missing_route');
  });

  test('slow 404 for an explicitly disabled flag path → feature_flag_disabled', () => {
    const flagGraph = graph({
      featureFlags: { '/billing': { included: false, enabled: false } },
    });
    const result = classifyEndpoint('GET /billing/invoices', probe({ status: 404, ms: 100 }), flagGraph, cfg);
    assert.equal(result.rootCause, 'feature_flag_disabled');
  });
});

// ---------------------------------------------------------------------------
// sample_not_found / invalid_sample_params / timeout
// ---------------------------------------------------------------------------

describe('probe sample diagnostics', () => {
  test('404 on known templated backend route -> sample_not_found', () => {
    const result = classifyEndpoint(
      'GET /cases/1',
      probe({ status: 404, routeKey: 'GET /cases/{case_id}' }),
      graph({ backendRoutes: { 'GET /cases/{case_id}': {} } }),
      cfg,
    );
    assert.equal(result.rootCause, 'sample_not_found');
    assert.ok(result.fixHint.includes('pathParamValues'));
  });

  test('422 validation failure -> invalid_sample_params', () => {
    const result = classifyEndpoint(
      'GET /executive/summary?period=1',
      probe({ status: 422 }),
      graph(),
      cfg,
    );
    assert.equal(result.rootCause, 'invalid_sample_params');
  });

  test('404 on configured generated sample path -> sample_unavailable', () => {
    const result = classifyEndpoint(
      'GET /cases/1',
      probe({ status: 404, routeKey: 'GET /cases/{case_id}' }),
      graph({ backendRoutes: { 'GET /cases/{case_id}': {} } }),
      { probe: { timeoutMs: 10000, generatedSamplePaths: ['^/cases/[^/]+$'] } },
    );
    assert.equal(result.rootCause, 'sample_unavailable');
    assert.ok(result.rootCauseDetail.includes('does not require'));
  });

  test('422 on configured generated sample path -> sample_unavailable', () => {
    const result = classifyEndpoint(
      'GET /entity-risk/user/1',
      probe({ status: 422, routeKey: 'GET /entity-risk/{entity_type}/{entity_id}' }),
      graph({ backendRoutes: { 'GET /entity-risk/{entity_type}/{entity_id}': {} } }),
      { probe: { timeoutMs: 10000, generatedSamplePaths: ['^/entity-risk/[^/]+'] } },
    );
    assert.equal(result.rootCause, 'sample_unavailable');
  });

  test('timed out request -> timeout', () => {
    const result = classifyEndpoint(
      'GET /agent/report',
      probe({ status: null, error: 'timeout of 15000ms exceeded' }),
      graph(),
      cfg,
    );
    assert.equal(result.rootCause, 'timeout');
  });
});

// ---------------------------------------------------------------------------
// Rule 4 — empty_db
// ---------------------------------------------------------------------------

describe('empty_db', () => {
  test('200 with empty=true → empty_db', () => {
    const result = classifyEndpoint('GET /rules', probe({ status: 200, empty: true }), graph(), cfg);
    assert.equal(result.rootCause, 'empty_db');
    assert.ok(result.rootCauseDetail.includes('No records'));
  });

  test('200 with empty=false → ok (not empty_db)', () => {
    const result = classifyEndpoint('GET /rules', probe({ status: 200, empty: false }), graph(), cfg);
    assert.equal(result.rootCause, 'ok');
  });

  test('emptyReason is included in detail when present', () => {
    const result = classifyEndpoint(
      'GET /alerts',
      probe({ status: 200, empty: true, emptyReason: 'empty_array' }),
      graph(),
      cfg,
    );
    assert.ok(result.rootCauseDetail.includes('empty_array'));
  });

  test('fix hint uses seedCommand from config when provided', () => {
    const customCfg = { probe: { timeoutMs: 10000 }, seedCommand: 'npm run db:seed' };
    const result = classifyEndpoint('GET /rules', probe({ status: 200, empty: true }), graph(), customCfg);
    assert.ok(result.fixHint.includes('npm run db:seed'));
  });

  test('fix hint is generic when seedCommand is absent', () => {
    const result = classifyEndpoint('GET /rules', probe({ status: 200, empty: true }), graph(), cfg);
    assert.ok(result.fixHint.includes('seedCommand'));
    // Should NOT contain any project-specific container names
    assert.ok(!result.fixHint.includes('ls-api'));
    assert.ok(!result.fixHint.includes('LightShield'));
  });

  test('configured quiet-state endpoint -> expected_empty', () => {
    const result = classifyEndpoint(
      'GET /parsers/quarantine?limit=25',
      probe({ status: 200, empty: true, emptyReason: 'empty_array' }),
      graph(),
      { probe: { timeoutMs: 10000, expectedEmptyPaths: ['^/parsers/quarantine$'] } },
    );
    assert.equal(result.rootCause, 'expected_empty');
    assert.equal(result.fixHint, null);
  });
});

// ---------------------------------------------------------------------------
// Rule 5 — auth_scope_mismatch
// ---------------------------------------------------------------------------

describe('auth_scope_mismatch', () => {
  test('403 → auth_scope_mismatch', () => {
    const result = classifyEndpoint('GET /admin/users', probe({ status: 403 }), graph(), cfg);
    assert.equal(result.rootCause, 'auth_scope_mismatch');
    assert.ok(result.rootCauseDetail.includes('403'));
  });

  test('401 → auth_scope_mismatch (expired/invalid token)', () => {
    const result = classifyEndpoint('GET /alerts', probe({ status: 401 }), graph(), cfg);
    assert.equal(result.rootCause, 'auth_scope_mismatch');
    assert.ok(result.rootCauseDetail.includes('401'));
  });

  test('403 fix hint mentions admin role or scopes', () => {
    const result = classifyEndpoint('GET /admin/users', probe({ status: 403 }), graph(), cfg);
    assert.ok(result.fixHint.toLowerCase().includes('scope') || result.fixHint.toLowerCase().includes('role'));
  });
});

// ---------------------------------------------------------------------------
// Rule 5b — precondition_required (428)
// ---------------------------------------------------------------------------

describe('precondition_required', () => {
  test('428 → precondition_required', () => {
    const result = classifyEndpoint('GET /alerts', probe({ status: 428 }), graph(), cfg);
    assert.equal(result.rootCause, 'precondition_required');
    assert.ok(result.rootCauseDetail.includes('428'));
  });

  test('428 is classified as precondition_required, not unknown', () => {
    const result = classifyEndpoint('GET /compliance/tasks', probe({ status: 428 }), graph(), cfg);
    assert.notEqual(result.rootCause, 'unknown');
  });

  test('fix hint mentions clearing the gate (terms/onboarding/MFA)', () => {
    const result = classifyEndpoint('GET /alerts', probe({ status: 428 }), graph(), cfg);
    const hint = result.fixHint.toLowerCase();
    assert.ok(hint.includes('terms') || hint.includes('onboarding') || hint.includes('mfa'));
  });

  // The package must stay app-agnostic — no LightShield-specific leakage.
  test('detail/hint contain no project-specific names', () => {
    const result = classifyEndpoint('GET /alerts', probe({ status: 428 }), graph(), cfg);
    assert.ok(!result.rootCauseDetail.includes('LightShield'));
    assert.ok(!result.fixHint.includes('LightShield'));
  });
});

// ---------------------------------------------------------------------------
// Rule 6 — schema_mismatch
// ---------------------------------------------------------------------------

describe('schema_mismatch', () => {
  test('200 + data + schemaErrors → schema_mismatch', () => {
    const result = classifyEndpoint(
      'GET /rules',
      probe({ status: 200, empty: false, schemaErrors: ['field "rule_name" missing in response'] }),
      graph(),
      cfg,
    );
    assert.equal(result.rootCause, 'schema_mismatch');
    assert.ok(result.rootCauseDetail.includes('rule_name'));
  });

  test('200 + empty + schemaErrors → empty_db wins (rule 4 before rule 6)', () => {
    // empty_db has higher priority than schema_mismatch
    const result = classifyEndpoint(
      'GET /rules',
      probe({ status: 200, empty: true, schemaErrors: ['field missing'] }),
      graph(),
      cfg,
    );
    assert.equal(result.rootCause, 'empty_db');
  });

  test('200 + data + no schemaErrors → ok', () => {
    const result = classifyEndpoint(
      'GET /rules',
      probe({ status: 200, empty: false, schemaErrors: [] }),
      graph(),
      cfg,
    );
    assert.equal(result.rootCause, 'ok');
  });
});

// ---------------------------------------------------------------------------
// Rule 7 — stream_dead (SSE / WebSocket)
// ---------------------------------------------------------------------------

describe('stream_dead', () => {
  test('SSE not connected → stream_dead', () => {
    const result = classifyEndpoint(
      'SSE /alerts/live',
      probe({ type: 'sse', connected: false, status: 'error', error: 'ECONNREFUSED' }),
      graph(),
      cfg,
    );
    assert.equal(result.rootCause, 'stream_dead');
    assert.ok(result.rootCauseDetail.includes('SSE'));
  });

  test('WS not connected → stream_dead', () => {
    const result = classifyEndpoint(
      'WS /ws',
      probe({ type: 'ws', connected: false, status: 'timeout', error: 'timeout' }),
      graph(),
      cfg,
    );
    assert.equal(result.rootCause, 'stream_dead');
    assert.ok(result.rootCauseDetail.includes('WS'));
  });

  test('SSE connected but no events → stream_dead', () => {
    const result = classifyEndpoint(
      'SSE /alerts/live',
      probe({ type: 'sse', connected: true, status: 'no_events' }),
      graph(),
      cfg,
    );
    assert.equal(result.rootCause, 'stream_dead');
    assert.ok(result.rootCauseDetail.includes('no events'));
  });

  test('WS connected but no frames → stream_dead', () => {
    const result = classifyEndpoint(
      'WS /ws',
      probe({ type: 'ws', connected: true, status: 'no_frames' }),
      graph(),
      cfg,
    );
    assert.equal(result.rootCause, 'stream_dead');
  });

  test('SSE connected and delivered event → ok', () => {
    const result = classifyEndpoint(
      'SSE /alerts/live',
      probe({ type: 'sse', connected: true, status: 'alive' }),
      graph(),
      cfg,
    );
    assert.equal(result.rootCause, 'ok');
  });

  test('WS connected and delivered frame → ok', () => {
    const result = classifyEndpoint(
      'WS /ws',
      probe({ type: 'ws', connected: true, status: 'alive' }),
      graph(),
      cfg,
    );
    assert.equal(result.rootCause, 'ok');
  });

  test('SSE classification ignores HTTP status field', () => {
    // type='sse' routes are handled entirely by connection state, not status code
    const result = classifyEndpoint(
      'SSE /alerts/live',
      probe({ type: 'sse', connected: false, status: 'error' }),
      graph(),
      cfg,
    );
    assert.equal(result.rootCause, 'stream_dead');
  });
});

// ---------------------------------------------------------------------------
// Rule 8 — server_error
// ---------------------------------------------------------------------------

describe('server_error', () => {
  test('500 → server_error', () => {
    const result = classifyEndpoint('GET /alerts', probe({ status: 500 }), graph(), cfg);
    assert.equal(result.rootCause, 'server_error');
  });

  test('502 → server_error', () => {
    const result = classifyEndpoint('GET /alerts', probe({ status: 502 }), graph(), cfg);
    assert.equal(result.rootCause, 'server_error');
  });

  test('503 → server_error', () => {
    const result = classifyEndpoint('GET /alerts', probe({ status: 503 }), graph(), cfg);
    assert.equal(result.rootCause, 'server_error');
  });

  test('fix hint does not contain hardcoded container names', () => {
    const result = classifyEndpoint('GET /alerts', probe({ status: 500 }), graph(), cfg);
    assert.ok(!result.fixHint.includes('ls-api'));
  });
});

// ---------------------------------------------------------------------------
// Rule 9 — slow_app / slow_dependency
// ---------------------------------------------------------------------------

describe('slow_app / slow_dependency', () => {
  test('200 at 8500ms with 10000ms timeout (85%) -> slow_app', () => {
    const result = classifyEndpoint(
      'GET /logs',
      probe({ status: 200, empty: false, ms: 8500 }),
      graph(),
      { probe: { timeoutMs: 10000 } },
    );
    assert.equal(result.rootCause, 'slow_app');
    assert.ok(result.rootCauseDetail.includes('8500ms'));
    assert.ok(result.rootCauseDetail.includes('85%'));
  });

  test('200 at exactly 80% of timeout -> NOT slow_app (boundary is exclusive)', () => {
    // ms > timeout * 0.8, not >=
    const result = classifyEndpoint(
      'GET /logs',
      probe({ status: 200, empty: false, ms: 8000 }),
      graph(),
      { probe: { timeoutMs: 10000 } },
    );
    assert.equal(result.rootCause, 'ok');
  });

  test('200 at 8001ms (just over 80%) -> slow_app', () => {
    const result = classifyEndpoint(
      'GET /logs',
      probe({ status: 200, empty: false, ms: 8001 }),
      graph(),
      { probe: { timeoutMs: 10000 } },
    );
    assert.equal(result.rootCause, 'slow_app');
  });

  test('uses default 10000ms timeout when config is absent', () => {
    // 9000ms should be slow even without a config
    const result = classifyEndpoint(
      'GET /logs',
      probe({ status: 200, empty: false, ms: 9000 }),
      graph(),
      null,
    );
    assert.equal(result.rootCause, 'slow_app');
  });

  test('empty_db wins over slow_app when response is empty', () => {
    const result = classifyEndpoint(
      'GET /logs',
      probe({ status: 200, empty: true, ms: 9000 }),
      graph(),
      cfg,
    );
    assert.equal(result.rootCause, 'empty_db');
  });

  test('OTel child-dominant traces classify as slow_dependency', () => {
    const result = classifyEndpoint(
      'GET /cases',
      probe({
        status: 200,
        empty: false,
        ms: 9000,
        otel: { classification: 'slow_dependency', slowComponent: 'db.query' },
      }),
      graph(),
      { probe: { timeoutMs: 10000 } },
    );
    assert.equal(result.rootCause, 'slow_dependency');
    assert.match(result.rootCauseDetail, /db\.query/);
  });
});

// ---------------------------------------------------------------------------
// ok
// ---------------------------------------------------------------------------

describe('ok', () => {
  test('200 + data + fast + no errors → ok', () => {
    const result = classifyEndpoint(
      'GET /alerts',
      probe({ status: 200, empty: false, ms: 50, schemaErrors: [] }),
      graph(),
      cfg,
    );
    assert.equal(result.rootCause, 'ok');
    assert.equal(result.rootCauseDetail, null);
    assert.equal(result.fixHint, null);
  });
});

// ---------------------------------------------------------------------------
// unknown
// ---------------------------------------------------------------------------

describe('unknown', () => {
  test('unrecognised status code → unknown', () => {
    const result = classifyEndpoint('GET /alerts', probe({ status: 418 }), graph(), cfg);
    assert.equal(result.rootCause, 'unknown');
  });

  test('unknown detail includes the status code', () => {
    const result = classifyEndpoint('GET /alerts', probe({ status: 418 }), graph(), cfg);
    assert.ok(result.rootCauseDetail.includes('418'));
  });

  test('unknown self-explains: says it is unclassified / not a confirmed pass', () => {
    const result = classifyEndpoint('GET /alerts', probe({ status: 418 }), graph(), cfg);
    assert.match(result.rootCauseDetail, /unclassified|no classifier rule matched/i);
    assert.match(result.rootCauseDetail, /not a confirmed pass/i);
  });

  test('unknown carries confidence: none and an unmatched flag', () => {
    const result = classifyEndpoint('GET /alerts', probe({ status: 418 }), graph(), cfg);
    assert.equal(result.confidence, 'none');
    assert.equal(result.unmatched, true);
  });

  test('unknown points the consumer at the evidence, not a false pass', () => {
    const result = classifyEndpoint('GET /alerts', probe({ status: 418 }), graph(), cfg);
    assert.match(result.fixHint, /evidence/i);
  });
});

// ---------------------------------------------------------------------------
// Priority ordering — the critical ordering tests
// ---------------------------------------------------------------------------

describe('priority ordering', () => {
  test('feature_flag_disabled beats missing_route for fast flagged 404', () => {
    const g = graph({
      featureFlags: { '/billing': { included: false, enabled: false } },
      // Route is also absent from spec — would be missing_route without flag
      backendRoutes: {},
    });
    const result = classifyEndpoint('GET /billing/invoices', probe({ status: 404, ms: 5 }), g, cfg);
    assert.equal(result.rootCause, 'feature_flag_disabled');
  });

  test('contract_mismatch beats missing_route when fuzzy match exists', () => {
    // Backend has GET /alerts/ (trailing slash), frontend calls GET /alerts
    const g = graph({ backendRoutes: { 'GET /alerts/': {} } });
    const result = classifyEndpoint('GET /alerts', probe({ status: 404, ms: 50 }), g, cfg);
    assert.equal(result.rootCause, 'contract_mismatch');
    assert.notEqual(result.rootCause, 'missing_route');
  });

  test('empty_db beats schema_mismatch when response is empty', () => {
    const result = classifyEndpoint(
      'GET /rules',
      probe({ status: 200, empty: true, schemaErrors: ['field missing'] }),
      graph(),
      cfg,
    );
    assert.equal(result.rootCause, 'empty_db');
  });

  test('stream_dead fires before any HTTP status rule for SSE/WS types', () => {
    // Even if status code were 200, SSE/WS is handled by connection state
    const result = classifyEndpoint(
      'SSE /alerts/live',
      probe({ type: 'sse', connected: false, status: 200 }),
      graph(),
      cfg,
    );
    assert.equal(result.rootCause, 'stream_dead');
  });

  test('feature_flag_disabled does NOT fire for fast 404 when flag is enabled', () => {
    const g = graph({
      featureFlags: { '/billing': { included: true, enabled: true } },
    });
    const result = classifyEndpoint('GET /billing/invoices', probe({ status: 404, ms: 3 }), g, cfg);
    assert.notEqual(result.rootCause, 'feature_flag_disabled');
  });
});

// ---------------------------------------------------------------------------
// getFlagName — auto-derivation
// ---------------------------------------------------------------------------

describe('getFlagName (via feature_flag_disabled hint)', () => {
  function flagResult(path) {
    const g = graph({
      featureFlags: { ['/' + path.split('/')[1]]: { included: false, enabled: false } },
    });
    return classifyEndpoint(`GET ${path}`, probe({ status: 404, ms: 5 }), g, cfg);
  }

  test('/analytics → HAS_ANALYTICS', () => {
    assert.ok(flagResult('/analytics/dashboards').fixHint.includes('HAS_ANALYTICS'));
  });

  test('/dns → HAS_REPORTS', () => {
    assert.ok(flagResult('/reports/exports').fixHint.includes('HAS_REPORTS'));
  });

  test('/ai-tool-ueba → HAS_USER_ACTIVITY (hyphens become underscores)', () => {
    assert.ok(flagResult('/user-activity/events').fixHint.includes('HAS_USER_ACTIVITY'));
  });
});

// ---------------------------------------------------------------------------
// clusterRootCauses
// ---------------------------------------------------------------------------

describe('clusterRootCauses', () => {
  test('5+ endpoints under same prefix with same cause form a cluster', () => {
    const results = {};
    for (let i = 0; i < 6; i++) {
      results[`GET /analytics/endpoint-${i}`] = { rootCause: 'missing_route' };
    }
    const clusters = clusterRootCauses(results);
    assert.equal(clusters.length, 1);
    assert.equal(clusters[0].prefix, '/analytics');
    assert.equal(clusters[0].rootCause, 'missing_route');
    assert.equal(clusters[0].count, 6);
  });

  test('fewer than 5 endpoints under a prefix do not cluster', () => {
    const results = {};
    for (let i = 0; i < 4; i++) {
      results[`GET /analytics/endpoint-${i}`] = { rootCause: 'missing_route' };
    }
    const clusters = clusterRootCauses(results);
    assert.equal(clusters.length, 0);
  });

  test('mixed causes under same prefix do not cluster unless one dominates', () => {
    const results = {
      'GET /alerts/a': { rootCause: 'missing_route' },
      'GET /alerts/b': { rootCause: 'missing_route' },
      'GET /alerts/c': { rootCause: 'missing_route' },
      'GET /alerts/d': { rootCause: 'missing_route' },
      'GET /alerts/e': { rootCause: 'missing_route' },
      'GET /alerts/f': { rootCause: 'server_error' },
    };
    const clusters = clusterRootCauses(results);
    assert.equal(clusters.length, 1);
    assert.equal(clusters[0].rootCause, 'missing_route');
    assert.equal(clusters[0].count, 5);
  });

  test('each cluster lists all endpoint keys', () => {
    const results = {};
    for (let i = 0; i < 5; i++) {
      results[`GET /dns/endpoint-${i}`] = { rootCause: 'feature_flag_disabled' };
    }
    const clusters = clusterRootCauses(results);
    assert.equal(clusters[0].keys.length, 5);
    assert.ok(clusters[0].keys.every(k => k.startsWith('GET /dns/')));
  });

  test('two separate prefixes produce two separate clusters', () => {
    const results = {};
    for (let i = 0; i < 5; i++) {
      results[`GET /alerts/e${i}`] = { rootCause: 'empty_db' };
      results[`GET /rules/e${i}`] = { rootCause: 'missing_route' };
    }
    const clusters = clusterRootCauses(results);
    assert.equal(clusters.length, 2);
    const prefixes = clusters.map(c => c.prefix).sort();
    assert.deepEqual(prefixes, ['/alerts', '/rules']);
  });

  test('returns empty array when no results', () => {
    const clusters = clusterRootCauses({});
    assert.deepEqual(clusters, []);
  });
});
