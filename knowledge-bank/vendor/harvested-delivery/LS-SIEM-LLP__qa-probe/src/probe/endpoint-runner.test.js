'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
const { probeEndpoint, resolveHardTimeoutMs } = require('./endpoint-runner.js');

const graph = () => ({ backendRoutes: {} });

// An http client whose request never resolves on its own — it only settles when
// the AbortSignal it was given fires. This simulates a streaming/long-poll endpoint
// that axios `timeout` would never cancel.
function hangingHttp() {
  return {
    request: (opts) => new Promise((_resolve, reject) => {
      const sig = opts && opts.signal;
      if (sig) {
        sig.addEventListener('abort', () => {
          const e = new Error('canceled');
          e.code = 'ERR_CANCELED';
          reject(e);
        }, { once: true });
      }
      // no timer that resolves — without an abort this would hang forever
    }),
  };
}

describe('resolveHardTimeoutMs', () => {
  test('defaults to timeoutMs + 2000', () => {
    assert.equal(resolveHardTimeoutMs({ probe: { timeoutMs: 4000 } }), 6000);
  });
  test('honors explicit hardTimeoutMs', () => {
    assert.equal(resolveHardTimeoutMs({ probe: { timeoutMs: 4000, hardTimeoutMs: 1234 } }), 1234);
  });
  test('falls back to a sane default with no config', () => {
    assert.equal(resolveHardTimeoutMs({}), 12000);
  });
});

describe('endpoint-runner hard timeout', () => {
  test('a hanging request is aborted by the hard wall-clock deadline', async () => {
    const cfg = { probe: { timeoutMs: 50, hardTimeoutMs: 120 } };
    const start = Date.now();
    const r = await probeEndpoint({ path: '/stream', method: 'GET' }, {}, hangingHttp(), graph(), cfg);
    const elapsed = Date.now() - start;
    assert.equal(r.status, null);
    assert.equal(r.timedOut, true);
    assert.match(r.error, /hard timeout/i);
    assert.ok(elapsed < 1000, `should abort near hardTimeoutMs, took ${elapsed}ms`);
  });

  test('does not hang forever when the server never responds', async () => {
    const cfg = { probe: { timeoutMs: 30, hardTimeoutMs: 80 } };
    // If the abort wiring regressed, this test would time out the test runner.
    const r = await probeEndpoint({ path: '/llm/chat', method: 'GET' }, {}, hangingHttp(), graph(), cfg);
    assert.equal(r.status, null);
    assert.match(r.error, /timeout/i);
  });
});

describe('endpoint-runner overall run deadline', () => {
  test('short-circuits without a request when the run signal is already aborted', async () => {
    const ac = new AbortController();
    ac.abort();
    const http = { request: () => { throw new Error('request should not be issued after deadline'); } };
    const r = await probeEndpoint({ path: '/x', method: 'GET' }, {}, http, graph(), { probe: {} }, 0, ac.signal);
    assert.equal(r.status, null);
    assert.match(r.error, /deadline/i);
  });

  test('aborts an in-flight request when the run signal fires', async () => {
    const ac = new AbortController();
    const cfg = { probe: { timeoutMs: 5000, hardTimeoutMs: 5000 } }; // hard cap far away
    const p = probeEndpoint({ path: '/stream', method: 'GET' }, {}, hangingHttp(), graph(), cfg, 0, ac.signal);
    setTimeout(() => ac.abort(), 50); // overall deadline fires mid-flight
    const r = await p;
    assert.equal(r.status, null);
    assert.match(r.error, /deadline/i);
  });
});

describe('endpoint-runner evidence capture', () => {
  const okHttp = (data, status = 200, headers = { 'content-type': 'application/json' }) =>
    ({ request: async () => ({ status, data, headers }) });

  test('a successful probe captures request, response sample, and timing', async () => {
    const r = await probeEndpoint({ path: '/users', method: 'GET' }, {}, okHttp([{ id: 1 }, { id: 2 }]), graph(), { probe: {} });
    assert.equal(r.status, 200);
    assert.ok(r.evidence, 'evidence present on every result');
    assert.equal(r.evidence.request.method, 'GET');
    assert.equal(r.evidence.request.path, '/users');
    assert.equal(r.evidence.response.status, 200);
    assert.match(r.evidence.response.sample, /id/);
    assert.equal(typeof r.evidence.timing.ms, 'number');
  });

  test('evidence never includes request headers (no auth-token leak)', async () => {
    const headers = { Authorization: 'Bearer super-secret-token' };
    const r = await probeEndpoint({ path: '/users', method: 'GET' }, headers, okHttp([]), graph(), { probe: {} });
    assert.equal(JSON.stringify(r.evidence).includes('super-secret-token'), false);
    assert.equal('headers' in r.evidence.request, false);
  });

  test('a large body is truncated in the evidence sample', async () => {
    const r = await probeEndpoint({ path: '/big', method: 'GET' }, {}, okHttp({ blob: 'x'.repeat(5000) }), graph(), { probe: {} });
    assert.ok(r.evidence.response.sample.length < 1000, 'sample is bounded');
    assert.match(r.evidence.response.sample, /truncated/);
  });

  test('a failed/aborted probe still captures evidence (error, no response)', async () => {
    const cfg = { probe: { timeoutMs: 30, hardTimeoutMs: 60 } };
    const r = await probeEndpoint({ path: '/stream', method: 'GET' }, {}, hangingHttp(), graph(), cfg);
    assert.equal(r.status, null);
    assert.ok(r.evidence);
    assert.equal(r.evidence.response, null);
    assert.match(r.evidence.error, /timeout/i);
  });
});
