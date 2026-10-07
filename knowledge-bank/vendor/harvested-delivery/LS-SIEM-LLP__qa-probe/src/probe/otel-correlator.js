'use strict';

const crypto = require('crypto');
const { fetchJaegerTrace } = require('./trace-fetchers/jaeger');
const { fetchTempoTrace } = require('./trace-fetchers/tempo');
const { fetchHoneycombTrace } = require('./trace-fetchers/honeycomb');

function createTraceContext() {
  const traceId = crypto.randomBytes(16).toString('hex');
  const spanId = crypto.randomBytes(8).toString('hex');
  return {
    traceId,
    spanId,
    traceparent: `00-${traceId}-${spanId}-01`,
  };
}

async function correlateTrace(traceId, config, options = {}) {
  const otel = ((config || {}).probe || {}).otel || {};
  if (!otel.enabled || !traceId) return null;
  const fetcher = options.fetcher || fetcherForBackend(otel.backend);
  const trace = await fetcher(traceId, otel);
  return classifyTrace(trace);
}

function fetcherForBackend(backend) {
  if (backend === 'tempo') return fetchTempoTrace;
  if (backend === 'honeycomb') return fetchHoneycombTrace;
  return fetchJaegerTrace;
}

function classifyTrace(trace) {
  const spans = normalizeSpans(trace);
  if (spans.length === 0) return null;
  const root = spans[0];
  const totalMs = root.durationMs || sum(spans.map(span => span.durationMs));
  const children = spans.slice(1);
  const slowChild = children.sort((a, b) => b.durationMs - a.durationMs)[0] || null;
  const childMs = slowChild ? slowChild.durationMs : 0;
  const selfMs = Math.max(0, totalMs - sum(children.map(span => span.durationMs)));
  const childDominant = totalMs > 0 && childMs / totalMs >= 0.6;

  return {
    totalMs,
    selfMs,
    childMs,
    slowComponent: slowChild ? slowChild.operationName : null,
    classification: childDominant ? 'slow_dependency' : 'slow_app',
  };
}

function normalizeSpans(trace) {
  const raw = trace && (trace.spans || trace.data && trace.data[0] && trace.data[0].spans || []);
  return raw.map(span => ({
    operationName: span.operationName || span.name || span.operation || 'unknown',
    durationMs: Number(span.durationMs !== undefined ? span.durationMs : (span.duration || 0) / 1000),
  })).filter(span => span.durationMs >= 0);
}

function sum(values) {
  return values.reduce((total, value) => total + value, 0);
}

module.exports = { createTraceContext, correlateTrace, classifyTrace, normalizeSpans };
