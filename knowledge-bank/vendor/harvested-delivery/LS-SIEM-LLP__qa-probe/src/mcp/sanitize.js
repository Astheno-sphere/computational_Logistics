'use strict';
// Strip content from MCP responses that could leak internal DB/server info
const SENSITIVE_PATTERNS = [
  /sqlalchemy\.\w+/gi,
  /psycopg\d*\.\w+/gi,
  /table\s+"?\w+"?\s+doesn'?t?\s+exist/gi,
  /relation\s+"?\w+"?\s+does\s+not\s+exist/gi,
  /DETAIL:\s*.+/gi,
  /HINT:\s*.+/gi,
  /File\s+"[^"]+",\s+line\s+\d+/gi,
  /Traceback\s+\(most\s+recent\s+call\s+last\)/gi,
  /at\s+\w+\s+\([^)]+:\d+:\d+\)/g,  // JS stack frames
];

function sanitizeString(str) {
  if (typeof str !== 'string') return str;
  for (const pat of SENSITIVE_PATTERNS) {
    str = str.replace(pat, '[redacted]');
  }
  return str;
}

function sanitizeResult(obj) {
  if (typeof obj === 'string') return sanitizeString(obj);
  if (Array.isArray(obj)) return obj.map(sanitizeResult);
  if (obj && typeof obj === 'object') {
    const out = {};
    for (const [k, v] of Object.entries(obj)) out[k] = sanitizeResult(v);
    return out;
  }
  return obj;
}

module.exports = { sanitizeResult };
