'use strict';

const { authenticate } = require('./authenticator');
const { collectEndpoints } = require('./sampler');
const { probeEndpoint } = require('./endpoint-runner');
const { checkSSE } = require('./sse-checker');
const { checkWS } = require('./ws-checker');
const { runSecurityChecks } = require('./security');
const { partitionByParams, harvestCollectionItems, applyDiscoveredIds } = require('./id-discovery');
const { runWriteFlows } = require('./write-flows');
const { runConcurrent } = require('./rate-limiter');
const { createHttpClient } = require('../analyze/backend-fetcher');
const { saveProbeResults } = require('../cache');
const { snapshotSchemas } = require('./schema-history');
const { runVisualProbe } = require('./visual-probe');

async function runProbe(graph, config) {
  const http = createHttpClient(config);
  const spinner = createSpinner();

  // 1. Authenticate
  spinner.start('Authenticating...');
  let headers;
  try {
    headers = await authenticate(config, http);
    spinner.succeed('Authenticated');
  } catch (err) {
    spinner.fail(`Authentication failed: ${err.message}`);
    throw err;
  }

  // 2. Collect endpoints to probe
  const endpoints = collectEndpoints(graph, config);
  spinner.succeed(`Probing ${endpoints.length} endpoints...`);

  const results = {};

  // 3. Separate HTTP, SSE, WS
  const httpEndpoints = endpoints.filter(e => e.type === 'http');
  const sseEndpoints = endpoints.filter(e => e.type === 'sse');
  const wsEndpoints = endpoints.filter(e => e.type === 'ws');

  // 4. HTTP probing with concurrency limit.
  // Optional overall deadline (config.probe.maxProbeMs) is a final backstop so a
  // cluster of slow endpoints can't run unbounded. Each request also has its own
  // hard wall-clock abort (see endpoint-runner), so a single hung stream can never
  // stall the run regardless of this setting.
  const maxProbeMs = config.probe && config.probe.maxProbeMs;
  const runController = maxProbeMs ? new AbortController() : null;
  let deadlineHit = false;
  const runKiller = runController
    ? setTimeout(() => { deadlineHit = true; runController.abort(); }, maxProbeMs)
    : null;

  let done = 0;
  const probeOne = async (endpoint) => {
    const result = await probeEndpoint(
      endpoint, headers, http, graph, config, 0, runController ? runController.signal : null,
    );
    const key = `${endpoint.method} ${endpoint.path}`;
    results[key] = result;
    done++;
    if (done % 10 === 0 || done === httpEndpoints.length) {
      spinner.start(`  Probing HTTP... ${done}/${httpEndpoints.length}`);
    }
    return result;
  };

  const concurrency = { concurrency: config.probe.concurrency || 5, delayMs: config.probe.delayMs || 50 };

  // ID chaining (on by default; disable with probe.idDiscovery: false): probe
  // param-less collections first, harvest a REAL id from each, then probe detail
  // routes (`/cases/{id}`) with it instead of a guessed `1`. Eliminates most
  // sample_not_found noise on unseeded databases. Pure read — no extra requests.
  const chain = !config.probe || config.probe.idDiscovery !== false;
  const { withParams, withoutParams } = chain
    ? partitionByParams(httpEndpoints)
    : { withParams: [], withoutParams: httpEndpoints };
  let chained = 0;

  try {
    if (chain && withParams.length) {
      await runConcurrent(withoutParams, probeOne, concurrency);
      chained = applyDiscoveredIds(withParams, harvestCollectionItems(results), config);
      await runConcurrent(withParams, probeOne, concurrency);
    } else {
      await runConcurrent(httpEndpoints, probeOne, concurrency);
    }
  } finally {
    if (runKiller) clearTimeout(runKiller);
  }
  if (deadlineHit) {
    spinner.warn(`HTTP probe hit the overall deadline (${maxProbeMs}ms); remaining endpoints recorded as deadline-exceeded.`);
  }
  spinner.succeed(`HTTP: ${httpEndpoints.length} endpoints probed${chained ? ` (${chained} detail route(s) used a discovered id)` : ''}`);

  // 4b. Security pass (opt-in via config.security): anonymous auth-bypass re-probe,
  // PII scan on responses, and an optional per-persona access matrix. GET-only, so
  // it never issues a write. Attaches `securityFinding` to results for the report.
  if (config.security && config.security.enabled) {
    spinner.start('Running security checks...');
    const probeAs = (endpoint, personaHeaders) => probeEndpoint(endpoint, personaHeaders || {}, http, graph, config);
    const sec = await runSecurityChecks(httpEndpoints, results, config, probeAs);
    spinner.succeed(`Security: ${sec.authBypass} auth-bypass, ${sec.privilegeEscalation} priv-esc, ${sec.piiLeak} PII (${sec.authBypassChecked} endpoints re-probed)`);
  }

  // 4c. Write-flow CRUD chains (opt-in via config.writeFlows.enabled). This MUTATES
  // DATA — every flow is explicitly defined and every created resource is deleted
  // at the end of its flow. Intended for a disposable / test-tenant environment.
  if (config.writeFlows && config.writeFlows.enabled) {
    process.stderr.write('[qa-probe] WARNING: write-flows are ENABLED — this MUTATES data. Use a disposable / test-tenant environment only.\n');
    spinner.start('Running write-flows...');
    const request = async ({ method, path, body }) => {
      const res = await http.request({ method: String(method).toLowerCase(), url: path, data: body, headers, validateStatus: () => true });
      return { status: res.status, body: res.data };
    };
    const wf = await runWriteFlows(config, request);
    results.__writeFlows = wf;
    spinner.succeed(`Write-flows: ${wf.passed}/${wf.ran} passed, ${wf.cleanedUp} cleaned up${wf.failed ? `, ${wf.failed} FAILED` : ''}`);
  }

  // 5. SSE checking
  if (sseEndpoints.length > 0 && config.probe.sse && config.probe.sse.enabled) {
    spinner.start(`Checking ${sseEndpoints.length} SSE endpoint(s)...`);
    for (const ep of sseEndpoints) {
      const url = config.baseUrl.replace(/\/$/, '') + ep.path;
      const result = await checkSSE(url, headers, config);
      results[`SSE ${ep.path}`] = result;
    }
    spinner.succeed(`SSE: ${sseEndpoints.length} endpoint(s) checked`);
  }

  // 6. WS checking
  if (wsEndpoints.length > 0 && config.probe.ws && config.probe.ws.enabled) {
    spinner.start(`Checking ${wsEndpoints.length} WebSocket endpoint(s)...`);
    for (const ep of wsEndpoints) {
      const url = config.baseUrl.replace(/\/$/, '').replace(/^https?/, 'wss') + ep.path;
      const result = await checkWS(url, headers, config);
      results[`WS ${ep.path}`] = result;
    }
    spinner.succeed(`WS: ${wsEndpoints.length} endpoint(s) checked`);
  }

  // 7. Visual probing
  if (config.probe.visual && config.probe.visual.enabled) {
    spinner.start('Running visual probe...');
    const visual = await runVisualProbe(graph, results, config);
    Object.assign(results, visual.syntheticResults);
    results.__visual = {
      routes: visual.routeResults,
      warnings: visual.warnings,
    };
    const issueCount = Object.values(visual.routeResults).filter(item =>
      item.httpScore >= 80 && item.density < item.densityThreshold
    ).length;
    spinner.succeed(`Visual probe: ${Object.keys(visual.routeResults).length} route(s), ${issueCount} low-density issue(s)`);
  }

  // 8. Save results
  const schemaDrift = snapshotSchemas(results, config);
  if (schemaDrift.length > 0) {
    results.__schemaDrift = schemaDrift;
  }
  await saveProbeResults(results, config);
  spinner.succeed(`Probe results saved → ${config.output.dir}/probe-results.json`);

  return results;
}

function createSpinner() {
  try {
    const ora = require('ora');
    const s = ora({ spinner: 'dots' });
    return {
      start: (msg) => s.start(msg),
      succeed: (msg) => s.succeed(msg),
      fail: (msg) => s.fail(msg),
      warn: (msg) => s.warn(msg),
    };
  } catch {
    return {
      start: (msg) => process.stdout.write(`  ... ${msg}\n`),
      succeed: (msg) => process.stdout.write(`  ✓ ${msg}\n`),
      fail: (msg) => process.stderr.write(`  ✗ ${msg}\n`),
      warn: (msg) => process.stdout.write(`  ⚠ ${msg}\n`),
    };
  }
}

module.exports = { runProbe };
