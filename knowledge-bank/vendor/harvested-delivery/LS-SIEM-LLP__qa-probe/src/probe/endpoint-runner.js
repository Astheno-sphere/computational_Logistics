'use strict';

const { validateSchema } = require('./schema-validator');
const { generateBody, resolvePostBodyMode, requestBodySchema } = require('./body-generator');
const { inferShape } = require('./schema-history');
const { createTraceContext, correlateTrace } = require('./otel-correlator');
const { evaluateAssertions, assertionsForEndpoint } = require('./assertions');

const MAX_RETRIES = 2;

/**
 * Resolve the hard per-request deadline (ms).
 * axios `timeout` is socket-inactivity based, so a response that keeps trickling
 * data (streaming / SSE-over-HTTP / LLM token stream) never trips it. This is a
 * wall-clock cap that fires regardless of socket activity. Defaults to a small
 * margin beyond `timeoutMs` so ordinary idle timeouts still report via axios.
 */
function resolveHardTimeoutMs(config) {
  const p = (config && config.probe) || {};
  if (p.hardTimeoutMs) return p.hardTimeoutMs;
  const base = p.timeoutMs || 10000;
  return base + 2000;
}

const MAX_SAMPLE_CHARS = 800;

/**
 * A bounded, serialized snapshot of a response body — the raw evidence an AI (or
 * human) needs to judge a result for themselves. Truncated so a large/streaming
 * body can't bloat the report. NOTE: this is the response, never the request
 * headers, so the auth token is never captured here.
 */
function sampleBody(body) {
  if (body === undefined || body === null) return null;
  let s;
  try {
    s = typeof body === 'string' ? body : JSON.stringify(body);
  } catch {
    s = String(body);
  }
  if (s == null) return null;
  if (s.length > MAX_SAMPLE_CHARS) {
    return `${s.slice(0, MAX_SAMPLE_CHARS)}… [truncated, ${s.length} chars total]`;
  }
  return s;
}

/**
 * The first list item's scalar fields — just enough for ID discovery to harvest a
 * real id from a collection response. Scalars only, so it stays tiny.
 */
function firstScalarItem(body) {
  let arr = null;
  if (Array.isArray(body)) arr = body;
  else if (body && typeof body === 'object') {
    for (const k of ['data', 'items', 'results', 'records']) {
      if (Array.isArray(body[k])) { arr = body[k]; break; }
    }
  }
  if (!arr || arr.length === 0) return null;
  const first = arr[0];
  if (!first || typeof first !== 'object' || Array.isArray(first)) return null;
  const out = {};
  for (const [k, v] of Object.entries(first)) {
    if (v !== null && typeof v !== 'object') out[k] = v;
  }
  return Object.keys(out).length ? out : null;
}

function abortedResult(routeKey, attempt, error, method, path, ms = 0) {
  return {
    status: null,
    ms,
    routeKey,
    error,
    empty: false,
    itemCount: null,
    schemaValid: null,
    schemaErrors: [],
    retries: attempt,
    timedOut: true,
    evidence: {
      request: { method: (method || '').toUpperCase(), path: path || null },
      response: null,
      error,
      timing: { ms },
    },
  };
}

/**
 * Probe a single HTTP endpoint.
 * Returns a probe result object.
 *
 * @param {AbortSignal|null} runSignal optional overall-run deadline signal; when it
 *   aborts, in-flight requests are cancelled and not-yet-started ones short-circuit.
 */
