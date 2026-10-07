'use strict';

const fastapi = require('./fastapi');

// Generic adapter — any OpenAPI 3.0 or Swagger 2.0 URL
async function fetchSpec(config, http) {
  const url = config.openApiUrl || '/openapi.json';
  let openapi = null;
  try {
    const res = await http.get(url);
    openapi = res.data;
  } catch (err) {
    process.stderr.write(
      `[qa-probe] OpenAPI spec unavailable at ${url}: ${err.message}\n` +
      `[qa-probe] Falling back to headless mode.\n`
    );
    return { routes: {}, featureFlags: {}, specUrl: url, framework: 'generic', headless: true, rawSpec: null };
  }

  return {
    routes: fastapi.normalizeOpenApiRoutes(openapi),
    featureFlags: {},
    specUrl: url,
    framework: 'generic',
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
