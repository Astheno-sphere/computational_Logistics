'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const { computeDensityFromSnapshot } = require('./layout-density');

describe('layout density', () => {
  test('computes density from rendered snapshot bounds', () => {
    const result = computeDensityFromSnapshot({
      root: {
        nodeName: 'BODY',
        rect: { width: 100, height: 100 },
        children: [
          { nodeName: 'DIV', rect: { width: 50, height: 50 }, children: [{ nodeName: '#text', nodeValue: 'Cases' }] },
        ],
      },
    }, { width: 100, height: 100 });

    assert.equal(result.viewportArea, 10000);
    assert.ok(result.density > 0.25);
    assert.equal(result.textNodeCount, 1);
  });

  test('blank snapshots produce near-zero density', () => {
    const result = computeDensityFromSnapshot({ root: { nodeName: 'BODY', children: [] } }, { width: 1280, height: 720 });
    assert.equal(result.density, 0);
    assert.equal(result.nonEmptyContainerCount, 0);
  });
});
