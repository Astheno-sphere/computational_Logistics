import type { RateLimitPolicy } from '../providers/types.js';

export interface Clock {
  now(): number;
}

export const systemClock: Clock = {
  now() {
    return Date.now();
  },
};

export interface RateLimiterOptions {
  policy: RateLimitPolicy;
  clock?: Clock;
}

export interface RateLimitDecision {
  allowed: boolean;
  remaining: number;
  retryAfterMs: number;
}

interface BucketState {
  tokens: number;
  lastRefillMs: number;
}

export interface RateLimiter {
  check(key?: string): RateLimitDecision;
  consume(key?: string): RateLimitDecision;
  reset(key?: string): void;
  policy(): RateLimitPolicy;
}

export function createRateLimiter(options: RateLimiterOptions): RateLimiter {
  const { policy } = options;
  if (policy.requestsPerInterval <= 0) {
    throw new Error('RateLimitPolicy.requestsPerInterval must be positive');
  }
  if (policy.intervalMs <= 0) {
    throw new Error('RateLimitPolicy.intervalMs must be positive');
  }

  const clock = options.clock ?? systemClock;
  const capacity = Math.max(policy.burst ?? policy.requestsPerInterval, 1);
  const refillPerMs = policy.requestsPerInterval / policy.intervalMs;
  const buckets = new Map<string, BucketState>();

  const refill = (state: BucketState): BucketState => {
    const nowMs = clock.now();
    const elapsed = Math.max(0, nowMs - state.lastRefillMs);
    const tokens = Math.min(capacity, state.tokens + elapsed * refillPerMs);
    return { tokens, lastRefillMs: nowMs };
  };

  const bucketFor = (key: string): BucketState => {
    const existing = buckets.get(key);
    if (existing) return existing;
    const fresh: BucketState = { tokens: capacity, lastRefillMs: clock.now() };
    buckets.set(key, fresh);
    return fresh;
  };

  const decide = (key: string, consume: boolean): RateLimitDecision => {
    const refreshed = refill(bucketFor(key));
    if (refreshed.tokens >= 1) {
      const next: BucketState = consume
        ? { tokens: refreshed.tokens - 1, lastRefillMs: refreshed.lastRefillMs }
        : refreshed;
      buckets.set(key, next);
      return {
        allowed: true,
        remaining: Math.floor(next.tokens),
        retryAfterMs: 0,
      };
    }
    buckets.set(key, refreshed);
    const missing = 1 - refreshed.tokens;
    const retryAfterMs = Math.ceil(missing / refillPerMs);
    return {
      allowed: false,
      remaining: 0,
      retryAfterMs,
    };
  };

  return {
    check(key = 'default') {
      return decide(key, false);
    },
    consume(key = 'default') {
      return decide(key, true);
    },
    reset(key) {
      if (key === undefined) {
        buckets.clear();
      } else {
        buckets.delete(key);
      }
    },
    policy() {
      return { ...policy };
    },
  };
}
