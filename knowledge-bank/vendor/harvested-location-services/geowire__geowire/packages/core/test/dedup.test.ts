import { describe, it, expect } from "vitest";
import { normalizeName, jaroWinkler, pairScore, phoneNsn } from "../src/pipeline/dedup/similarity.js";
import { dedup } from "../src/pipeline/dedup/dedup.js";
import { mergeCluster } from "../src/pipeline/dedup/merge-fields.js";
import { builtPlace } from "./helpers.js";

describe("normalizeName", () => {
  it("법인 접미사를 제거한다", () => {
    expect(normalizeName("Pharmacie Centrale SARL")).toBe("pharmacie centrale");
    expect(normalizeName("Acme Inc.")).toBe("acme");
    expect(normalizeName("본가 주식회사")).toBe("본가");
  });

  it("NFKC 정규화 + 소문자 + 구두점 정리", () => {
    expect(normalizeName("Ｃａｆé")).toBe("café");
    expect(normalizeName("GS25  강남점")).toBe("gs25 강남점");
  });
});

describe("phoneNsn (국가코드/선행 0 정규화)", () => {
  it("국제표기와 국내표기가 같은 NSN 꼬리를 갖는다 (KR)", () => {
    // +82 2 1234 5678  vs  02-1234-5678
    const intl = phoneNsn("+82-2-1234-5678"); // "82212345678"
    const natl = phoneNsn("02-1234-5678"); // "212345678"
    expect(intl.endsWith(natl) || natl.endsWith(intl)).toBe(true);
  });
  it("국내 트렁크 프리픽스 0을 벗긴다", () => {
    expect(phoneNsn("02-888-7777")).toBe("28887777");
    expect(phoneNsn("010-1234-5678")).toBe("1012345678");
  });
  it("국제 접두 00을 벗긴다", () => {
    expect(phoneNsn("0082-2-1234-5678")).toBe("82212345678");
  });
});

describe("jaroWinkler", () => {
  it("동일 문자열은 1", () => {
    expect(jaroWinkler("martha", "martha")).toBe(1);
  });
  it("접두사 유사 문자열은 높은 점수", () => {
    expect(jaroWinkler("martha", "marhta")).toBeGreaterThan(0.9);
  });
  it("무관 문자열은 낮은 점수", () => {
    expect(jaroWinkler("abc", "xyz")).toBeLessThan(0.5);
  });
});

