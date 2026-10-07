import { describe, it, expect } from "vitest";
import { createGeoWire } from "../src/geowire.js";
import { fakeProvider, place } from "./helpers.js";

const paid = { currency: "USD" as const, perCall: { search: 0.032 } };

describe("cost-aware 전략", () => {
  it("무료 공급자를 먼저 시도하고, 결과가 있으면 유료는 호출하지 않는다", async () => {
    let googleCalled = false;
    const geo = createGeoWire({
      providers: [
        fakeProvider({
          id: "google",
          authType: "apiKey",
          cost: paid,
          search: () => {
            googleCalled = true;
            return [place({ providerPlaceId: "g", name: "G" })];
          },
        }),
        fakeProvider({ id: "nominatim", search: [place({ providerPlaceId: "n", name: "N" })] }),
      ],
      // google이 priority가 더 높아도 cost-aware는 무료(nominatim)를 먼저 부른다
      config: { providers: { google: { priority: 100 }, nominatim: { priority: 1 } } },
    });
    const res = await geo.searchPlaces({ query: "x", options: { strategy: "cost-aware" } });
    expect(res.results[0]!.name).toBe("N");
    expect(googleCalled).toBe(false);
    expect(res.meta.providersUsed.map((u) => u.provider)).toEqual(["nominatim"]);
    expect(res.meta.estimatedCostUSD).toBeUndefined(); // 유료 호출 0 → 비용 없음
  });

  it("무료가 빈 결과면 유료로 폴백하고 비용을 기록한다", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({
          id: "google",
          authType: "apiKey",
          cost: paid,
          search: [place({ providerPlaceId: "g", name: "G" })],
        }),
        fakeProvider({ id: "nominatim", search: [] }), // 무료지만 결과 없음
      ],
      config: { providers: { google: { priority: 100 }, nominatim: { priority: 1 } } },
    });
    const res = await geo.searchPlaces({ query: "x", options: { strategy: "cost-aware" } });
    expect(res.results[0]!.name).toBe("G");
    expect(res.meta.providersUsed.map((u) => u.provider)).toEqual(["nominatim", "google"]);
    expect(res.meta.estimatedCostUSD).toBeCloseTo(0.032);
  });
});

describe("weighted 전략", () => {
  it("priority 동률이면 요청 국가를 커버하는 공급자를 먼저 시도한다", async () => {
    const order: string[] = [];
    const geo = createGeoWire({
      providers: [
        fakeProvider({
          id: "google", // 글로벌(coverage 없음)
          search: () => {
            order.push("google");
            return [place({ providerPlaceId: "g", name: "G" })];
          },
        }),
        fakeProvider({
          id: "kakao",
          coverage: ["KR"],
          search: () => {
            order.push("kakao");
            return [place({ providerPlaceId: "k", name: "K" })];
          },
        }),
      ],
      config: { providers: { google: { priority: 10 }, kakao: { priority: 10 } } },
    });
    const res = await geo.searchPlaces({ query: "x", country: "KR", options: { strategy: "weighted" } });
    expect(res.results[0]!.name).toBe("K"); // KR 커버리지 가점 → kakao 먼저 → 정지
    expect(order).toEqual(["kakao"]);
  });

  it("priority 동률·국가 없음이면 저비용(무료) 공급자를 먼저 시도한다", async () => {
    const order: string[] = [];
    const geo = createGeoWire({
      providers: [
        fakeProvider({
          id: "google",
          authType: "apiKey",
          cost: paid,
          search: () => {
            order.push("google");
            return [place({ providerPlaceId: "g", name: "G" })];
          },
        }),
        fakeProvider({
          id: "nominatim",
          search: () => {
            order.push("nominatim");
            return [place({ providerPlaceId: "n", name: "N" })];
          },
        }),
      ],
      config: { providers: { google: { priority: 10 }, nominatim: { priority: 10 } } },
    });
    const res = await geo.searchPlaces({ query: "x", options: { strategy: "weighted" } });
    expect(res.results[0]!.name).toBe("N");
    expect(order).toEqual(["nominatim"]);
  });
});

describe("fastest 전략", () => {
  it("가장 빨리 결과를 낸 공급자를 반환하고 느린 공급자는 버린다", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({ id: "slow", delayMs: 60, search: [place({ providerPlaceId: "s", name: "SLOW" })] }),
        fakeProvider({ id: "fast", delayMs: 5, search: [place({ providerPlaceId: "f", name: "FAST" })] }),
      ],
    });
    const res = await geo.searchPlaces({ query: "x", options: { strategy: "fastest" } });
    expect(res.results[0]!.name).toBe("FAST");
    expect(res.meta.providersUsed.map((u) => u.provider)).toEqual(["fast"]); // slow는 버려짐
  });

  it("가장 빠른 응답이 빈 결과면 다음으로 결과를 낸 응답을 기다린다", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({ id: "fast-empty", delayMs: 5, search: [] }),
        fakeProvider({ id: "slow-hit", delayMs: 40, search: [place({ providerPlaceId: "h", name: "HIT" })] }),
      ],
    });
    const res = await geo.searchPlaces({ query: "x", options: { strategy: "fastest" } });
    expect(res.results[0]!.name).toBe("HIT");
    expect(res.meta.providersUsed.map((u) => u.provider)).toContain("slow-hit");
  });
});
