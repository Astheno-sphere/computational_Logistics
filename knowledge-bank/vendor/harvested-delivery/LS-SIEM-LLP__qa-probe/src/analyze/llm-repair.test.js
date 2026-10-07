'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { parseFile } = require('./frontend-parser');
const { repairSource, withinGuardrails } = require('./llm-repair');

test('LLM repair extracts API calls from provider-corrected source', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-probe-llm-'));
  const file = path.join(root, 'Broken.tsx');
  fs.writeFileSync(file, "export function Broken( { api.get('/cases')", 'utf8');
  const provider = { repair: () => "export function Broken(){ api.get('/cases'); return <div/> }" };
  const calls = parseFile(file, {
    relBase: root,
    llmRepair: { enabled: true, provider: 'ollama', maxLineDelta: 5, maxCharDelta: 200 },
    llmRepairProvider: provider,
    warnings: [],
  });

  assert.equal(calls[0].path, '/cases');
  assert.equal(calls[0].parsedVia, 'llm-repair');
  assert.equal(calls[0].llmProvider, 'ollama');
});

test('LLM repair rejects garbage provider output', () => {
  const result = repairSource('Broken.tsx', 'export const x = ', {
    enabled: true,
    provider: 'ollama',
    maxLineDelta: 5,
    maxCharDelta: 200,
  }, { repair: () => 'not valid {' });

  assert.equal(result, null);
});

test('LLM repair guardrails reject large line deltas', () => {
  assert.equal(withinGuardrails('a\nb', 'a\nb\nc\nd\ne\nf\ng', { maxLineDelta: 2, maxCharDelta: 200 }), false);
});
