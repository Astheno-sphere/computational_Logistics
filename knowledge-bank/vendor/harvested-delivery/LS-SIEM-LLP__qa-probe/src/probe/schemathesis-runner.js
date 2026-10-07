'use strict';

const { spawn } = require('child_process');
const { parseSchemathesisOutput } = require('./schemathesis-parser');

function runSchemathesis(config, options = {}) {
  const cfg = ((config || {}).probe || {}).schemathesis || {};
  if (!cfg.enabled) return Promise.resolve([]);
  const command = cfg.command || 'schemathesis';
  const args = ['run', config.openApiUrl || '/openapi.json', '--checks', 'all', '--hypothesis-max-examples', String(cfg.hypothesisExamples || 50), '--report', 'json'];
  const spawnFn = options.spawn || spawn;
  return new Promise((resolve) => {
    const child = spawnFn(command, args, { timeout: cfg.timeoutMs || 300000 });
    let stdout = '';
    let stderr = '';
    child.stdout && child.stdout.on('data', chunk => { stdout += chunk; });
    child.stderr && child.stderr.on('data', chunk => { stderr += chunk; });
    child.on('error', err => {
      resolve([{ rootCause: 'validation_edge_case', error: `${command} unavailable: ${err.message}. Install schemathesis with pip to enable this probe.` }]);
    });
    child.on('close', () => {
      setImmediate(() => {
        try {
          resolve(parseSchemathesisOutput(stdout));
        } catch (err) {
          resolve([{ rootCause: 'validation_edge_case', error: stderr || err.message }]);
        }
      });
    });
  });
}

module.exports = { runSchemathesis };
