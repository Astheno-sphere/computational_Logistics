'use strict';

const { Command } = require('commander');
const pkg = require('../../package.json');

const program = new Command();

program
  .name('qa-probe')
  .description('Local QA agent — maps frontend routes → backend APIs, probes live, scores pages 0–100')
  .version(pkg.version);

program
  .command('analyze')
  .description('Parse frontend source + fetch backend OpenAPI spec → writes .qaprobe/graph.json')
  .option('-c, --config <path>', 'path to qa-probe.config.js', './qa-probe.config.js')
  .option('--headless', 'skip OpenAPI fetch, discover endpoints from frontend source only')
  .action((opts) => {
    require('./commands/analyze')(opts);
  });

program
  .command('probe')
  .description('Authenticate + hit every mapped endpoint → writes .qaprobe/probe-results.json')
  .option('-c, --config <path>', 'path to qa-probe.config.js', './qa-probe.config.js')
  .action((opts) => {
    require('./commands/probe')(opts);
  });

program
  .command('report')
  .description('Root-cause analysis + score routes → writes report.json, report.md, ai-context.md')
  .option('-c, --config <path>', 'path to qa-probe.config.js', './qa-probe.config.js')
  .option('--fail-under <score>', 'exit 1 if overall score < N (CI gate)', parseInt)
  .action((opts) => {
    require('./commands/report')(opts);
  });

program
  .command('fix')
  .description('Generate high-confidence remediation diffs from the latest qa-probe report')
  .option('-c, --config <path>', 'path to qa-probe.config.js', './qa-probe.config.js')
  .option('--apply', 'apply high-confidence fixes to disk')
  .option('--pr', 'prepare changes for a pull request branch')
  .action((opts) => {
    require('./commands/fix')(opts);
  });

program
  .command('label <endpoint> <verdict>')
  .description('Record feedback on a diagnosis, reapplied on future runs. verdict: expected|ignore|known_gate|ok (suppress) or bug|real_bug|confirm.')
  .option('-c, --config <path>', 'path to qa-probe.config.js', './qa-probe.config.js')
  .option('-r, --reason <text>', 'why this verdict (recommended — it is the audit trail)')
  .option('-s, --signal <rootCause>', 'only apply while the endpoint produces this rootCause (default: any)')
  .option('--by <name>', 'who recorded this (default: human)')
  .action((endpoint, verdict, opts) => {
    require('./commands/label')(endpoint, verdict, opts);
  });

program
  .command('mcp')
  .description('Start MCP server over stdio — wires qa-probe tools into Claude and Codex')
  .option('-c, --config <path>', 'path to qa-probe.config.js', './qa-probe.config.js')
  .action((opts) => {
    require('./commands/mcp')(opts);
  });

program
  .command('run')
  .description('Run analyze → probe → report in sequence (all-in-one pipeline)')
  .option('-c, --config <path>', 'path to qa-probe.config.js', './qa-probe.config.js')
  .option('--fail-under <score>', 'exit 1 if overall score < N (CI gate)', parseInt)
  .option('--headless', 'skip OpenAPI fetch, discover endpoints from frontend source only')
  .action((opts) => {
    require('./commands/run')(opts);
  });

program.parse(process.argv);
