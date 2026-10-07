'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { generateCoverage } = require('./coverage');
const { renderCoverageMarkdown } = require('./formatters/coverage-md');
const { runReport } = require('./index');

function baseGraph(overrides = {}) {
  return {
    meta: { baseUrl: 'http://localhost:3000', headless: false },
    backendRoutes: {
      'GET /users': { summary: 'List users', tags: ['users'] },
      'GET /api/internal/health': { summary: 'Internal health', tags: ['internal'] },
      ...overrides.backendRoutes,
    },
    frontendRoutes: {
      '/users': {
        component: 'UsersPage',
        apiCalls: [{
          method: 'GET',
          path: '/api/users',
          backendPath: '/users',
          matchedBackendRoute: 'GET /users',
          callSite: 'frontend/src/UsersPage.tsx:7',
          readFields: ['user_name'],
        }],
      },
      ...overrides.frontendRoutes,
    },
    ...overrides.graph,
  };
}

function config(outputDir = '.qaprobe') {
  return {
    baseUrl: 'http://localhost:3000',
    output: { dir: outputDir, formats: ['json'] },
    probe: { timeoutMs: 10000 },
    report: { coverage: { enabled: true, ignoreEndpointGlobs: [] } },
  };
}

test('coverage lists OpenAPI endpoints with no frontend reference', () => {
  const coverage = generateCoverage(baseGraph(), {}, config());

  assert.deepEqual(
    coverage.deadEndpoints.map(item => item.endpoint),
    ['GET /api/internal/health']
  );
});

test('coverage respects dead endpoint ignore globs', () => {
  const cfg = config();
  cfg.report.coverage.ignoreEndpointGlobs = ['GET /api/internal/*'];

  const coverage = generateCoverage(baseGraph(), {}, cfg);

  assert.deepEqual(coverage.deadEndpoints, []);
});

test('coverage lists frontend files whose calls are outside the spec or always 404', () => {
  const graph = baseGraph({
    frontendRoutes: {
      '/legacy': {
        component: 'LegacyWidget',
        apiCalls: [{
          method: 'GET',
          path: '/api/legacy',
          backendPath: '/legacy',
          matchedBackendRoute: null,
          callSite: 'frontend/src/LegacyWidget.tsx:12',
        }],
      },
      '/gone': {
        component: 'GoneWidget',
        apiCalls: [{
          method: 'GET',
          path: '/api/gone',
          backendPath: '/gone',
          matchedBackendRoute: 'GET /gone',
          callSite: 'frontend/src/GoneWidget.tsx:5',
        }],
      },
    },
    backendRoutes: {
      'GET /gone': { summary: 'Removed endpoint' },
    },
  });
  const probeResults = {
    'GET /gone': { status: 404 },
  };

  const coverage = generateCoverage(graph, probeResults, config());

  assert.deepEqual(
    coverage.deadComponents.map(item => item.file).sort(),
    ['frontend/src/GoneWidget.tsx', 'frontend/src/LegacyWidget.tsx']
  );
});

test('coverage lists response fields returned by the backend but not read by the frontend', () => {
  const probeResults = {
    'GET /users': {
      status: 200,
      responseShape: {
        type: 'object',
        fields: {
          user_name: 'string',
          email: 'string',
          ssn: 'string',
        },
      },
    },
  };

  const coverage = generateCoverage(baseGraph(), probeResults, config());

  assert.deepEqual(coverage.orphanedFields, [{
    endpoint: 'GET /users',
    routeKey: null,
    fields: ['email', 'ssn'],
    readFields: ['user_name'],
  }]);
});

test('coverage formatter renders dead endpoints and orphaned fields', () => {
  const coverage = {
    generatedAt: '2026-05-08T00:00:00.000Z',
    summary: { deadEndpointCount: 1, deadComponentCount: 0, orphanedFieldCount: 2 },
    deadEndpoints: [{ endpoint: 'GET /api/internal/health', tags: [], summary: 'Internal health' }],
    deadComponents: [],
    orphanedFields: [{ endpoint: 'GET /users', fields: ['email', 'ssn'], readFields: ['user_name'] }],
  };

  const markdown = renderCoverageMarkdown(coverage).join('\n');

  assert.match(markdown, /GET \/api\/internal\/health/);
  assert.match(markdown, /email, ssn/);
});

test('runReport emits coverage.md when report.coverage.enabled is true', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-probe-coverage-'));
  const cfg = config('.qaprobe');
  const probeResults = {
    'GET /users': {
      status: 200,
      ms: 10,
      empty: false,
      schemaErrors: [],
      responseShape: { type: 'object', fields: { user_name: 'string', email: 'string', ssn: 'string' } },
    },
  };

  const oldCwd = process.cwd();
  process.chdir(root);
  let report;
  try {
    report = await runReport(baseGraph(), probeResults, cfg);
  } finally {
    process.chdir(oldCwd);
  }
  const coverageMd = fs.readFileSync(path.join(root, '.qaprobe', 'coverage.md'), 'utf8');

  assert.equal(report.coverage.summary.deadEndpointCount, 1);
  assert.match(coverageMd, /GET \/api\/internal\/health/);
  assert.match(coverageMd, /email, ssn/);
});