async function probeEndpoint(endpoint, headers, http, graph, config, attempt = 0, runSignal = null) {
  const { path: endpointPath, method, routeKey } = endpoint;
  const start = Date.now();

  // Overall run deadline already exceeded — don't even start this request.
  if (runSignal && runSignal.aborted) {
    return abortedResult(routeKey, attempt, 'probe run deadline exceeded', method, endpointPath);
  }

  // Hard per-request wall-clock abort: guarantees this request (and its concurrency
  // slot) can never hang indefinitely, even on a continuously-streaming response.
  const controller = new AbortController();
  const hardMs = resolveHardTimeoutMs(config);
  let timedOut = false;
  const killer = setTimeout(() => { timedOut = true; controller.abort(); }, hardMs);
  const onRunAbort = () => controller.abort();
  if (runSignal) runSignal.addEventListener('abort', onRunAbort, { once: true });

  let result;
  try {
    const routeInfo = routeKey && graph.backendRoutes ? graph.backendRoutes[routeKey] : null;
    const bodyMode = resolvePostBodyMode(endpoint, config);
    const requestSchema = requestBodySchema(routeInfo);
    const requestBody = ['POST', 'PUT', 'PATCH'].includes(method)
      ? generateBody(endpoint, requestSchema, bodyMode, config)
      : undefined;
    const traceContext = config.probe && config.probe.otel && config.probe.otel.enabled
      ? createTraceContext()
      : null;
    const requestHeaders = traceContext
      ? { ...headers, traceparent: traceContext.traceparent }
      : headers;
    const res = await http.request({
      method: method.toLowerCase(),
      url: endpointPath,
      headers: requestHeaders,
      data: requestBody,
      // Hard wall-clock abort (see resolveHardTimeoutMs) — covers streaming responses
      // that axios `timeout` would never cancel.
      signal: controller.signal,
      // Accept JSON and event-stream (for endpoints that might be either)
      validateStatus: () => true,
    });

    // Handle 429 rate-limit with backoff and retry
    if (res.status === 429 && attempt < MAX_RETRIES) {
      const retryAfter = res.headers['retry-after'];
      const waitMs = retryAfter ? parseInt(retryAfter, 10) * 1000 : Math.pow(2, attempt) * 1000;
      // Stop this attempt's deadline before backing off, then retry with a fresh one.
      clearTimeout(killer);
      if (runSignal) runSignal.removeEventListener('abort', onRunAbort);
      await new Promise(r => setTimeout(r, waitMs));
      return probeEndpoint(endpoint, headers, http, graph, config, attempt + 1, runSignal);
    }

    const ms = Date.now() - start;
    const body = res.data;

    // Determine if response is empty
    let empty = false;
    let itemCount = null;
    let emptyReason = null;

    if (res.status === 200) {
      if (body === null || body === undefined || body === '') {
        empty = true;
        emptyReason = 'null_body';
      } else if (Array.isArray(body) && body.length === 0) {
        empty = true;
        emptyReason = 'empty_array';
        itemCount = 0;
      } else if (Array.isArray(body)) {
        itemCount = body.length;
      } else if (typeof body === 'object' && body !== null) {
        // Check for common "empty" patterns: { data: [], results: [], items: [] }
        const keys = Object.keys(body);
        const listKey = keys.find(k => ['data', 'results', 'items', 'records'].includes(k));
        if (listKey && Array.isArray(body[listKey]) && body[listKey].length === 0) {
          empty = true;
          emptyReason = `empty_nested_array (${listKey})`;
          itemCount = 0;
        } else if (listKey && Array.isArray(body[listKey])) {
          itemCount = body[listKey].length;
        }
      }
    }

    // Schema validation
    let schemaValid = null;
    let schemaErrors = [];
    let validation = null;
    if (res.status === 200 && routeInfo) {
      if (routeInfo && routeInfo.responseSchema) {
        const bodyForValidation = Array.isArray(body) ? body : body;
        validation = validateSchema(bodyForValidation, routeInfo.responseSchema);
        schemaValid = validation.valid;
        schemaErrors = validation.errors;
      }
    }

    let otel = null;
    if (traceContext) {
      try {
        otel = await correlateTrace(traceContext.traceId, config);
      } catch (err) {
        otel = { error: err.message, traceId: traceContext.traceId };
      }
    }

    // Read-only response assertions: check declared invariants on the 2xx body.
    let assertionFailures = null;
    if (res.status >= 200 && res.status < 300) {
      const rules = assertionsForEndpoint(config, method, endpointPath);
      if (rules) {
        const failures = evaluateAssertions(body, rules);
        if (failures.length) assertionFailures = failures;
      }
    }

    result = {
      status: res.status,
      ms,
      routeKey,
      empty,
      itemCount,
      emptyReason,
      schemaValid,
      schemaErrors,
      validation: validation ? { ok: validation.ok, errors: validation.errors } : null,
      responseShape: res.status === 200 ? inferShape(body) : null,
      requestBodyMode: requestBody === undefined ? 'empty' : bodyMode,
      contentType: res.headers['content-type'] || null,
      retries: attempt,
      traceId: traceContext ? traceContext.traceId : null,
      otel,
      assertionFailures,
      // First list item's scalar fields — used by ID discovery to chain detail routes.
      firstItem: (res.status >= 200 && res.status < 300) ? firstScalarItem(body) : null,
      // Verifiable evidence: the request issued and a bounded snapshot of what the
      // server actually returned, so a consumer never has to trust the label blind.
      evidence: {
        request: { method: method.toUpperCase(), path: endpointPath },
        response: {
          status: res.status,
          contentType: res.headers['content-type'] || null,
          bodyType: Array.isArray(body) ? 'array' : (body === null ? 'null' : typeof body),
          itemCount,
          sample: sampleBody(body),
        },
        timing: { ms },
      },
    };
  } catch (err) {
    const ms = Date.now() - start;
    const runAborted = !!(runSignal && runSignal.aborted) && !timedOut;
    const error = timedOut
      ? `hard timeout: response did not complete within ${hardMs}ms (possible streaming/long-poll endpoint)`
      : runAborted
        ? 'probe run deadline exceeded'
        : err.message;
    result = {
      status: null,
      ms,
      routeKey,
      error,
      empty: false,
      itemCount: null,
      schemaValid: null,
      schemaErrors: [],
      retries: attempt,
      timedOut: timedOut || runAborted,
      evidence: {
        request: { method: method.toUpperCase(), path: endpointPath },
        response: null,
        error,
        timing: { ms },
      },
    };
  } finally {
    clearTimeout(killer);
    if (runSignal) runSignal.removeEventListener('abort', onRunAbort);
  }

  return result;
}

module.exports = { probeEndpoint, resolveHardTimeoutMs };
