import { describe, expect, it } from "vitest";
import { runConformanceTests, jsonFetch, createTestContext } from "@geowirehq/provider-testkit";
import { createNaverProvider } from "../src/index.js";
import { stripHtml, naverCoord } from "../src/parse.js";

const localBody = {
  total: 1,
  start: 1,
  display: 1,
  items: [
    {
      title: "<b>스타벅스</b> 강남R점",
      link: "https://www.starbucks.co.kr",
      category: "음식점>카페,디저트",
      description: "",
      telephone: "1522-3232",
      address: "서울특별시 강남구 역삼동 825",
      roadAddress: "서울특별시 강남구 강남대로 390",
      mapx: "1270286020",
      mapy: "374972000",
    },
  ],
};

const provider = createNaverProvider({ clientId: "id", clientSecret: "secret" });

runConformanceTests(provider, {
  fixtures: {
    search: {
      request: { query: "스타벅스 강남", limit: 5 },
      responseBody: localBody,
      minResults: 1,
    },
    geocode: {
      request: { address: "서울 강남구 강남대로 390", country: "KR", limit: 5 },
      responseBody: localBody,
      minResults: 1,
    },
  },
});

describe("naver parse 유틸", () => {
  it("stripHtml는 <b> 태그와 엔티티를 제거한다", () => {
    expect(stripHtml("<b>스타벅스</b> 강남 &amp; 역삼")).toBe("스타벅스 강남 & 역삼");
  });
  it("naverCoord는 WGS84*1e7 정수를 십진 도로 변환한다", () => {
    expect(naverCoord("1270286020")).toBeCloseTo(127.028602, 5);
    expect(naverCoord("374972000")).toBeCloseTo(37.4972, 4);
    // 이미 십진 도면 그대로
    expect(naverCoord("127.0286")).toBeCloseTo(127.0286, 4);
    expect(naverCoord("")).toBeUndefined();
  });
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

describe("createNaverProvider — BYOK", () => {
  it("Client ID/Secret이 없으면 MISSING_CREDENTIALS를 던진다", async () => {
    const noCreds = createNaverProvider({ clientId: "id" }); // secret 누락
    const ctx = createTestContext(jsonFetch(localBody));
    await expect(noCreds.searchPlaces!({ query: "x", limit: 5 }, ctx)).rejects.toMatchObject({
      code: "MISSING_CREDENTIALS",
    });
  });

  it("title 하이라이트 제거·좌표 변환·주소 매핑을 한다", async () => {
    const ctx = createTestContext(jsonFetch(localBody));
    const places = await provider.searchPlaces!({ query: "스타벅스", limit: 5 }, ctx);
    expect(places).toHaveLength(1);
    expect(places[0]!.name).toBe("스타벅스 강남R점"); // <b> 제거됨
    expect(places[0]!.location.longitude).toBeCloseTo(127.028602, 5);
    expect(places[0]!.location.latitude).toBeCloseTo(37.4972, 4);
    expect(places[0]!.contact?.phone).toBe("1522-3232");
    expect(places[0]!.address?.formatted).toBe("서울특별시 강남구 강남대로 390");
    expect(places[0]!.categories).toContain("카페");
  });

  it("Client ID/Secret 헤더와 display 상한(5)을 전달한다", async () => {
    const { fetch, urls, hdr } = capture(localBody);
    await provider.searchPlaces!({ query: "카페", limit: 50 }, createTestContext(fetch));
    expect(hdr[0]!.get("X-Naver-Client-Id")).toBe("id");
    expect(hdr[0]!.get("X-Naver-Client-Secret")).toBe("secret");
    expect(new URL(urls[0]!).searchParams.get("display")).toBe("5");
  });
});
