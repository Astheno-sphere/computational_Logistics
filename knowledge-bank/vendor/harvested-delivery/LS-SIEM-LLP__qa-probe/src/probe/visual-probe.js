'use strict';

const path = require('path');
const { createCdpDriver } = require('../analyze/cdp-driver');
const { getOutputDir, ensureDir } = require('../cache');
const { scoreRoute } = require('../report/scorer');
const { classifyEndpoint } = require('../report/root-cause');

async function runVisualProbe(graph, probeResults, config, options = {}) {
  const visualConfig = (config.probe && config.probe.visual) || {};
  const threshold = visualConfig.densityThreshold === undefined ? 0.10 : visualConfig.densityThreshold;
  const viewport = {
    width: visualConfig.viewportWidth || 1280,
    height: visualConfig.viewportHeight || 720,
  };
  const routeResults = {};
  const syntheticResults = {};
  const warnings = [];
  const driver = options.driver || createCdpDriver({
    ...((config.analyze && config.analyze.runtime) || {}),
    viewport,
    ignoreHTTPSErrors: config.probe && config.probe.ignoreHTTPSErrors,
  });

  try {
    for (const [routePath, routeData] of Object.entries(graph.frontendRoutes || {})) {
      if (routePath === '__unmatched__') continue;
      const endpointCauses = classifyRouteEndpoints(routeData, probeResults, graph, config);
      const httpScore = scoreRoute(routePath, routeData, probeResults, endpointCauses, config).score;
      if (httpScore < 80) continue;

      const routeUrl = buildVisualRouteUrl(routePath, config);
      try {
        const capture = await driver.captureRoute(routeUrl, {
          viewport,
          screenshotPath: screenshotPathFor(routePath, config),
          navigationTimeoutMs: visualConfig.navigationTimeoutMs || 30000,
        });
        const density = capture.density || {};
        const result = {
          type: 'visual',
          status: 200,
          routePath,
          routeUrl,
          httpScore,
          density: density.density || 0,
          densityThreshold: threshold,
          screenshotPath: capture.screenshotPath || null,
          textNodeCount: density.textNodeCount || 0,
          imageCount: density.imageCount || 0,
          nonEmptyContainerCount: density.nonEmptyContainerCount || 0,
        };
        routeResults[routePath] = result;
        syntheticResults[`VISUAL ${routePath}`] = result;
      } catch (err) {
        warnings.push({
          route: routePath,
          phase: 'visual-probe',
          error: err && err.message ? err.message : String(err),
        });
      }
    }
  } finally {
    if (!options.driver && driver && typeof driver.close === 'function') {
      await driver.close();
    }
  }

  return { routeResults, syntheticResults, warnings };
}

function classifyRouteEndpoints(routeData, probeResults, graph, config) {
  const causes = {};
  for (const call of routeData.apiCalls || []) {
    const key = `${call.method} ${call.backendPath || call.path}`;
    causes[key] = classifyEndpoint(key, probeResults[key], graph, config);
  }
  return causes;
}

function buildVisualRouteUrl(routePath, config) {
  const runtimeConfig = (config.analyze && config.analyze.runtime) || {};
  const base = runtimeConfig.baseUrl || config.frontendBaseUrl || config.baseUrl;
  const cleanBase = String(base || '').replace(/\/$/, '');
  const cleanRoute = routePath === '/' ? '/' : '/' + String(routePath || '').replace(/^\/+/, '');
  return cleanBase + cleanRoute;
}

function screenshotPathFor(routePath, config) {
  const dir = path.join(getOutputDir(config), 'visual');
  ensureDir(dir);
  const safeName = routePath === '/' ? 'root' : routePath.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '');
  return path.join(dir, `${safeName || 'route'}.png`);
}

module.exports = {
  runVisualProbe,
  buildVisualRouteUrl,
  classifyRouteEndpoints,
};
