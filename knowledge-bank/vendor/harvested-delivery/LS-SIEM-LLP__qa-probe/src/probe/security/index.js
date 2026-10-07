'use strict';

const { detectAuthBypass } = require('./auth-bypass-checker');
const { scanPii } = require('./pii-scanner');
const { authHeadersForPersona, runPersonaMatrix, detectPrivilegeEscalation } = require('../personas');

/**
 * Security pass — runs AFTER the primary authed probe. Attaches `securityFinding`
 * to probe results (the classifier surfaces these first, with high severity).
 *
 * Opt-in via `config.security.enabled`. All re-probing is GET-only so the pass
 * never issues a write.
 *
 * @param probeAs (endpoint, headers) => Promise<result>  re-probe with given headers
 */
async function runSecurityChecks(httpEndpoints, results, config, probeAs) {
  const sec = (config && config.security) || {};
  const summary = { authBypassChecked: 0, authBypass: 0, piiLeak: 0, privilegeEscalation: 0 };
  if (!sec.enabled) return summary;

  const gets = httpEndpoints.filter(e => String(e.method).toUpperCase() === 'GET');

  // 1. Auth-bypass — re-probe each authed-200 GET as anonymous (no auth). If it
  //    still returns 200, the endpoint is missing its auth guard. Zero config.
  if (sec.authBypass !== false) {
    for (const ep of gets) {
      const key = `${ep.method} ${ep.path}`;
      const authed = results[key];
      if (!authed || !(authed.status === 200 || authed.status === 204)) continue;
      const anon = await probeAs(ep, {});
      summary.authBypassChecked++;
      const finding = detectAuthBypass(key, authed.status, anon.status);
      if (finding) {
        authed.securityFinding = { ...finding, confidence: 'high' };
        summary.authBypass++;
      }
    }
  }

  // 2. PII scan — inspect the captured response sample for SSN/CC/email/phone
  //    patterns not on the allowlist. Heuristic, so confidence is medium.
  if (sec.pii !== false) {
    const allow = sec.piiAllow || [];
    for (const [key, r] of Object.entries(results)) {
      if (key.startsWith('__') || !r || r.securityFinding) continue;
      const sample = r.evidence && r.evidence.response && r.evidence.response.sample;
      if (!sample) continue;
      const findings = scanPii(sample, allow);
      if (findings.length) {
        const kinds = findings.map(f => f.kind);
        r.securityFinding = {
          rootCause: 'pii_leak',
          detail: `Possible ${kinds.join(', ')} in the response body`,
          kinds,
          confidence: 'medium',
        };
        summary.piiLeak++;
      }
    }
  }

  // 3. Persona matrix — opt-in. Probe each GET as each configured persona and
  //    flag any persona that reached a route your policy says it shouldn't.
  if (Array.isArray(sec.personas) && sec.personas.length) {
    const matrix = await runPersonaMatrix(gets, sec.personas, (ep, persona) =>
      probeAs(ep, authHeadersForPersona(persona)));
    for (const f of detectPrivilegeEscalation(matrix, sec.policies || {})) {
      const r = results[f.endpoint];
      if (r && !r.securityFinding) {
        r.securityFinding = {
          rootCause: 'privilege_escalation',
          detail: `persona "${f.persona}" reached ${f.endpoint} (expected ${f.expected}, got ${f.actual})`,
          confidence: 'high',
        };
        summary.privilegeEscalation++;
      }
    }
  }

  return summary;
}

module.exports = { runSecurityChecks };
