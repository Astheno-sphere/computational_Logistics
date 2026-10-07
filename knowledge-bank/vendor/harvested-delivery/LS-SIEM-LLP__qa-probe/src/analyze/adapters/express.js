'use strict';

const fastapi = require('./fastapi');

async function fetchSpec(config, http) {
  const candidates = [
    config.openApiUrl,
    '/api-docs/swagger.json',
    '/swagger.json',
    '/api/swagger.json',
  ].filter(Boolean);

  let openapi = null;
  let specUrl = null;
  for (const url of candidates) {
    try {
      const res = await http.get(url);
      if (res.data && (res.data.openapi || res.data.swagger)) {
        openapi = res.data;
        specUrl = url;
        break;
      }
    } catch {
      // try next
    }
  }

  if (!openapi) {
    process.stderr.write(
      `[qa-probe] OpenAPI spec not found for Express app. Tried: ${candidates.join(', ')}\n` +
      `[qa-probe] Falling back to headless mode.\n`
    );
    return { routes: {}, featureFlags: {}, specUrl: null, framework: 'express', headless: true, rawSpec: null };
  }

  return {
    routes: fastapi.normalizeOpenApiRoutes(openapi),
    featureFlags: {},
    specUrl,
    framework: 'express',
    headless: false,
    rawSpec: openapi,
  };
}

function isAuthRequired(path, spec) {
  return fastapi.isAuthRequired(path, spec);
}

function buildAuthRequest(config) {
  return fastapi.buildAuthRequest(config);
}

function extractToken(loginResponse, config) {
  return fastapi.extractToken(loginResponse, config);
}

module.exports = { fetchSpec, isAuthRequired, buildAuthRequest, extractToken };
