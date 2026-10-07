'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { harToRuntimeCalls, isApiRequest } = require('./har-import.js');

const cfg = { frontendApiPrefix: '/api' };

function entry(url, { method = 'GET', resourceType, mimeType } = {}) {
  return {
    _resourceType: resourceType,
    request: { method, url },
    response: { content: { mimeType } },
  };
}

describe('isApiRequest', () => {
  test('xhr/fetch requests are API requests', () => {
    assert.equal(isApiRequest(entry('http://x/foo', { resourceType: 'xhr' }), cfg), true);
    assert.equal(isApiRequest(entry('http://x/bar', { resourceType: 'fetch' }), cfg), true);
  });
  test('json responses are API requests', () => {
    assert.equal(isApiRequest(entry('http://x/data', { mimeType: 'application/json' }), cfg), true);
  });
  test('prefix-matched paths are API requests', () => {
    assert.equal(isApiRequest(entry('http://x/api/users'), cfg), true);
  });
  test('static assets are not', () => {
    assert.equal(isApiRequest(entry('http://x/app.js', { resourceType: 'script' }), cfg), false);
    assert.equal(isApiRequest(entry('http://x/logo.png'), cfg), false);
  });
});

describe('harToRuntimeCalls', () => {
  function writeHar(entries) {
    const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'qa-har-')), 'net.har');
    fs.writeFileSync(file, JSON.stringify({ log: { entries } }));
    return file;
  }

  test('extracts API calls, dedupes, and buckets under __unmatched__', () => {
    const file = writeHar([
      entry('http://x/api/users?page=1', { resourceType: 'xhr' }),
      entry('http://x/api/users?page=2', { resourceType: 'xhr' }), // same METHOD+path → deduped
      entry('http://x/api/cases/5', { method: 'GET', mimeType: 'application/json' }),
      entry('http://x/main.css'), // static → skipped
    ]);
    const map = harToRuntimeCalls(file, cfg);
    const calls = map.get('__unmatched__');
    assert.ok(calls, 'calls bucketed under __unmatched__');
    assert.equal(calls.length, 2, 'deduped, static skipped');
    assert.deepEqual(calls.map(c => c.path).sort(), ['/api/cases/5', '/api/users']);
    assert.equal(calls[0].source, 'har');
  });

  test('missing file → empty map', () => {
    assert.equal(harToRuntimeCalls('/does/not/exist.har', cfg).size, 0);
  });

  test('a HAR with no API requests → empty map', () => {
    const file = writeHar([entry('http://x/app.js', { resourceType: 'script' })]);
    assert.equal(harToRuntimeCalls(file, cfg).size, 0);
  });
});
