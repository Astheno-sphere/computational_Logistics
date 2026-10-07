import { describe, expect, it } from "vitest";
import { runConformanceTests, jsonFetch, createTestContext } from "@geowirehq/provider-testkit";
import { createFoursquareProvider } from "../src/index.js";

const detail = {
  fsq_place_id: "fsq_abc123",
  name: "Blue Bottle Coffee",
  latitude: 37.7764,
  longitude: -122.423,
  location: {
    formatted_address: "66 Mint St, San Francisco, CA 94103",
    address: "66 Mint St",
    locality: "San Francisco",
    region: "CA",
    postcode: "94103",
    country: "US",
  },
  categories: [{ name: "Café" }, { name: "Coffee Shop" }],
  tel: "(510) 653-3394",
  website: "https://bluebottlecoffee.com",
  rating: 9.0, // 0~10 스케일 → 4.5로 정규화
  price: 2,
  popularity: 0.87,
  photos: [
    { prefix: "https://fastly.4sqi.net/img/general/", suffix: "/12345_abc.jpg", width: 1920, height: 1440 },
    { prefix: "https://fastly.4sqi.net/img/general/", suffix: "/67890_def.jpg" },
  ],
};

const searchBody = { results: [detail] };

const provider = createFoursquareProvider({ apiKey: "test-key" });

runConformanceTests(provider, {
  fixtures: {
    search: {
      request: { query: "Blue Bottle", near: { latitude: 37.7764, longitude: -122.423 }, radiusMeters: 2000, limit: 5 },
      responseBody: searchBody,
      minResults: 1,
    },
    getPlace: {
      request: { id: "fsq_abc123" },
      responseBody: detail,
      minResults: 1,
    },
  },
});

function capture(body: unknown): { fetch: typeof globalThis.fetch; urls: string[]; hdr: Headers[] } {
  const urls: string[] = [];
  const hdr: Headers[] = [];
  const fetch = (async (input: string | URL, init?: RequestInit) => {
    urls.push(String(input));
    hdr.push(new Headers(init?.headers));
    return { ok: true, status: 200, json: async () => body } as unknown as Response;
  }) as unknown as typeof globalThis.fetch;
  return { fetch, urls, hdr };
}

describe("createFoursquareProvider — BYOK", () => {
  it("키가 없으면 MISSING_CREDENTIALS를 던진다", async () => {
    const noKey = createFoursquareProvider({});
    const ctx = createTestContext(jsonFetch(searchBody));
    await expect(noKey.searchPlaces!({ query: "x", limit: 5 }, ctx)).rejects.toMatchObject({
      code: "MISSING_CREDENTIALS",
    });
  });

  it("검색 결과를 정규화한다(WGS84 좌표·카테고리·국가 ISO·연락처)", async () => {
    const ctx = createTestContext(jsonFetch(searchBody));
    const places = await provider.searchPlaces!(
      { query: "Blue Bottle", near: { latitude: 37.7764, longitude: -122.423 }, limit: 5 },
      ctx,
    );
    expect(places).toHaveLength(1);
    expect(places[0]!.providerPlaceId).toBe("fsq_abc123");
    expect(places[0]!.location).toEqual({ latitude: 37.7764, longitude: -122.423 });
    expect(places[0]!.categories).toEqual(["Café", "Coffee Shop"]);
    expect(places[0]!.address?.country).toBe("US");
    expect(places[0]!.address?.city).toBe("San Francisco");
    expect(places[0]!.contact?.phone).toBe("(510) 653-3394");
  });

  it("Bearer 인증 + X-Places-Api-Version 헤더와 ll/radius를 전달한다", async () => {
    const { fetch, urls, hdr } = capture(searchBody);
    await provider.searchPlaces!(
      { query: "coffee", near: { latitude: 40.0, longitude: -73.0 }, radiusMeters: 3000, limit: 5 },
      createTestContext(fetch),
    );
    expect(hdr[0]!.get("Authorization")).toBe("Bearer test-key");
    expect(hdr[0]!.get("X-Places-Api-Version")).toBeTruthy();
    const url = new URL(urls[0]!);
    expect(url.searchParams.get("ll")).toBe("40,-73");
    expect(url.searchParams.get("radius")).toBe("3000");
  });

  it("getPlace: fsq_place_id로 단일 상세를 조회한다", async () => {
    const ctx = createTestContext(jsonFetch(detail));
    const p = await provider.getPlace!({ id: "fsq_abc123" }, ctx);
    expect(p?.name).toBe("Blue Bottle Coffee");
    expect(p?.contact?.website).toBe("https://bluebottlecoffee.com");
  });

  it("평점(0~10→0~5)·가격대·사진을 business로 파싱한다(역할 소싱: POI 전문)", async () => {
    const ctx = createTestContext(jsonFetch(detail));
    const p = await provider.getPlace!({ id: "fsq_abc123" }, ctx);
    expect(p?.business?.rating).toBe(4.5); // 9.0/2
    expect(p?.business?.priceLevel).toBe(2);
    expect(p?.business?.popularity).toBe(0.87); // 유동인구 프록시

    // prefix+original+suffix로 조립된 공개 CDN URL(키 불필요)
    expect(p?.business?.photos).toEqual([
      "https://fastly.4sqi.net/img/general/original/12345_abc.jpg",
      "https://fastly.4sqi.net/img/general/original/67890_def.jpg",
    ]);
  });
});
