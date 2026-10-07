'use strict';

module.exports = {
  name: 'qa_probe_explain_failure',
  description: 'Explain in plain English why a specific frontend route is showing no data or failing. Ask: "Why is /rules showing no data?"',
  inputSchema: {
    type: 'object',
    properties: {
      route: { type: 'string', description: 'Frontend route path (e.g. /rules)' },
    },
    required: ['route'],
  },
  async execute({ route } = {}, { report, graph, probeResults }) {
    if (!report || !graph) return { error: 'No report or graph available. Run qa-probe run first.' };

    const routeData = report.routes && report.routes[route];
    if (!routeData) {
      return { error: `Route "${route}" not in report. Available routes: ${Object.keys(report.routes || {}).slice(0, 10).join(', ')}` };
    }

    const graphRoute = graph.frontendRoutes && graph.frontendRoutes[route];
    const apiCalls = (graphRoute && graphRoute.apiCalls) || [];
    const callDetails = [];

    // Index the per-endpoint diagnostics so each call can carry its classification,
    // confidence, and verifiable evidence — not just a status code.
    const diagByKey = {};
    for (const d of (report.endpointDiagnostics || [])) diagByKey[d.endpoint] = d;

    for (const call of apiCalls) {
      const key = `${call.method} ${call.backendPath || call.path}`;
      const probe = probeResults && probeResults[key];
      const diag = diagByKey[key];
      callDetails.push({
        call: key,
        callSite: call.callSite,
        status: probe ? probe.status : 'not probed',
        ms: probe ? probe.ms : null,
        empty: probe ? probe.empty : null,
        itemCount: probe ? probe.itemCount : null,
        rootCause: diag ? diag.rootCause : null,
        // Calibrated confidence: how much the diagnosis should be trusted.
        // 'none' means qa-probe could not classify this — treat it as unverified.
        confidence: diag ? diag.confidence : null,
        // Raw, verifiable evidence (sanitized): the request issued and what the
        // server actually returned. Check this rather than trusting the label.
        evidence: probe ? probe.evidence || null : null,
      });
    }

    const unclassified = callDetails.filter(c => c.rootCause === 'unknown' || c.confidence === 'none');

    return {
      route,
      score: routeData.score,
      status: routeData.status,
      rootCause: routeData.rootCause,
      rootCauseDetail: routeData.rootCauseDetail,
      fixHint: routeData.fixHint,
      // Transparency contract for AI consumers: be explicit when a result is NOT verified.
      trust: unclassified.length > 0
        ? `${unclassified.length} of ${callDetails.length} calls are UNCLASSIFIED (confidence: none). qa-probe has no rule for them — treat them as unverified, inspect each call's evidence, and do not report them as passing.`
        : 'All probed calls were classified with a known rule; inspect each call\'s evidence to verify.',
      apiCalls: callDetails,
      featureFlag: graph.featureFlags && graph.featureFlags[route],
    };
  },
};
