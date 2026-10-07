'use strict';

const INTROSPECTION_QUERY = '{__schema{queryType{fields{name args{name type{name kind ofType{name kind}}} type{name kind ofType{name kind}}}} mutationType{fields{name args{name type{name kind ofType{name kind}}} type{name kind ofType{name kind}}}}}}';

async function fetchSpec(config, http) {
  const graphqlConfig = config.graphql || {};
  const endpoint = graphqlConfig.endpoint || '/graphql';
  const headers = graphqlConfig.authToken ? { Authorization: `Bearer ${graphqlConfig.authToken}` } : {};
  const res = await http.post(endpoint, { query: INTROSPECTION_QUERY }, { headers });
  const schema = res.data && res.data.data && res.data.data.__schema;

  return {
    routes: normalizeGraphqlSchema(schema, endpoint, !!graphqlConfig.authToken),
    featureFlags: {},
    specUrl: endpoint,
    framework: 'graphql',
    headless: false,
    rawSpec: schema || null,
  };
}

function normalizeGraphqlSchema(schema, endpoint = '/graphql', requiresAuth = false) {
  const routes = {};
  addOperations(routes, endpoint, 'query', schema && schema.queryType && schema.queryType.fields, requiresAuth);
  addOperations(routes, endpoint, 'mutation', schema && schema.mutationType && schema.mutationType.fields, requiresAuth);
  return routes;
}

function addOperations(routes, endpoint, operationType, fields, requiresAuth) {
  for (const field of fields || []) {
    const key = `POST ${endpoint}#${operationType}.${field.name}`;
    routes[key] = {
      summary: `GraphQL ${operationType} ${field.name}`,
      tags: ['graphql', operationType],
      requiresAuth,
      parameters: (field.args || []).map(arg => arg.name),
      requestBody: {
        content: {
          'application/json': {
            schema: {
              type: 'object',
              required: ['query'],
              properties: {
                query: { type: 'string' },
                variables: { type: 'object' },
              },
            },
          },
        },
      },
      responseSchema: {
        type: 'object',
        properties: {
          data: {
            type: 'object',
            properties: {
              [field.name]: graphQlTypeToSchema(field.type),
            },
          },
        },
      },
      graphql: { operationType, field: field.name },
    };
  }
}

function graphQlTypeToSchema(type) {
  const named = unwrapType(type);
  const name = named && named.name;
  if (['Int', 'Float'].includes(name)) return { type: 'number' };
  if (name === 'Boolean') return { type: 'boolean' };
  if (name === 'String' || name === 'ID') return { type: 'string' };
  return { type: 'object' };
}

function unwrapType(type) {
  let current = type;
  while (current && current.ofType) current = current.ofType;
  return current;
}

function isAuthRequired(path, spec) {
  const route = Object.values((spec && spec.routes) || {}).find(item => item.graphql || path === '/graphql');
  return route ? !!route.requiresAuth : false;
}

function buildAuthRequest() {
  return null;
}

function extractToken() {
  return {};
}

module.exports = {
  INTROSPECTION_QUERY,
  fetchSpec,
  normalizeGraphqlSchema,
  isAuthRequired,
  buildAuthRequest,
  extractToken,
};
