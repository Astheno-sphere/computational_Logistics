'use strict';

function remediateEmptyDb({ report, config = {} }) {
  const fixes = [];
  for (const item of (report && report.endpointDiagnostics) || []) {
    if (item.rootCause !== 'empty_db') continue;
    const seed = config.seedCommand || 'your project seed command';
    fixes.push({
      id: `empty-db:${item.endpoint}`,
      title: `Seed data for ${item.endpoint}`,
      strategy: 'empty_db',
      confidence: config.seedCommand ? 0.8 : 0.5,
      autoApply: false,
      suggestion: `Run ${seed} to populate test/demo records for ${item.endpoint}.`,
      diff: '',
    });
  }
  return fixes;
}

module.exports = { remediateEmptyDb };
