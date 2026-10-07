'use strict';

const fs = require('fs');
const path = require('path');
const { loadConfig } = require('../../config');
const { buildRemediations, renderFixes, applyFixes } = require('../../remediate');

module.exports = async function fixCommand(opts) {
  const config = await loadConfig(opts.config);
  const outDir = path.resolve(process.cwd(), config.output.dir);
  const graph = readJson(path.join(outDir, 'graph.json'));
  const probeResults = readJson(path.join(outDir, 'probe-results.json'));
  const report = readJson(path.join(outDir, 'report.json'));
  const fixes = buildRemediations(graph, probeResults, report, config);

  if (opts.apply || opts.pr) {
    const applied = applyFixes(fixes, process.cwd());
    process.stdout.write(`${applied.filter(item => item.applied).length} fix(es) applied.\n`);
    if (opts.pr) {
      process.stdout.write('PR mode prepared local changes. Create the branch/commit/PR with your git tooling.\n');
    }
    return;
  }

  process.stdout.write(renderFixes(fixes));
  process.stdout.write('\n');
};

function readJson(filePath) {
  if (!fs.existsSync(filePath)) return {};
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}
