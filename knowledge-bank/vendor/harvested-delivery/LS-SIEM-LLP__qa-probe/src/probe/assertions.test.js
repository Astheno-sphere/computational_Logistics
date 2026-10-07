'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
const { evaluateAssertions, resolveField, assertionsForEndpoint } = require('./assertions.js');
const { classifyEndpoint } = require('../report/root-cause.js');

describe('resolveField', () => {
  test('dot path', () => {
    assert.deepEqual(resolveField({ a: { b: 5 } }, 'a.b'), [5]);
  });
  test('array wildcard fans out', () => {
    assert.deepEqual(resolveField({ items: [{ id: 1 }, { id: 2 }] }, 'items[].id'), [1, 2]);
  });
  test('root path returns the whole body', () => {
    assert.deepEqual(resolveField([1, 2], ''), [[1, 2]]);
  });
});

describe('evaluateAssertions', () => {
  test('passing invariants produce no failures', () => {
    const body = { total: 3, items: [{ severity: 'high' }, { severity: 'low' }] };
    const rules = [
      { field: 'total', gte: 0 },
      { field: 'items', type: 'array', maxItems: 100 },
      { field: 'items[].severity', in: ['low', 'medium', 'high', 'critical'] },
    ];
    assert.deepEqual(evaluateAssertions(body, rules), []);
  });

  test('enum violation on a wildcard field is caught', () => {
    const body = { items: [{ severity: 'high' }, { severity: 'BOGUS' }] };
    const fails = evaluateAssertions(body, [{ field: 'items[].severity', in: ['low', 'high'] }]);
    assert.equal(fails.length, 1);
    assert.match(fails[0], /BOGUS.*not in/);
  });

  test('numeric bound violation is caught', () => {
    const fails = evaluateAssertions({ total: -2 }, [{ field: 'total', gte: 0 }]);
    assert.match(fails[0], /-2 < 0/);
  });

  test('present + type are checked', () => {
    const fails = evaluateAssertions({ items: [] }, [{ field: 'name', present: true }]);
    assert.match(fails[0], /expected present/);
  });

  test('absent optional field is not flagged unless present is asserted', () => {
    assert.deepEqual(evaluateAssertions({}, [{ field: 'maybe', type: 'string' }]), []);
  });

  test('maxItems violation', () => {
    const fails = evaluateAssertions({ items: [1, 2, 3] }, [{ field: 'items', maxItems: 2 }]);
    assert.match(fails[0], /expected <= 2 items/);
  });
});

describe('assertionsForEndpoint', () => {
  test('looks up rules by "METHOD path"', () => {
    const config = { assertions: { 'GET /alerts': [{ field: 'total', gte: 0 }] } };
    assert.ok(assertionsForEndpoint(config, 'get', '/alerts'));
    assert.equal(assertionsForEndpoint(config, 'POST', '/alerts'), null);
  });
});

describe('classifier surfaces assertion failures', () => {
  test('assertionFailures → assertion_failed (high confidence), before empty/ok', () => {
    const r = classifyEndpoint('GET /alerts',
      { status: 200, empty: false, assertionFailures: ['total: -1 < 0'] },
      {}, { probe: {} });
    assert.equal(r.rootCause, 'assertion_failed');
    assert.equal(r.confidence, 'high');
    assert.match(r.rootCauseDetail, /assertion\(s\) failed/);
  });

  test('no assertionFailures → normal classification', () => {
    const r = classifyEndpoint('GET /alerts', { status: 200, empty: false }, {}, { probe: {} });
    assert.notEqual(r.rootCause, 'assertion_failed');
  });
});
