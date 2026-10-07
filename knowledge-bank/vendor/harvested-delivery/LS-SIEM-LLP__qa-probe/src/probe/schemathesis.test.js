'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const EventEmitter = require('events');
const { Readable } = require('stream');
const { parseSchemathesisOutput } = require('./schemathesis-parser');
const { runSchemathesis } = require('./schemathesis-runner');
const { classifyEndpoint } = require('../report/root-cause');

test('schemathesis parser emits validation_edge_case with payload hint', () => {
  const failures = parseSchemathesisOutput(JSON.stringify({
    failures: [{ method: 'POST', path: '/cases', check: 'not_a_server_error', payload: { age: -1 } }],
  }));

  assert.equal(failures[0].endpoint, 'POST /cases');
  assert.equal(failures[0].rootCause, 'validation_edge_case');
  assert.match(failures[0].fixHint, /age/);
});

test('schemathesis runner parses mocked JSON subprocess output', async () => {
  const spawn = () => {
    const child = new EventEmitter();
    child.stdout = Readable.from([JSON.stringify({ failures: [{ method: 'GET', path: '/health', check: 'status' }] })]);
    child.stderr = Readable.from([]);
    process.nextTick(() => child.emit('close', 1));
    return child;
  };
  const failures = await runSchemathesis({
    openApiUrl: './openapi.json',
    probe: { schemathesis: { enabled: true, command: 'schemathesis', hypothesisExamples: 1, timeoutMs: 1000 } },
  }, { spawn });

  assert.equal(failures[0].rootCause, 'validation_edge_case');
});

test('root cause classifier surfaces schemathesis failures', () => {
  const result = classifyEndpoint('POST /cases', {
    status: 200,
    schemathesisFailure: { check: 'payload accepted', fixHint: 'Reject invalid age' },
  }, {}, { probe: {} });
  assert.equal(result.rootCause, 'validation_edge_case');
  assert.match(result.fixHint, /Reject invalid age/);
});
