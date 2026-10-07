'use strict';

const { loadConfig } = require('../../config/loader');
const { runReport } = require('../../report');
const { loadGraph, loadProbeResults } = require('../../cache');
const { printSummary } = require('../output');

module.exports = async function report(opts) {
  try {
    const config = loadConfig(opts.config);
    const graph = await loadGraph(config);
    if (!graph) {
      console.error('No graph.json found. Run `qa-probe analyze` first.');
      process.exit(1);
    }
    const probeResults = await loadProbeResults(config);
    if (!probeResults) {
      console.error('No probe-results.json found. Run `qa-probe probe` first.');
      process.exit(1);
    }

    const report = await runReport(graph, probeResults, config);
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
