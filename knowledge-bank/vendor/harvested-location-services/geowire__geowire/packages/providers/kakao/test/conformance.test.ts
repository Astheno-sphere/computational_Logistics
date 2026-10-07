import { describe, expect, it } from "vitest";
import { runConformanceTests, jsonFetch, createTestContext } from "@geowirehq/provider-testkit";
import { createKakaoProvider } from "../src/index.js";

const keywordBody = {
  documents: [
    {
      id: "8137464",
      place_name: "스타벅스 강남R점",
      category_name: "음식점 > 카페 > 커피전문점 > 스타벅스",
      category_group_code: "CE7",
      category_group_name: "카페",
      phone: "1522-3232",
      address_name: "서울 강남구 역삼동 825",
      road_address_name: "서울 강남구 강남대로 390",
      x: "127.028",
      y: "37.4979",
      place_url: "http://place.map.kakao.com/8137464",
      distance: "120",
    },
  ],
  meta: { total_count: 1, pageable_count: 1, is_end: true },
};

const addressBody = {
  documents: [
    {
      address_name: "서울 강남구 테헤란로 152",
      x: "127.036",
      y: "37.500",
      address_type: "ROAD_ADDR",
      address: {
        address_name: "서울 강남구 역삼동 737",
        region_1depth_name: "서울",
        region_2depth_name: "강남구",
        region_3depth_name: "역삼동",
        zip_code: "",
      },
      road_address: {
        address_name: "서울 강남구 테헤란로 152",
        region_1depth_name: "서울",
        region_2depth_name: "강남구",
        region_3depth_name: "역삼동",
        road_name: "테헤란로",
        building_name: "강남파이낸스센터",
        zone_no: "06236",
      },
    },
  ],
  meta: { total_count: 1, is_end: true },
};

const reverseBody = {
  documents: [
    {
      road_address: {
        address_name: "서울특별시 중구 세종대로 110",
        region_1depth_name: "서울",
        region_2depth_name: "중구",
        region_3depth_name: "태평로1가",
        road_name: "세종대로",
        building_name: "서울특별시청",
        zone_no: "04524",
      },
      address: {
        address_name: "서울 중구 태평로1가 31",
        region_1depth_name: "서울",
        region_2depth_name: "중구",
        region_3depth_name: "태평로1가",
        zip_code: "100-101",
      },
    },
  ],
  meta: { total_count: 1 },
};

const provider = createKakaoProvider({ apiKey: "test-key" });

runConformanceTests(provider, {
  fixtures: {
    search: {
      request: { query: "스타벅스", near: { latitude: 37.4979, longitude: 127.0276 }, radiusMeters: 2000, limit: 5 },
      responseBody: keywordBody,
      minResults: 1,
    },
    geocode: {
      request: { address: "서울 강남구 테헤란로 152", country: "KR", limit: 5 },
      responseBody: addressBody,
      minResults: 1,
    },
    reverseGeocode: {
      request: { location: { latitude: 37.5665, longitude: 126.978 } },
      responseBody: reverseBody,
      minResults: 1,
    },
  },
});

/** 요청 URL·헤더를 기록하는 fetch 스텁 */
function capture(body: unknown): { fetch: typeof globalThis.fetch; urls: string[]; auth: string[] } {
  const urls: string[] = [];
  const auth: string[] = [];
  const fetch = (async (input: string | URL, init?: RequestInit) => {
    urls.push(String(input));
    const h = new Headers(init?.headers);
    auth.push(h.get("Authorization") ?? "");
    return { ok: true, status: 200, json: async () => body } as unknown as Response;
  }) as unknown as typeof globalThis.fetch;
  return { fetch, urls, auth };
}

describe("createKakaoProvider — BYOK", () => {
  it("키가 없으면 MISSING_CREDENTIALS를 던진다", async () => {
    const noKey = createKakaoProvider({});
    const ctx = createTestContext(jsonFetch(keywordBody));
    await expect(noKey.searchPlaces!({ query: "x", limit: 5 }, ctx)).rejects.toMatchObject({
      code: "MISSING_CREDENTIALS",
    });
  });

  it("keyword 검색을 정규화하고 카테고리·연락처·좌표를 매핑한다", async () => {
    const ctx = createTestContext(jsonFetch(keywordBody));
    const places = await provider.searchPlaces!({ query: "스타벅스", limit: 5 }, ctx);
    expect(places).toHaveLength(1);
    expect(places[0]!.providerPlaceId).toBe("8137464");
    expect(places[0]!.name).toBe("스타벅스 강남R점");
    expect(places[0]!.categories).toContain("cafe");
    expect(places[0]!.location).toEqual({ latitude: 37.4979, longitude: 127.028 });
    expect(places[0]!.contact?.phone).toBe("1522-3232");
    expect(places[0]!.address?.formatted).toBe("서울 강남구 강남대로 390");
  });

  it("geocode(address.json)는 도로명 구조화 필드를 채운다", async () => {
    const ctx = createTestContext(jsonFetch(addressBody));
    const places = await provider.geocode!({ address: "테헤란로 152", limit: 5 }, ctx);
    const a = places[0]!.address!;
    expect(a.country).toBe("KR");
    expect(a.region).toBe("서울");
    expect(a.city).toBe("강남구");
    expect(a.district).toBe("역삼동");
    expect(a.street).toBe("테헤란로");
    expect(a.postalCode).toBe("06236");
  });

  it("near+radius는 x·y·radius·sort=distance 파라미터로 전달된다 (KakaoAK 인증)", async () => {
    const { fetch, urls, auth } = capture(keywordBody);
    await provider.searchPlaces!(
      { query: "카페", near: { latitude: 37.4979, longitude: 127.0276 }, radiusMeters: 3000, limit: 5 },
      createTestContext(fetch),
    );
    const url = new URL(urls[0]!);
    expect(url.searchParams.get("x")).toBe("127.0276");
    expect(url.searchParams.get("y")).toBe("37.4979");
    expect(url.searchParams.get("radius")).toBe("3000");
    expect(url.searchParams.get("sort")).toBe("distance");
    expect(auth[0]).toBe("KakaoAK test-key");
  });

  it("radius는 최대 20km로 clamp된다", async () => {
    const { fetch, urls } = capture(keywordBody);
    await provider.searchPlaces!(
      { query: "카페", near: { latitude: 37.5, longitude: 127.0 }, radiusMeters: 99999, limit: 5 },
      createTestContext(fetch),
    );
    expect(new URL(urls[0]!).searchParams.get("radius")).toBe("20000");
  });
});
