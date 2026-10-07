import { describe, it, expect } from "vitest";
import { createGeoWire } from "../src/geowire.js";
import { fakeProvider, place } from "./helpers.js";

describe("searchPlaces — first-success 전략 (기본)", () => {
  it("첫 공급자가 결과를 내면 다음 공급자는 호출하지 않는다", async () => {
    let bCalled = false;
    const geo = createGeoWire({
      providers: [
        fakeProvider({ id: "a", search: [place({ providerPlaceId: "1", name: "A약국" })] }),
        fakeProvider({ id: "b", search: () => { bCalled = true; return []; } }),
      ],
      config: { providers: { a: { priority: 10 }, b: { priority: 1 } } },
    });
    const res = await geo.searchPlaces({ query: "약국" });
    expect(res.results).toHaveLength(1);
    expect(res.results[0]!.name).toBe("A약국");
    expect(bCalled).toBe(false);
    expect(res.meta.providersUsed.map((u) => u.provider)).toEqual(["a"]);
    expect(res.meta.strategy).toBe("first-success");
  });

  it("첫 공급자가 실패하면 다음으로 폴백하고 meta.providersFailed에 기록한다", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({ id: "a", failWith: "TIMEOUT" }),
        fakeProvider({ id: "b", search: [place({ providerPlaceId: "2", name: "B약국" })] }),
      ],
      config: { providers: { a: { priority: 10 }, b: { priority: 1 } } },
    });
    const res = await geo.searchPlaces({ query: "약국" });
    expect(res.results[0]!.name).toBe("B약국");
    expect(res.meta.providersFailed).toEqual([{ provider: "a", reason: "TIMEOUT" }]);
    expect(res.meta.providersUsed.map((u) => u.provider)).toEqual(["b"]);
  });

  it("빈 결과도 폴백을 유발한다", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({ id: "a", search: [] }),
        fakeProvider({ id: "b", search: [place({ providerPlaceId: "2", name: "B" })] }),
      ],
      config: { providers: { a: { priority: 10 }, b: { priority: 1 } } },
    });
    const res = await geo.searchPlaces({ query: "x" });
    expect(res.results[0]!.name).toBe("B");
    // a는 호출됐고 ok지만 0건 → providersUsed에 count 0으로 남는다
    expect(res.meta.providersUsed).toEqual([
      { provider: "a", resultCount: 0, latencyMs: expect.any(Number) },
      { provider: "b", resultCount: 1, latencyMs: expect.any(Number) },
    ]);
  });

  it("MISSING_CREDENTIALS는 failed가 아니라 skipped로 분류", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({ id: "google", authType: "apiKey", failWith: "MISSING_CREDENTIALS" }),
        fakeProvider({ id: "nominatim", search: [place({ providerPlaceId: "n1", name: "N" })] }),
      ],
      config: { providers: { google: { priority: 10 }, nominatim: { priority: 1 } } },
    });
    const res = await geo.searchPlaces({ query: "x" });
    expect(res.meta.providersSkipped).toEqual([{ provider: "google", reason: "MISSING_CREDENTIALS" }]);
    expect(res.meta.providersFailed).toEqual([]);
    expect(res.results[0]!.name).toBe("N");
  });
});

