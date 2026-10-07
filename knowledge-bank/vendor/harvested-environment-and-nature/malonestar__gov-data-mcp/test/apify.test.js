import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { createClient, ApifyError, TERMINAL_STATES } from '../src/apify.js';

const here = dirname(fileURLToPath(import.meta.url));

/** Fake clock: sleep advances virtual time instantly, so timing logic is testable. */
function fakeClock() {
  let t = 1_000_000;
  return {
    now: () => t,
    sleep: async ms => { t += ms; },
    advance: ms => { t += ms; },
  };
}

/** Scripted fetch: each entry is matched in order against the request path. */
function scriptedFetch(script) {
  const calls = [];
  const impl = async (url, opts = {}) => {
    calls.push({ url, method: opts.method || 'GET' });
    const step = script.shift();
    if (!step) throw new Error(`unexpected request: ${opts.method || 'GET'} ${url}`);
    if (step.match && !url.includes(step.match)) throw new Error(`expected ${step.match} but got ${url}`);
    return {
      ok: step.status ? step.status < 400 : true,
      status: step.status || 200,
      text: async () => (typeof step.body === 'string' ? step.body : JSON.stringify(step.body ?? { data: null })),
    };
  };
  impl.calls = calls;
  return impl;
}

const RUN = (status, extra = {}) => ({ body: { data: { id: 'run1', status, defaultDatasetId: 'ds1', ...extra } } });
/** One settle read = dataset meta then items, issued together. */
const READ = (itemCount, items) => ([
  { match: '/datasets/ds1', body: { data: { itemCount } } },
  { match: '/datasets/ds1/items', body: items },
]);

function client(script, opts = {}) {
  const clock = fakeClock();
  const fetchImpl = scriptedFetch(script);
  return { c: createClient({ token: 't', fetchImpl, sleep: clock.sleep, now: clock.now, ...opts }), fetchImpl, clock };
}

test('a missing token fails immediately with actionable guidance', () => {
  assert.throws(() => createClient({ token: '' }), err => {
    assert.ok(err instanceof ApifyError);
    assert.match(err.message, /APIFY_TOKEN/);
    assert.match(err.message, /console\.apify\.com/);
    return true;
  });
});

test('a successful run returns rows', async () => {
  const { c } = client([
    { match: '/acts/malonestar~demo/runs', ...RUN('RUNNING') },
    { match: '/actor-runs/run1', ...RUN('SUCCEEDED') },
    ...READ(2, [{ a: 1 }, { a: 2 }]),
  ]);
  const r = await c.runActor('malonestar/demo', {});
  assert.equal(r.status, 'SUCCEEDED');
  assert.equal(r.itemCount, 2);
  assert.equal(r.statusMessage, null);
});

test('both Apify envelope shapes are handled — a bare array is not read for a .data key', async () => {
  // /datasets/<id>/items returns a BARE ARRAY; almost everything else returns
  // { data: ... }. Reading .data off the array gives undefined, which the caller
  // reads as "no rows" — a confident empty produced by a successful request.
  // Measured live 2026-08-11: this made every dataset read return [] forever
  // while the dataset's own itemCount correctly reported 1.
  const { c } = client([
    { match: '/datasets/ds1', body: { data: { itemCount: 1 } } },
    { match: '/datasets/ds1/items', body: [{ real: 'row' }] },
  ]);
  assert.deepEqual(await c.request('/datasets/ds1'), { itemCount: 1 }, 'the wrapped shape must be unwrapped');
  assert.deepEqual(await c.request('/datasets/ds1/items'), [{ real: 'row' }], 'the bare-array shape must pass through intact');
});

// --- The dataset-lag defect, measured live 2026-08-11 --------------------------

test('an early empty read is NOT believed — polling continues until the rows appear', async () => {
  // Reproduces the real failure: run SUCCEEDED, first dataset read returned [] and
  // itemCount 0, and the row was there moments later.
  const { c, fetchImpl } = client([
    { ...RUN('SUCCEEDED') },
    ...READ(0, []),
    ...READ(0, []),
    ...READ(1, [{ in_karst_terrain: true }]),
  ]);
  const r = await c.runActor('malonestar/demo', {});
  assert.equal(r.itemCount, 1, 'the lagging row was dropped and a zero was published instead');
  assert.equal(r.statusMessage, null, 'a run with rows must not carry the "matched nothing" note');
  assert.equal(fetchImpl.calls.length, 7, 'expected three settle reads');
});

test('a non-zero itemCount alone disproves "empty", even while items still reads []', async () => {
  const { c } = client([
    { ...RUN('SUCCEEDED') },
    ...READ(5, []),      // meta already knows about 5 rows; items has not caught up
    ...READ(5, []),
    ...READ(5, [{ a: 1 }, { a: 2 }, { a: 3 }, { a: 4 }, { a: 5 }]),
  ]);
  const r = await c.runActor('malonestar/demo', {});
  assert.equal(r.itemCount, 5);
});

