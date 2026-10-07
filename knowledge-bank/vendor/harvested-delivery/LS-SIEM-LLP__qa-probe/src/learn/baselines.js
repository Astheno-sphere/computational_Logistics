'use strict';

function addSample(grouped, endpoint, ms, responseSize, itemCount) {
  if (!endpoint) return;
  if (!grouped.has(endpoint)) grouped.set(endpoint, { latencies: [], sizes: [], cardinalities: [] });
  const bucket = grouped.get(endpoint);
  if (typeof ms === 'number') bucket.latencies.push(ms);
  if (typeof responseSize === 'number') bucket.sizes.push(responseSize);
  if (typeof itemCount === 'number') bucket.cardinalities.push(itemCount);
}

function computeBaselines(runs) {
  const grouped = new Map();
  for (const run of runs || []) {
    // Prefer endpointMetrics — it covers EVERY probed endpoint, including healthy
    // ones, so a regression on a normally-passing endpoint can be detected. Fall
    // back to endpointDiagnostics (issues only) for runs recorded before metrics.
    const metrics = run.endpointMetrics;
    if (metrics && typeof metrics === 'object') {
      for (const [endpoint, m] of Object.entries(metrics)) {
        addSample(grouped, endpoint, m.ms, m.responseSize, m.itemCount);
      }
    } else {
      for (const item of run.endpointDiagnostics || []) {
        addSample(grouped, item.endpoint, item.ms, item.responseSize, item.itemCount);
      }
    }
  }

  const out = {};
  for (const [endpoint, values] of grouped.entries()) {
    out[endpoint] = {
      latency: summarize(values.latencies),
      responseSize: summarize(values.sizes),
      cardinality: summarize(values.cardinalities),
    };
  }
  return out;
}

function summarize(values) {
  const sorted = [...values].sort((a, b) => a - b);
  if (sorted.length === 0) return null;
  return {
    min: sorted[0],
    max: sorted[sorted.length - 1],
    mean: mean(sorted),
    sigma: sigma(sorted),
    p50: percentile(sorted, 50),
    p95: percentile(sorted, 95),
    p99: percentile(sorted, 99),
    count: sorted.length,
  };
}

function percentile(sorted, p) {
  const idx = Math.ceil((p / 100) * sorted.length) - 1;
  return sorted[Math.max(0, Math.min(sorted.length - 1, idx))];
}

function mean(values) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function sigma(values) {
  const avg = mean(values);
  return Math.sqrt(values.reduce((sum, value) => sum + Math.pow(value - avg, 2), 0) / values.length);
}

function historicalFixSuggestion(endpoint, rootCause, runs) {
  for (const run of [...(runs || [])].reverse()) {
    for (const fix of run.resolvedFixes || []) {
      if (fix.endpoint === endpoint && fix.rootCause === rootCause) return fix.fixHint || fix.summary || null;
    }
  }
  return null;
}

module.exports = { computeBaselines, summarize, historicalFixSuggestion };
