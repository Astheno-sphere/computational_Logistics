'use strict';

const fs = require('fs');
const path = require('path');

function writeAiContext(report, graph, config) {
  const lines = [];
  const score = report.overallScore || 0;
  const diagnostics = report.endpointDiagnostics || [];

  lines.push('QA-PROBE AI CONTEXT');
  lines.push(`Base URL: ${report.meta && report.meta.baseUrl}`);
  lines.push(`Generated: ${report.meta && report.meta.generatedAt}`);
  lines.push(`Overall score: ${score}/100`);
  lines.push(`Headless mode: ${(report.meta && report.meta.headless) || false}`);
  lines.push(`Endpoint issues: ${diagnostics.length}`);
  lines.push('NOTE: confidence=none / cause=unknown means qa-probe could NOT classify it — treat as UNVERIFIED, not a pass; inspect the evidence.');
  if (report.baselines) {
    lines.push(`Baselines: ${report.baselines.endpointsWithBaseline} learned / ${report.baselines.runsAnalyzed} runs / ${report.baselines.anomaliesFlagged} anomaly(ies)`);
  }
  if (report.feedback && report.feedback.applied && report.feedback.applied.length) {
    lines.push(`Feedback applied: ${report.feedback.suppressed} suppressed, ${report.feedback.confirmed} confirmed (acknowledged endpoints are known/expected, not bugs)`);
  }
  if (report.writeFlows && report.writeFlows.ran) {
    lines.push(`Write-flows: ${report.writeFlows.passed}/${report.writeFlows.ran} passed, ${report.writeFlows.failed} failed`);
  }
  const secCount = diagnostics.filter(d => ['auth_bypass', 'privilege_escalation', 'pii_leak'].includes(d.rootCause)).length;
  if (secCount) lines.push(`SECURITY FINDINGS: ${secCount} (auth_bypass / privilege_escalation / pii_leak — high priority)`);
  lines.push('');

  const broken = Object.entries(report.routes || {})
    .filter(([, d]) => (d.score || 0) < 80)
    .sort((a, b) => (a[1].score || 0) - (b[1].score || 0));

  if (broken.length > 0) {
    lines.push(`BROKEN/DEGRADED ROUTES (${broken.length}):`);
    for (const [routePath, data] of broken) {
      lines.push(`  ${routePath} -> score=${data.score}, cause=${displayCause(data.rootCause)}`);
      if (data.rootCauseDetail) lines.push(`    detail: ${data.rootCauseDetail}`);
      if (data.fixHint) lines.push(`    fix: ${data.fixHint}`);
    }
    lines.push('');
  }

  if (report.rootCauseSummary && Object.keys(report.rootCauseSummary).length > 0) {
    lines.push('ROOT CAUSES:');
    for (const [cause, data] of Object.entries(report.rootCauseSummary)) {
      lines.push(`  ${displayCause(cause)} (${cause}): ${data.count} endpoint(s) -> ${(data.affectedRoutes || []).slice(0, 5).join(', ')}`);
    }
    lines.push('');
  }

  if (diagnostics.length > 0) {
    lines.push('ENDPOINT DIAGNOSTICS:');
    for (const item of diagnostics.slice(0, 40)) {
      const affected = item.affectedRoutes && item.affectedRoutes.length > 0
        ? item.affectedRoutes.join(', ')
        : 'backend-only/unmatched';
      lines.push(`  ${item.endpoint} -> ${item.label} severity=${item.severity} confidence=${item.confidence} affected=${affected}`);
      if (item.status !== null && item.status !== undefined) lines.push(`    status=${item.status} ms=${item.ms}`);
      if (item.emptyReason) lines.push(`    empty_signal=${item.emptyReason}`);
      if (item.error) lines.push(`    error=${item.error}`);
      if (item.detail) lines.push(`    detail=${item.detail}`);
    }
    lines.push('');
  }

  if (report.blastRadius && Object.keys(report.blastRadius).length > 0) {
    lines.push('HIGH BLAST RADIUS:');
    for (const [ep, data] of Object.entries(report.blastRadius)) {
      lines.push(`  ${ep} (${displayCause(data.rootCause)}) -> affects ${data.affectedRouteCount} routes`);
    }
    lines.push('');
  }

  const disabledFlags = Object.entries(graph.featureFlags || {})
    .filter(([, f]) => !f.included || !f.enabled);
  if (disabledFlags.length > 0) {
    lines.push('DISABLED FEATURE FLAGS:');
    disabledFlags.forEach(([prefix, flag]) => {
      lines.push(`  ${prefix}: included=${flag.included}, enabled=${flag.enabled}`);
    });
    lines.push('');
  }

  if (report.regression) {
    const { newFailures = [], newPasses = [] } = report.regression;
    if (newFailures.length > 0) {
      lines.push(`NEW REGRESSIONS: ${newFailures.join(', ')}`);
      lines.push('');
    }
    if (newPasses.length > 0) {
      lines.push(`NEWLY PASSING: ${newPasses.join(', ')}`);
      lines.push('');
    }
  }

  const healthy = Object.entries(report.routes || {})
    .filter(([, d]) => (d.score || 0) >= 80)
    .map(([r]) => r);
  if (healthy.length > 0) {
    lines.push(`HEALTHY ROUTES (${healthy.length}): ${healthy.slice(0, 20).join(', ')}${healthy.length > 20 ? ' ...' : ''}`);
  }

  const outPath = path.join(process.cwd(), config.output.dir, 'ai-context.md');
  fs.writeFileSync(outPath, lines.join('\n'), 'utf8');
  return outPath;
}

function displayCause(rootCause) {
  if (rootCause === 'empty_db') return 'no_data';
  if (rootCause === 'expected_empty') return 'expected_empty';
  if (rootCause === 'sample_unavailable') return 'sample_unavailable';
  if (rootCause === 'unknown') return 'needs_review';
  if (rootCause === 'invalid_sample_params') return 'invalid_sample';
  return rootCause || 'ok';
}

module.exports = { writeAiContext };
