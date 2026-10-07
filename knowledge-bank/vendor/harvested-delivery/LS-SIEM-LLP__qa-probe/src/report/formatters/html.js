'use strict';

const fs = require('fs');
const path = require('path');

function writeHtmlReport(report, config) {
  const outPath = path.join(process.cwd(), config.output.dir, 'report.html');
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, renderHtmlReport(report), 'utf8');
  return outPath;
}

function renderHtmlReport(report) {
  const score = Number(report.overallScore || 0);
  const diagnostics = report.endpointDiagnostics || [];
  const routes = Object.entries(report.routes || {});
  const highIssues = diagnostics.filter(d => d.severity === 'critical' || d.severity === 'high');
  const mappedIssues = diagnostics.filter(d => d.affectedRouteCount > 0);
  const noData = diagnostics.filter(d => d.rootCause === 'empty_db');
  const regressions = (report.regression && report.regression.newFailures) || [];
  const newlyPassing = (report.regression && report.regression.newPasses) || [];

  const healthClass = score >= 90 ? 'excellent' : score >= 75 ? 'good' : score >= 50 ? 'warn' : 'bad';
  const generatedAt = formatDate(report.meta && report.meta.generatedAt);
  const title = `qa-probe report - ${score}/100`;

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4f5f7;
      --panel: #ffffff;
      --panel-soft: #f9fafb;
      --text: #101418;
      --muted: #5b6673;
      --line: #d9dee5;
      --line-soft: #edf0f4;
      --blue: #245b9d;
      --green: #1f8a4c;
      --amber: #b7791f;
      --red: #c2413a;
      --ink: #17202a;
      --shadow: none;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      letter-spacing: 0;
    }
    .shell { max-width: 1160px; margin: 0 auto; padding: 28px 22px 54px; }
    .topbar {
      display: flex;
      justify-content: space-between;
      gap: 28px;
      align-items: flex-start;
      margin-bottom: 18px;
      padding-bottom: 18px;
      border-bottom: 2px solid var(--text);
    }
    .brand { display: flex; flex-direction: column; gap: 8px; }
    h1 { margin: 0; font-size: 28px; line-height: 1.12; font-weight: 760; }
    .subtle { color: var(--muted); font-size: 14px; }
    .target { display: inline-flex; gap: 8px; align-items: center; color: var(--muted); font-size: 13px; }
    .target code { color: var(--ink); background: #edf2f7; padding: 3px 7px; border-radius: 6px; }
    .score-card {
      min-width: 230px;
      background: transparent;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 18px;
    }
    .score-row { display: flex; justify-content: space-between; align-items: baseline; gap: 16px; }
    .score { font-size: 42px; line-height: 1; font-weight: 780; }
    .score-label { color: var(--muted); font-size: 12px; text-transform: uppercase; font-weight: 720; }
    .meter { height: 8px; background: #e8ecf1; border-radius: 4px; overflow: hidden; margin-top: 14px; }
    .meter > span { display: block; height: 100%; width: ${clamp(score, 0, 100)}%; background: ${scoreColor(score)}; }
    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 3px 9px;
      border-radius: 4px;
      border: 1px solid var(--line);
      background: var(--panel-soft);
      color: var(--muted);
      font-size: 12px;
      font-weight: 680;
      white-space: nowrap;
    }
    .badge.high, .badge.critical, .badge.bad { border-color: #f4c7c3; background: #fff1f0; color: var(--red); }
    .badge.medium, .badge.warn { border-color: #f1d29b; background: #fff8e7; color: var(--amber); }
    .badge.low, .badge.good { border-color: #bfe4cf; background: #eefaf3; color: var(--green); }
    .badge.info, .badge.excellent { border-color: #b8d4fb; background: #eff6ff; color: var(--blue); }
    .grid { display: grid; gap: 14px; }
    .kpis { grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 18px 0 18px; }
    .kpi { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 14px 15px; }
    .kpi strong { display: block; font-size: 25px; margin-bottom: 5px; }
    .section { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; margin-top: 14px; overflow: hidden; }
    .section-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 16px 18px;
      border-bottom: 1px solid var(--line-soft);
    }
    h2 { margin: 0; font-size: 16px; line-height: 1.25; }
    .section-copy { margin: 4px 0 0; color: var(--muted); font-size: 13px; }
    .body { padding: 16px 18px 18px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th {
      text-align: left;
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .03em;
      border-bottom: 1px solid var(--line);
      padding: 10px 9px;
      white-space: nowrap;
    }
    td { border-bottom: 1px solid var(--line-soft); padding: 11px 9px; vertical-align: top; }
    tr:last-child td { border-bottom: 0; }
    code, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }
    .endpoint { color: var(--ink); font-weight: 680; word-break: break-word; }
    .evidence { color: var(--muted); max-width: 420px; }
    .routes { color: var(--muted); max-width: 280px; }
    .route-name { font-weight: 680; color: var(--ink); }
    .route-score { font-weight: 760; }
    .split { display: grid; grid-template-columns: minmax(0, 1fr) minmax(320px, .62fr); gap: 16px; }
    .summary-list { display: grid; gap: 10px; }
    .summary-item { display: flex; justify-content: space-between; gap: 16px; padding: 10px 12px; background: var(--panel-soft); border: 1px solid var(--line-soft); border-radius: 6px; }
    .summary-item span { color: var(--muted); }
    .empty-state { color: var(--muted); padding: 16px; background: var(--panel-soft); border: 1px dashed var(--line); border-radius: 6px; }
    .footer { color: var(--muted); font-size: 12px; margin-top: 22px; }
    @media (max-width: 860px) {
      .topbar, .split { display: block; }
      .score-card { margin-top: 16px; }
      .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .table-wrap { overflow-x: auto; }
    }
    @media print {
      body { background: #fff; }
      .shell { max-width: none; padding: 18px; }
      .section, .kpi, .score-card { box-shadow: none; break-inside: avoid; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <div class="topbar">
      <div class="brand">
        <h1>qa-probe QA Report</h1>
        <div class="target">
          <span>Target</span>
          <code>${escapeHtml((report.meta && report.meta.baseUrl) || 'unknown')}</code>
        </div>
        <div class="subtle">Generated ${escapeHtml(generatedAt)} from static route analysis and live endpoint probes.</div>
      </div>
      <aside class="score-card">
        <div class="score-row">
          <div>
            <div class="score-label">Overall route health</div>
            <div class="score">${score}<span class="subtle">/100</span></div>
          </div>
          <span class="badge ${healthClass}">${escapeHtml(scoreLabel(score))}</span>
        </div>
        <div class="meter" aria-label="overall score"><span></span></div>
      </aside>
    </div>

    <section class="grid kpis" aria-label="run summary">
      ${kpi('Endpoint issues', diagnostics.length)}
      ${kpi('High severity', highIssues.length)}
      ${kpi('Mapped to UI routes', mappedIssues.length)}
      ${kpi('Frontend routes', routes.length)}
    </section>

    <section class="split">
      <div class="section">
        <div class="section-head">
          <div>
            <h2>Run Summary</h2>
            <p class="section-copy">A compact view of route health, endpoint failures, and likely data gaps.</p>
          </div>
        </div>
        <div class="body summary-list">
          ${summaryItem('Mode', (report.meta && report.meta.headless) ? 'Headless HTTP probe' : 'OpenAPI-backed probe')}
          ${summaryItem('Likely real backend issues', `${highIssues.length} high severity endpoint issue(s)`)}
          ${summaryItem('Likely demo data gaps', `${noData.length} non-expected no-data response(s)`)}
          ${summaryItem('Regression signal', `${regressions.length} new failure(s), ${newlyPassing.length} newly passing`)}
        </div>
      </div>
      <div class="section">
        <div class="section-head">
          <div>
            <h2>Root Cause Mix</h2>
            <p class="section-copy">Grouped by the classification used for route scoring and endpoint diagnostics.</p>
          </div>
        </div>
        <div class="body">
          ${renderRootCauseSummary(report.rootCauseSummary || {})}
        </div>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <h2>Priority Endpoint Diagnostics</h2>
          <p class="section-copy">Status, latency, timeout/error, and affected UI routes for the highest-signal findings.</p>
        </div>
        <span class="badge high">${highIssues.length} high</span>
      </div>
      <div class="body table-wrap">
        ${renderDiagnosticsTable(diagnostics.filter(d => d.severity === 'critical' || d.severity === 'high' || d.affectedRouteCount > 0).slice(0, 80))}
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <h2>Route Health</h2>
          <p class="section-copy">Sorted by lowest score so weak user journeys appear first.</p>
        </div>
      </div>
      <div class="body table-wrap">
        ${renderRoutesTable(routes)}
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <h2>No Data Evidence</h2>
          <p class="section-copy">Successful responses with empty payloads. These often indicate seed data or environment setup gaps.</p>
        </div>
        <span class="badge low">${noData.length} no data</span>
      </div>
      <div class="body table-wrap">
        ${renderNoDataTable(noData.slice(0, 80))}
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <h2>Regression Signal</h2>
          <p class="section-copy">Compares this run with the previous saved run.</p>
        </div>
      </div>
      <div class="body">
        ${renderRegression(regressions, newlyPassing)}
      </div>
    </section>

    <div class="footer">
      Generated by qa-probe. Full machine-readable evidence is available in report.json and probe-results.json.
    </div>
  </main>
</body>
</html>`;
}

function renderRootCauseSummary(summary) {
  const entries = Object.entries(summary);
  if (entries.length === 0) return '<div class="empty-state">No root cause issues found.</div>';
  return `<table><thead><tr><th>Label</th><th>Count</th><th>Affected routes</th></tr></thead><tbody>${entries
    .sort((a, b) => (b[1].count || 0) - (a[1].count || 0))
    .map(([cause, data]) => `<tr><td><span class="badge info">${escapeHtml(displayCause(cause))}</span></td><td>${Number(data.count || 0)}</td><td class="routes">${escapeHtml(formatRouteList(data.affectedRoutes || []))}</td></tr>`)
    .join('')}</tbody></table>`;
}

function renderDiagnosticsTable(items) {
  if (!items.length) return '<div class="empty-state">No priority endpoint diagnostics found.</div>';
  return `<table><thead><tr><th>Endpoint</th><th>Label</th><th>Severity</th><th>Evidence</th><th>Affected routes</th></tr></thead><tbody>${items
    .map(item => `<tr>
      <td class="endpoint mono">${escapeHtml(item.endpoint)}</td>
      <td><span class="badge ${escapeHtml(item.severity || 'info')}">${escapeHtml(item.label || item.rootCause || 'issue')}</span></td>
      <td>${escapeHtml(item.severity || 'info')}</td>
      <td class="evidence">${escapeHtml(summarizeEvidence(item))}</td>
      <td class="routes">${escapeHtml(formatAffectedRoutes(item))}</td>
    </tr>`)
    .join('')}</tbody></table>`;
}

function renderRoutesTable(routes) {
  if (!routes.length) return '<div class="empty-state">No frontend routes were scored.</div>';
  return `<table><thead><tr><th>Route</th><th>Score</th><th>Status</th><th>Primary cause</th><th>API calls</th></tr></thead><tbody>${routes
    .sort((a, b) => (a[1].score || 0) - (b[1].score || 0))
    .map(([route, data]) => `<tr>
      <td class="route-name mono">${escapeHtml(route)}</td>
      <td class="route-score" style="color:${scoreColor(data.score || 0)}">${Number(data.score || 0)}/100</td>
      <td>${escapeHtml(data.status || 'unknown')}</td>
      <td><span class="badge ${causeClass(data.rootCause)}">${escapeHtml(displayCause(data.rootCause || 'ok'))}</span></td>
      <td>${Number(data.apiCallCount || 0)}</td>
    </tr>`)
    .join('')}</tbody></table>`;
}

function renderNoDataTable(items) {
  if (!items.length) return '<div class="empty-state">No empty successful responses were observed.</div>';
  return `<table><thead><tr><th>Endpoint</th><th>Empty signal</th><th>Latency</th><th>Affected routes</th></tr></thead><tbody>${items
    .map(item => `<tr>
      <td class="endpoint mono">${escapeHtml(item.endpoint)}</td>
      <td>${escapeHtml(item.emptyReason || 'empty payload')}</td>
      <td>${escapeHtml(item.ms == null ? 'unknown' : `${item.ms}ms`)}</td>
      <td class="routes">${escapeHtml(formatAffectedRoutes(item))}</td>
    </tr>`)
    .join('')}</tbody></table>`;
}

function renderRegression(newFailures, newPasses) {
  if (!newFailures.length && !newPasses.length) {
    return '<div class="empty-state">No new pass/fail changes compared with the previous run.</div>';
  }
  const failures = newFailures.length
    ? `<div class="summary-item"><strong>New failures</strong><span>${escapeHtml(newFailures.join(', '))}</span></div>`
    : '';
  const passes = newPasses.length
    ? `<div class="summary-item"><strong>Newly passing</strong><span>${escapeHtml(newPasses.join(', '))}</span></div>`
    : '';
  return `<div class="summary-list">${failures}${passes}</div>`;
}

function kpi(label, value) {
  return `<div class="kpi"><strong>${escapeHtml(value)}</strong><span class="subtle">${escapeHtml(label)}</span></div>`;
}

function summaryItem(label, value) {
  return `<div class="summary-item"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(value)}</span></div>`;
}

function displayCause(rootCause) {
  if (rootCause === 'empty_db') return 'no_data';
  if (rootCause === 'expected_empty') return 'expected_empty';
  if (rootCause === 'sample_unavailable') return 'sample_unavailable';
  if (rootCause === 'unknown') return 'needs_review';
  if (rootCause === 'invalid_sample_params') return 'invalid_sample';
  return rootCause || 'ok';
}

function causeClass(rootCause) {
  if (['server_error', 'missing_route', 'contract_mismatch', 'auth_scope_mismatch', 'schema_mismatch', 'stream_dead'].includes(rootCause)) return 'high';
  if (['slow_but_working', 'feature_flag_disabled', 'timeout', 'unknown'].includes(rootCause)) return 'medium';
  if (rootCause === 'empty_db') return 'low';
  if (rootCause === 'expected_empty' || rootCause === 'sample_unavailable') return 'info';
  return 'info';
}

function formatAffectedRoutes(item) {
  return formatRouteList(item.affectedRoutes || []) || 'backend-only / unmatched';
}

function formatRouteList(routes) {
  if (!routes.length) return '';
  return routes.slice(0, 4).join(', ') + (routes.length > 4 ? ` +${routes.length - 4} more` : '');
}

function summarizeEvidence(item) {
  const parts = [];
  if (item.status !== null && item.status !== undefined) parts.push(`status=${item.status}`);
  if (item.ms !== null && item.ms !== undefined) parts.push(`${item.ms}ms`);
  if (item.emptyReason) parts.push(item.emptyReason);
  if (item.error) parts.push(item.error);
  if (item.detail) parts.push(item.detail);
  return parts.join('; ') || 'see probe-results.json';
}

function scoreColor(score) {
  if (score >= 90) return '#1f8a4c';
  if (score >= 75) return '#2f7dcf';
  if (score >= 50) return '#b7791f';
  return '#c2413a';
}

function scoreLabel(score) {
  if (score >= 90) return 'excellent';
  if (score >= 75) return 'good';
  if (score >= 50) return 'needs attention';
  return 'broken';
}

function formatDate(value) {
  if (!value) return 'unknown time';
  try {
    return new Date(value).toLocaleString('en', {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return value;
  }
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function escapeHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

module.exports = { writeHtmlReport, renderHtmlReport };
