'use strict';

const PATTERNS = {
  ssn: /\b\d{3}-\d{2}-\d{4}\b/g,
  email: /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi,
  phone: /\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b/g,
  credit_card: /\b(?:\d[ -]*?){13,16}\b/g,
};

function scanPii(body, documentedFields = []) {
  const text = typeof body === 'string' ? body : JSON.stringify(body || {});
  const documented = new Set(documentedFields);
  const findings = [];
  for (const [kind, pattern] of Object.entries(PATTERNS)) {
    const matches = text.match(pattern) || [];
    if (matches.length && !documented.has(kind)) {
      findings.push({ kind, count: matches.length, rootCause: 'pii_leak' });
    }
  }
  return findings;
}

module.exports = { scanPii, PATTERNS };
