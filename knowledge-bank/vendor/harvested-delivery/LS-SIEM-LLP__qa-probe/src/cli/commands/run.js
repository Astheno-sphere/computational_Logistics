'use strict';

const { loadConfig } = require('../../config/loader');
const { runAnalyze } = require('../../analyze');
const { runProbe } = require('../../probe');
const { runReport } = require('../../report');
const { printGraphSummary, printProbeResults, printSummary } = require('../output');

module.exports = async function run(opts) {
  try {
    const config = loadConfig(opts.config);

    // Phase 1: Analyze
    const graph = await runAnalyze(config, { headless: opts.headless });
    printGraphSummary(graph);

    // Phase 2: Probe
    const results = await runProbe(graph, config);
    printProbeResults(results);

    // Phase 3: Report
    const report = await runReport(graph, results, config);
    printSummary(report);

    if (opts.failUnder !== undefined && report.overallScore < opts.failUnder) {
      console.error(`Score ${report.overallScore} is below threshold ${opts.failUnder} — failing.`);
      process.exit(1);
    }

    process.exit(0);
  } catch (err) {
    console.error(`\nError: ${err.message}`);
    if (process.env.DEBUG) console.error(err.stack);
    process.exit(1);
  }
};
