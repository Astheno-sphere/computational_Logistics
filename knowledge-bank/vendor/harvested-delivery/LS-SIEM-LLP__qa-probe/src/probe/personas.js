'use strict';

function authHeadersForPersona(persona = {}) {
  const auth = persona.auth || {};
  if (auth.type === 'bearer' && auth.token) return { Authorization: `Bearer ${auth.token}` };
  if (auth.type === 'api-key' && auth.apiKey) return { [auth.apiKeyHeader || 'X-API-Key']: auth.apiKey };
  if (auth.type === 'cookie' && auth.cookie) return { Cookie: auth.cookie };
  if (auth.headers) return { ...auth.headers };
  return {};
}

async function runPersonaMatrix(endpoints, personas, probeOne) {
  const matrix = {};
  for (const persona of personas || []) {
    matrix[persona.name] = {};
    for (const endpoint of endpoints || []) {
      const result = await probeOne(endpoint, persona);
      matrix[persona.name][`${endpoint.method} ${endpoint.path}`] = result.status;
    }
  }
  return matrix;
}

function detectPrivilegeEscalation(matrix, policies = {}) {
  const findings = [];
  for (const [persona, routes] of Object.entries(matrix || {})) {
    for (const [endpoint, status] of Object.entries(routes || {})) {
      const expected = (((policies[persona] || {})[endpoint]) || null);
      if ((expected === 403 || expected === 401) && status === 200) {
        findings.push({
          endpoint,
          persona,
          expected,
          actual: status,
          rootCause: 'privilege_escalation',
        });
      }
    }
  }
  return findings;
}

module.exports = { authHeadersForPersona, runPersonaMatrix, detectPrivilegeEscalation };