describe("pairScore", () => {
  it("같은 장소(가까운 좌표 + 유사 이름)는 높은 점수", () => {
    const a = builtPlace({ provider: "n", providerPlaceId: "1", name: "GS25 Gangnam", location: { latitude: 37.498, longitude: 127.028 } });
    const b = builtPlace({ provider: "g", providerPlaceId: "2", name: "GS25 Gangnam Branch", location: { latitude: 37.4981, longitude: 127.0281 } });
    expect(pairScore(a, b)).toBeGreaterThan(0.75);
  });

  it("다른 장소(먼 좌표 + 다른 이름)는 낮은 점수", () => {
    const a = builtPlace({ provider: "n", providerPlaceId: "1", name: "GS25", location: { latitude: 37.5, longitude: 127.0 } });
    const b = builtPlace({ provider: "g", providerPlaceId: "2", name: "Starbucks", location: { latitude: 35.1, longitude: 129.0 } });
    expect(pairScore(a, b)).toBeLessThan(0.5);
  });

  it("전화번호 일치가 점수를 끌어올린다", () => {
    const a = builtPlace({ provider: "n", providerPlaceId: "1", name: "약국", location: { latitude: 10, longitude: 20 }, contact: { phone: "028887777" } });
    const b = builtPlace({ provider: "g", providerPlaceId: "2", name: "약국", location: { latitude: 10.0001, longitude: 20.0001 }, contact: { phone: "02-888-7777" } });
    expect(pairScore(a, b)).toBeGreaterThan(0.9);
  });

  it("교차문자 상호도 근접+웹 일치면 병합된다 (Starbucks vs 스타벅스)", () => {
    // 이름 유사도 0이지만 같은 좌표 + 같은 웹사이트 → 동일 장소로 확정
    const g = builtPlace({ provider: "google", providerPlaceId: "ChIJ1", name: "Starbucks", location: { latitude: 37.4979, longitude: 127.0276 }, contact: { website: "https://www.starbucks.co.kr/" } });
    const n = builtPlace({ provider: "nominatim", providerPlaceId: "node/1", name: "스타벅스", location: { latitude: 37.49792, longitude: 127.02761 }, contact: { website: "http://starbucks.co.kr" } });
    expect(pairScore(g, n)).toBe(1);
  });

  it("교차문자 상호도 근접+전화(동일 뒷자리) 일치면 병합된다", () => {
    const g = builtPlace({ provider: "google", providerPlaceId: "ChIJ2", name: "Starbucks", location: { latitude: 37.4979, longitude: 127.0276 }, contact: { phone: "02-1234-5678" } });
    const n = builtPlace({ provider: "nominatim", providerPlaceId: "node/2", name: "스타벅스", location: { latitude: 37.49792, longitude: 127.02761 }, contact: { phone: "0212345678" } });
    expect(pairScore(g, n)).toBe(1);
  });

  it("국제(+82)와 국내(02) 전화 표기 차이를 흡수해 병합된다 (KR 실사용)", () => {
    // Google은 보통 +82 국제표기, 국내 데이터는 02 국내표기 — 이제 동일 번호로 인식
    const g = builtPlace({ provider: "google", providerPlaceId: "ChIJ3", name: "Starbucks", location: { latitude: 37.4979, longitude: 127.0276 }, contact: { phone: "+82-2-1234-5678" } });
    const n = builtPlace({ provider: "internal", providerPlaceId: "S1", name: "스타벅스 강남", location: { latitude: 37.49792, longitude: 127.02761 }, contact: { phone: "02-1234-5678" } });
    expect(pairScore(g, n)).toBe(1);
  });

  it("교차문자 상호가 강한 식별자(전화/웹) 없이 좌표만 가까우면 병합 안 함 (안전)", () => {
    // 같은 건물의 서로 다른 가게일 수 있으므로 이름 언어가 다르고 corroboration 없으면 미병합
    const g = builtPlace({ provider: "google", providerPlaceId: "ChIJ2", name: "Starbucks", location: { latitude: 37.4979, longitude: 127.0276 } });
    const n = builtPlace({ provider: "nominatim", providerPlaceId: "node/2", name: "스타벅스", location: { latitude: 37.49792, longitude: 127.02761 } });
    expect(pairScore(g, n)).toBeLessThan(0.75);
  });

  it("전화가 같아도 멀리 떨어지면 병합 안 함 (프랜차이즈 공용번호 방어)", () => {
    const a = builtPlace({ provider: "g", providerPlaceId: "1", name: "Starbucks", location: { latitude: 37.5, longitude: 127.0 }, contact: { phone: "1522-3232" } });
    const b = builtPlace({ provider: "n", providerPlaceId: "2", name: "스타벅스", location: { latitude: 37.6, longitude: 127.1 }, contact: { phone: "1522-3232" } });
    expect(pairScore(a, b)).toBeLessThan(0.75);
  });
});

