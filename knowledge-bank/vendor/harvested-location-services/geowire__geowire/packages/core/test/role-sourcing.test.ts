import { describe, it, expect } from "vitest";
import { createGeoWire } from "../src/geowire.js";
import { fakeProvider, place } from "./helpers.js";

/**
 * 역할 기반 필드 소싱 (설계 §7.3, "Stripe for Maps" 비전의 핵심).
 * 각 공급자가 manifest.fieldAuthority로 선언한 **권위 필드**를 병합이 존중하는지 검증한다:
 *   OSM=좌표(기반 지도), Kakao=현지 상호·주소(국가 보완), Google=평점·리뷰·연락처.
 * priority가 아니라 **필드별 권위**가 승자를 정한다는 점, 그리고 provenance(sources[].fields)에
 * 누가 무엇을 기여했는지 기록된다는 점을 함께 확인한다.
 */
describe("역할 기반 필드 소싱 (fieldAuthority)", () => {
  const PHONE = "+82-2-1234-5678"; // 동일 전화 → 교차문자(한글↔라틴) 병합 보장

  function threeSourceGeo() {
    const osmLoc = { latitude: 37.4979, longitude: 127.0276 };
    return createGeoWire({
      providers: [
        // OSM: 좌표가 권위 (기반 지도). 이름은 빈약, business 없음.
        fakeProvider({
          id: "nominatim",
          fieldAuthority: { location: 10, address: 6 },
          policy: { maxCacheTtlSeconds: 86400, canStorePermanently: true, attributionRequired: "© OSM" },
          search: [
            place({
              providerPlaceId: "node/1",
              name: "Starbucks",
              location: osmLoc,
              address: { formatted: "Teheran-ro, Gangnam", street: "Teheran-ro" },
              contact: { phone: PHONE },
            }),
          ],
        }),
        // Kakao: 현지 상호·주소가 권위 (국가 보완). 좌표는 약간 어긋남.
        fakeProvider({
          id: "kakao",
          coverage: ["KR"],
          fieldAuthority: { name: 9, address: 8 },
          policy: { maxCacheTtlSeconds: 86400, canStorePermanently: false, attributionRequired: "© Kakao" },
          search: [
            place({
              providerPlaceId: "kakao-1",
              name: "스타벅스 강남R점",
              location: { latitude: 37.49792, longitude: 127.02761 },
              address: { formatted: "서울 강남구 테헤란로 101", city: "서울", district: "강남구", street: "테헤란로 101" },
              contact: { phone: PHONE },
            }),
          ],
        }),
        // Google: 평점·리뷰·연락처가 권위. 좌표는 약간 어긋남.
        fakeProvider({
          id: "google",
          fieldAuthority: { business: 10, contact: 8 },
          policy: { maxCacheTtlSeconds: null, canStorePermanently: false, attributionRequired: "Powered by Google" },
          search: [
            place({
              providerPlaceId: "ChIJ1",
              name: "Starbucks Gangnam",
              location: { latitude: 37.49791, longitude: 127.02759 },
              contact: { phone: PHONE, website: "https://starbucks.co.kr" },
              business: {
                rating: 4.5,
                reviewCount: 1200,
                reviews: [{ author: "Jane", rating: 5, text: "Great coffee", source: "google" }],
              },
            }),
          ],
        }),
      ],
      config: { routing: { defaultStrategy: "merge" } },
    });
  }

  it("각 필드를 역할 권위 공급자에서 가져와 하나의 레코드로 합친다", async () => {
    const res = await threeSourceGeo().searchPlaces({ query: "스타벅스" });

    // 세 소스가 하나로 병합
    expect(res.meta.dedup).toEqual({ before: 3, after: 1 });
    const p = res.results[0]!;
    expect(p.sources).toHaveLength(3);

    // 이름 = Kakao(현지 상호, name 권위 9)
    expect(p.name).toBe("스타벅스 강남R점");
    // 좌표 = OSM(기반 지도, location 권위 10)
    expect(p.location).toEqual({ latitude: 37.4979, longitude: 127.0276 });
    // 주소 = Kakao(현지 주소, address 8 > OSM 6)
    expect(p.address?.city).toBe("서울");
    // 평점·리뷰 = Google(business 권위 10) — 리뷰가 business에 실려 함께 승계
    expect(p.business?.rating).toBe(4.5);
    expect(p.business?.reviews?.[0]?.text).toBe("Great coffee");
    // 웹사이트 = Google(contact 권위 8)
    expect(p.contact?.website).toBe("https://starbucks.co.kr");
  });

  it("provenance(sources[].fields)에 누가 무엇을 기여했는지 기록한다", async () => {
    const res = await threeSourceGeo().searchPlaces({ query: "스타벅스" });
    const byProvider = Object.fromEntries(
      res.results[0]!.sources.map((s) => [s.provider, (s.fields ?? []).sort()]),
    );
    expect(byProvider.nominatim).toEqual(["location"]);
    expect(byProvider.kakao).toEqual(["address", "name"]);
    expect(byProvider.google).toEqual(["business", "contact"]);
  });

  it("business 하위 필드를 합성한다 — 리뷰는 Google, 사진은 Foursquare가 공존", async () => {
    const loc = { latitude: 37.4979, longitude: 127.0276 };
    const geo = createGeoWire({
      providers: [
        // Google: business 권위 10 — 평점·리뷰 제공(사진 없음)
        fakeProvider({
          id: "google",
          fieldAuthority: { business: 10 },
          search: [
            place({
              providerPlaceId: "g1",
              name: "Blue Bottle",
              location: loc,
              contact: { phone: PHONE },
              business: {
                rating: 4.6,
                reviewCount: 900,
                reviews: [{ text: "Best latte", rating: 5, source: "google" }],
              },
            }),
          ],
        }),
        // Foursquare: business 권위 6 — 사진 제공(리뷰 없음)
        fakeProvider({
          id: "foursquare",
          fieldAuthority: { business: 6 },
          search: [
            place({
              providerPlaceId: "f1",
              name: "Blue Bottle Coffee",
              location: { latitude: 37.49791, longitude: 127.02761 },
              contact: { phone: PHONE },
              business: {
                rating: 4.4,
                photos: ["https://cdn.example.com/a.jpg", "https://cdn.example.com/b.jpg"],
              },
            }),
          ],
        }),
      ],
      config: { routing: { defaultStrategy: "merge" } },
    });
    const p = (await geo.searchPlaces({ query: "blue bottle" })).results[0]!;
    expect(p.sources).toHaveLength(2); // 병합되어 2 소스
    // 스칼라 rating = Google(권위 승자)
    expect(p.business?.rating).toBe(4.6);
    // 리뷰 = Google, 사진 = Foursquare — 한 레코드에 공존
    expect(p.business?.reviews?.[0]?.text).toBe("Best latte");
    expect(p.business?.photos).toEqual([
      "https://cdn.example.com/a.jpg",
      "https://cdn.example.com/b.jpg",
    ]);
    // 두 소스 모두 business에 기여한 것으로 provenance 기록
    const bizContributors = p.sources
      .filter((s) => (s.fields ?? []).includes("business"))
      .map((s) => s.provider)
      .sort();
    expect(bizContributors).toEqual(["foursquare", "google"]);
  });

  it("priority가 높아도 필드 권위가 있으면 권위 공급자가 그 필드를 이긴다", async () => {
    // google에 최상위 priority를 줘도 좌표는 여전히 OSM(location 권위)에서 온다.
    const osmLoc = { latitude: 37.4979, longitude: 127.0276 };
    const geo = createGeoWire({
      providers: [
        fakeProvider({
          id: "nominatim",
          fieldAuthority: { location: 10 },
          search: [place({ providerPlaceId: "n1", name: "Cafe", location: osmLoc, contact: { phone: PHONE } })],
        }),
        fakeProvider({
          id: "google",
          search: [
            place({
              providerPlaceId: "g1",
              name: "Cafe",
              location: { latitude: 37.498, longitude: 127.0277 }, // 근접하나 살짝 어긋남(~15m)
              contact: { phone: PHONE },
            }),
          ],
        }),
      ],
      config: {
        routing: { defaultStrategy: "merge" },
        providers: { google: { enabled: true, priority: 100 }, nominatim: { enabled: true, priority: 0 } },
      },
    });
    const p = (await geo.searchPlaces({ query: "cafe" })).results[0]!;
    expect(p.location).toEqual(osmLoc); // priority 100인 google이 아니라 OSM 좌표
  });
});
