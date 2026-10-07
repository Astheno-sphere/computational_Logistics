'use strict';

const { generateForSchema } = require('./minimal');

let faker = null;
try {
  faker = require('@faker-js/faker').faker;
} catch {
  faker = null;
}

function generateRealisticBody(schema) {
  return generate(schema || {}, null);
}

function generate(schema, fieldName) {
  const type = Array.isArray(schema.type) ? schema.type.find(t => t !== 'null') : schema.type;
  if (schema.example !== undefined) return schema.example;
  if (schema.default !== undefined) return schema.default;

  if (type === 'object' || schema.properties) {
    const required = new Set(schema.required || []);
    const out = {};
    for (const [field, fieldSchema] of Object.entries(schema.properties || {})) {
      if (required.has(field)) out[field] = generate(fieldSchema, field);
    }
    return out;
  }
  if (type === 'array') return [];
  if (type === 'integer' || type === 'number') return realisticNumber(fieldName);
  if (type === 'boolean') return false;
  if (type === 'string') return realisticString(fieldName);
  return generateForSchema(schema, false);
}

function realisticString(fieldName) {
  const name = String(fieldName || '').toLowerCase();
  if (faker) {
    if (name.includes('email')) return faker.internet.email();
    if (name.includes('phone')) return faker.phone.number();
    if (name.includes('name')) return faker.person.fullName();
    if (name.includes('id')) return faker.string.uuid();
    return faker.lorem.word();
  }
  if (name.includes('email')) return 'qa-probe@example.com';
  if (name.includes('phone')) return '+15555550100';
  if (name.includes('name')) return 'QA Probe User';
  if (name.includes('id')) return '00000000-0000-4000-8000-000000000001';
  return 'sample';
}

function realisticNumber(fieldName) {
  const name = String(fieldName || '').toLowerCase();
  if (faker && name.includes('age')) return faker.number.int({ min: 18, max: 90 });
  if (faker) return faker.number.int({ min: 1, max: 100 });
  return name.includes('age') ? 30 : 1;
}

module.exports = { generateRealisticBody };
