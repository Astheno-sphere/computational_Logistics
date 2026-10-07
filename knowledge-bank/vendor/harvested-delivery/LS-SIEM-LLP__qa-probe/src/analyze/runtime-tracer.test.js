'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { parseFrontendSrc } = require('./frontend-parser');
const { buildGraph } = require('./graph-builder');
const {
  traceRuntimeRoutes,
  extractApiCallsFromRequests,
  buildRouteUrl,
} = require('./runtime-tracer');

function tempProject(files) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-probe-runtime-'));
  for (const [name, content] of Object.entries(files)) {
    const filePath = path.join(root, name);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, content, 'utf8');
  }
  return root;
}

describe('runtime tracer', () => {
  test('extracts API requests from runtime browser observations', () => {
    const calls = extractApiCallsFromRequests([
      { method: 'GET', url: 'http://localhost:5173/assets/app.js' },
      { method: 'GET', url: 'http://localhost:8000/api/cases?filter=open' },
      { method: 'POST', url: '/api/search' },
    ], '/cases', { frontendApiPrefix: '/api' });

    assert.deepEqual(
      calls.map(call => `${call.source} ${call.method} ${call.path}`),
      ['runtime GET /api/cases', 'runtime POST /api/search'],
    );
  });

  test('uses runtime base URL when present', () => {
    assert.equal(
      buildRouteUrl('/cases', {
        baseUrl: 'http://backend.local',
        analyze: { runtime: { baseUrl: 'http://frontend.local' } },
      }, { baseUrl: 'http://frontend.local' }),
      'http://frontend.local/cases',
    );
  });

  test('dynamic function-built URL is discovered at runtime and tagged runtime', async () => {
    const root = tempProject({
      'src/Cases.tsx': `
        function buildUrl(name, filter) { return '/api/' + name + '?filter=' + filter; }
        api.get(buildUrl('cases', f));
      `,
    });

    const apiCalls = parseFrontendSrc(path.join(root, 'src'));
    assert.equal(apiCalls.allCalls.length, 0);

    const frontendRoutes = new Map([
      ['/cases', { component: 'Cases', authGuard: 'Route', requiredScopes: [] }],
    ]);
    const fakeDriver = {
      async traceRoute(url) {
        assert.equal(url, 'http://frontend.local/cases');
        return {
          requests: [
            { method: 'GET', url: 'http://backend.local/api/cases?filter=open' },
          ],
          domSnapshot: { root: { nodeName: '#document' } },
        };
      },
    };

    const config = {
      baseUrl: 'http://backend.local',
      frontendSrc: path.join(root, 'src'),
      frontendApiPrefix: '/api',
      analyze: {
        runtime: {
          enabled: true,
          baseUrl: 'http://frontend.local',
          navigationTimeoutMs: 30000,
          captureWindowMs: 5000,
        },
      },
    };

    const runtimeTrace = await traceRuntimeRoutes(frontendRoutes, config, { driver: fakeDriver, warnings: [] });
    const graph = buildGraph({
      frontendRoutes,
      apiCalls,
      runtimeCalls: runtimeTrace.runtimeCalls,
      runtimeDomSnapshots: runtimeTrace.domSnapshots,
      backendSpec: {
        routes: { 'GET /cases': { responseSchema: null } },
        featureFlags: {},
        headless: false,
      },
      config,
    });

    assert.deepEqual(graph.frontendRoutes['/cases'].apiCalls, [{
      method: 'GET',
      path: '/api/cases',
      backendPath: '/cases',
      matchedBackendRoute: 'GET /cases',
      callSite: 'runtime:/cases',
      rawPath: 'http://backend.local/api/cases?filter=open',
      source: 'runtime',
    }]);
    assert.equal(graph.runtimeDomSnapshots['/cases'].root.nodeName, '#document');
  });

  test('runtime navigation failures emit warnings without aborting', async () => {
    const frontendRoutes = new Map([
      ['/broken', { component: 'Broken', authGuard: 'Route', requiredScopes: [] }],
    ]);
    const warnings = [];
    const runtimeTrace = await traceRuntimeRoutes(frontendRoutes, {
      baseUrl: 'http://frontend.local',
      frontendApiPrefix: '/api',
      analyze: { runtime: { enabled: true } },
    }, {
      warnings,
      driver: {
        async traceRoute() {
          throw new Error('navigation timeout');
        },
      },
    });

    assert.deepEqual(runtimeTrace.runtimeCalls.get('/broken'), []);
    assert.equal(warnings[0].phase, 'runtime-trace');
    assert.match(warnings[0].error, /navigation timeout/);
  });
});
