'use strict';

const { createCdpDriver } = require('./cdp-driver');

const DEFAULT_CAPTURE_WINDOW_MS = 5000;

async function traceRuntimeRoutes(frontendRoutes, config, options = {}) {
  const runtimeConfig = (config.analyze && config.analyze.runtime) || {};
  const warnings = options.warnings || [];
  const driver = options.driver || createCdpDriver(runtimeConfig);
  const runtimeCalls = new Map();
  const domSnapshots = {};

  try {
    for (const routePath of frontendRoutes.keys()) {
      const url = buildRouteUrl(routePath, config, runtimeConfig);
      try {
        const trace = await driver.traceRoute(url, {
          navigationTimeoutMs: runtimeConfig.navigationTimeoutMs || 30000,
          captureWindowMs: runtimeConfig.captureWindowMs || DEFAULT_CAPTURE_WINDOW_MS,
        });
        const calls = extractApiCallsFromRequests(trace.requests || [], routePath, config);
        runtimeCalls.set(routePath, calls);
        if (trace.domSnapshot) {
          domSnapshots[routePath] = trace.domSnapshot;
        }
      } catch (err) {
        warnings.push({
          route: routePath,
          url,
          phase: 'runtime-trace',
          error: err && err.message ? err.message : String(err),
        });
        runtimeCalls.set(routePath, []);
      }
    }
  } finally {
    if (!options.driver && driver && typeof driver.close === 'function') {
      await driver.close();
    }
  }

  return { runtimeCalls, domSnapshots, warnings };
}

function extractApiCallsFromRequests(requests, routePath, config) {
  const prefixes = normalizePrefixes(config.frontendApiPrefix || '/api');
  const seen = new Set();
  const calls = [];

  for (const request of requests) {
    const method = String(request.method || 'GET').toUpperCase();
    const requestPath = requestPathname(request.url);
    if (!requestPath || !prefixes.some(prefix => requestPath === prefix || requestPath.startsWith(prefix + '/'))) {
      continue;
    }

    const key = `${method} ${requestPath}`;
    if (seen.has(key)) continue;
    seen.add(key);
    calls.push({
      method,
      path: requestPath,
      rawPath: request.url,
      callSite: `runtime:${routePath}`,
      source: 'runtime',
      routePath,
    });
  }

  return calls;
}

function buildRouteUrl(routePath, config, runtimeConfig = {}) {
  const base = runtimeConfig.baseUrl || config.frontendBaseUrl || config.baseUrl;
  const cleanBase = String(base || '').replace(/\/$/, '');
  const cleanRoute = routePath === '/' ? '/' : '/' + String(routePath || '').replace(/^\/+/, '');
  return cleanBase + cleanRoute;
}

function requestPathname(url) {
  try {
    return new URL(url).pathname;
  } catch {
    return String(url || '').split('?')[0];
  }
}

function normalizePrefixes(prefix) {
  return (Array.isArray(prefix) ? prefix : [prefix])
    .filter(Boolean)
    .map(item => item === '/' ? '/' : String(item).replace(/\/$/, ''));
}

module.exports = {
  traceRuntimeRoutes,
  extractApiCallsFromRequests,
  buildRouteUrl,
};
