'use strict';

/**
 * Summarize blast radius: for each backend route that has failures,
 * show how many frontend routes would be impacted.
 */
function getBlastRadiusSummary(graph, probeResults, rootCauses) {
  const summary = {};

  for (const [endpointKey, cause] of Object.entries(rootCauses)) {
    if (cause.rootCause === 'ok' || cause.rootCause === 'slow_but_working') continue;

    const blastData = graph.blastRadius && graph.blastRadius[endpointKey];
    const calledByCount = (blastData && blastData.calledByCount) || 0;
    const calledByRoutes = (blastData && blastData.calledByRoutes) || [];

    if (calledByCount > 0) {
      summary[endpointKey] = {
        rootCause: cause.rootCause,
        affectedRouteCount: calledByCount,
        affectedRoutes: calledByRoutes,
      };
    }
  }

  // Sort by most impactful
  return Object.entries(summary)
    .sort((a, b) => b[1].affectedRouteCount - a[1].affectedRouteCount)
    .reduce((acc, [k, v]) => { acc[k] = v; return acc; }, {});
}

module.exports = { getBlastRadiusSummary };
