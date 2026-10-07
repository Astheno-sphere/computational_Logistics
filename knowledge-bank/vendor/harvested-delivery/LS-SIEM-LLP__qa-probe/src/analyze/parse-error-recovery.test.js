'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { parseFile } = require('./frontend-parser');
const { createParseCache } = require('./parse-cache');

function tempProject(files) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-probe-parse-recovery-'));
  for (const [name, content] of Object.entries(files)) {
    const filePath = path.join(root, name);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, content, 'utf8');
  }
  return root;
}

describe('parse error recovery', () => {
  test('clean files still extract routes', () => {
    const root = tempProject({
      'src/Clean.tsx': "api.get('/api/cases');\n",
    });
    const warnings = [];
    const calls = parseFile(path.join(root, 'src', 'Clean.tsx'), { relBase: root, warnings });
    assert.deepEqual(calls.map(c => `${c.method} ${c.path}`), ['GET /cases']);
    assert.equal(warnings.length, 0);
  });

  test('syntax errors emit warnings and do not throw', () => {
    const root = tempProject({
      'src/Broken.tsx': "export function Broken() {\n  api.get('/api/cases');\n  return <div>;\n",
    });
    const warnings = [];
    const calls = parseFile(path.join(root, 'src', 'Broken.tsx'), { relBase: root, warnings });
    assert.deepEqual(calls, []);
    assert.equal(warnings.length, 1);
    assert.match(warnings[0].error, /Unexpected|Unterminated|expected/i);
  });

  test('parse failure falls back to cached AST and marks calls stale', () => {
    const root = tempProject({
      'src/Cached.tsx': "api.get('/api/cached');\n",
    });
    const filePath = path.join(root, 'src', 'Cached.tsx');
    const parseCache = createParseCache({ outputDir: path.join(root, '.qaprobe') });
    const cleanCalls = parseFile(filePath, { relBase: root, parseCache, warnings: [] });
    parseCache.save();
    assert.equal(cleanCalls.length, 1);

    fs.writeFileSync(filePath, "export function Cached() {\n  return <div>;\n", 'utf8');
    const warnings = [];
    const staleCalls = parseFile(filePath, { relBase: root, parseCache, warnings });
    assert.deepEqual(staleCalls.map(c => `${c.method} ${c.path}`), ['GET /cached']);
    assert.equal(staleCalls[0].staleParse, true);
    assert.equal(warnings[0].staleParse, true);
  });
});
