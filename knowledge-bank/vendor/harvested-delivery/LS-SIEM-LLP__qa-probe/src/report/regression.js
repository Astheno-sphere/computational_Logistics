'use strict';

/**
 * Compare current report against previous run to detect regressions and new passes.
 */
function detectRegression(currentReport, previousReport) {
  if (!previousReport) return { newFailures: [], newPasses: [], unchanged: [] };

  const prevRoutes = previousReport.routes || {};
  const currRoutes = currentReport.routes || {};

  const newFailures = [];
  const newPasses = [];
  const unchanged = [];

  for (const [routePath, curr] of Object.entries(currRoutes)) {
    const prev = prevRoutes[routePath];
    if (!prev) continue; // new route, not a regression

    const wasHealthy = prev.status === 'healthy';
    const isHealthy = curr.status === 'healthy';

    if (wasHealthy && !isHealthy) {
      newFailures.push(routePath);
    } else if (!wasHealthy && isHealthy) {
      newPasses.push(routePath);
    } else {
      unchanged.push(routePath);
    }
  }

  return { newFailures, newPasses, unchanged };
}

module.exports = { detectRegression };
