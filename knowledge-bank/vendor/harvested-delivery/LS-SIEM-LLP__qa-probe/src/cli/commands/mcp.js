'use strict';

const { loadConfig } = require('../../config/loader');
const { startMcpServer } = require('../../mcp/server');

module.exports = async function mcp(opts) {
  try {
    const config = loadConfig(opts.config);
    await startMcpServer(config);
  } catch (err) {
    console.error(`\nError: ${err.message}`);
    if (process.env.DEBUG) console.error(err.stack);
    process.exit(1);
  }
};
