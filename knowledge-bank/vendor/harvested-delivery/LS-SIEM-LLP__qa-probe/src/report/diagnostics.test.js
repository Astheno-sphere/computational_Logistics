'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const { buildEndpointDiagnostics } = require('./index.js');

describe('buildEndpointDiagnostics', () => {
  test('adds evidence, product label, severity, confidence, and affected routes', () => {
    const graph = {
      frontendRoutes: {
        '/alerts': {
          apiCalls: [
            { method: 'GET', backendPath: '/alerts/dedup' },
          ],
        },
      },
    };
    const evidence = {
      request: { method: 'GET', path: '/alerts/dedup' },
      response: { status: 200, contentType: 'application/json', bodyType: 'array', itemCount: 0, sample: '[]' },
      timing: { ms: 42 },
    };
    const probeResults = {
      'GET /alerts/dedup': {
        status: 200,
        ms: 42,
        empty: true,
        emptyReason: 'empty_array',
        itemCount: 0,
        evidence,
      },
    };
    const rootCauses = {
      'GET /alerts/dedup': {
        rootCause: 'empty_db',
        rootCauseDetail: 'GET /alerts/dedup -> 200 but empty_array.',
        fixHint: 'Seed demo data.',
      },
    };

    const diagnostics = buildEndpointDiagnostics(graph, probeResults, rootCauses);

    assert.equal(diagnostics.length, 1);
    assert.equal(diagnostics[0].endpoint, 'GET /alerts/dedup');
    assert.equal(diagnostics[0].label, 'no_data');
    assert.equal(diagnostics[0].severity, 'low');
    assert.equal(diagnostics[0].confidence, 'medium');
    assert.deepEqual(diagnostics[0].affectedRoutes, ['/alerts']);
    assert.equal(diagnostics[0].emptyReason, 'empty_array');
    // Evidence flows through verbatim so a consumer can verify the diagnosis.
    assert.deepEqual(diagnostics[0].evidence, evidence);
  });

  test('an unclassified (unknown) endpoint reports confidence: none, not a false guess', () => {
    const diagnostics = buildEndpointDiagnostics(
      { frontendRoutes: {} },
      { 'GET /agent/report': { status: null, ms: 15000, error: 'timeout of 15000ms exceeded' } },
      { 'GET /agent/report': { rootCause: 'unknown', rootCauseDetail: 'timeout' } },
    );

    assert.equal(diagnostics[0].label, 'needs_review');
    // 'none' (not 'low') — qa-probe had no rule for this; it must not imply a weak guess.
    assert.equal(diagnostics[0].confidence, 'none');
    assert.deepEqual(diagnostics[0].affectedRoutes, []);
    assert.equal(diagnostics[0].error, 'timeout of 15000ms exceeded');
  });

  test('an explicit classifier confidence overrides the rootCause default', () => {
    const diagnostics = buildEndpointDiagnostics(
      { frontendRoutes: {} },
      { 'GET /x': { status: 428 } },
      { 'GET /x': { rootCause: 'precondition_required', confidence: 'high' } },
    );
    assert.equal(diagnostics[0].confidence, 'high');
  });

  test('an acknowledged (feedback-suppressed) endpoint is dropped from issue diagnostics', () => {
    const diagnostics = buildEndpointDiagnostics(
      { frontendRoutes: { '/alerts': { apiCalls: [{ method: 'GET', backendPath: '/alerts' }] } } },
      { 'GET /alerts': { status: 200, empty: true } },
      { 'GET /alerts': { rootCause: 'acknowledged', acknowledged: true, priorRootCause: 'empty_db' } },
    );
    assert.deepEqual(diagnostics, []);
  });

  test('suppresses expected-empty and generated-sample statuses from issue diagnostics', () => {
    const diagnostics = buildEndpointDiagnostics(
      {
        frontendRoutes: {
          '/parsers': { apiCalls: [{ method: 'GET', backendPath: '/parsers/quarantine' }] },
          '/cases': { apiCalls: [{ method: 'GET', backendPath: '/cases/1' }] },
        },
      },
      {
        'GET /parsers/quarantine': { status: 200, empty: true, emptyReason: 'empty_array' },
        'GET /cases/1': { status: 404, empty: false },
      },
      {
        'GET /parsers/quarantine': { rootCause: 'expected_empty' },
        'GET /cases/1': { rootCause: 'sample_unavailable' },
      },
    );

    assert.deepEqual(diagnostics, []);
  });
});
