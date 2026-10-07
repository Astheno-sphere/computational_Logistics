import { createHash } from "node:crypto";
import type { Clock } from "@geowirehq/provider-sdk";
import type { CacheAdapter, CachedResponse } from "./adapter.js";

interface Entry {
  value: CachedResponse;
  expiresAtMs: number;
}

export interface MemoryCacheOptions {
  /** 최대 항목 수 (초과 시 LRU 방출). 기본 1000 */
  maxEntries?: number;
  /** 만료 판정용 시계. 기본 Date.now */
  now?: Clock;
}

/**
 * 인메모리 LRU 캐시 (설계 §7 cache/memory, §8.4).
 * 키는 정규화된 요청 해시. Map의 삽입 순서로 LRU를 구현한다(get 시 최근으로 갱신).
 * 만료 항목은 조회 시 지연 삭제한다.
 */
export class MemoryCache implements CacheAdapter {
  private readonly store = new Map<string, Entry>();
  private readonly maxEntries: number;
  private readonly now: Clock;

  constructor(options: MemoryCacheOptions = {}) {
    this.maxEntries = options.maxEntries ?? 1000;
    this.now = options.now ?? Date.now;
  }

  async get(key: string): Promise<CachedResponse | undefined> {
    const entry = this.store.get(key);
    if (!entry) return undefined;
    if (this.now() >= entry.expiresAtMs) {
      this.store.delete(key);
      return undefined;
    }
    // LRU 갱신: 삭제 후 재삽입으로 최근 위치로 이동
    this.store.delete(key);
    this.store.set(key, entry);
    return entry.value;
  }

  async set(key: string, value: CachedResponse): Promise<void> {
    this.store.delete(key);
    this.store.set(key, { value, expiresAtMs: this.now() + value.ttlSeconds * 1000 });
    while (this.store.size > this.maxEntries) {
      const oldest = this.store.keys().next().value;
      if (oldest === undefined) break;
      this.store.delete(oldest);
    }
  }

  async delete(key: string): Promise<void> {
    this.store.delete(key);
  }

  async clear(): Promise<void> {
    this.store.clear();
  }

  /** 현재 항목 수 (테스트·진단용) */
  get size(): number {
    return this.store.size;
  }
}

/**
 * 정규화된 요청으로 안정적 캐시 키를 만든다.
 * 연산 종류(capability) + 요청 필드를 정렬 직렬화해 해시한다 —
 * 키 순서·미지정 옵션에 관계없이 동일 의미의 요청은 같은 키를 얻는다.
 */
export function cacheKey(capability: string, request: unknown): string {
  const canonical = stableStringify({ capability, request });
  return createHash("sha256").update(canonical).digest("base64url").slice(0, 32);
}

/** 키 정렬 직렬화 (undefined 필드 제외) — 캐시 키 안정성 보장 */
function stableStringify(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value) ?? "null";
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  const entries = Object.entries(value as Record<string, unknown>)
    .filter(([, v]) => v !== undefined)
    .sort(([a], [b]) => a.localeCompare(b));
  return `{${entries.map(([k, v]) => `${JSON.stringify(k)}:${stableStringify(v)}`).join(",")}}`;
}
