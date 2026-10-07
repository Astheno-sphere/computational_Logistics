import { describe, it, expect } from "vitest";
import { createNominatimProvider } from "@geowirehq/provider-nominatim";
import { createGoogleProvider } from "@geowirehq/provider-google";
import { createInternalProvider } from "@geowirehq/provider-internal";
import { createGeoWire } from "../src/geowire.js";

/** GS25 강남점을 nominatim과 google이 서로 다른 표기로 반환 (같은 좌표 → 병합 대상) */
const NOMINATIM_BODY = [
  {
    osm_type: "node",
    osm_id: 555,
    lat: "37.4981",
    lon: "127.0281",
    name: "GS25 Gangnam",
    display_name: "GS25 Gangnam, Teheran-ro, Gangnam-gu, Seoul",
    category: "shop",
    type: "convenience",
    importance: 0.3,
    address: { road: "Teheran-ro", city: "Seoul", country_code: "kr" },
  },
];

const GOOGLE_BODY = {
  places: [
    {
      id: "ChIJgs25gangnam",
      displayName: { text: "GS25 Gangnam Branch", languageCode: "en" },
      formattedAddress: "Teheran-ro 2, Gangnam-gu, Seoul",
      location: { latitude: 37.498, longitude: 127.028 },
      types: ["convenience_store", "store"],
      rating: 4.1,
      userRatingCount: 88,
    },
  ],
};

// 우리약국은 GS25와 3km 이상 떨어뜨려 dedup에서 확실히 분리되게 한다
const INTERNAL_CSV = `store_id,name,address,phone,latitude,longitude,opening_hours
OWN-1,우리약국 강남,서울 강남구 봉은사로 5,02-777-8888,37.5200,127.0500,Mo-Su 08:00-24:00`;

/** URL로 각 공급자의 픽스처 응답을 분기하는 fetch */
function routedFetch(overrides: { googleStatus?: number } = {}) {
  return async (url: string): Promise<Response> => {
    const json = (body: unknown, status = 200) =>
      new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
    if (url.includes("nominatim")) return json(NOMINATIM_BODY);
    if (url.includes("places.googleapis")) {
      if (overrides.googleStatus) return json({ error: {} }, overrides.googleStatus);
      return json(GOOGLE_BODY);
    }
    if (url.includes("maps.googleapis")) return json({ status: "OK", results: [] });
    return json({});
  };
}

function build(opts: { googleKey?: string } = {}) {
  return createGeoWire({
    config: {
      routing: { defaultStrategy: "merge" },
      providers: { internal: { priority: 100 }, google: { priority: 10 }, nominatim: { priority: 1 } },
    },
    baseFetch: routedFetch(),
    providers: [
      createInternalProvider({ csv: INTERNAL_CSV }),
      createNominatimProvider({ sleep: async () => {} }),
      createGoogleProvider({ apiKey: opts.googleKey, placesBaseUrl: "https://places.googleapis.com/v1" }),
    ],
  });
}

describe("3-공급자 merge E2E (internal + nominatim + google)", () => {
  it("키가 있으면 3개 공급자를 병합하고 GS25는 nominatim+google로 합쳐진다 (DoD)", async () => {
    const geo = build({ googleKey: "test-key" });
    const res = await geo.searchPlaces({ query: "강남" });

    // internal 매장(우리약국) + 병합된 GS25 = 2건
    expect(res.results).toHaveLength(2);
    expect(res.meta.providersUsed.map((u) => u.provider).sort()).toEqual([
      "google",
      "internal",
      "nominatim",
    ]);

    // 고객 자체 데이터(priority 100, confidence 1)가 최상위
    expect(res.results[0]!.name).toBe("우리약국 강남");

    // GS25는 두 공급자 병합
    const gs25 = res.results.find((r) => r.sources.length === 2)!;
    expect(gs25.sources.map((s) => s.provider).sort()).toEqual(["google", "nominatim"]);

    // 유료(google) 사용 → 비용 노출
    expect(res.meta.estimatedCostUSD).toBeCloseTo(0.032);
    expect(res.meta.dedup).toEqual({ before: 3, after: 2 });
  });

  it("google 키가 없으면 MISSING_CREDENTIALS로 skip되고 나머지 2개로 동작한다 (DoD)", async () => {
    const geo = build({}); // 키 없음
    const res = await geo.searchPlaces({ query: "강남" });

    expect(res.meta.providersSkipped).toContainEqual({ provider: "google", reason: "MISSING_CREDENTIALS" });
    expect(res.meta.providersFailed).toEqual([]);
    expect(res.meta.providersUsed.map((u) => u.provider).sort()).toEqual(["internal", "nominatim"]);
    expect(res.meta.estimatedCostUSD).toBeUndefined(); // 유료 미사용
    // 고객 매장 최상위 유지
    expect(res.results[0]!.name).toBe("우리약국 강남");
  });
});
