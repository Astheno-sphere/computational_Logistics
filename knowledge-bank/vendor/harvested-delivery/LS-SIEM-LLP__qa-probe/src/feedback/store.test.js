'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');

const { addLabel, loadFeedback, applyFeedback, applicableLabel } = require('./store.js');

function tmpConfig() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'qaprobe-fb-'));
  return { output: { dir } };
}

describe('feedback store — write & read', () => {
  test('addLabel persists a label that loadFeedback reads back', () => {
    const config = tmpConfig();
    const { label } = addLabel(config, { endpoint: 'GET /alerts', verdict: 'expected', reason: 'demo db is empty by design', by: 'human' });
    assert.equal(label.verdict, 'expected');
    assert.equal(label.effect, 'suppress');
    assert.equal(label.by, 'human');
    assert.ok(label.at, 'timestamp recorded');

    const store = loadFeedback(config);
    assert.equal(store.labels['GET /alerts'].reason, 'demo db is empty by design');
  });

  test('invalid verdict is rejected', () => {
    const config = tmpConfig();
    assert.throws(() => addLabel(config, { endpoint: 'GET /x', verdict: 'maybe' }), /Invalid verdict/);
  });

  test('missing endpoint is rejected', () => {
    const config = tmpConfig();
    assert.throws(() => addLabel(config, { verdict: 'expected' }), /endpoint is required/);
  });

  test('loadFeedback returns an empty store when no file exists', () => {
    const store = loadFeedback(tmpConfig());
    assert.deepEqual(store.labels, {});
  });
});

describe('feedback store — apply onto classifications', () => {
  test('suppress verdict reclassifies the cause as acknowledged with provenance', () => {
    const config = tmpConfig();
    addLabel(config, { endpoint: 'GET /alerts', verdict: 'expected', reason: 'empty by design', by: 'ai' });
    const causes = { 'GET /alerts': { rootCause: 'empty_db', rootCauseDetail: 'x', fixHint: 'seed' } };

    const applied = applyFeedback(causes, config);

    assert.equal(causes['GET /alerts'].rootCause, 'acknowledged');
    assert.equal(causes['GET /alerts'].acknowledged, true);
    assert.equal(causes['GET /alerts'].priorRootCause, 'empty_db');
    assert.equal(causes['GET /alerts'].feedback.by, 'ai');
    assert.match(causes['GET /alerts'].rootCauseDetail, /acknowledged via feedback/i);
    assert.equal(causes['GET /alerts'].fixHint, null);
    assert.equal(applied.length, 1);
    assert.equal(applied[0].effect, 'suppress');
  });

  test('confirm verdict keeps the diagnosis but marks it confirmed + high confidence', () => {
    const config = tmpConfig();
    addLabel(config, { endpoint: 'GET /reports', verdict: 'bug', reason: 'real 500' });
    const causes = { 'GET /reports': { rootCause: 'server_error' } };

    applyFeedback(causes, config);

    assert.equal(causes['GET /reports'].rootCause, 'server_error', 'still flagged');
    assert.equal(causes['GET /reports'].confirmed, true);
    assert.equal(causes['GET /reports'].confidence, 'high');
  });

  test('honesty guard: a signal-scoped label does NOT apply once the result changes', () => {
    const config = tmpConfig();
    // "this empty_db is expected" — scoped to empty_db only
    addLabel(config, { endpoint: 'GET /alerts', verdict: 'expected', signal: 'empty_db' });
    const store = loadFeedback(config);

    // Endpoint now returns a real server_error — the old label must NOT suppress it.
    assert.equal(applicableLabel(store, 'GET /alerts', 'server_error'), null);
    assert.ok(applicableLabel(store, 'GET /alerts', 'empty_db'), 'still applies while empty_db');

    const causes = { 'GET /alerts': { rootCause: 'server_error' } };
    applyFeedback(causes, config);
    assert.equal(causes['GET /alerts'].rootCause, 'server_error', 'regression is not hidden');
  });

  test("signal: 'any' (default) applies regardless of rootCause", () => {
    const config = tmpConfig();
    addLabel(config, { endpoint: 'GET /x', verdict: 'ignore' });
    const causes = { 'GET /x': { rootCause: 'invalid_sample_params' } };
    applyFeedback(causes, config);
    assert.equal(causes['GET /x'].rootCause, 'acknowledged');
  });
});
