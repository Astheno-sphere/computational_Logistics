'use strict';

function generateMinimalBody(schema) {
  return generateForSchema(schema || {});
}

function generateForSchema(schema) {
  if (!schema || typeof schema !== 'object') return null;
  const type = Array.isArray(schema.type) ? schema.type.find(t => t !== 'null') : schema.type;
  if (schema.default !== undefined) return schema.default;
  if (schema.example !== undefined) return schema.example;

  if (type === 'object' || schema.properties) {
    const required = new Set(schema.required || []);
    const out = {};
    for (const [field, fieldSchema] of Object.entries(schema.properties || {})) {
      if (required.has(field)) {
        out[field] = generateForSchema(fieldSchema);
      }
    }
    return out;
  }
  if (type === 'array') return [];
  if (type === 'integer' || type === 'number') return 0;
  if (type === 'boolean') return false;
  if (type === 'string') return '';
  return null;
}

module.exports = { generateMinimalBody, generateForSchema };
