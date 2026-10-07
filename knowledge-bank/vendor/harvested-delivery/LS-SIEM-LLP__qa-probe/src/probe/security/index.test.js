'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
const { runSecurityChecks } = require('./index.js');
const { classifyEndpoint } = require('../../report/root-cause.js');

const ev = (sample) => ({ evidence: { response: { sample } } });

describe('security pass — disabled by default', () => {
  test('does nothing unless config.security.enabled', async () => {
    const results = { 'GET /x': { status: 200, ...ev('{}') } };
    const sum = await runSecurityChecks([{ method: 'GET', path: '/x' }], results, {}, async () => ({ status: 200 }));
    assert.deepEqual(sum, { authBypassChecked: 0, authBypass: 0, piiLeak: 0, privilegeEscalation: 0 });
    assert.equal(results['GET /x'].securityFinding, undefined);
  });
});

describe('security pass — auth bypass', () => {
  const config = { security: { enabled: true, pii: false } };

  test('authed-200 GET that also returns 200 anonymously is flagged auth_bypass', async () => {
    const results = { 'GET /secret': { status: 200, ...ev('{}') } };
    const sum = await runSecurityChecks([{ method: 'GET', path: '/secret' }], results, config, async () => ({ status: 200 }));
    assert.equal(sum.authBypass, 1);
    assert.equal(results['GET /secret'].securityFinding.rootCause, 'auth_bypass');
    assert.equal(results['GET /secret'].securityFinding.confidence, 'high');
  });

  test('endpoint that rejects anonymous (401) is NOT flagged', async () => {
    const results = { 'GET /secret': { status: 200, ...ev('{}') } };
    const sum = await runSecurityChecks([{ method: 'GET', path: '/secret' }], results, config, async () => ({ status: 401 }));
    assert.equal(sum.authBypass, 0);
    assert.equal(results['GET /secret'].securityFinding, undefined);
  });

  test('never re-probes non-GET endpoints (no writes)', async () => {
    const results = { 'POST /things': { status: 200, ...ev('{}') } };
    let calls = 0;
    await runSecurityChecks([{ method: 'POST', path: '/things' }], results, config, async () => { calls++; return { status: 200 }; });
    assert.equal(calls, 0, 'POST is never re-probed');
  });
});

describe('security pass — PII scan', () => {
  const config = { security: { enabled: true, authBypass: false } };

  test('flags an SSN in a response body as pii_leak (medium confidence)', async () => {
    const results = { 'GET /users': { status: 200, ...ev('{"ssn":"123-45-6789"}') } };
    const sum = await runSecurityChecks([{ method: 'GET', path: '/users' }], results, config, async () => ({ status: 200 }));
    assert.equal(sum.piiLeak, 1);
    assert.equal(results['GET /users'].securityFinding.rootCause, 'pii_leak');
    assert.deepEqual(results['GET /users'].securityFinding.kinds, ['ssn']);
  });

  test('allowlisted PII kinds are not flagged', async () => {
    const results = { 'GET /users': { status: 200, ...ev('{"email":"a@b.com"}') } };
    const cfg = { security: { enabled: true, authBypass: false, piiAllow: ['email'] } };
    const sum = await runSecurityChecks([{ method: 'GET', path: '/users' }], results, cfg, async () => ({ status: 200 }));
    assert.equal(sum.piiLeak, 0);
  });
});

describe('security pass — persona privilege escalation', () => {
  test('flags a persona that reached a route its policy forbids', async () => {
    const config = {
      security: {
        enabled: true, authBypass: false, pii: false,
        personas: [{ name: 'viewer', auth: { type: 'bearer', token: 'v' } }],
        policies: { viewer: { 'GET /admin/x': 403 } },
      },
    };
    const results = { 'GET /admin/x': { status: 200, ...ev('{}') } };
    const sum = await runSecurityChecks([{ method: 'GET', path: '/admin/x' }], results, config, async () => ({ status: 200 }));
    assert.equal(sum.privilegeEscalation, 1);
    assert.equal(results['GET /admin/x'].securityFinding.rootCause, 'privilege_escalation');
  });
});

describe('classifier surfaces security findings with calibrated confidence', () => {
  test('auth_bypass → high', () => {
    const r = classifyEndpoint('GET /x', { status: 200, securityFinding: { rootCause: 'auth_bypass', detail: 'x' } }, {}, { probe: {} });
    assert.equal(r.rootCause, 'auth_bypass');
    assert.equal(r.confidence, 'high');
  });
  test('pii_leak → medium (regex heuristic)', () => {
    const r = classifyEndpoint('GET /x', { status: 200, securityFinding: { rootCause: 'pii_leak', detail: 'x' } }, {}, { probe: {} });
    assert.equal(r.confidence, 'medium');
  });
});
