'use strict';

const { openApiToZod } = require('./openapi-to-zod');

function validateSchema(body, responseSchema) {
  if (!responseSchema || body === null || body === undefined) {
    return { valid: true, ok: true, errors: [] };
  }

  try {
    const schema = openApiToZod(responseSchema);
    const result = schema.safeParse(body);
    if (result.success) return { valid: true, ok: true, errors: [], issues: [] };
    return {
      valid: false,
      ok: false,
      errors: result.error.issues.map(formatIssue),
      issues: result.error.issues,
    };
  } catch (err) {
    return { valid: true, ok: true, errors: [], issues: [], validatorError: err.message };
  }
}

function formatIssue(issue) {
  const field = issue.path && issue.path.length > 0 ? issue.path.join('.') : '(root)';
  if (issue.code === 'invalid_type') {
    if (issue.received === 'undefined') {
      return `Missing required field: "${field}"`;
    }
    return `Type mismatch at "${field}": expected ${issue.expected}, got ${issue.received}`;
  }
  return `${field}: ${issue.message}`;
}

module.exports = { validateSchema };
