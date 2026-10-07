'use strict';

const { generateMinimalBody } = require('./body-strategies/minimal');
const { generateRealisticBody } = require('./body-strategies/realistic');
const { generateExampleBody } = require('./body-strategies/example');
const { generateHarBody } = require('./body-strategies/har');

function generateBody(endpoint, schema, strategy = 'minimal', config = {}) {
  if (strategy === 'empty') return undefined;
  if (strategy === 'har') return generateHarBody(endpoint, schema, config);
  if (strategy === 'example') return generateExampleBody(schema) || generateMinimalBody(schema);
  if (strategy === 'realistic') return generateRealisticBody(schema);
  return generateMinimalBody(schema);
}

function resolvePostBodyMode(endpoint, config) {
  const probeConfig = (config && config.probe) || {};
  const overrides = probeConfig.postBodyOverrides || {};
  const endpointPath = endpoint.path || '';
  for (const [pattern, mode] of Object.entries(overrides)) {
    if (globMatches(pattern, endpointPath)) return mode;
  }
  return probeConfig.postBodyMode || 'minimal';
}

function requestBodySchema(routeInfo) {
  const body = routeInfo && routeInfo.requestBody;
  if (!body) return null;
  if (body.content && body.content['application/json']) {
    return body.content['application/json'].schema || null;
  }
  return body.schema || body;
}

function globMatches(pattern, value) {
  const escaped = pattern
    .replace(/[.+^${}()|[\]\\]/g, '\\$&')
    .replace(/\*/g, '.*');
  return new RegExp(`^${escaped}$`).test(value);
}

module.exports = { generateBody, resolvePostBodyMode, requestBodySchema, globMatches };
