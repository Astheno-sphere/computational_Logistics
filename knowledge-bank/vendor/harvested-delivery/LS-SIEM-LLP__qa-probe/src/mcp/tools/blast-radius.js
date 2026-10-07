'use strict';

module.exports = {
  name: 'qa_probe_get_blast_radius',
  description: 'Find out how many frontend routes would break if a backend endpoint goes down. Ask: "What pages break if GET /alerts goes down?"',
  inputSchema: {
    type: 'object',
    properties: {
      endpoint: { type: 'string', description: 'Backend endpoint key, e.g. "GET /alerts"' },
    },
    required: ['endpoint'],
  },
  async execute({ endpoint } = {}, { graph }) {
    if (!graph) return { error: 'No graph available. Run qa-probe analyze first.' };

    // Direct lookup
    const direct = graph.blastRadius && graph.blastRadius[endpoint];
    if (direct) {
      return {
        endpoint,
        affectedRouteCount: direct.calledByCount,
        affectedRoutes: direct.calledByRoutes,
      };
    }

    // Try case-insensitive or partial match
    const allKeys = Object.keys(graph.blastRadius || {});
    const match = allKeys.find(k => k.toLowerCase() === endpoint.toLowerCase());
    if (match) {
      const d = graph.blastRadius[match];
      return {
        endpoint: match,
        affectedRouteCount: d.calledByCount,
        affectedRoutes: d.calledByRoutes,
      };
    }

    // Show what we have
    const topByImpact = allKeys
      .map(k => ({ endpoint: k, count: graph.blastRadius[k].calledByCount }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);

    return {
      error: `Endpoint "${endpoint}" not in blast radius map.`,
      hint: 'Top endpoints by impact:',
      topByImpact,
    };
  },
};
