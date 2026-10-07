'use strict';

const REPLACEMENTS = [
  [/\b\d{3}-\d{2}-\d{4}\b/g, '000-00-0000'],
  [/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi, 'user@example.test'],
  [/\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b/g, '555-010-0000'],
  [/\b(?:\d[ -]*?){13,16}\b/g, '4111111111111111'],
  [/\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/gi, '00000000-0000-4000-8000-000000000000'],
];

function anonymizeHarBody(body) {
  let text = typeof body === 'string' ? body : JSON.stringify(body || {});
  for (const [pattern, replacement] of REPLACEMENTS) text = text.replace(pattern, replacement);
  try { return JSON.parse(text); } catch { return text; }
}

module.exports = { anonymizeHarBody };
