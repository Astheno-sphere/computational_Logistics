'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { runVisualProbe, buildVisualRouteUrl } = require('./visual-probe');
const { classifyEndpoint } = require('../report/root-cause');

function config(outputDir, overrides = {}) {
  return {
    baseUrl: 'http://backend.local',
    frontendApiPrefix: '/api',
    output: { dir: outputDir },
    analyze: { runtime: { baseUrl: 'http://frontend.local' } },
    scoring: {},
    probe: {
      timeoutMs: 10000,
      visual: {
        enabled: true,
        viewportWidth: 1280,
        viewportHeight: 720,
        densityThreshold: 0.10,
        ...overrides,
      },
    },
  };
}

describe('visual probe', () => {
  test('builds frontend route URLs from runtime base URL', () => {
    assert.equal(buildVisualRouteUrl('/cases', config('.qaprobe')), 'http://frontend.local/cases');
  });

  test('flags data received but not rendered when HTTP route is healthy and density is low', async () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-probe-visual-'));
    const cfg = config(path.join(root, '.qaprobe'));
    const graph = {
      frontendRoutes: {
        '/cases': {
          component: 'Cases',
          apiCalls: [{ method: 'GET', backendPath: '/cases', path: '/api/cases' }],
        },
      },
      backendRoutes: { 'GET /cases': {} },
    };
    const probeResults = {
      'GET /cases': { status: 200, ms: 20, empty: false, schemaErrors: [] },
    };

    const visual = await runVisualProbe(graph, probeResults, cfg, {
      driver: {
        async captureRoute(url) {
          assert.equal(url, 'http://frontend.local/cases');
          return {
            screenshotPath: path.join(root, 'cases.png'),
            density: { density: 0.02, textNodeCount: 0, imageCount: 0, nonEmptyContainerCount: 0 },
          };
        },
      },
    });

    const result = visual.syntheticResults['VISUAL /cases'];
    const cause = classifyEndpoint('VISUAL /cases', result, graph, cfg);
    assert.equal(cause.rootCause, 'data_received_not_rendered');
    assert.ok(cause.fixHint.includes('data fetched but not rendered'));
  });

  test('skips visual capture when HTTP score is already unhealthy', async () => {
    const cfg = config('.qaprobe');
    const graph = {
      frontendRoutes: {
        '/cases': {
          component: 'Cases',
          apiCalls: [{ method: 'GET', backendPath: '/cases', path: '/api/cases' }],
        },
      },
      backendRoutes: {},
    };
    const probeResults = {
      'GET /cases': { status: 404, ms: 20, empty: false, schemaErrors: [] },
    };
    let called = false;
    const visual = await runVisualProbe(graph, probeResults, cfg, {
      driver: {
        async captureRoute() {
          called = true;
          return { density: { density: 0 } };
        },
      },
    });

    assert.equal(called, false);
    assert.deepEqual(visual.routeResults, {});
  });
});
