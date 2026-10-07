'use strict';

const { findHarBody } = require('../har-replay');
const { generateMinimalBody } = require('./minimal');

function generateHarBody(endpoint, schema, config) {
  return findHarBody(endpoint, endpoint.routeKey, config) || generateMinimalBody(schema);
}

module.exports = { generateHarBody };
