import assert from 'node:assert/strict';
import test from 'node:test';

import {
  isLocalDisplayHost,
  selectDisplayProfile
} from '../static/modules/display-runtime.js';

test('recognizes loopback hosts as local display surfaces', () => {
  assert.equal(isLocalDisplayHost('localhost'), true);
  assert.equal(isLocalDisplayHost('127.0.0.1'), true);
  assert.equal(isLocalDisplayHost('[::1]'), true);
  assert.equal(isLocalDisplayHost('app.daedalmap.com'), false);
});

test('selects a local power profile unless the local device is explicitly small', () => {
  assert.equal(selectDisplayProfile({ hostname: 'localhost', hardwareConcurrency: 12 }), 'localPower');
  assert.equal(selectDisplayProfile({ hostname: 'localhost', deviceMemory: 4 }), 'hostedSafe');
});

test('uses enhanced hosted budgets only for capable unconstrained devices', () => {
  const capable = { hostname: 'app.daedalmap.com', deviceMemory: 16, hardwareConcurrency: 12 };
  assert.equal(selectDisplayProfile(capable), 'hostedEnhanced');
  assert.equal(selectDisplayProfile({ ...capable, saveData: true }), 'hostedSafe');
  assert.equal(selectDisplayProfile({ ...capable, effectiveType: '3g' }), 'hostedSafe');
});

