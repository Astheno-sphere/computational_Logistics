import { describe, it, expect } from "vitest";
import { runConformanceTests, jsonFetch, statusFetch, createTestContext, mockJson } from "@geowirehq/provider-testkit";
import { GeoProviderError } from "@geowirehq/provider-sdk";
import { createGoogleProvider } from "../src/index.js";

const searchBody = {
  places: [
    {
      id: "ChIJgangnam1",
      displayName: { text: "GS25 강남점", languageCode: "ko" },
      formattedAddress: "서울특별시 강남구 테헤란로 1",
      addressComponents: [
        { longText: "테헤란로", shortText: "테헤란로", types: ["route"] },
        { longText: "강남구", shortText: "강남구", types: ["sublocality_level_1", "sublocality", "political"] },
        { longText: "서울특별시", shortText: "서울특별시", types: ["locality", "political"] },
        { longText: "대한민국", shortText: "KR", types: ["country", "political"] },
        { longText: "06232", shortText: "06232", types: ["postal_code"] },
      ],
      location: { latitude: 37.498, longitude: 127.028 },
      types: ["convenience_store", "store", "point_of_interest", "establishment"],
      rating: 4.2,
      userRatingCount: 130,
      nationalPhoneNumber: "02-555-1234",
      websiteUri: "https://gs25.example.com",
      priceLevel: "PRICE_LEVEL_INEXPENSIVE",
      regularOpeningHours: { weekdayDescriptions: ["월요일: 24시간 영업"] },
    },
  ],
};

const geocodeBody = {
  status: "OK",
  results: [
    {
      place_id: "ChIJseoulcityhall",
      formatted_address: "서울특별시청, 세종대로 110, 중구, 서울, 대한민국",
      geometry: { location: { lat: 37.5665, lng: 126.978 } },
      types: ["premise"],
      address_components: [
        { long_name: "서울특별시청", short_name: "서울특별시청", types: ["premise"] },
        { long_name: "중구", short_name: "중구", types: ["sublocality", "political"] },
        { long_name: "서울", short_name: "서울", types: ["locality", "political"] },
        { long_name: "대한민국", short_name: "KR", types: ["country", "political"] },
      ],
    },
  ],
};

// getPlace(Place Details)는 reviews를 추가로 반환한다(역할 소싱: 리뷰는 Google 권위).
const detailsBody = {
  ...searchBody.places[0],
  reviews: [
    {
      rating: 5,
      text: { text: "친절하고 깨끗해요", languageCode: "ko" },
      authorAttribution: { displayName: "김철수" },
      relativePublishTimeDescription: "2주 전",
      publishTime: "2026-07-01T09:00:00Z",
    },
    { rating: 4, originalText: { text: "괜찮음" } },
  ],
};

const provider = createGoogleProvider({ apiKey: "test-key" });

runConformanceTests(provider, {
  fixtures: {
    search: {
      request: { query: "GS25 near Gangnam", limit: 5 },
      responseBody: searchBody,
      minResults: 1,
    },
    geocode: {
      request: { address: "서울특별시청", country: "KR", limit: 5 },
      responseBody: geocodeBody,
      minResults: 1,
    },
    reverseGeocode: {
      request: { location: { latitude: 37.5665, longitude: 126.978 } },
      responseBody: geocodeBody,
      minResults: 1,
    },
    getPlace: {
      request: { id: "ChIJgangnam1" },
      responseBody: detailsBody,
      minResults: 1,
    },
  },
});

