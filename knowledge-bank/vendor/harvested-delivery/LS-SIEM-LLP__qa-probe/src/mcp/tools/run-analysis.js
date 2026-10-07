'use strict';

module.exports = {
  name: 'qa_probe_run_analysis',
  description: 'Trigger a full qa-probe pipeline (analyze + probe + report) and return a summary. Ask: "Run a full QA check and give me the summary."',
  inputSchema: {
    type: 'object',
    properties: {
      headless: {
        type: 'boolean',
        description: 'Run in headless mode (no OpenAPI fetch). Default: false.',
      },
    },
  },
  async execute({ headless = false } = {}, { config, updateState }) {
    if (!config) return { error: 'No config loaded.' };

    try {
      const { runAnalyze } = require('../../analyze');
      const { runProbe } = require('../../probe');
      const { runReport } = require('../../report');

      const graph = await runAnalyze(config, { headless });
      const probeResults = await runProbe(graph, config);
      const report = await runReport(graph, probeResults, config);

      // Update the MCP server's in-memory state
      if (updateState) updateState({ graph, probeResults, report });

      return {
        overallScore: report.overallScore,
        routeCount: Object.keys(report.routes || {}).length,
        brokenRoutes: Object.entries(report.routes || {})
          .filter(([, d]) => d.status !== 'healthy')
          .map(([r, d]) => ({ route: r, score: d.score, cause: d.rootCause })),
        rootCauseSummary: report.rootCauseSummary,
        regression: report.regression,
        outputDir: config.output.dir,
      };
    } catch (err) {
      return { error: err.message };
    }
  },
};
