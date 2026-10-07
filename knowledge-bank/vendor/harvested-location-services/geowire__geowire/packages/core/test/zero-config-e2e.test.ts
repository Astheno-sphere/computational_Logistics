import { describe, it, expect } from "vitest";
import { createNominatimProvider } from "@geowirehq/provider-nominatim";
import { createGeoWire } from "../src/geowire.js";
import { SearchPlacesResponse } from "@geowirehq/schema";

/** 호치민 약국 검색에 대한 Nominatim jsonv2 응답 픽스처 (실호출 없이 E2E) */
const HCMC_PHARMACIES = [
  {
    osm_type: "node",
    osm_id: 1001,
    lat: "10.7769",
    lon: "106.7009",
    name: "Nhà thuốc Long Châu",
    category: "amenity",
    type: "pharmacy",
    importance: 0.42,
    address: { country_code: "vn", city: "Ho Chi Minh City", road: "Nguyễn Huệ", postcode: "700000" },
  },
  {
    osm_type: "node",
    osm_id: 1002,
    lat: "10.7801",
    lon: "106.6952",
    name: "Pharmacity",
    category: "amenity",
    type: "pharmacy",
    importance: 0.35,
    address: { country_code: "vn", city: "Ho Chi Minh City" },
  },
];

/** 픽스처 응답을 돌려주는 fetch (rate limiter sleep도 무력화) */
function fixtureProvider() {
  return createNominatimProvider({ sleep: async () => {} });
}
function fixtureFetch(payload: unknown) {
  return async () =>
    new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
}

describe("Zero-config E2E (실제 nominatim provider + 픽스처)", () => {
  it("설정 파일 없이 createGeoWire() → nominatim 검색 성공 (DoD)", async () => {
    const geo = createGeoWire({
      providers: [fixtureProvider()],
      baseFetch: fixtureFetch(HCMC_PHARMACIES),
    });

    const res = await geo.searchPlaces({ query: "pharmacy near Ho Chi Minh" });

    expect(res.results).toHaveLength(2);
    expect(res.results.map((r) => r.name)).toContain("Nhà thuốc Long Châu");
    expect(res.results[0]!.id).toMatch(/^gwp_/);
    expect(res.results[0]!.sources[0]!.provider).toBe("nominatim");
    expect(res.meta.providersUsed.map((u) => u.provider)).toEqual(["nominatim"]);
    expect(res.meta.attributions).toContain("© OpenStreetMap contributors");
    expect(res.results[0]!.attributions).toContain("© OpenStreetMap contributors");
  });

  it("유니코드 쿼리(Nguyễn Huệ)를 정상 처리한다", async () => {
    const geo = createGeoWire({
      providers: [fixtureProvider()],
      baseFetch: fixtureFetch(HCMC_PHARMACIES),
    });
    const res = await geo.searchPlaces({ query: "Nguyễn Huệ pharmacy" });
    expect(res.results.length).toBeGreaterThan(0);
  });

  it("응답이 SearchPlacesResponse 스키마를 통과한다 (런타임 자기 검증)", async () => {
    const geo = createGeoWire({
      providers: [fixtureProvider()],
      baseFetch: fixtureFetch(HCMC_PHARMACIES),
    });
    const res = await geo.searchPlaces({ query: "pharmacy" });
    expect(() => SearchPlacesResponse.parse(res)).not.toThrow();
  });

  it("geocode도 동일 파이프라인으로 동작한다", async () => {
    const geo = createGeoWire({
      providers: [fixtureProvider()],
      baseFetch: fixtureFetch(HCMC_PHARMACIES),
    });
    const res = await geo.geocode({ address: "Nguyễn Huệ, Ho Chi Minh" });
    expect(res.results.length).toBeGreaterThan(0);
    expect(res.results[0]!.location.latitude).toBeCloseTo(10.7769, 2);
  });
});
