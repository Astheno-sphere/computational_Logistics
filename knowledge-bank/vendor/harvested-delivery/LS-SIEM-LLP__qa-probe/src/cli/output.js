'use strict';

const chalk = require('chalk');
const Table = require('cli-table3');

function scoreColor(score) {
  if (score >= 80) return chalk.green;
  if (score >= 50) return chalk.yellow;
  return chalk.red;
}

function statusIcon(status) {
  switch (status) {
    case 'healthy':  return chalk.green('✓');
    case 'degraded': return chalk.yellow('⚠');
    case 'broken':   return chalk.red('✗');
    default:         return chalk.gray('?');
  }
}

function printSummary(report) {
  const score = report.overallScore || 0;
  const color = scoreColor(score);

  console.log('');
  console.log(chalk.bold('─── qa-probe report ───────────────────────────────'));
  console.log(`  Overall score: ${color.bold(score + '/100')}`);
  console.log('');

  // Root cause summary
  if (report.rootCauseSummary && Object.keys(report.rootCauseSummary).length > 0) {
    console.log(chalk.bold('  Root causes:'));
    for (const [cause, data] of Object.entries(report.rootCauseSummary)) {
      console.log(`    ${chalk.cyan(displayCause(cause))}: ${data.count} endpoint(s)`);
    }
    if (report.endpointDiagnostics && report.endpointDiagnostics.length > 0) {
      const high = report.endpointDiagnostics.filter(d => d.severity === 'high' || d.severity === 'critical').length;
      const mapped = report.endpointDiagnostics.filter(d => d.affectedRouteCount > 0).length;
      console.log(`    ${chalk.gray('diagnostics')}: ${report.endpointDiagnostics.length} issue(s), ${high} high severity, ${mapped} mapped to route(s)`);
    }
    console.log('');
  }

  // Route table
  const table = new Table({
    head: [
      chalk.bold('Route'),
      chalk.bold('Score'),
      chalk.bold('Status'),
      chalk.bold('Root Cause'),
    ],
    colWidths: [32, 8, 12, 40],
    style: { head: [], border: [] },
  });

  const routeEntries = Object.entries(report.routes || {})
    .sort((a, b) => (a[1].score || 0) - (b[1].score || 0));

  for (const [route, data] of routeEntries) {
    const s = data.score || 0;
    const color = scoreColor(s);
    table.push([
      route.length > 30 ? route.slice(0, 29) + '…' : route,
      color(String(s)),
      statusIcon(data.status) + ' ' + (data.status || '?'),
      displayCause(data.rootCause || '').replace(/_/g, ' '),
    ]);
  }

  console.log(table.toString());

  // Regression summary
  if (report.regression) {
    const { newFailures = [], newPasses = [] } = report.regression;
    if (newFailures.length > 0) {
      console.log('');
      console.log(chalk.red.bold(`  ⚠  New failures (${newFailures.length}):`));
      newFailures.forEach(f => console.log(`    ${chalk.red('✗')} ${f}`));
    }
    if (newPasses.length > 0) {
      console.log('');
      console.log(chalk.green.bold(`  ✓  Newly passing (${newPasses.length}):`));
      newPasses.forEach(p => console.log(`    ${chalk.green('✓')} ${p}`));
    }
  }

  console.log('');
}

function printGraphSummary(graph) {
  const routeCount = Object.keys(graph.frontendRoutes || {}).length;
  const backendCount = Object.keys(graph.backendRoutes || {}).length;
  const callCount = Object.values(graph.frontendRoutes || {})
    .reduce((n, r) => n + (r.apiCalls ? r.apiCalls.length : 0), 0);
  const flagCount = Object.keys(graph.featureFlags || {}).length;

  console.log('');
  console.log(chalk.bold('─── analyze graph ──────────────────────────────────'));
  console.log(`  Frontend routes : ${chalk.cyan(routeCount)}`);
  console.log(`  Backend routes  : ${chalk.cyan(backendCount)}`);
  console.log(`  API call sites  : ${chalk.cyan(callCount)}`);
  console.log(`  Feature flags   : ${chalk.cyan(flagCount)}`);
  if (graph.meta && graph.meta.headless) {
    console.log(`  Mode            : ${chalk.yellow('headless (no OpenAPI)')}`);
  }
  console.log('');
}

function printProbeResults(results) {
  const entries = Object.entries(results || {});
  const ok = entries.filter(([, v]) => v.status === 200).length;
  const errors = entries.filter(([, v]) => v.status && v.status !== 200).length;
  const empty = entries.filter(([, v]) => v.empty).length;

  console.log('');
  console.log(chalk.bold('─── probe results ──────────────────────────────────'));
  console.log(`  Probed : ${chalk.cyan(entries.length)} endpoints`);
  console.log(`  OK     : ${chalk.green(ok)}`);
  console.log(`  Error  : ${chalk.red(errors)}`);
  console.log(`  Empty  : ${chalk.yellow(empty)} (200 but no data)`);
  console.log('');
}

function displayCause(rootCause) {
  if (rootCause === 'empty_db') return 'no_data';
  if (rootCause === 'expected_empty') return 'expected_empty';
  if (rootCause === 'sample_unavailable') return 'sample_unavailable';
  if (rootCause === 'invalid_sample_params') return 'invalid_sample';
  if (rootCause === 'unknown') return 'needs_review';
  return rootCause || 'ok';
}

module.exports = { printSummary, printGraphSummary, printProbeResults };
