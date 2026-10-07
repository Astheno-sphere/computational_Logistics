'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
const { ConfigSchema } = require('./schema.js');

describe('ConfigSchema — new feature keys survive parsing', () => {
  // Regression: Zod strips unknown keys, so any feature whose config key is
  // missing from the schema is silently dead via the config file. This pins the
  // full opt-in surface so that can't happen again.
  const raw = {
    baseUrl: 'http://localhost:8000',
    openApiFile: './spec.json',
    security: {
      enabled: true,
      piiAllow: ['email'],
      personas: [{ name: 'viewer', auth: { type: 'bearer', token: 't' } }],
      policies: { viewer: { 'GET /admin': 403 } },
    },
    assertions: { 'GET /alerts': [{ field: 'total', gte: 0 }, { field: 'items[].severity', in: ['low', 'high'] }] },
    writeFlows: { enabled: true, flows: [{ name: 'x', idField: 'id', create: { method: 'POST', path: '/x', body: { a: 1 } }, delete: { path: '/x/{id}' } }] },
    feedbackFile: './fb.json',
    probe: { idDiscovery: false, hardTimeoutMs: 5000, maxProbeMs: 60000, maxResponseBytes: 1000 },
    analyze: { har: { enabled: true, harFile: './r.har' } },
    scoring: { securityIssue: -99, assertionFailed: -33 },
    report: { baselineRuns: 5 },
  };

  const parsed = ConfigSchema.safeParse(raw);

  test('parse succeeds', () => {
    assert.equal(parsed.success, true, parsed.success ? '' : JSON.stringify(parsed.error.issues));
  });

  test('security (top-level) survives with its fields', () => {
    const s = parsed.data.security;
    assert.equal(s.enabled, true);
    assert.deepEqual(s.piiAllow, ['email']);
    assert.equal(s.personas[0].name, 'viewer');
    assert.equal(s.policies.viewer['GET /admin'], 403);
    assert.equal(s.authBypass, true); // defaulted on when enabled
  });

  test('assertions survive', () => {
    assert.equal(parsed.data.assertions['GET /alerts'][0].gte, 0);
    assert.deepEqual(parsed.data.assertions['GET /alerts'][1].in, ['low', 'high']);
  });

  test('writeFlows survive', () => {
    assert.equal(parsed.data.writeFlows.enabled, true);
    assert.equal(parsed.data.writeFlows.flows[0].create.path, '/x');
    assert.deepEqual(parsed.data.writeFlows.flows[0].create.body, { a: 1 });
  });

  test('probe tuning keys survive', () => {
    assert.equal(parsed.data.probe.idDiscovery, false);
    assert.equal(parsed.data.probe.hardTimeoutMs, 5000);
    assert.equal(parsed.data.probe.maxProbeMs, 60000);
  });

  test('analyze.har, openApiFile, feedbackFile, scoring overrides, baselineRuns survive', () => {
    assert.equal(parsed.data.analyze.har.enabled, true);
    assert.equal(parsed.data.openApiFile, './spec.json');
    assert.equal(parsed.data.feedbackFile, './fb.json');
    assert.equal(parsed.data.scoring.securityIssue, -99);
    assert.equal(parsed.data.report.baselineRuns, 5);
  });

  test('sensible defaults when omitted (security off, idDiscovery on)', () => {
    const d = ConfigSchema.safeParse({ baseUrl: 'http://x.test' });
    assert.equal(d.success, true);
    assert.equal(d.data.security.enabled, false);
    assert.equal(d.data.writeFlows.enabled, false);
    assert.equal(d.data.probe.idDiscovery, true);
  });
});