describe("createGoogleProvider — BYOK", () => {
  it("키가 없으면 MISSING_CREDENTIALS를 던진다", async () => {
    const noKey = createGoogleProvider({});
    const ctx = createTestContext(jsonFetch(searchBody));
    await expect(noKey.searchPlaces!({ query: "x", limit: 10 }, ctx)).rejects.toMatchObject({
      code: "MISSING_CREDENTIALS",
    });
  });

  it("Places 응답을 정규화하고 카테고리·연락처·평점을 매핑한다", async () => {
    const ctx = createTestContext(jsonFetch(searchBody));
    const places = await provider.searchPlaces!({ query: "GS25", limit: 10 }, ctx);
    expect(places).toHaveLength(1);
    expect(places[0]!.providerPlaceId).toBe("ChIJgangnam1");
    expect(places[0]!.categories).toContain("convenience");
    expect(places[0]!.categories).not.toContain("establishment"); // 일반 type 제외
    expect(places[0]!.contact?.phone).toBe("02-555-1234");
    expect(places[0]!.business?.rating).toBe(4.2);
    expect(places[0]!.business?.priceLevel).toBe(1);
    expect(places[0]!.localizedNames).toEqual({ ko: "GS25 강남점" });
  });

  it("검색 결과도 addressComponents를 구조화 주소 필드로 파싱한다 (geocode와 동일 스키마)", async () => {
    const ctx = createTestContext(jsonFetch(searchBody));
    const places = await provider.searchPlaces!({ query: "GS25", limit: 10 }, ctx);
    const addr = places[0]!.address!;
    expect(addr.formatted).toBe("서울특별시 강남구 테헤란로 1");
    expect(addr.country).toBe("KR");
    expect(addr.city).toBe("서울특별시");
    expect(addr.district).toBe("강남구");
    expect(addr.street).toBe("테헤란로");
    expect(addr.postalCode).toBe("06232");
  });

  it("Geocoding status가 REQUEST_DENIED면 AUTH_FAILED로 정규화한다", async () => {
    const ctx = createTestContext(jsonFetch({ status: "REQUEST_DENIED", results: [] }));
    await expect(
      provider.geocode!({ address: "x", limit: 5 }, ctx),
    ).rejects.toMatchObject({ code: "AUTH_FAILED" });
  });

  it("Geocoding status가 ZERO_RESULTS면 빈 배열 (에러 아님)", async () => {
    const ctx = createTestContext(jsonFetch({ status: "ZERO_RESULTS", results: [] }));
    const out = await provider.geocode!({ address: "없는주소", limit: 5 }, ctx);
    expect(out).toEqual([]);
  });

  it("getPlace는 단일 place를 반환한다", async () => {
    const ctx = createTestContext(jsonFetch(detailsBody));
    const place = await provider.getPlace!({ id: "ChIJgangnam1" }, ctx);
    expect(place?.providerPlaceId).toBe("ChIJgangnam1");
  });

  it("getPlace는 리뷰를 business.reviews로 파싱한다(역할 소싱: Google=리뷰)", async () => {
    const ctx = createTestContext(jsonFetch(detailsBody));
    const place = await provider.getPlace!({ id: "ChIJgangnam1" }, ctx);
    const reviews = place?.business?.reviews;
    expect(reviews).toHaveLength(2);
    expect(reviews![0]).toMatchObject({
      author: "김철수",
      rating: 5,
      text: "친절하고 깨끗해요",
      relativeTime: "2주 전",
      source: "google",
    });
    // text 없이 originalText만 있어도 파싱
    expect(reviews![1]).toMatchObject({ rating: 4, text: "괜찮음", source: "google" });
  });

  it("getPlace는 reviews를 FieldMask에 포함한다(search는 비용상 제외)", async () => {
    const masks: string[] = [];
    const ctx = createTestContext((url, init) => {
      masks.push(new Headers(init?.headers).get("X-Goog-FieldMask") ?? "");
      return mockJson(detailsBody);
    });
    await provider.getPlace!({ id: "ChIJgangnam1" }, ctx);
    expect(masks[0]).toContain("reviews");

    // 대조: search FieldMask에는 reviews가 없다(Enterprise+Atmosphere SKU 회피)
    const searchMasks: string[] = [];
    const ctx2 = createTestContext((url, init) => {
      searchMasks.push(new Headers(init?.headers).get("X-Goog-FieldMask") ?? "");
      return mockJson(searchBody);
    });
    await provider.searchPlaces!({ query: "x", limit: 10 }, ctx2);
    expect(searchMasks[0]).not.toContain("reviews");
  });

  it("HTTP 403은 AUTH_FAILED로 정규화한다", async () => {
    const ctx = createTestContext(statusFetch(403), { retries: 0 });
    await expect(
      provider.searchPlaces!({ query: "x", limit: 10 }, ctx),
    ).rejects.toBeInstanceOf(GeoProviderError);
  });
});

const routeBody = {
  routes: [
    {
      distanceMeters: 9950,
      duration: "600s",
      legs: [
        { distanceMeters: 5000, duration: "300s" },
        { distanceMeters: 4950, duration: "300s" },
      ],
      polyline: {
        geoJsonLinestring: {
          type: "LineString",
          coordinates: [
            [126.978, 37.5665],
            [127.0276, 37.4979],
          ],
        },
      },
    },
  ],
};

describe("createGoogleProvider — Routes(길찾기·거리행렬, BYOK)", () => {
  const WPS = [
    { latitude: 37.5665, longitude: 126.978 },
    { latitude: 37.5172, longitude: 127.0473 },
    { latitude: 37.4979, longitude: 127.0276 },
  ];

  it("route: 거리·시간(600s→600)·구간·GeoJSON 지오메트리를 파싱한다", async () => {
    const ctx = createTestContext(jsonFetch(routeBody));
    const routes = await provider.route!(
      { waypoints: WPS, mode: "driving", alternatives: false, geometry: true },
      ctx,
    );
    expect(routes[0]!.distanceMeters).toBe(9950);
    expect(routes[0]!.durationSeconds).toBe(600); // "600s" → 600
    expect(routes[0]!.legs).toHaveLength(2);
    expect(routes[0]!.geometry?.type).toBe("LineString");
  });

  it("route: travelMode·중간경유지·POST 바디를 올바르게 보낸다", async () => {
    let body: Record<string, unknown> = {};
    let mask = "";
    const ctx = createTestContext((url, init) => {
      body = JSON.parse(String(init?.body));
      mask = new Headers(init?.headers).get("X-Goog-FieldMask") ?? "";
      return mockJson(routeBody);
    });
    await provider.route!({ waypoints: WPS, mode: "walking", alternatives: false, geometry: false }, ctx);
    expect(body.travelMode).toBe("WALK");
    // 첫·마지막은 origin/destination, 가운데는 intermediates
    expect(body.intermediates).toHaveLength(1);
    expect(mask).toContain("routes.distanceMeters");
    expect(mask).not.toContain("polyline"); // geometry:false면 폴리라인 미요청
  });

  it("distanceMatrix: originIndex/destinationIndex로 배치, ROUTE_NOT_FOUND는 빈 셀", async () => {
    const matrixBody = [
      { originIndex: 0, destinationIndex: 0, distanceMeters: 9950, duration: "600s", condition: "ROUTE_EXISTS" },
      { originIndex: 0, destinationIndex: 1, condition: "ROUTE_NOT_FOUND" },
    ];
    const ctx = createTestContext(jsonFetch(matrixBody));
    const m = await provider.distanceMatrix!(
      {
        origins: [{ latitude: 37.57, longitude: 126.98 }],
        destinations: [
          { latitude: 37.49, longitude: 127.02 },
          { latitude: 37.51, longitude: 127.05 },
        ],
        mode: "driving",
      },
      ctx,
    );
    expect(m.rows[0]![0]).toEqual({ distanceMeters: 9950, durationSeconds: 600 });
    expect(m.rows[0]![1]).toEqual({}); // ROUTE_NOT_FOUND → 빈 셀
  });
});
