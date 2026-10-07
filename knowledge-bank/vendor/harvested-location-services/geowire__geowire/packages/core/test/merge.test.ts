import { describe, it, expect } from "vitest";
import { createGeoWire } from "../src/geowire.js";
import { fakeProvider, place } from "./helpers.js";

describe("merge 전략 E2E", () => {
  it("두 공급자를 병렬 호출하고 동일 장소를 병합한다", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({
          id: "nominatim",
          policy: { maxCacheTtlSeconds: 86400, canStorePermanently: true, attributionRequired: "© OSM" },
          search: [place({ providerPlaceId: "node/1", name: "GS25 Gangnam", location: { latitude: 37.498, longitude: 127.028 } })],
        }),
        fakeProvider({
          id: "google",
          policy: { maxCacheTtlSeconds: null, canStorePermanently: false, attributionRequired: "Powered by Google" },
          search: [place({ providerPlaceId: "ChIJ1", name: "GS25 Gangnam Branch", location: { latitude: 37.4981, longitude: 127.0281 } })],
        }),
      ],
      config: { routing: { defaultStrategy: "merge" } },
    });
    const res = await geo.searchPlaces({ query: "GS25" });
    expect(res.meta.strategy).toBe("merge");
    expect(res.meta.dedup).toEqual({ before: 2, after: 1 });
    expect(res.results).toHaveLength(1);
    expect(res.results[0]!.sources).toHaveLength(2);
    // 두 공급자 모두 사용됨
    expect(res.meta.providersUsed.map((u) => u.provider).sort()).toEqual(["google", "nominatim"]);
    // attribution 합집합
    expect(res.meta.attributions.sort()).toEqual(["Powered by Google", "© OSM"]);
    expect(res.results[0]!.attributions.sort()).toEqual(["Powered by Google", "© OSM"]);
  });

  it("merge에서 서로 다른 장소는 둘 다 유지한다", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({ id: "a", search: [place({ providerPlaceId: "1", name: "Pharmacy", location: { latitude: 10, longitude: 20 } })] }),
        fakeProvider({ id: "b", search: [place({ providerPlaceId: "2", name: "Cafe", location: { latitude: 40, longitude: 100 } })] }),
      ],
      config: { routing: { defaultStrategy: "merge" } },
    });
    const res = await geo.searchPlaces({ query: "x" });
    expect(res.meta.dedup).toEqual({ before: 2, after: 2 });
    expect(res.results).toHaveLength(2);
  });

  it("merge에서 한 공급자가 실패해도 나머지로 결과를 낸다 (부분 실패 허용)", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({ id: "a", failWith: "PROVIDER_UNAVAILABLE" }),
        fakeProvider({ id: "b", search: [place({ providerPlaceId: "2", name: "B" })] }),
      ],
      config: { routing: { defaultStrategy: "merge" } },
    });
    const res = await geo.searchPlaces({ query: "x" });
    expect(res.results[0]!.name).toBe("B");
    expect(res.meta.providersFailed).toEqual([{ provider: "a", reason: "PROVIDER_UNAVAILABLE" }]);
    expect(res.meta.providersUsed.map((u) => u.provider)).toEqual(["b"]);
  });
});
