'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { createTraceContext, classifyTrace, correlateTrace } = require('./otel-correlator');

test('createTraceContext emits a W3C traceparent header', () => {
  const ctx = createTraceContext();
  assert.match(ctx.traceparent, /^00-[a-f0-9]{32}-[a-f0-9]{16}-01$/);
});

test('classifyTrace marks child-dominant traces as slow_dependency', () => {
  const result = classifyTrace({
    spans: [
      { operationName: 'GET /cases', durationMs: 1000 },
      { operationName: 'db.query', durationMs: 900 },
    ],
  });

  assert.equal(result.classification, 'slow_dependency');
  assert.equal(result.slowComponent, 'db.query');
});

test('correlateTrace uses injected fetcher and returns slow dependency details', async () => {
  const result = await correlateTrace('abc', {
    probe: { otel: { enabled: true, backend: 'jaeger', baseUrl: 'http://jaeger.local' } },
  }, {
    fetcher: async () => ({
      spans: [
        { operationName: 'GET /cases', durationMs: 1000 },
        { operationName: 'db.query', durationMs: 900 },
      ],
    }),
  });

  assert.equal(result.classification, 'slow_dependency');
  assert.equal(result.slowComponent, 'db.query');
});
