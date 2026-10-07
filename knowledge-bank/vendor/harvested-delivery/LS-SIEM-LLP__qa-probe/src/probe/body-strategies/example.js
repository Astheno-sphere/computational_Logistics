'use strict';

function generateExampleBody(schema) {
  if (!schema || typeof schema !== 'object') return null;
  if (schema.example !== undefined) return schema.example;
  if (schema.examples) {
    if (Array.isArray(schema.examples) && schema.examples.length > 0) {
      return unwrapExample(schema.examples[0]);
    }
    const first = Object.values(schema.examples)[0];
    if (first !== undefined) return unwrapExample(first);
  }
  return null;
}

function unwrapExample(example) {
  if (example && typeof example === 'object' && Object.prototype.hasOwnProperty.call(example, 'value')) {
    return example.value;
  }
  return example;
}

module.exports = { generateExampleBody };
