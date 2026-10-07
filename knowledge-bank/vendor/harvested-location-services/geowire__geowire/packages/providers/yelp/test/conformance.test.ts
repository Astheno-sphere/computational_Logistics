import { describe, it, expect } from "vitest";
import { createTestContext, jsonFetch, mockJson, statusFetch } from "@geowirehq/provider-testkit";
import { createYelpProvider } from "../src/index.js";

const business = {
  id: "blue-bottle-sf",
  name: "Blue Bottle Coffee",
  coordinates: { latitude: 37.7764, longitude: -122.423 },
  location: {
    address1: "66 Mint St",
    city: "San Francisco",
    state: "CA",
    zip_code: "94103",
    country: "US",
    display_address: ["66 Mint St", "San Francisco, CA 94103"],
  },
  categories: [{ alias: "coffee", title: "Coffee & Tea" }],
  phone: "+15106533394",
  display_phone: "(510) 653-3394",
  rating: 4.5,
  review_count: 1200,
  price: "$$",
  url: "https://www.yelp.com/biz/blue-bottle-sf",
  image_url: "https://s3-media.yelp.com/photo.jpg",
  photos: ["https://s3-media.yelp.com/p1.jpg", "https://s3-media.yelp.com/p2.jpg"],
};

const searchBody = { businesses: [business], total: 1 };
const reviewsBody = {
  reviews: [
    { text: "Best latte in SoMa", rating: 5, user: { name: "Jane D." }, time_created: "2016-08-29 00:41:13" },
  ],
};

const NEAR = { latitude: 37.7764, longitude: -122.423 };

describe("createYelpProvider — BYOK", () => {
  const provider = createYelpProvider({ apiKey: "test-key" });

  it("키가 없으면 MISSING_CREDENTIALS를 던진다", async () => {
    const noKey = createYelpProvider({});
    const ctx = createTestContext(jsonFetch(searchBody));
    await expect(noKey.searchPlaces!({ query: "coffee", near: NEAR, limit: 20 }, ctx)).rejects.toMatchObject({
      code: "MISSING_CREDENTIALS",
    });
  });

  it("검색 결과를 정규화한다(평점 0~5·리뷰수·가격·카테고리·주소·연락처)", async () => {
    const ctx = createTestContext(jsonFetch(searchBody));
    const places = await provider.searchPlaces!({ query: "coffee", near: NEAR, limit: 20 }, ctx);
    expect(places).toHaveLength(1);
    const p = places[0]!;
    expect(p.providerPlaceId).toBe("blue-bottle-sf");
    expect(p.location).toEqual({ latitude: 37.7764, longitude: -122.423 });
    expect(p.categories).toEqual(["Coffee & Tea"]);
    expect(p.address?.country).toBe("US");
    expect(p.address?.region).toBe("CA");
    expect(p.address?.postalCode).toBe("94103");
    expect(p.contact?.phone).toBe("+15106533394");
    expect(p.business?.rating).toBe(4.5); // Yelp는 이미 5점 척도
    expect(p.business?.reviewCount).toBe(1200);
    expect(p.business?.priceLevel).toBe(2); // "$$" → 2
  });

  it("Bearer 인증 헤더와 latitude/longitude/radius를 전달한다", async () => {
    const urls: string[] = [];
    const auth: string[] = [];
    const ctx = createTestContext((url, init) => {
      urls.push(String(url));
      auth.push(new Headers(init?.headers).get("Authorization") ?? "");
      return mockJson(searchBody);
    });
    await provider.searchPlaces!({ query: "coffee", near: NEAR, radiusMeters: 3000, limit: 20 }, ctx);
    expect(auth[0]).toBe("Bearer test-key");
    const url = new URL(urls[0]!);
    expect(url.searchParams.get("latitude")).toBe("37.7764");
    expect(url.searchParams.get("radius")).toBe("3000");
  });

  it("near가 없으면 빈 결과(Yelp는 위치 필수 → 폴백 유도)", async () => {
    const ctx = createTestContext(jsonFetch(searchBody));
    const places = await provider.searchPlaces!({ query: "coffee", limit: 20 }, ctx);
    expect(places).toEqual([]);
  });

  it("getPlace는 상세 + 리뷰 발췌를 business.reviews로 병합한다(Yelp=리뷰)", async () => {
    // /businesses/{id} → 상세, /businesses/{id}/reviews → 리뷰
    const ctx = createTestContext((url) =>
      mockJson(String(url).includes("/reviews") ? reviewsBody : business),
    );
    const p = await provider.getPlace!({ id: "blue-bottle-sf" }, ctx);
    expect(p?.name).toBe("Blue Bottle Coffee");
    expect(p?.business?.photos).toHaveLength(2);
    expect(p?.business?.reviews?.[0]).toMatchObject({
      text: "Best latte in SoMa",
      rating: 5,
      author: "Jane D.",
      source: "yelp",
    });
  });

  it("리뷰 호출이 실패해도 상세는 반환한다(best-effort)", async () => {
    const ctx = createTestContext((url) => {
      if (String(url).includes("/reviews")) return mockJson({}, { status: 500 });
      return mockJson(business);
    });
    const p = await provider.getPlace!({ id: "blue-bottle-sf" }, ctx);
    expect(p?.name).toBe("Blue Bottle Coffee");
    expect(p?.business?.reviews).toBeUndefined();
  });

  it("HTTP 401은 AUTH_FAILED로 정규화한다", async () => {
    const ctx = createTestContext(statusFetch(401), { retries: 0 });
    await expect(
      provider.searchPlaces!({ query: "x", near: NEAR, limit: 20 }, ctx),
    ).rejects.toMatchObject({ code: "AUTH_FAILED" });
  });
});
