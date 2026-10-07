'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { authHeadersForPersona, runPersonaMatrix, detectPrivilegeEscalation } = require('../personas');
const { scanPii } = require('./pii-scanner');
const { detectAuthBypass } = require('./auth-bypass-checker');
const { buildIdorProbePaths, detectIdorAccess } = require('./idor-detector');
const { classifyEndpoint } = require('../../report/root-cause');

test('multi-persona matrix flags analyst privilege escalation on admin endpoint', async () => {
  const personas = [{ name: 'admin' }, { name: 'analyst' }];
  const endpoints = [{ method: 'GET', path: '/admin/users' }];
  const matrix = await runPersonaMatrix(endpoints, personas, async (endpoint, persona) => ({
    status: persona.name === 'admin' ? 200 : 200,
  }));
  const findings = detectPrivilegeEscalation(matrix, {
    analyst: { 'GET /admin/users': 403 },
  });

  assert.equal(matrix.admin['GET /admin/users'], 200);
  assert.equal(findings[0].rootCause, 'privilege_escalation');
});

test('persona auth helper builds bearer headers', () => {
  assert.deepEqual(
    authHeadersForPersona({ auth: { type: 'bearer', token: 'test-token' } }),
    { Authorization: 'Bearer test-token' },
  );
});

test('PII scanner flags undocumented sensitive values', () => {
  const findings = scanPii({ email: 'user@example.com', ssn: '123-45-6789' }, []);
  assert.deepEqual(findings.map(item => item.kind).sort(), ['email', 'ssn']);
});

test('auth bypass checker flags anonymous 200 on authenticated endpoint', () => {
  const finding = detectAuthBypass('GET /admin/users', 200, 200);
  assert.equal(finding.rootCause, 'auth_bypass');
});

test('IDOR detector builds sample IDs and flags cross-persona object reads', () => {
  assert.deepEqual(buildIdorProbePaths('/cases/{id}', ['1', '2']), ['/cases/1', '/cases/2']);
  const findings = detectIdorAccess([{ endpoint: 'GET /cases/2', persona: 'analyst', ownerPersona: 'admin', status: 200 }]);
  assert.equal(findings[0].rootCause, 'privilege_escalation');
});

test('root cause classifier surfaces security findings', () => {
  const result = classifyEndpoint('GET /admin/users', {
    status: 200,
    securityFinding: { rootCause: 'auth_bypass', detail: 'anonymous access' },
  }, {}, { probe: {} });
  assert.equal(result.rootCause, 'auth_bypass');
  assert.match(result.fixHint, /authentication/);
});
