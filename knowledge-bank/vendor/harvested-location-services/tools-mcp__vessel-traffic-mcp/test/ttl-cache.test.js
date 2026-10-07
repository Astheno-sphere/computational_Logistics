import assert from 'node:assert/strict';
import { test } from 'node:test';

import { buildCacheKey, createTtlCache } from '../dist/util/cache.js';

function fakeClock(start = 0) {
  let nowMs = start;
  return {
    now() {
      return nowMs;
    },
    advance(ms) {
      nowMs += ms;
    },
  };
}

test('ttl cache returns entries before expiry and drops them after', () => {
  const clock = fakeClock(1_000);
  const cache = createTtlCache({ defaultTtlMs: 1000, clock });

  cache.set('mmsi:111', { lat: 1.1, lon: 1.2 });
  const fresh = cache.get('mmsi:111');
  assert.deepEqual(fresh?.value, { lat: 1.1, lon: 1.2 });
  assert.equal(fresh?.stale, false);

  clock.advance(999);
  assert.deepEqual(cache.get('mmsi:111')?.value, { lat: 1.1, lon: 1.2 });

  clock.advance(1);
  assert.equal(cache.get('mmsi:111'), undefined);
  assert.equal(cache.size(), 0);
});

test('stale threshold flags entries that have not expired yet', () => {
  const clock = fakeClock();
  const cache = createTtlCache({ defaultTtlMs: 10_000, staleAfterMs: 5_000, clock });

  cache.set('k', 'v');
  assert.equal(cache.get('k')?.stale, false);
  clock.advance(5_000);
  assert.equal(cache.get('k')?.stale, true);
  clock.advance(4_999);
  assert.equal(cache.get('k')?.stale, true);
  clock.advance(1);
  assert.equal(cache.get('k'), undefined);
});

test('per-entry ttl override works', () => {
  const clock = fakeClock();
  const cache = createTtlCache({ defaultTtlMs: 10_000, clock });

  cache.set('short', 1, 100);
  cache.set('long', 2);

  clock.advance(150);
  assert.equal(cache.get('short'), undefined);
  assert.deepEqual(cache.get('long')?.value, 2);
});

test('maxEntries evicts oldest first', () => {
  const clock = fakeClock();
  const cache = createTtlCache({ defaultTtlMs: 10_000, clock, maxEntries: 2 });

  cache.set('a', 1);
  cache.set('b', 2);
  cache.set('c', 3);

  assert.equal(cache.get('a'), undefined);
  assert.deepEqual(cache.get('b')?.value, 2);
  assert.deepEqual(cache.get('c')?.value, 3);
});

test('buildCacheKey is deterministic regardless of part order', () => {
  const a = buildCacheKey([
    { name: 'mmsi', value: '111' },
    { name: 'box', value: 'NW' },
  ]);
  const b = buildCacheKey([
    { name: 'box', value: 'NW' },
    { name: 'mmsi', value: '111' },
  ]);
  assert.equal(a, b);
  assert.equal(a, 'box=NW|mmsi=111');
});

test('buildCacheKey forbids credential-shaped key parts', () => {
  assert.throws(
    () => buildCacheKey([{ name: 'api_key', value: 'secret-A' }]),
    /credentials must not influence cache keys/,
  );
  assert.throws(
    () => buildCacheKey([{ name: 'Authorization', value: 'Bearer abc' }]),
    /credentials must not influence cache keys/,
  );
  assert.throws(
    () => buildCacheKey([{ name: 'Cookie', value: 'session=1' }]),
    /credentials must not influence cache keys/,
  );
});

test('buildCacheKey skips undefined/null but keeps explicit empty strings', () => {
  const key = buildCacheKey([
    { name: 'mmsi', value: undefined },
    { name: 'imo', value: null },
    { name: 'name', value: '' },
  ]);
  assert.equal(key, 'name=');
});

test('TTL options validate positive defaults', () => {
  assert.throws(() => createTtlCache({ defaultTtlMs: 0 }), /defaultTtlMs/);
  assert.throws(
    () => createTtlCache({ defaultTtlMs: 1000 }).set('x', 1, -1),
    /ttlMs must be positive/,
  );
});
