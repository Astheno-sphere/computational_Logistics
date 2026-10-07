'use strict';

const { loadConfig } = require('../../config/loader');
const { runProbe } = require('../../probe');
const { loadGraph } = require('../../cache');
const { printProbeResults } = require('../output');

module.exports = async function probe(opts) {
  try {
    const config = loadConfig(opts.config);
    const graph = await loadGraph(config);
    if (!graph) {
      console.error('No graph.json found. Run `qa-probe analyze` first.');
      process.exit(1);
    }
    const results = await runProbe(graph, config);
    printProbeResults(results);
    process.exit(0);
  } catch (err) {
    console.error(`\nError: ${err.message}`);
    if (process.env.DEBUG) console.error(err.stack);
    process.exit(1);
  }
};