test('a genuine zero is only accepted after repeated reads agree over a real time window', async () => {
  const { c, fetchImpl } = client([
    { ...RUN('SUCCEEDED') },
    ...READ(0, []),
    ...READ(0, []),
    ...READ(0, []),
  ]);
  const r = await c.runActor('malonestar/demo', {});
  assert.equal(r.itemCount, 0);
  assert.equal(fetchImpl.calls.length, 7, 'a zero was accepted on fewer than three reads');
  // The whole contract has to be stated, not just the tail of it: an agent must be
  // able to tell that the run SUCCEEDED, the query was well-formed, the source was
  // reached, and only then that it matched nothing.
  assert.match(r.statusMessage, /SUCCEEDED/);
  assert.match(r.statusMessage, /zero rows/);
  assert.match(r.statusMessage, /well-formed/);
  assert.match(r.statusMessage, /source was reached/);
  assert.match(r.statusMessage, /genuinely matched nothing/);
});

test('rows that never become readable are an explicit propagation error, never a zero', async () => {
  const script = [{ ...RUN('SUCCEEDED') }];
  for (let i = 0; i < 40; i++) script.push(...READ(3, []));
  const { c } = client(script);
  const r = await c.runActor('malonestar/demo', {});
  assert.equal(r.status, 'DATASET_UNSETTLED');
  assert.equal(r.itemCount, 0);
  assert.match(r.statusMessage, /reports 3 row\(s\)/);
  assert.match(r.statusMessage, /not an empty result/);
});

// --- Run-status honesty --------------------------------------------------------

test('a FAILED run resolves with the failure, never with an empty success', async () => {
  const { c } = client([{ ...RUN('FAILED', { statusMessage: 'upstream returned HTTP 503' }) }]);
  const r = await c.runActor('malonestar/demo', {});
  assert.equal(r.status, 'FAILED');
  assert.equal(r.itemCount, 0);
  assert.match(r.statusMessage, /upstream returned HTTP 503/);
  assert.match(r.statusMessage, /never as "nothing was found"/);
});

test('the dataset is not even fetched when the run did not succeed', async () => {
  const { c, fetchImpl } = client([{ ...RUN('ABORTED') }]);
  await c.runActor('malonestar/demo', {});
  assert.equal(fetchImpl.calls.length, 1, 'a non-successful run must not read the dataset');
});

test('polling continues through non-terminal states', async () => {
  const { c, fetchImpl } = client([
    { ...RUN('READY') },
    { ...RUN('RUNNING') },
    { ...RUN('RUNNING') },
    { ...RUN('SUCCEEDED') },
    ...READ(1, [{ ok: true }]),
  ]);
  const r = await c.runActor('malonestar/demo', {}, { pollMs: 10 });
  assert.equal(r.itemCount, 1);
  assert.equal(fetchImpl.calls.length, 6);
});

test('a client-side wait timeout is reported as unfinished, not as zero results', async () => {
  const { c } = client([{ ...RUN('RUNNING') }]);
  const r = await c.runActor('malonestar/demo', {}, { waitSecs: -1 });
  assert.equal(r.status, 'CLIENT_TIMEOUT');
  assert.match(r.statusMessage, /NOT evidence that the source returned nothing/);
});

// --- Transport ----------------------------------------------------------------

test('429 and 5xx are retried with backoff, then fail loudly as a platform problem', async () => {
  const { c, fetchImpl } = client([
    { status: 429, body: {} },
    { status: 503, body: {} },
    { ...RUN('SUCCEEDED') },
    ...READ(1, [{ a: 1 }]),
  ]);
  const r = await c.runActor('malonestar/demo', {});
  assert.equal(r.status, 'SUCCEEDED');
  assert.equal(fetchImpl.calls.length, 5);

  const { c: c2 } = client([{ status: 500, body: {} }, { status: 500, body: {} }, { status: 500, body: {} }, { status: 500, body: {} }]);
  await assert.rejects(() => c2.runActor('malonestar/demo', {}), err => {
    assert.equal(err.retryable, true);
    assert.match(err.message, /no conclusion should be drawn about the underlying government source/);
    return true;
  });
});

test('a 4xx is an answer and is not retried', async () => {
  const { c, fetchImpl } = client([{ status: 404, body: { error: { type: 'record-not-found', message: 'Actor was not found' } } }]);
  await assert.rejects(() => c.runActor('malonestar/nope', {}), err => {
    assert.match(err.message, /record-not-found/);
    assert.equal(err.retryable, false);
    return true;
  });
  assert.equal(fetchImpl.calls.length, 1);
});

test('an HTML error page is reported as such, not parsed into a false empty result', async () => {
  const { c } = client([{ status: 200, body: '<!DOCTYPE html><html>maintenance</html>' }]);
  await assert.rejects(() => c.runActor('malonestar/demo', {}), err => {
    assert.match(err.message, /non-JSON body/);
    return true;
  });
});

test('maxItems is passed through to the dataset read', async () => {
  const { c } = client([
    { ...RUN('SUCCEEDED') },
    { match: '/datasets/ds1', body: { data: { itemCount: 1 } } },
    { match: 'limit=7', body: [{ a: 1 }] },
  ]);
  await c.runActor('malonestar/demo', {}, { maxItems: 7 });
});

test('TERMINAL_STATES covers every Apify terminal status', () => {
  assert.deepEqual([...TERMINAL_STATES].sort(), ['ABORTED', 'FAILED', 'SUCCEEDED', 'TIMED-OUT']);
});

test('index.js is wiring only — no scoring, ranking or filtering logic lives there', () => {
  const src = readFileSync(join(here, '..', 'src', 'index.js'), 'utf8');
  for (const forbidden of ['.sort(', '.filter(x', 'score', 'localeCompare']) {
    assert.equal(src.includes(forbidden), false, `decision logic "${forbidden}" leaked into index.js`);
  }
});
