'use strict';

// Read-only response assertions. Declare invariants the API response must satisfy
// and qa-probe checks them on every 2xx response — catching logic bugs (enum
// drift, bad counts, broken pagination, missing/renamed fields) that a plain
// smoke probe misses. No writes; purely inspects the response body.
//
// Rule shape (any combination of checks on one `field`):
//   { field: 'items[].severity', in: ['low','medium','high','critical'] }
//   { field: 'total', gte: 0 }
//   { field: 'items', type: 'array', maxItems: 100 }
//   { field: 'name', present: true, type: 'string', pattern: '^.+$' }
// `field` supports dot paths and array wildcards: `items[].user.id`.

const MAX_FAILURES = 12;

function json(v) {
  try { return JSON.stringify(v); } catch { return String(v); }
}

function typeName(v) {
  if (Array.isArray(v)) return 'array';
  if (v === null) return 'null';
  return typeof v;
}

function matchesType(v, type) {
  if (type === 'array') return Array.isArray(v);
  if (type === 'object') return v !== null && typeof v === 'object' && !Array.isArray(v);
  if (type === 'null') return v === null;
  return typeName(v) === type;
}

/**
 * Resolve a field path to the list of values it selects. A wildcard segment
 * (`items[]`) fans out across array elements, so `items[].id` returns every id.
 */
function resolveField(body, fieldPath) {
  if (!fieldPath) return [body];
  let current = [body];
  for (const rawPart of String(fieldPath).split('.')) {
    const wildcard = rawPart.endsWith('[]');
    const key = wildcard ? rawPart.slice(0, -2) : rawPart;
    const next = [];
    for (const c of current) {
      if (c == null) continue;
      const v = key === '' ? c : c[key];
      if (wildcard) {
        if (Array.isArray(v)) next.push(...v);
      } else {
        next.push(v);
      }
    }
    current = next;
  }
  return current;
}

function checkValue(label, v, rule, failures) {
  if (rule.type && !matchesType(v, rule.type)) {
    failures.push(`${label}: expected type ${rule.type}, got ${typeName(v)}`);
  }
  if (rule.in && !rule.in.includes(v)) {
    failures.push(`${label}: ${json(v)} not in ${json(rule.in)}`);
  }
  if (rule.pattern && !(typeof v === 'string' && new RegExp(rule.pattern).test(v))) {
    failures.push(`${label}: ${json(v)} does not match /${rule.pattern}/`);
  }
  if (typeof rule.gte === 'number' && !(v >= rule.gte)) failures.push(`${label}: ${json(v)} < ${rule.gte}`);
  if (typeof rule.lte === 'number' && !(v <= rule.lte)) failures.push(`${label}: ${json(v)} > ${rule.lte}`);
  if (typeof rule.gt === 'number' && !(v > rule.gt)) failures.push(`${label}: ${json(v)} <= ${rule.gt}`);
  if (typeof rule.lt === 'number' && !(v < rule.lt)) failures.push(`${label}: ${json(v)} >= ${rule.lt}`);
  if (rule.nonEmpty && !(v != null && v.length > 0)) failures.push(`${label}: expected non-empty`);
  if (typeof rule.minItems === 'number' && !(Array.isArray(v) && v.length >= rule.minItems)) {
    failures.push(`${label}: expected >= ${rule.minItems} items`);
  }
  if (typeof rule.maxItems === 'number' && !(Array.isArray(v) && v.length <= rule.maxItems)) {
    failures.push(`${label}: expected <= ${rule.maxItems} items`);
  }
}

/**
 * Evaluate assertion rules against a response body. Returns an array of failure
 * strings (empty = all passed).
 */
function evaluateAssertions(body, rules) {
  const failures = [];
  for (const rule of rules || []) {
    if (!rule || typeof rule !== 'object') continue;
    const label = rule.field || '<root>';
    const values = resolveField(body, rule.field);

    if (rule.present && (values.length === 0 || values.some(v => v === undefined))) {
      failures.push(`${label}: expected present, missing`);
    }
    for (const v of values) {
      // Skip value-level checks on absent fields unless presence was asserted —
      // avoids false positives on legitimately optional fields.
      if (v === undefined) continue;
      checkValue(label, v, rule, failures);
      if (failures.length >= MAX_FAILURES) return failures.slice(0, MAX_FAILURES);
    }
  }
  return failures.slice(0, MAX_FAILURES);
}

/** Look up the assertion rules configured for an endpoint key ("GET /alerts"). */
function assertionsForEndpoint(config, method, path) {
  const all = config && config.assertions;
  if (!all) return null;
  return all[`${String(method).toUpperCase()} ${path}`] || null;
}

module.exports = { evaluateAssertions, resolveField, assertionsForEndpoint };
