'use strict';

module.exports = {
  name: 'qa_probe_get_report',
  description: 'Get the QA report with route scores and root causes. Ask: "Show me all broken routes" or "What is the overall score?"',
  inputSchema: {
    type: 'object',
    properties: {
      filter: {
        type: 'string',
        enum: ['all', 'broken', 'degraded', 'healthy'],
        description: 'Filter routes by status. Default: all.',
      },
    },
  },
  async execute({ filter = 'all' } = {}, { report }) {
    if (!report) return { error: 'No report available. Run qa-probe run first.' };

    let routes = Object.entries(report.routes || {});
    if (filter === 'broken') routes = routes.filter(([, d]) => d.status === 'broken');
    else if (filter === 'degraded') routes = routes.filter(([, d]) => d.status === 'degraded');
    else if (filter === 'healthy') routes = routes.filter(([, d]) => d.status === 'healthy');

    return {
      overallScore: report.overallScore,
      routeCount: routes.length,
      rootCauseSummary: report.rootCauseSummary,
      regression: report.regression,
      routes: Object.fromEntries(routes),
    };
  },
};