describe("dedup", () => {
  it("동일 약국 2-공급자 → 결과 1건 + sources 2개 (DoD)", () => {
    const places = [
      builtPlace({ provider: "nominatim", providerPlaceId: "node/1", name: "GS25 Gangnam", location: { latitude: 37.498, longitude: 127.028 } }),
      builtPlace({ provider: "google", providerPlaceId: "ChIJ1", name: "GS25 Gangnam Branch", location: { latitude: 37.4981, longitude: 127.0281 } }),
    ];
    const res = dedup(places, { mergeThreshold: 0.75, providerRank: () => 0 });
    expect(res.before).toBe(2);
    expect(res.after).toBe(1);
    expect(res.merged[0]!.sources).toHaveLength(2);
    expect(res.merged[0]!.sources.map((s) => s.provider).sort()).toEqual(["google", "nominatim"]);
  });

  it("서로 다른 장소는 병합하지 않는다", () => {
    const places = [
      builtPlace({ provider: "n", providerPlaceId: "1", name: "GS25", location: { latitude: 37.5, longitude: 127.0 } }),
      builtPlace({ provider: "n", providerPlaceId: "2", name: "Starbucks", location: { latitude: 35.1, longitude: 129.0 } }),
    ];
    const res = dedup(places, { mergeThreshold: 0.75, providerRank: () => 0 });
    expect(res.after).toBe(2);
  });

  it("빈/단일 입력은 그대로 통과", () => {
    expect(dedup([], { mergeThreshold: 0.75, providerRank: () => 0 }).after).toBe(0);
    const one = [builtPlace({ provider: "n", providerPlaceId: "1", name: "X" })];
    expect(dedup(one, { mergeThreshold: 0.75, providerRank: () => 0 }).after).toBe(1);
  });

  it("44→27→8 스타일: 다수 중복 축소", () => {
    // 4개 클러스터 × 각 3개 표기 = 12개 → 4개로
    const places = [];
    const clusters = [
      { name: "Pharmacy A", lat: 10.0, lon: 20.0 },
      { name: "Cafe B", lat: 11.0, lon: 21.0 },
      { name: "Store C", lat: 12.0, lon: 22.0 },
      { name: "Clinic D", lat: 13.0, lon: 23.0 },
    ];
    let idc = 0;
    for (const c of clusters) {
      for (const p of ["nominatim", "google", "internal"]) {
        places.push(
          builtPlace({ provider: p, providerPlaceId: `${p}-${idc++}`, name: c.name, location: { latitude: c.lat + 0.00005, longitude: c.lon + 0.00005 } }),
        );
      }
    }
    const res = dedup(places, { mergeThreshold: 0.75, providerRank: () => 0 });
    expect(res.before).toBe(12);
    expect(res.after).toBe(4);
  });
});

describe("mergeCluster — 필드별 강점 + provenance", () => {
  it("location은 nominatim, openingHours는 google에서 취하고 provenance를 기록한다", () => {
    const nomi = builtPlace({
      provider: "nominatim",
      providerPlaceId: "node/1",
      name: "GS25",
      location: { latitude: 37.498, longitude: 127.028 },
    });
    const goog = builtPlace({
      provider: "google",
      providerPlaceId: "ChIJ1",
      name: "GS25 Gangnam",
      location: { latitude: 37.4979, longitude: 127.0279 },
      business: { openingHours: "Mo-Su 00:00-24:00", rating: 4.5 },
    });
    const merged = mergeCluster([nomi, goog], { providerRank: (id) => (id === "google" ? 5 : 1) });

    // location은 강점 테이블상 nominatim
    expect(merged.location).toEqual({ latitude: 37.498, longitude: 127.028 });
    // business는 google만 보유
    expect(merged.business?.openingHours).toBe("Mo-Su 00:00-24:00");
    // provenance: nominatim이 location, google이 business 기여
    const nomiSrc = merged.sources.find((s) => s.provider === "nominatim")!;
    const googSrc = merged.sources.find((s) => s.provider === "google")!;
    expect(nomiSrc.fields).toContain("location");
    expect(googSrc.fields).toContain("business");
  });

  it("다중 소스 병합 시 confidence에 보너스", () => {
    const a = builtPlace({ provider: "n", providerPlaceId: "1", name: "X", confidence: 0.8 });
    const b = builtPlace({ provider: "g", providerPlaceId: "2", name: "X", confidence: 0.7 });
    const merged = mergeCluster([a, b], { providerRank: () => 0 });
    expect(merged.confidence).toBeGreaterThan(0.8);
  });
});
