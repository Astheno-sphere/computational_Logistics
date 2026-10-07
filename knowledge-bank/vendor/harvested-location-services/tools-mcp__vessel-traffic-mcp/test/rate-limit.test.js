import assert from 'node:assert/strict';
import { test } from 'node:test';

import { createRateLimiter } from '../dist/util/rate-limit.js';

function fakeClock(start = 0) {
  let nowMs = start;
  return {
    now() {
      return nowMs;
    },
    advance(ms) {
      nowMs += ms;
    },
    set(ms) {
      nowMs = ms;
    },
  };
}

test('rate limiter is deterministic under injected clock — AISHub one-request-per-minute pattern', () => {
  const clock = fakeClock(1_000_000);
  const limiter = createRateLimiter({
    policy: { requestsPerInterval: 1, intervalMs: 60_000, scope: 'per-instance' },
    clock,
  });

  const first = limiter.consume('aishub');
  assert.equal(first.allowed, true);
  assert.equal(first.remaining, 0);

  const second = limiter.consume('aishub');
  assert.equal(second.allowed, false);
  assert.equal(second.retryAfterMs, 60_000);

  clock.advance(30_000);
  const third = limiter.consume('aishub');
  assert.equal(third.allowed, false);
  assert.equal(third.retryAfterMs, 30_000);

  clock.advance(30_000);
  const fourth = limiter.consume('aishub');
  assert.equal(fourth.allowed, true);
});

test('check() does not consume tokens', () => {
  const clock = fakeClock();
  const limiter = createRateLimiter({
    policy: { requestsPerInterval: 2, intervalMs: 1000 },
    clock,
  });

  const peek = limiter.check();
  assert.equal(peek.allowed, true);
  assert.equal(peek.remaining, 2);

  const after = limiter.consume();
  assert.equal(after.allowed, true);
  assert.equal(after.remaining, 1);
});

test('per-key buckets are independent', () => {
  const clock = fakeClock();
  const limiter = createRateLimiter({
    policy: { requestsPerInterval: 1, intervalMs: 60_000 },
    clock,
  });

  assert.equal(limiter.consume('profile-a').allowed, true);
  assert.equal(limiter.consume('profile-a').allowed, false);
  assert.equal(limiter.consume('profile-b').allowed, true);
});

test('burst capacity controls steady-state allowance', () => {
  const clock = fakeClock();
  const limiter = createRateLimiter({
    policy: { requestsPerInterval: 1, intervalMs: 1000, burst: 3 },
    clock,
  });

  assert.equal(limiter.consume().allowed, true);
  assert.equal(limiter.consume().allowed, true);
  assert.equal(limiter.consume().allowed, true);
  assert.equal(limiter.consume().allowed, false);

  clock.advance(1000);
  assert.equal(limiter.consume().allowed, true);
});

test('reset() clears bucket state for repeatable tests', () => {
  const clock = fakeClock();
  const limiter = createRateLimiter({
    policy: { requestsPerInterval: 1, intervalMs: 60_000 },
    clock,
  });

  assert.equal(limiter.consume('k').allowed, true);
  assert.equal(limiter.consume('k').allowed, false);
  limiter.reset('k');
  assert.equal(limiter.consume('k').allowed, true);

  limiter.reset();
  assert.equal(limiter.consume('k').allowed, true);
});

test('policy validation rejects zero/negative configuration', () => {
  assert.throws(
    () => createRateLimiter({ policy: { requestsPerInterval: 0, intervalMs: 1000 } }),
    /requestsPerInterval/,
  );
  assert.throws(
    () => createRateLimiter({ policy: { requestsPerInterval: 1, intervalMs: 0 } }),
    /intervalMs/,
  );
});
