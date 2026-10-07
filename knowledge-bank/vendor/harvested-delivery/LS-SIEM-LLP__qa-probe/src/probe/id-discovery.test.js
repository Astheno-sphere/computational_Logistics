'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
const {
  partitionByParams, harvestCollectionItems, discoverFills, applyDiscoveredIds, idFromItem,
} = require('./id-discovery.js');

describe('partitionByParams', () => {
  test('splits {param} routes from param-less ones', () => {
    const eps = [
      { method: 'GET', path: '/cases', routeKey: 'GET /cases' },
      { method: 'GET', path: '/cases/1', routeKey: 'GET /cases/{case_id}' },
    ];
    const { withParams, withoutParams } = partitionByParams(eps);
    assert.equal(withoutParams.length, 1);
    assert.equal(withParams.length, 1);
    assert.equal(withParams[0].routeKey, 'GET /cases/{case_id}');
  });
});

describe('harvestCollectionItems', () => {
  test('maps collection path → first item from probed GET results', () => {
    const results = {
      'GET /cases': { status: 200, firstItem: { id: 42, name: 'x' } },
      'POST /cases': { status: 200, firstItem: { id: 99 } }, // non-GET ignored
      'GET /empty': { status: 200, firstItem: null },
    };
    const m = harvestCollectionItems(results);
    assert.deepEqual(m.get('/cases'), { id: 42, name: 'x' });
    assert.equal(m.has('/empty'), false);
  });
});

describe('idFromItem', () => {
  test('prefers the param name, then common id fields', () => {
    assert.equal(idFromItem({ case_id: 7, id: 1 }, 'case_id'), '7');
    assert.equal(idFromItem({ id: 1, uuid: 'u' }, 'missing'), '1');
    assert.equal(idFromItem({ slug: 'abc' }, 'x'), 'abc');
    assert.equal(idFromItem({ nested: {} }, 'x'), null);
  });
});

describe('discoverFills', () => {
  test('derives the collection ("/cases") for "/cases/{case_id}"', () => {
    const items = new Map([['/cases', { id: 42 }]]);
    assert.deepEqual(discoverFills('GET /cases/{case_id}', items), { case_id: '42' });
  });
  test('handles a suffix route ("/cases/{id}/tags")', () => {
    const items = new Map([['/cases', { id: 7 }]]);
    assert.deepEqual(discoverFills('GET /cases/{id}/tags', items), { id: '7' });
  });
  test('no collection probed → no fill (falls back to defaults elsewhere)', () => {
    assert.deepEqual(discoverFills('GET /cases/{id}', new Map()), {});
  });
});

describe('applyDiscoveredIds', () => {
  test('rewrites the detail path with a real id and records it', () => {
    const eps = [{ method: 'GET', path: '/cases/1', routeKey: 'GET /cases/{case_id}' }];
    const items = new Map([['/cases', { id: 42 }]]);
    const applied = applyDiscoveredIds(eps, items, { probe: {} });
    assert.equal(applied, 1);
    assert.equal(eps[0].path, '/cases/42');
    assert.deepEqual(eps[0].discoveredIds, { case_id: '42' });
  });

  test('falls back to config default when nothing discovered', () => {
    const eps = [{ method: 'GET', path: '/cases/1', routeKey: 'GET /cases/{id}' }];
    const applied = applyDiscoveredIds(eps, new Map(), { probe: { pathParamValues: { id: '5' } } });
    assert.equal(applied, 0);
    assert.equal(eps[0].path, '/cases/1', 'path unchanged when no discovery');
  });
});
