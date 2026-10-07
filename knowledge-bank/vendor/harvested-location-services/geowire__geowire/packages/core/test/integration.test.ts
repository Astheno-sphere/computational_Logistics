import { describe, it, expect } from "vitest";
import { dedup } from "../src/pipeline/dedup/dedup.js";
import { createGeoWire } from "../src/geowire.js";
import { fakeProvider, place, builtPlace } from "./helpers.js";

/**
 * 같은 장소가 Google/OSM에서 이름 표기만 다르게 나오는 10쌍 (설계 §7.3 DoD).
 * 각 쌍은 사실상 동일 좌표 → 병합되어야 한다. 쌍끼리는 멀리 떨어뜨려 교차 병합을 방지.
 */
const NAME_VARIANT_PAIRS: [string, string][] = [
  ["Pharmacie Centrale", "Pharmacie Centrale SARL"],
  ["GS25 Gangnam", "GS25 Gangnam Branch"],
  ["Starbucks Coffee", "Starbucks"],
  ["McDonald's", "McDonalds"],
  ["7-Eleven", "7 Eleven"],
  ["Nhà thuốc Long Châu", "Nha thuoc Long Chau"],
  ["Café de Flore", "Cafe de Flore"],
  ["Deutsche Bank AG", "Deutsche Bank"],
  ["The Coffee Bean & Tea Leaf", "Coffee Bean and Tea Leaf"],
  ["김밥천국 강남점", "김밥천국"],
];

describe("dedup 정확도 스냅샷 — 이름 표기만 다른 동일 장소 10쌍", () => {
  it("각 쌍이 병합되어 20건 → 10건이 된다", () => {
    const places = NAME_VARIANT_PAIRS.flatMap(([a, b], i) => {
      const lat = 10 + i; // 쌍마다 위도 1도 차이(쌍 간 분리)
      const lon = 20 + i;
      return [
        builtPlace({ provider: "osm", providerPlaceId: `osm-${i}`, name: a, location: { latitude: lat, longitude: lon } }),
        builtPlace({ provider: "google", providerPlaceId: `g-${i}`, name: b, location: { latitude: lat + 0.00008, longitude: lon + 0.00008 } }),
      ];
    });
    const res = dedup(places, { mergeThreshold: 0.75, providerRank: () => 0 });
    expect(res.before).toBe(20);
    expect(res.after).toBe(10);
    // 각 병합 결과는 정확히 2개 소스
    for (const p of res.merged) expect(p.sources).toHaveLength(2);
  });
});

describe("BYOK — 키 없는 유료 공급자 skip (3-공급자 merge)", () => {
  it("google 키 없음 → skipped, 나머지 2개로 merge 결과를 낸다", async () => {
    const geo = createGeoWire({
      config: { routing: { defaultStrategy: "merge" }, providers: { internal: { priority: 100 } } },
      providers: [
        fakeProvider({
          id: "internal",
          search: [place({ providerPlaceId: "store-1", name: "우리매장", location: { latitude: 37.5, longitude: 127.0 } })],
        }),
        fakeProvider({
          id: "nominatim",
          policy: { maxCacheTtlSeconds: 86400, canStorePermanently: true, attributionRequired: "© OpenStreetMap contributors" },
          search: [place({ providerPlaceId: "node-9", name: "다른곳", location: { latitude: 40, longitude: 100 } })],
        }),
        fakeProvider({ id: "google", authType: "apiKey", failWith: "MISSING_CREDENTIALS" }),
      ],
    });
    const res = await geo.searchPlaces({ query: "매장" });

    expect(res.meta.providersSkipped).toContainEqual({ provider: "google", reason: "MISSING_CREDENTIALS" });
    expect(res.meta.providersFailed).toEqual([]);
    expect(res.meta.providersUsed.map((u) => u.provider).sort()).toEqual(["internal", "nominatim"]);
    // 고객 자체 데이터(priority 100)가 최상위
    expect(res.results[0]!.name).toBe("우리매장");
  });

  it("google 키가 있으면(성공) merge 결과에 google 소스가 등장한다", async () => {
    const geo = createGeoWire({
      config: { routing: { defaultStrategy: "merge" } },
      providers: [
        fakeProvider({
          id: "nominatim",
          search: [place({ providerPlaceId: "node-1", name: "GS25", location: { latitude: 37.5, longitude: 127.0 } })],
        }),
        fakeProvider({
          id: "google",
          authType: "apiKey",
          cost: { currency: "USD", perCall: { search: 0.032 } },
          search: [place({ providerPlaceId: "ChIJ-1", name: "GS25 Gangnam", location: { latitude: 37.5, longitude: 127.0 } })],
        }),
      ],
    });
    const res = await geo.searchPlaces({ query: "GS25" });
    expect(res.results).toHaveLength(1);
    expect(res.results[0]!.sources.map((s) => s.provider).sort()).toEqual(["google", "nominatim"]);
    expect(res.meta.estimatedCostUSD).toBeCloseTo(0.032);
  });
});

describe("fallback — 죽은 공급자 → 다음으로 전환", () => {
  it("first-success에서 1순위 실패 시 2순위로 폴백하고 meta에 기록한다", async () => {
    const geo = createGeoWire({
      config: { providers: { primary: { priority: 10 }, secondary: { priority: 1 } } },
      providers: [
        fakeProvider({ id: "primary", failWith: "PROVIDER_UNAVAILABLE" }),
        fakeProvider({ id: "secondary", search: [place({ providerPlaceId: "s1", name: "폴백결과" })] }),
      ],
    });
    const res = await geo.searchPlaces({ query: "x" });
    expect(res.results[0]!.name).toBe("폴백결과");
    expect(res.meta.providersFailed).toEqual([{ provider: "primary", reason: "PROVIDER_UNAVAILABLE" }]);
    expect(res.meta.providersUsed.map((u) => u.provider)).toEqual(["secondary"]);
  });
});
