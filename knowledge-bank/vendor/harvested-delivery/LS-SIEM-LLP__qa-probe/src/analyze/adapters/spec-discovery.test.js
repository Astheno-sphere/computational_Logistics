'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { loadSpec, looksLikeSpec } = require('./fastapi.js');

const SPEC = { openapi: '3.0.0', paths: { '/x': {} } };

function http(handler) {
  return { get: async (url) => handler(url) };
}

describe('looksLikeSpec', () => {
  test('accepts openapi / swagger / paths shapes', () => {
    assert.equal(looksLikeSpec({ openapi: '3.0.0' }), true);
    assert.equal(looksLikeSpec({ swagger: '2.0' }), true);
    assert.equal(looksLikeSpec({ paths: {} }), true);
    assert.equal(looksLikeSpec({ nope: 1 }), false);
    assert.equal(looksLikeSpec('not an object'), false);
  });
});

describe('loadSpec — discovery', () => {
  test('returns the configured URL when it serves a spec', async () => {
    const { spec, source } = await loadSpec({ openApiUrl: '/openapi.json' }, http(() => ({ data: SPEC })));
    assert.deepEqual(spec, SPEC);
    assert.equal(source, '/openapi.json');
  });

  test('falls back to a common path when the configured URL 404s', async () => {
    const seen = [];
    const client = http((url) => {
      seen.push(url);
      if (url === '/v3/api-docs') return { data: SPEC };
      const e = new Error('404'); throw e;
    });
    const { source } = await loadSpec({ openApiUrl: '/openapi.json' }, client);
    assert.equal(source, '/v3/api-docs');
    assert.ok(seen.includes('/openapi.json'), 'tried the configured URL first');
  });

  test('reads a local spec file when openApiFile is set (no HTTP)', async () => {
    const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'qa-spec-')), 'openapi.json');
    fs.writeFileSync(file, JSON.stringify(SPEC));
    let called = false;
    const { spec, source } = await loadSpec({ openApiFile: file }, http(() => { called = true; return {}; }));
    assert.deepEqual(spec, SPEC);
    assert.equal(source, file);
    assert.equal(called, false, 'no HTTP when a local file is configured');
  });

  test('throws when nothing yields a spec', async () => {
    await assert.rejects(loadSpec({ openApiUrl: '/openapi.json' }, http(() => { throw new Error('down'); })));
  });
});
