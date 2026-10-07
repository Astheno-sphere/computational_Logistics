import { describe, expect, it } from "vitest";
import { runConformanceTests, jsonFetch, createTestContext } from "@geowirehq/provider-testkit";
import { createBaiduProvider } from "../src/index.js";
import { bd09ToWgs84 } from "../src/coords.js";

const placeBody = {
  status: 0,
  results: [
    {
      name: "天安门",
      location: { lat: 39.915, lng: 116.4103 }, // BD-09
      address: "北京市东城区东长安街",
      telephone: "010-12345678",
      uid: "abc123def456",
      detail_info: { tag: "旅游景点;风景名胜", detail_url: "http://map.baidu.com/place/abc123" },
    },
  ],
};

const geocodeBody = {
  status: 0,
  result: { location: { lng: 116.4103, lat: 39.915 }, level: "地名", precise: 0, confidence: 50 },
};

const reverseBody = {
  status: 0,
  result: {
    formatted_address: "北京市东城区东长安街",
    addressComponent: {
      country: "中国",
      province: "北京市",
      city: "北京市",
      district: "东城区",
      street: "东长安街",
      adcode: "110101",
    },
  },
};

const provider = createBaiduProvider({ apiKey: "test-ak" });

runConformanceTests(provider, {
  fixtures: {
    search: {
      request: { query: "天安门", near: { latitude: 39.905, longitude: 116.397 }, radiusMeters: 2000, limit: 5 },
      responseBody: placeBody,
      minResults: 1,
    },
    geocode: {
      request: { address: "北京市东城区东长安街", country: "CN", limit: 5 },
      responseBody: geocodeBody,
      minResults: 1,
    },
    reverseGeocode: {
      request: { location: { latitude: 39.905, longitude: 116.397 } },
      responseBody: reverseBody,
      minResults: 1,
    },
  },
});

describe("bd09ToWgs84 좌표 변환", () => {
  it("BD-09를 WGS84로 변환한다(입력과 달라지고 중국 범위 유지)", () => {
    const wgs = bd09ToWgs84(116.4103, 39.915);
    expect(wgs.latitude).toBeGreaterThan(39.8);
    expect(wgs.latitude).toBeLessThan(39.95);
    expect(wgs.longitude).toBeGreaterThan(116.35);
    expect(wgs.longitude).toBeLessThan(116.45);
    // 변환이 실제로 일어났는지(BD-09 원본과 다름)
    expect(Math.abs(wgs.latitude - 39.915)).toBeGreaterThan(0.005);
    expect(Math.abs(wgs.longitude - 116.4103)).toBeGreaterThan(0.005);
  });
});

describe("createBaiduProvider — BYOK", () => {
  it("AK가 없으면 MISSING_CREDENTIALS를 던진다", async () => {
    const noKey = createBaiduProvider({});
    const ctx = createTestContext(jsonFetch(placeBody));
    await expect(
      noKey.searchPlaces!({ query: "x", near: { latitude: 39.9, longitude: 116.4 }, limit: 5 }, ctx),
    ).rejects.toMatchObject({ code: "MISSING_CREDENTIALS" });
  });

  it("status가 101이면 AUTH_FAILED로 정규화한다", async () => {
    const ctx = createTestContext(jsonFetch({ status: 101, message: "invalid ak" }));
    await expect(
      provider.searchPlaces!({ query: "x", near: { latitude: 39.9, longitude: 116.4 }, limit: 5 }, ctx),
    ).rejects.toMatchObject({ code: "AUTH_FAILED" });
  });

  it("near가 없으면 빈 결과를 반환한다(폴백 유도)", async () => {
    const ctx = createTestContext(jsonFetch(placeBody));
    const places = await provider.searchPlaces!({ query: "天安门", limit: 5 }, ctx);
    expect(places).toEqual([]);
  });

  it("place 검색: BD-09 좌표 변환·태그·연락처를 매핑한다", async () => {
    const ctx = createTestContext(jsonFetch(placeBody));
    const places = await provider.searchPlaces!(
      { query: "天安门", near: { latitude: 39.905, longitude: 116.397 }, limit: 5 },
      ctx,
    );
    expect(places).toHaveLength(1);
    expect(places[0]!.providerPlaceId).toBe("abc123def456");
    expect(places[0]!.categories).toContain("旅游景点");
    expect(places[0]!.contact?.phone).toBe("010-12345678");
    // BD-09(39.915) → WGS84로 변환되어 원본과 다름
    expect(Math.abs(places[0]!.location.latitude - 39.915)).toBeGreaterThan(0.005);
  });

  it("reverse: 도로명 구조화 주소를 채운다", async () => {
    const ctx = createTestContext(jsonFetch(reverseBody));
    const places = await provider.reverseGeocode!(
      { location: { latitude: 39.905, longitude: 116.397 } },
      ctx,
    );
    const a = places[0]!.address!;
    expect(a.country).toBe("CN");
    expect(a.region).toBe("北京市");
    expect(a.district).toBe("东城区");
    expect(a.street).toBe("东长安街");
  });
});
