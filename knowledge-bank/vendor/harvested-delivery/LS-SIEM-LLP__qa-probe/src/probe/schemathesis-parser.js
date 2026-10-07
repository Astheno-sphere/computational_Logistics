'use strict';

function parseSchemathesisOutput(output) {
  const data = typeof output === 'string' ? JSON.parse(output || '{}') : output || {};
  const failures = data.failures || data.results && data.results.failures || [];
  return failures.map(normalizeFailure);
}

function normalizeFailure(failure) {
  const method = String(failure.method || failure.http_method || '').toUpperCase();
  const path = failure.path || failure.endpoint || '/';
  const payload = failure.payload || failure.request && failure.request.body || null;
  return {
    endpoint: `${method} ${path}`.trim(),
    method,
    path,
    check: failure.check || failure.name || 'schema_check',
    status: failure.status || failure.status_code || null,
    payload,
    rootCause: 'validation_edge_case',
    fixHint: `Schemathesis found ${failure.check || failure.name || 'a validation edge case'} for ${method} ${path}. Offending payload: ${safePayload(payload)}`,
  };
}

function safePayload(payload) {
  const text = JSON.stringify(payload || {});
  return text.length > 240 ? `${text.slice(0, 237)}...` : text;
}

module.exports = { parseSchemathesisOutput, normalizeFailure };
