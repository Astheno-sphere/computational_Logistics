'use strict';

const { parse } = require('@babel/parser');
const { getRepairProvider } = require('./llm-providers/disabled');

const PARSE_OPTS = {
  sourceType: 'module',
  plugins: ['typescript', 'jsx', 'decorators-legacy', 'classProperties', 'optionalChaining', 'nullishCoalescingOperator', 'dynamicImport'],
  errorRecovery: true,
};

function repairSource(filePath, source, config = {}, providerOverride = null) {
  const llm = config.enabled ? config : { enabled: false, provider: 'disabled' };
  if (!llm.enabled) return null;
  if (Buffer.byteLength(source, 'utf8') > (llm.maxFileBytes || 50000)) return null;
  const provider = providerOverride || getRepairProvider(llm.provider, llm);
  const repaired = provider.repair ? provider.repair({ filePath, source, config: llm }) : null;
  if (!repaired || !withinGuardrails(source, repaired, llm)) return null;
  try {
    const ast = parse(repaired, PARSE_OPTS);
    ast.__qaProbeParsedVia = 'llm-repair';
    ast.__qaProbeLlmProvider = llm.provider || 'disabled';
    return { ast, repaired };
  } catch {
    return null;
  }
}

function withinGuardrails(original, repaired, config = {}) {
  const maxLineDelta = config.maxLineDelta === undefined ? 5 : config.maxLineDelta;
  const maxCharDelta = config.maxCharDelta === undefined ? 200 : config.maxCharDelta;
  const lineDelta = Math.abs(lineCount(original) - lineCount(repaired));
  const charDelta = Math.abs(original.length - repaired.length);
  return lineDelta <= maxLineDelta && charDelta <= maxCharDelta;
}

function lineCount(value) {
  return String(value || '').split(/\r?\n/).length;
}

module.exports = { repairSource, withinGuardrails };
