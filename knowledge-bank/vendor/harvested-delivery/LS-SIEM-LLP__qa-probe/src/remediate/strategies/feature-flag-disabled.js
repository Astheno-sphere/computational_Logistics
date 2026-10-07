'use strict';

function remediateFeatureFlagDisabled({ report }) {
  const fixes = [];
  for (const item of (report && report.endpointDiagnostics) || []) {
    if (item.rootCause !== 'feature_flag_disabled') continue;
    fixes.push({
      id: `feature-flag-disabled:${item.endpoint}`,
      title: `Enable feature flag for ${item.endpoint}`,
      strategy: 'feature_flag_disabled',
      confidence: 0.6,
      autoApply: false,
      suggestion: item.fixHint || 'Enable the disabled feature flag in your application configuration.',
      diff: '',
    });
  }
  return fixes;
}

module.exports = { remediateFeatureFlagDisabled };
