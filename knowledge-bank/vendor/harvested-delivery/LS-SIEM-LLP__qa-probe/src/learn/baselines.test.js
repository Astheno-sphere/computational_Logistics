'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { computeBaselines, historicalFixSuggestion } = require('./baselines');
const { detectAnomalies } = require('./anomaly-detector');
const { saveToHistory, loadRecentRuns } = require('../cache/history');
const { classifyEndpoint } = require('../report/root-cause');

test('baseline anomaly detector flags cardinality far outside historical range', () => {
  const runs = Array.from({ length: 30 }, (_, i) => ({
    endpointDiagnostics: [{ endpoint: 'GET /api/cases', itemCount: 100 + (i % 11), ms: 100 }],
  }));
  const baselines = computeBaselines(runs);
  const findings = detectAnomalies({ 'GET /api/cases': { itemCount: 3, ms: 100 } }, baselines);

  assert.equal(findings[0].rootCause, 'anomaly_vs_baseline');
  assert.match(findings[0].detail, /Historical cardinality: 100-110; this run: 3/);
});

test('history keeps thirty runs by default', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-probe-history-'));
  const config = { output: { dir: path.join(root, '.qaprobe') } };
  for (let i = 0; i < 35; i++) saveToHistory({ n: i, endpointDiagnostics: [] }, config);

  assert.equal(loadRecentRuns(config, 40).length, 30);
});

test('historical fix suggestion returns matching resolved fix', () => {
  const hint = historicalFixSuggestion('GET /cases', 'empty_db', [{
    resolvedFixes: [{ endpoint: 'GET /cases', rootCause: 'empty_db', fixHint: 'Run seed' }],
  }]);
  assert.equal(hint, 'Run seed');
});

test('root cause classifier surfaces baseline anomalies', () => {
  const result = classifyEndpoint('GET /api/cases', {
    status: 200,
    anomaly: { detail: 'Historical cardinality: 50-200; this run: 3' },
  }, {}, { probe: {} });
  assert.equal(result.rootCause, 'anomaly_vs_baseline');
  assert.equal(result.confidence, 'medium');
});

test('baselines are learned from endpointMetrics (every endpoint, not just issues)', () => {
  // Healthy endpoints never appear in endpointDiagnostics; endpointMetrics covers them.
  const runs = Array.from({ length: 10 }, () => ({
    endpointDiagnostics: [],
    endpointMetrics: { 'GET /api/cases': { status: 200, ms: 100, itemCount: 100 } },
  }));
  const baselines = computeBaselines(runs);
  assert.ok(baselines['GET /api/cases'], 'baseline built from endpointMetrics');
  const findings = detectAnomalies({ 'GET /api/cases': { itemCount: 0, ms: 100 } }, baselines);
  assert.equal(findings[0].rootCause, 'anomaly_vs_baseline');
});

const { attachBaselineAnomalies } = require('../report/index');

test('anomaly attaches to a healthy 2xx response that deviates', () => {
  const runs = Array.from({ length: 6 }, () => ({ endpointMetrics: { 'GET /x': { status: 200, ms: 50, itemCount: 100 } } }));
  const baselines = computeBaselines(runs);
  const probeResults = { 'GET /x': { status: 200, ms: 50, itemCount: 3, empty: false } };
  const flagged = attachBaselineAnomalies(probeResults, baselines);
  assert.equal(flagged, 1);
  assert.ok(probeResults['GET /x'].anomaly, 'anomaly attached');
});

test('anomaly never masks a hard failure or an empty result', () => {
  const runs = Array.from({ length: 6 }, () => ({ endpointMetrics: { 'GET /a': { status: 200, ms: 50, itemCount: 100 }, 'GET /b': { status: 200, ms: 50, itemCount: 100 } } }));
  const baselines = computeBaselines(runs);
  const probeResults = {
    'GET /a': { status: 500, ms: 50, itemCount: 3 },          // hard failure
    'GET /b': { status: 200, ms: 50, itemCount: 0, empty: true }, // empty_db
  };
  attachBaselineAnomalies(probeResults, baselines);
  assert.equal(probeResults['GET /a'].anomaly, undefined, '500 keeps its server_error diagnosis');
  assert.equal(probeResults['GET /b'].anomaly, undefined, 'empty result keeps its empty_db diagnosis');
});
