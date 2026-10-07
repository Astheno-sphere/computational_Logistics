'use strict';

const fs = require('fs');
const path = require('path');
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;

async function fetchSpec(config) {
  const trpcConfig = config.trpc || {};
  const endpoint = trpcConfig.endpoint || '/api/trpc';
  const routerFile = path.resolve(process.cwd(), trpcConfig.routerFile || config.trpcRouter || './server/routers/index.ts');
  const source = fs.readFileSync(routerFile, 'utf8');
  const procedures = extractProcedures(source);

  return {
    routes: normalizeTrpcProcedures(procedures, endpoint),
    featureFlags: {},
    specUrl: routerFile,
    framework: 'trpc',
    headless: false,
    rawSpec: { routerFile, procedures },
  };
}

function extractProcedures(source) {
  const ast = parser.parse(source, {
    sourceType: 'module',
    plugins: ['typescript', 'jsx'],
    errorRecovery: true,
  });
  const procedures = [];

  traverse(ast, {
    ObjectProperty(pathNode) {
      const name = getPropertyName(pathNode.node.key);
      const procedureType = getProcedureType(pathNode.node.value);
      if (name && procedureType) {
        procedures.push({ name, type: procedureType });
      }
    },
  });

  return procedures;
}

function normalizeTrpcProcedures(procedures, endpoint = '/api/trpc') {
  const routes = {};
  for (const procedure of procedures || []) {
    const method = procedure.type === 'subscription' ? 'GET' : 'POST';
    const key = `${method} ${endpoint}/${procedure.name}`;
    routes[key] = {
      summary: `tRPC ${procedure.type} ${procedure.name}`,
      tags: ['trpc', procedure.type],
      requiresAuth: false,
      parameters: [],
      requestBody: {
        content: {
          'application/json': {
            schema: { type: 'object' },
          },
        },
      },
      responseSchema: null,
      trpc: { procedure: procedure.name, type: procedure.type },
    };
  }
  return routes;
}

function getProcedureType(node) {
  let current = node;
  while (current) {
    if (current.type === 'CallExpression') {
      const calleeType = getMemberName(current.callee);
      if (['query', 'mutation', 'subscription'].includes(calleeType)) return calleeType;
      current = current.callee && current.callee.object;
      continue;
    }
    if (current.type === 'MemberExpression') {
      const member = getMemberName(current);
      if (['query', 'mutation', 'subscription'].includes(member)) return member;
      current = current.object;
      continue;
    }
    return null;
  }
  return null;
}

function getMemberName(node) {
  if (!node || node.type !== 'MemberExpression') return null;
  return getPropertyName(node.property);
}

function getPropertyName(node) {
  if (!node) return null;
  if (node.type === 'Identifier') return node.name;
  if (node.type === 'StringLiteral') return node.value;
  return null;
}

function isAuthRequired() {
  return false;
}

function buildAuthRequest() {
  return null;
}

function extractToken() {
  return {};
}

module.exports = {
  fetchSpec,
  extractProcedures,
  normalizeTrpcProcedures,
  isAuthRequired,
  buildAuthRequest,
  extractToken,
};
