'use strict';

function detectAnomalies(currentResults, baselines) {
  const findings = [];
  for (const [endpoint, result] of Object.entries(currentResults || {})) {
    if (endpoint.startsWith('__')) continue;
    const baseline = baselines[endpoint];
    if (!baseline) continue;
    const checks = [
      ['latency', result.ms],
      ['cardinality', result.itemCount],
      ['responseSize', result.responseSize],
    ];
    for (const [metric, value] of checks) {
      const summary = baseline[metric];
      if (typeof value !== 'number' || !summary || summary.count < 2) continue;
      const tolerance = (summary.sigma || 1) * 3;
      if (value < summary.mean - tolerance || value > summary.mean + tolerance) {
        findings.push({
          endpoint,
          metric,
          value,
          rootCause: 'anomaly_vs_baseline',
          detail: `Historical ${metric}: ${summary.min}-${summary.max}; this run: ${value}`,
        });
      }
    }
  }
  return findings;
}

module.exports = { detectAnomalies };
