import { describe, expect, it } from "vitest";
import { runConformanceTests, jsonFetch, createTestContext } from "@geowirehq/provider-testkit";
import { createNominatimProvider } from "../src/index.js";

const searchBody = [
  {
    osm_type: "node",
    osm_id: 123,
    place_id: 1,
    lat: "10.7769",
    lon: "106.7009",
    name: "Pharmacity",
    display_name: "Pharmacity, Nguyễn Huệ, Bến Nghé, Quận 1, Hồ Chí Minh, Việt Nam",
    category: "amenity",
    type: "pharmacy",
    importance: 0.35,
    addresstype: "amenity",
    address: {
      road: "Nguyễn Huệ",
      city: "Hồ Chí Minh",
      country_code: "vn",
      postcode: "70000",
    },
  },
];

const koreaGeocode = [
  {
    osm_type: "way",
    osm_id: 42,
    lat: "37.5665",
    lon: "126.978",
    name: "서울특별시청",
    display_name: "서울특별시청, 세종대로, 중구, 서울, 대한민국",
    category: "office",
    type: "government",
    importance: 0.6,
    address: { road: "세종대로", city: "서울", country_code: "kr" },
  },
];

const reverseBody = {
  osm_type: "way",
  osm_id: 99,
  lat: "37.5665",
  lon: "126.978",
  name: "",
  display_name: "중구, 서울, 대한민국",
  category: "boundary",
  type: "administrative",
  address: { city: "서울", country_code: "kr" },
};

// 테스트에서는 rate limit 대기를 no-op으로 (공용 서버 예절은 rate-limit.test.ts에서 검증)
const provider = createNominatimProvider({ sleep: async () => {} });

runConformanceTests(provider, {
  fixtures: {
    search: {
      request: { query: "pharmacy near Nguyễn Huệ", limit: 5 },
      responseBody: searchBody,
      minResults: 1,
    },
    geocode: {
      request: { address: "서울특별시청", country: "KR", limit: 5 },
      responseBody: koreaGeocode,
      minResults: 1,
    },
    reverseGeocode: {
      request: { location: { latitude: 37.5665, longitude: 126.978 } },
      responseBody: reverseBody,
      minResults: 1,
    },
  },
});

describe("createNominatimProvider", () => {
  it("parses a live-shaped search response through the retrying fetch", async () => {
    const ctx = createTestContext(jsonFetch(searchBody));
    const places = await provider.searchPlaces!(
      { query: "pharmacy", limit: 10 },
      ctx,
    );
    expect(places).toHaveLength(1);
    expect(places[0]?.providerPlaceId).toBe("node/123");
    expect(places[0]?.address?.country).toBe("VN");
  });

  it("handles a single-object reverse response", async () => {
    const ctx = createTestContext(jsonFetch(reverseBody));
    const places = await provider.reverseGeocode!(
      { location: { latitude: 37.5665, longitude: 126.978 } },
      ctx,
    );
    expect(places).toHaveLength(1);
    expect(places[0]?.name).toBe("중구");
  });
});

/** 요청 URL을 기록하는 fetch 스텁 */
function capturingFetch(body: unknown): { fetch: typeof globalThis.fetch; urls: string[] } {
  const urls: string[] = [];
  const fetch = (async (input: string | URL) => {
    urls.push(String(input));
    return { ok: true, status: 200, json: async () => body } as unknown as Response;
  }) as unknown as typeof globalThis.fetch;
  return { fetch, urls };
}

describe("nominatim search location biasing", () => {
  const near = { latitude: 37.4979, longitude: 127.0276 }; // 강남역

  it("bounds the query to a viewbox when near + radiusMeters are given", async () => {
    const { fetch, urls } = capturingFetch(searchBody);
    await provider.searchPlaces!(
      { query: "coffee", near, radiusMeters: 2000, limit: 3 },
      createTestContext(fetch),
    );
    const url = new URL(urls[0]!);
    const viewbox = url.searchParams.get("viewbox");
    expect(viewbox, "viewbox should be present").toBeTruthy();
    expect(url.searchParams.get("bounded")).toBe("1");
    // viewbox = left,top,right,bottom (경도/위도) — near를 감싸야 한다
    const [left, top, right, bottom] = viewbox!.split(",").map(Number);
    expect(left).toBeLessThan(near.longitude);
    expect(right).toBeGreaterThan(near.longitude);
    expect(top).toBeGreaterThan(near.latitude);
    expect(bottom).toBeLessThan(near.latitude);
  });

  it("biases (viewbox, no bounded) when only near is given", async () => {
    const { fetch, urls } = capturingFetch(searchBody);
    await provider.searchPlaces!({ query: "coffee", near, limit: 3 }, createTestContext(fetch));
    const url = new URL(urls[0]!);
    expect(url.searchParams.get("viewbox")).toBeTruthy();
    expect(url.searchParams.get("bounded")).toBeNull();
  });

  it("stays a global query when no near is given", async () => {
    const { fetch, urls } = capturingFetch(searchBody);
    await provider.searchPlaces!({ query: "coffee", limit: 3 }, createTestContext(fetch));
    const url = new URL(urls[0]!);
    expect(url.searchParams.get("viewbox")).toBeNull();
    expect(url.searchParams.get("bounded")).toBeNull();
  });

  it("clamps the viewbox to valid ranges near the antimeridian / poles", async () => {
    const { fetch, urls } = capturingFetch(searchBody);
    await provider.searchPlaces!(
      { query: "x", near: { latitude: 89.9, longitude: 179.9 }, radiusMeters: 50_000, limit: 3 },
      createTestContext(fetch),
    );
    const viewbox = new URL(urls[0]!).searchParams.get("viewbox")!;
    const [left, top, right, bottom] = viewbox.split(",").map(Number);
    for (const lon of [left, right]) expect(Math.abs(lon)).toBeLessThanOrEqual(180);
    for (const lat of [top, bottom]) expect(Math.abs(lat)).toBeLessThanOrEqual(90);
  });
});
