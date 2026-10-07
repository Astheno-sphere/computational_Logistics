'use strict';

const { loadConfig } = require('../../config/loader');
const { runAnalyze } = require('../../analyze');
const { printGraphSummary } = require('../output');

module.exports = async function analyze(opts) {
  try {
    const config = loadConfig(opts.config);
    if (opts.headless) config._headless = true;
    const graph = await runAnalyze(config, { headless: opts.headless });
    printGraphSummary(graph);
    process.exit(0);
  } catch (err) {
    console.error(`\nError: ${err.message}`);
    if (process.env.DEBUG) console.error(err.stack);
    process.exit(1);
  }
};
