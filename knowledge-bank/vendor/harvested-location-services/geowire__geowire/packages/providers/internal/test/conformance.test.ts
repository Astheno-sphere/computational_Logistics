import { describe, it, expect } from "vitest";
import { runConformanceTests, createTestContext, jsonFetch } from "@geowirehq/provider-testkit";
import { createInternalProvider } from "../src/index.js";
import { parseCsvRecords } from "../src/csv.js";
import { StoreIndex } from "../src/store.js";

const CSV = `store_id,name,address,phone,latitude,longitude,opening_hours
S001,강남 우리매장,"서울 강남구 테헤란로 1, 2층",02-111-2222,37.498,127.028,Mo-Su 09:00-22:00
S002,홍대 우리매장,서울 마포구 양화로 3,02-333-4444,37.556,126.922,24/7
S003,부산 우리매장,부산 해운대구,051-555-6666,35.163,129.163,Mo-Fr 10:00-20:00`;

const provider = createInternalProvider({ csv: CSV });

runConformanceTests(provider, {
  usesHttp: false,
  fixtures: {
    search: { request: { query: "우리매장", limit: 10 }, minResults: 1 },
  },
});

describe("CSV 파싱", () => {
  it("따옴표로 감싼 쉼표 포함 필드를 처리한다", () => {
    const records = parseCsvRecords(CSV);
    expect(records).toHaveLength(3);
    expect(records[0]!.address).toBe("서울 강남구 테헤란로 1, 2층");
    expect(records[0]!.store_id).toBe("S001");
  });

  it("빈 텍스트는 빈 배열", () => {
    expect(parseCsvRecords("")).toEqual([]);
  });
});

describe("createInternalProvider — 검색", () => {
  it("이름 부분일치로 검색한다", async () => {
    const ctx = createTestContext(jsonFetch({}));
    const res = await provider.searchPlaces!({ query: "강남", limit: 10 }, ctx);
    expect(res).toHaveLength(1);
    expect(res[0]!.name).toBe("강남 우리매장");
    expect(res[0]!.providerPlaceId).toBe("S001");
    expect(res[0]!.confidence).toBe(1);
    expect(res[0]!.business?.openingHours).toBe("Mo-Su 09:00-22:00");
    expect(res[0]!.contact?.phone).toBe("02-111-2222");
  });

  it("near + radiusMeters로 반경 필터하고 거리순 정렬한다", async () => {
    const ctx = createTestContext(jsonFetch({}));
    // 강남(37.498,127.028) 근처 5km 반경 → 강남 매장만
    const res = await provider.searchPlaces!(
      { query: "우리매장", near: { latitude: 37.498, longitude: 127.028 }, radiusMeters: 5000, limit: 10 },
      ctx,
    );
    expect(res.map((r) => r.name)).toEqual(["강남 우리매장"]);
    expect(res[0]!.distanceMeters).toBeLessThan(100);
  });

  it("near가 있으면 전체를 거리순으로 정렬한다", async () => {
    const ctx = createTestContext(jsonFetch({}));
    const res = await provider.searchPlaces!(
      { query: "우리매장", near: { latitude: 37.5, longitude: 127.0 }, limit: 10 },
      ctx,
    );
    // 서울 두 매장이 부산보다 앞
    expect(res[res.length - 1]!.name).toBe("부산 우리매장");
  });

  it("매칭 없으면 빈 배열", async () => {
    const ctx = createTestContext(jsonFetch({}));
    const res = await provider.searchPlaces!({ query: "없는매장이름xyz", limit: 10 }, ctx);
    expect(res).toEqual([]);
  });
});

describe("StoreIndex — 컬럼 별칭 + 방어적 파싱", () => {
  it("lat/lng 별칭과 category 컬럼을 인식한다", () => {
    const records = parseCsvRecords(`id,name,lat,lng,category
X1,카페 A,37.5,127.0,"cafe,coffee"`);
    const index = new StoreIndex(records);
    expect(index.places).toHaveLength(1);
    expect(index.places[0]!.providerPlaceId).toBe("X1");
    expect(index.places[0]!.categories).toEqual(["cafe", "coffee"]);
  });

  it("좌표/이름 없는 행은 건너뛴다", () => {
    const records = parseCsvRecords(`store_id,name,latitude,longitude
A,이름있음,37.5,127.0
B,,37.5,127.0
C,좌표없음,abc,xyz`);
    const index = new StoreIndex(records);
    expect(index.places.map((p) => p.providerPlaceId)).toEqual(["A"]);
  });

  it("WGS84 범위를 벗어난 좌표 행은 건너뛴다 (lat 200, lon 500 등)", () => {
    const records = parseCsvRecords(`store_id,name,latitude,longitude
OK,정상,37.5,127.0
BADLAT,위도초과,200,127.0
BADLON,경도초과,37.5,500`);
    const index = new StoreIndex(records);
    expect(index.places.map((p) => p.providerPlaceId)).toEqual(["OK"]);
  });
});