describe("Place 정규화", () => {
  it("gwp_ id·sources·attributions를 채운다", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({
          id: "nominatim",
          policy: { maxCacheTtlSeconds: 86400, canStorePermanently: true, attributionRequired: "© OSM" },
          search: [place({ providerPlaceId: "node/1", name: "약국", location: { latitude: 10, longitude: 20 } })],
        }),
      ],
    });
    const res = await geo.searchPlaces({ query: "약국" });
    const p = res.results[0]!;
    expect(p.id).toMatch(/^gwp_/);
    expect(p.sources).toHaveLength(1);
    expect(p.sources[0]).toMatchObject({ provider: "nominatim", providerPlaceId: "node/1" });
    expect(p.sources[0]!.fetchedAt).toMatch(/T.*Z$/);
    expect(p.attributions).toEqual(["© OSM"]);
    expect(res.meta.attributions).toEqual(["© OSM"]);
  });

  it("near가 주어지면 distanceMeters를 계산하고 거리순 정렬한다", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({
          id: "p",
          search: [
            place({ providerPlaceId: "far", name: "먼곳", location: { latitude: 1, longitude: 1 } }),
            place({ providerPlaceId: "near", name: "가까운곳", location: { latitude: 0.001, longitude: 0.001 } }),
          ],
        }),
      ],
    });
    const res = await geo.searchPlaces({ query: "x", near: { latitude: 0, longitude: 0 } });
    expect(res.results.map((r) => r.name)).toEqual(["가까운곳", "먼곳"]);
    expect(res.results[0]!.distanceMeters).toBeGreaterThan(0);
    expect(res.results[0]!.distanceMeters!).toBeLessThan(res.results[1]!.distanceMeters!);
  });

  it("radiusMeters를 벗어난 결과를 하드 필터로 제외한다", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({
          id: "p",
          search: [
            // 약 157km 밖 — radiusMeters=10km에서 제외되어야 함
            place({ providerPlaceId: "far", name: "먼곳", location: { latitude: 1, longitude: 1 } }),
            // 약 157m — 반경 안, 유지
            place({ providerPlaceId: "near", name: "가까운곳", location: { latitude: 0.001, longitude: 0.001 } }),
          ],
        }),
      ],
    });
    const res = await geo.searchPlaces({
      query: "x",
      near: { latitude: 0, longitude: 0 },
      radiusMeters: 10_000,
    });
    expect(res.results.map((r) => r.name)).toEqual(["가까운곳"]);
  });

  it("표시 주소(formatted)를 구조화 필드 기반 표준 형식으로 통일한다", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({
          id: "p",
          search: [
            place({
              providerPlaceId: "1",
              name: "Empire State Building",
              location: { latitude: 40.7484, longitude: -73.9857 },
              address: {
                formatted: "공급자 원문(장황한 계층 문자열)",
                city: "New York",
                region: "New York",
                postalCode: "10001",
                country: "US",
              },
            }),
          ],
        }),
      ],
    });
    const res = await geo.searchPlaces({ query: "x" });
    expect(res.results[0]!.address!.formatted).toBe("New York, New York, 10001, United States");
  });

  it("limit을 적용한다", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({
          id: "p",
          search: [
            place({ providerPlaceId: "1", name: "1" }),
            place({ providerPlaceId: "2", name: "2" }),
            place({ providerPlaceId: "3", name: "3" }),
          ],
        }),
      ],
    });
    const res = await geo.searchPlaces({ query: "x", limit: 2 });
    expect(res.results).toHaveLength(2);
  });

  it("응답은 SearchPlacesResponse 스키마를 통과한다 (자기 검증)", async () => {
    const geo = createGeoWire({
      providers: [fakeProvider({ id: "p", search: [place({ providerPlaceId: "1", name: "X" })] })],
    });
    // searchPlaces 내부에서 SearchPlacesResponse.parse를 통과했으므로 도달 = 검증됨
    const res = await geo.searchPlaces({ query: "x" });
    expect(res.meta.providersSkipped).toEqual([]);
    expect(res.meta.providersFailed).toEqual([]);
  });
});

describe("plan — 라우팅·제한", () => {
  it("options.providers로 사용할 공급자를 제한한다", async () => {
    let aCalled = false;
    const geo = createGeoWire({
      providers: [
        fakeProvider({ id: "a", search: () => { aCalled = true; return [place({ providerPlaceId: "1", name: "A" })]; } }),
        fakeProvider({ id: "b", search: [place({ providerPlaceId: "2", name: "B" })] }),
      ],
    });
    const res = await geo.searchPlaces({ query: "x", options: { providers: ["b"] } });
    expect(aCalled).toBe(false);
    expect(res.results[0]!.name).toBe("B");
  });

  it("country 라우팅이 공급자 순서를 오버라이드한다", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({ id: "google", search: [place({ providerPlaceId: "g", name: "G" })] }),
        fakeProvider({ id: "nominatim", search: [place({ providerPlaceId: "n", name: "N" })] }),
      ],
      config: {
        routing: { countries: { KR: { providers: ["nominatim", "google"] } } },
      },
    });
    const res = await geo.searchPlaces({ query: "x", country: "KR" });
    // KR 라우팅: nominatim 우선 → first-success가 nominatim에서 정지
    expect(res.results[0]!.name).toBe("N");
  });

  it("요청 options.strategy가 전략을 오버라이드한다", async () => {
    const geo = createGeoWire({
      providers: [fakeProvider({ id: "a", search: [place({ providerPlaceId: "1", name: "A" })] })],
    });
    const res = await geo.searchPlaces({ query: "x", options: { strategy: "merge" } });
    expect(res.meta.strategy).toBe("merge");
  });
});
