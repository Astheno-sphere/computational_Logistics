'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
const { runWriteFlows, runOneFlow, extractId } = require('./write-flows.js');

// A fake request fn driven by a handler; records every call for assertions.
function recorder(handler) {
  const calls = [];
  const request = async (req) => {
    calls.push(req);
    return handler(req);
  };
  return { request, calls };
}

const flow = {
  name: 'thing-crud',
  create: { method: 'POST', path: '/things', body: { name: 'x' } },
  read: { method: 'GET', path: '/things/{id}' },
  update: { method: 'PATCH', path: '/things/{id}', body: { name: 'y' } },
  delete: { method: 'DELETE', path: '/things/{id}' },
  idField: 'id',
};

describe('extractId', () => {
  test('top-level and wrapped ids', () => {
    assert.equal(extractId({ id: 7 }, 'id'), 7);
    assert.equal(extractId({ data: { id: 9 } }, 'id'), 9);
    assert.equal(extractId({ nope: 1 }, 'id'), null);
  });
});

describe('runOneFlow — happy path', () => {
  test('create→read→update→delete all succeed and resource is cleaned up', async () => {
    let deleted = false;
    const { request, calls } = recorder((req) => {
      if (req.method === 'POST') return { status: 201, body: { id: 5 } };
      if (req.method === 'PATCH') return { status: 200, body: {} };
      if (req.method === 'DELETE') { deleted = true; return { status: 204, body: null }; }
      if (req.method === 'GET') return { status: deleted ? 404 : 200, body: deleted ? null : { id: 5 } };
      return { status: 200, body: {} };
    });
    const res = await runOneFlow(flow, request);
    assert.equal(res.ok, true, JSON.stringify(res.findings));
    assert.equal(res.createdId, 5);
    assert.equal(res.cleanedUp, true);
    // verify the chain used the created id, and DELETE ran after the PATCH
    const patchIdx = calls.findIndex(c => c.method === 'PATCH' && c.path === '/things/5');
    const deleteIdx = calls.findIndex(c => c.method === 'DELETE' && c.path === '/things/5');
    assert.ok(patchIdx >= 0, 'update used the created id');
    assert.ok(deleteIdx > patchIdx, 'cleanup DELETE ran after the update');
  });
});

describe('runOneFlow — failures are reported', () => {
  test('a failing create yields a finding and no cleanup', async () => {
    const { request, calls } = recorder(() => ({ status: 422, body: { error: 'bad' } }));
    const res = await runOneFlow(flow, request);
    assert.equal(res.ok, false);
    assert.match(res.findings[0].detail, /expected 2xx, got 422/);
    assert.equal(calls.some(c => c.method === 'DELETE'), false, 'nothing created → nothing to delete');
  });

  test('a failing update is flagged but cleanup STILL runs', async () => {
    let deleted = false;
    const { request } = recorder((req) => {
      if (req.method === 'POST') return { status: 201, body: { id: 8 } };
      if (req.method === 'PATCH') return { status: 500, body: null };
      if (req.method === 'DELETE') { deleted = true; return { status: 204, body: null }; }
      return { status: 404, body: null };
    });
    const res = await runOneFlow(flow, request);
    assert.equal(res.ok, false);
    assert.ok(res.findings.some(f => f.step === 'update'));
    assert.equal(deleted, true, 'cleanup runs even when an earlier step failed');
    assert.equal(res.cleanedUp, true);
  });

  test('cleanup runs even if a step throws', async () => {
    let deleted = false;
    const { request } = recorder((req) => {
      if (req.method === 'POST') return { status: 201, body: { id: 3 } };
      if (req.method === 'GET' && !deleted) throw new Error('network blip');
      if (req.method === 'DELETE') { deleted = true; return { status: 204, body: null }; }
      return { status: 404, body: null };
    });
    const res = await runOneFlow(flow, request);
    assert.equal(deleted, true, 'cleanup runs after a thrown step');
    assert.ok(res.findings.some(f => f.step === 'error'));
  });
});

describe('runWriteFlows — opt-in only', () => {
  test('disabled by default does nothing', async () => {
    const { request, calls } = recorder(() => ({ status: 200, body: {} }));
    const sum = await runWriteFlows({}, request);
    assert.equal(sum.enabled, false);
    assert.equal(sum.ran, 0);
    assert.equal(calls.length, 0, 'no requests issued when disabled');
  });

  test('aggregates pass/fail/cleanup across flows', async () => {
    let deleted = false;
    const { request } = recorder((req) => {
      if (req.method === 'POST') return { status: 201, body: { id: 1 } };
      if (req.method === 'PATCH') return { status: 200, body: {} };
      if (req.method === 'DELETE') { deleted = true; return { status: 204, body: null }; }
      if (req.method === 'GET') return { status: deleted ? 404 : 200, body: deleted ? null : { id: 1 } };
      return { status: 200, body: {} };
    });
    const sum = await runWriteFlows({ writeFlows: { enabled: true, flows: [flow] } }, request);
    assert.equal(sum.ran, 1);
    assert.equal(sum.passed, 1);
    assert.equal(sum.cleanedUp, 1);
  });
});
