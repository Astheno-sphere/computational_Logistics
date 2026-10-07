import { systemClock, type Clock } from './rate-limit.js';

export interface TtlCacheOptions {
  defaultTtlMs: number;
  staleAfterMs?: number;
  clock?: Clock;
  maxEntries?: number;
}

export interface TtlCacheEntry<T> {
  value: T;
  storedAt: number;
  expiresAt: number;
  stale: boolean;
}

export interface TtlCache<T> {
  get(key: string): TtlCacheEntry<T> | undefined;
  set(key: string, value: T, ttlMs?: number): void;
  delete(key: string): void;
  clear(): void;
  size(): number;
}

interface StoredEntry<T> {
  value: T;
  storedAt: number;
  expiresAt: number;
}

export function createTtlCache<T>(options: TtlCacheOptions): TtlCache<T> {
  if (options.defaultTtlMs <= 0) {
    throw new Error('TtlCacheOptions.defaultTtlMs must be positive');
  }
  const clock = options.clock ?? systemClock;
  const staleAfterMs = options.staleAfterMs ?? options.defaultTtlMs;
  const entries = new Map<string, StoredEntry<T>>();
  const maxEntries = options.maxEntries ?? Number.MAX_SAFE_INTEGER;

  const evictIfNeeded = () => {
    while (entries.size > maxEntries) {
      const oldestKey = entries.keys().next().value;
      if (oldestKey === undefined) break;
      entries.delete(oldestKey);
    }
  };

  return {
    get(key) {
      const entry = entries.get(key);
      if (!entry) return undefined;
      const nowMs = clock.now();
      if (nowMs >= entry.expiresAt) {
        entries.delete(key);
        return undefined;
      }
      return {
        value: entry.value,
        storedAt: entry.storedAt,
        expiresAt: entry.expiresAt,
        stale: nowMs - entry.storedAt >= staleAfterMs,
      };
    },
    set(key, value, ttlMs) {
      const effectiveTtl = ttlMs ?? options.defaultTtlMs;
      if (effectiveTtl <= 0) {
        throw new Error('ttlMs must be positive');
      }
      const nowMs = clock.now();
      entries.delete(key);
      entries.set(key, {
        value,
        storedAt: nowMs,
        expiresAt: nowMs + effectiveTtl,
      });
      evictIfNeeded();
    },
    delete(key) {
      entries.delete(key);
    },
    clear() {
      entries.clear();
    },
    size() {
      return entries.size;
    },
  };
}

const forbiddenKeyParts = new Set([
  'apikey',
  'api_key',
  'authorization',
  'auth_token',
  'authtoken',
  'bearer',
  'cookie',
  'set-cookie',
  'sessionid',
  'session_id',
  'password',
  'secret',
  'token',
]);

export interface CacheKeyPart {
  name: string;
  value: string | number | boolean | undefined | null;
}

export function buildCacheKey(parts: CacheKeyPart[]): string {
  const normalized: string[] = [];
  for (const part of parts) {
    if (part.value === undefined || part.value === null) continue;
    const nameLc = part.name.toLowerCase();
    if (forbiddenKeyParts.has(nameLc)) {
      throw new Error(`cache key part "${part.name}" is forbidden — credentials must not influence cache keys`);
    }
    normalized.push(`${nameLc}=${String(part.value)}`);
  }
  return normalized.sort().join('|');
}
