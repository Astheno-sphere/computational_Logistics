import { describe, it, expect } from "vitest";
import { createGeoWire } from "../src/geowire.js";
import { fakeProvider, place } from "./helpers.js";

const FIXED = Date.parse("2026-07-17T00:00:00.000Z");

describe("cache (M4)", () => {
  it("동일 요청 재호출은 cache hit — 공급자를 다시 호출하지 않는다", async () => {
    let calls = 0;
    const geo = createGeoWire({
      now: () => FIXED,
      providers: [
        fakeProvider({
          id: "nominatim",
          policy: { maxCacheTtlSeconds: 86400, canStorePermanently: true, attributionRequired: "© OSM" },
          onCall: () => { calls++; },
          search: [place({ providerPlaceId: "1", name: "약국" })],
        }),
      ],
    });
    const r1 = await geo.searchPlaces({ query: "약국" });
    expect(r1.meta.cache).toEqual({ hit: false });
    const r2 = await geo.searchPlaces({ query: "약국" });
    expect(r2.meta.cache?.hit).toBe(true);
    expect(r2.meta.cache?.ttlSeconds).toBe(3600); // min(default 3600, osm 86400)
    expect(calls).toBe(1);
    expect(r2.results[0]!.name).toBe("약국");
  });

  it("캐시 금지 소스(google null)가 병합에 기여하면 응답을 캐시하지 않는다 (혼합 정책 불변식)", async () => {
    let calls = 0;
    const geo = createGeoWire({
      now: () => FIXED,
      config: { routing: { defaultStrategy: "merge" } },
      providers: [
        fakeProvider({
          id: "nominatim",
          policy: { maxCacheTtlSeconds: 86400, canStorePermanently: true },
          search: [place({ providerPlaceId: "1", name: "GS25", location: { latitude: 37.5, longitude: 127 } })],
        }),
        fakeProvider({
          id: "google",
          policy: { maxCacheTtlSeconds: null, canStorePermanently: false },
          onCall: () => { calls++; },
          search: [place({ providerPlaceId: "g1", name: "GS25", location: { latitude: 37.5, longitude: 127 } })],
        }),
      ],
    });
    await geo.searchPlaces({ query: "GS25" });
    const r2 = await geo.searchPlaces({ query: "GS25" });
    expect(r2.meta.cache?.hit).toBe(false); // 캐시되지 않았으므로 여전히 miss
    expect(calls).toBe(2); // google이 두 번 다 호출됨
  });
});

describe("budget gate (M4)", () => {
  it("요청당 예산 초과 유료 공급자는 QUOTA_EXCEEDED로 제외하고 무료로 폴백", async () => {
    const geo = createGeoWire({
      now: () => FIXED,
      config: {
        routing: { defaultStrategy: "merge" },
        budget: { perRequestMaxUSD: 0.01 },
        providers: { google: { priority: 10 }, nominatim: { priority: 1 } },
      },
      providers: [
        fakeProvider({
          id: "google",
          authType: "apiKey",
          cost: { currency: "USD", perCall: { search: 0.032 } },
          search: [place({ providerPlaceId: "g", name: "구글" })],
        }),
        fakeProvider({ id: "nominatim", search: [place({ providerPlaceId: "n", name: "OSM" })] }),
      ],
    });
    const res = await geo.searchPlaces({ query: "x" });
    expect(res.meta.providersSkipped).toContainEqual({ provider: "google", reason: "QUOTA_EXCEEDED" });
    expect(res.meta.providersUsed.map((u) => u.provider)).toEqual(["nominatim"]);
    expect(res.meta.estimatedCostUSD).toBeUndefined(); // 무료만 사용
  });

  it("유료 공급자 사용 시 estimatedCostUSD를 meta에 노출한다", async () => {
    const geo = createGeoWire({
      now: () => FIXED,
      config: { budget: { perRequestMaxUSD: 1 } },
      providers: [
        fakeProvider({
          id: "google",
          authType: "apiKey",
          cost: { currency: "USD", perCall: { search: 0.032 } },
          search: [place({ providerPlaceId: "g", name: "구글" })],
        }),
      ],
    });
    const res = await geo.searchPlaces({ query: "x" });
    expect(res.meta.estimatedCostUSD).toBeCloseTo(0.032);
  });
});

describe("circuit breaker (M4)", () => {
  it("연속 실패가 임계값에 도달하면 이후 요청에서 공급자를 skip한다", async () => {
    let calls = 0;
    const geo = createGeoWire({
      now: () => FIXED, // 시간 고정 → cooldown 미경과
      providers: [
        fakeProvider({ id: "dead", onCall: () => { calls++; }, failWith: "PROVIDER_UNAVAILABLE" }),
        fakeProvider({ id: "backup", search: [place({ providerPlaceId: "b", name: "백업" })] }),
      ],
      config: { providers: { dead: { priority: 10 }, backup: { priority: 1 } } },
    });
    // 기본 임계값 5회 — 5번 요청하면 dead가 5회 실패해 회로 open
    for (let i = 0; i < 5; i++) {
      const res = await geo.searchPlaces({ query: `q${i}` }); // 매번 다른 쿼리(캐시 회피)
      expect(res.results[0]!.name).toBe("백업");
    }
    expect(calls).toBe(5);
    // 6번째: dead는 회로 open → 호출되지 않고 skipped
    const res6 = await geo.searchPlaces({ query: "q6" });
    expect(calls).toBe(5); // 호출 수 증가 없음
    expect(res6.meta.providersSkipped).toContainEqual({ provider: "dead", reason: "PROVIDER_UNAVAILABLE" });
    expect(res6.results[0]!.name).toBe("백업");
  });
});
