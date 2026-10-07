'use strict';

const fs = require('fs');
const path = require('path');
const { remediateContractMismatch } = require('./strategies/contract-mismatch');
const { remediateFeatureFlagDisabled } = require('./strategies/feature-flag-disabled');
const { remediateEmptyDb } = require('./strategies/empty-db');

const STRATEGIES = [
  remediateContractMismatch,
  remediateFeatureFlagDisabled,
  remediateEmptyDb,
];

function buildRemediations(graph, probeResults, report, config = {}) {
  const fixes = [];
  for (const strategy of STRATEGIES) {
    fixes.push(...strategy({ graph, probeResults, report, config }));
  }
  return fixes.sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
}

function renderFixes(fixes, { includeSuggestions = true } = {}) {
  if (!fixes.length) return 'No auto-remediations available.';
  return fixes
    .filter(fix => includeSuggestions || fix.confidence >= 0.8)
    .map(fix => [
      `# ${fix.title}`,
      `# confidence=${fix.confidence.toFixed(2)} ${fix.autoApply ? 'auto-apply' : 'suggestion-only'}`,
      fix.diff || fix.suggestion || '',
    ].join('\n'))
    .join('\n\n');
}

function applyFixes(fixes, cwd = process.cwd()) {
  const applied = [];
  const root = path.resolve(cwd);
  for (const fix of fixes) {
    if ((fix.confidence || 0) < 0.8 || !fix.patch) continue;
    const filePath = path.resolve(root, fix.patch.file);
    if (!isInsideRoot(filePath, root)) {
      applied.push({ ...fix, applied: false, reason: 'outside_cwd' });
      continue;
    }
    const current = fs.readFileSync(filePath, 'utf8');
    if (!current.includes(fix.patch.before)) {
      applied.push({ ...fix, applied: false, reason: 'pattern_not_found' });
      continue;
    }
    fs.writeFileSync(filePath, current.replace(fix.patch.before, fix.patch.after), 'utf8');
    applied.push({ ...fix, applied: true });
  }
  return applied;
}

function isInsideRoot(filePath, root) {
  const relative = path.relative(root, filePath);
  return relative === '' || (!!relative && !relative.startsWith('..') && !path.isAbsolute(relative));
}

module.exports = { buildRemediations, renderFixes, applyFixes };
