import { describe, it, expect, beforeEach } from "vitest";
import { defineProvider } from "@geowirehq/provider-sdk";
import type { GeoProvider, ProviderPlace } from "@geowirehq/provider-sdk";
import { createGeoWire } from "../src/geowire.js";
import { manifest } from "./helpers.js";

const CENTER = { latitude: 37.5, longitude: 127.0 };

let coordSeq = 0;
function p(
  id: string,
  name: string,
  rating?: number,
  priceLevel?: number,
  loc?: { latitude: number; longitude: number },
): ProviderPlace {
  // 장소마다 반경 내에서 서로 다른 좌표 — 근접 병합에 안 걸리게 충분히 벌린다
  coordSeq += 1;
  const pp: ProviderPlace = {
    providerPlaceId: id,
    name,
    categories: [],
    location: loc ?? { latitude: 37.5 + coordSeq * 0.0015, longitude: 127.0 + coordSeq * 0.0008 },
  };
  if (rating != null || priceLevel != null) {
    pp.business = {};
    if (rating != null) pp.business.rating = rating;
    if (priceLevel != null) pp.business.priceLevel = priceLevel;
  }
  return pp;
}

/** 쿼리별로 다른 결과를 내는 테스트 provider */
function catProvider(byQuery: Record<string, ProviderPlace[]>): GeoProvider {
  return defineProvider({
    manifest: manifest({ id: "biz", capabilities: ["search"] }),
    async searchPlaces(req: { query: string }) {
      return byQuery[req.query] ?? [];
    },
  });
}

describe("analyzeArea (지역/상권 분석)", () => {
  beforeEach(() => {
    coordSeq = 0;
  });

  it("업종별 개수·밀도·평점 지형을 집계한다", async () => {
    const geo = createGeoWire({
      providers: [
        catProvider({
          cafe: [p("c1", "Blue Bottle", 4.5), p("c2", "Starbucks", 3.5), p("c3", "Twosome Place")],
          bakery: [p("b1", "Paris Baguette", 4.0, 2)],
        }),
      ],
    });
    const res = await geo.analyzeArea({
      center: CENTER,
      radiusMeters: 1000,
      categories: ["cafe", "bakery"],
    });
    const ins = res.insights;
    // 면적 = π*(1km)² ≈ 3.142 km²
    expect(ins.areaSqKm).toBeCloseTo(3.142, 2);

    const cafe = ins.categories.find((c) => c.category === "cafe")!;
    expect(cafe.count).toBe(3);
    expect(cafe.densityPerSqKm).toBeCloseTo(3 / 3.142, 1);
    // 평점 표본은 rating 있는 2건(4.5, 3.5) → 평균 4.0
    expect(cafe.rating).toEqual({ count: 2, average: 4, min: 3.5, max: 4.5 });
    // topPlaces는 평점 내림차순
    expect(cafe.topPlaces[0]!.name).toBe("Blue Bottle");

    const bakery = ins.categories.find((c) => c.category === "bakery")!;
    expect(bakery.count).toBe(1);
    expect(bakery.priceLevel).toEqual({ count: 1, average: 2, min: 2, max: 2 });

    // 전체: 4개 장소(중복 없음), 전체 평점 표본 3건(4.5,3.5,4.0)
    expect(ins.totalPlaces).toBe(4);
    expect(ins.rating?.count).toBe(3);
    expect(ins.rating?.average).toBeCloseTo(4.0, 5);
  });

  it("여러 업종에 같은 장소가 걸리면 totalPlaces에서 중복 제거된다", async () => {
    const shared = p("shared", "Corner Store", 4.0);
    const geo = createGeoWire({
      providers: [
        catProvider({
          cafe: [shared, p("c1", "Blue Bottle", 4.5)],
          "convenience store": [shared], // 같은 providerPlaceId → 같은 gwp_ id
        }),
      ],
    });
    const res = await geo.analyzeArea({
      center: CENTER,
      radiusMeters: 500,
      categories: ["cafe", "convenience store"],
    });
    // cafe 2 + conv 1 = 3건이지만 shared 중복이라 총 2
    expect(res.insights.categories[0]!.count).toBe(2);
    expect(res.insights.categories[1]!.count).toBe(1);
    expect(res.insights.totalPlaces).toBe(2);
  });

  it("활동 프록시(popularity 평균·리뷰 합계)를 집계하고 실측 아님을 라벨링한다", async () => {
    const withActivity = (id: string, name: string, pop: number, reviews: number): ProviderPlace => {
      const pp = p(id, name);
      pp.business = { popularity: pop, reviewCount: reviews };
      return pp;
    };
    const geo = createGeoWire({
      providers: [
        catProvider({
          cafe: [withActivity("c1", "Blue Bottle", 0.9, 100), withActivity("c2", "Onion", 0.7, 50)],
        }),
      ],
    });
    const res = await geo.analyzeArea({ center: CENTER, radiusMeters: 1000, categories: ["cafe"] });
    const act = res.insights.categories[0]!.activity!;
    expect(act.avgPopularity).toBeCloseTo(0.8, 5);
    expect(act.totalReviews).toBe(150);
    expect(act.note).toContain("not measured foot-traffic");
  });

  it("demographics 공급자가 중심점을 커버하면 인구통계를 포함한다", async () => {
    const censusish: GeoProvider = defineProvider({
      manifest: manifest({ id: "census", capabilities: ["demographics"], authType: "apiKey", coverage: ["US"] }),
      async demographics() {
        return { areaName: "Tract 1", areaLevel: "tract", population: 5000, source: "census" };
      },
    });
    const geo = createGeoWire({
      providers: [catProvider({ cafe: [p("c1", "Blue Bottle", 4.5)] }), censusish],
    });
    const res = await geo.analyzeArea({ center: CENTER, radiusMeters: 1000, categories: ["cafe"] });
    expect(res.insights.demographics?.population).toBe(5000);
    expect(res.insights.demographics?.attributions).toBeDefined();
  });

  it("응답 meta에 사용 공급자를 합산해 노출한다", async () => {
    const geo = createGeoWire({
      providers: [catProvider({ cafe: [p("c1", "Cafe A", 4.5)] })],
    });
    const res = await geo.analyzeArea({ center: CENTER, radiusMeters: 1000, categories: ["cafe"] });
    expect(res.meta.providersUsed.map((u) => u.provider)).toContain("biz");
    expect(res.meta.strategy).toBe("merge");
  });
});
