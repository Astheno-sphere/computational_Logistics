import { describe, it, expect } from "vitest";
import { MemoryCache, cacheKey } from "../src/cache/memory.js";
import type { CachedResponse } from "../src/cache/adapter.js";

const sample = (ttl = 100): CachedResponse => ({
  results: [],
  meta: {
    providersUsed: [],
    providersSkipped: [],
    providersFailed: [],
    strategy: "first-success",
    attributions: [],
  },
  ttlSeconds: ttl,
});

describe("MemoryCache", () => {
  it("set 후 get으로 조회된다", async () => {
    const c = new MemoryCache({ now: () => 0 });
    await c.set("k", sample());
    expect(await c.get("k")).toBeDefined();
  });

  it("TTL 경과 후 만료된다", async () => {
    let t = 0;
    const c = new MemoryCache({ now: () => t });
    await c.set("k", sample(10)); // 만료 = 10_000ms
    t = 9_999;
    expect(await c.get("k")).toBeDefined();
    t = 10_000;
    expect(await c.get("k")).toBeUndefined();
  });

  it("maxEntries 초과 시 LRU 방출", async () => {
    const c = new MemoryCache({ now: () => 0, maxEntries: 2 });
    await c.set("a", sample());
    await c.set("b", sample());
    await c.get("a"); // a를 최근으로 승격
    await c.set("c", sample()); // b가 가장 오래됨 → 방출
    expect(await c.get("a")).toBeDefined();
    expect(await c.get("b")).toBeUndefined();
    expect(await c.get("c")).toBeDefined();
    expect(c.size).toBe(2);
  });
});

describe("cacheKey", () => {
  it("키 순서·미지정 옵션에 무관하게 안정적", () => {
    const k1 = cacheKey("search", { query: "a", limit: 10, near: undefined });
    const k2 = cacheKey("search", { limit: 10, query: "a" });
    expect(k1).toBe(k2);
  });

  it("다른 요청은 다른 키", () => {
    expect(cacheKey("search", { query: "a" })).not.toBe(cacheKey("search", { query: "b" }));
    expect(cacheKey("search", { query: "a" })).not.toBe(cacheKey("geocode", { query: "a" }));
  });
});
