'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const { scoreRoute } = require('./scorer.js');

describe('scoreRoute', () => {
  test('does not penalize expected-empty quiet queues or generated sample misses', () => {
    const scored = scoreRoute(
      '/parsers',
      {
        apiCalls: [
          { method: 'GET', backendPath: '/parsers/quarantine' },
          { method: 'GET', backendPath: '/cases/1' },
        ],
      },
      {
        'GET /parsers/quarantine': { status: 200, empty: true },
        'GET /cases/1': { status: 404 },
      },
      {
        'GET /parsers/quarantine': { rootCause: 'expected_empty' },
        'GET /cases/1': { rootCause: 'sample_unavailable' },
      },
      { scoring: {} },
    );

    assert.equal(scored.score, 100);
    assert.equal(scored.status, 'healthy');
    assert.deepEqual(scored.penalties, []);
  });
});
