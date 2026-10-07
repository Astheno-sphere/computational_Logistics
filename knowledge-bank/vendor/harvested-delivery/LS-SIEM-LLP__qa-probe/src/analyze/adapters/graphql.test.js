'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { fetchSpec, normalizeGraphqlSchema } = require('./graphql');
const { getAdapter } = require('../backend-fetcher');
const { ConfigSchema } = require('../../config/schema');

test('GraphQL adapter converts introspection queries and mutations into endpoints', async () => {
  const http = {
    post: async () => ({
      data: {
        data: {
          __schema: {
            queryType: {
              fields: [{ name: 'cases', args: [{ name: 'filter', type: { name: 'String' } }], type: { name: 'CaseList' } }],
            },
            mutationType: {
              fields: [{ name: 'createCase', args: [{ name: 'input', type: { name: 'CaseInput' } }], type: { name: 'Case' } }],
            },
          },
        },
      },
    }),
  };

  const spec = await fetchSpec({
    graphql: { endpoint: '/graphql', authToken: 'test-token' },
  }, http);

  assert.deepEqual(Object.keys(spec.routes).sort(), [
    'POST /graphql#mutation.createCase',
    'POST /graphql#query.cases',
  ]);
  assert.equal(spec.routes['POST /graphql#query.cases'].requiresAuth, true);
  assert.deepEqual(spec.routes['POST /graphql#query.cases'].parameters, ['filter']);
});

test('GraphQL route normalizer handles missing mutation type', () => {
  const routes = normalizeGraphqlSchema({
    queryType: { fields: [{ name: 'viewer', args: [], type: { name: 'String' } }] },
  });

  assert.equal(Object.keys(routes).length, 1);
  assert.equal(routes['POST /graphql#query.viewer'].responseSchema.properties.data.properties.viewer.type, 'string');
});

test('config and backend fetcher register the graphql framework', () => {
  const config = ConfigSchema.parse({
    baseUrl: 'http://localhost:3000',
    framework: 'graphql',
  });

  assert.equal(config.graphql.endpoint, '/graphql');
  assert.equal(getAdapter(config.framework), require('./graphql'));
});
