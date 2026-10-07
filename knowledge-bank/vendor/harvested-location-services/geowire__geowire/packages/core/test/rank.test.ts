import { describe, it, expect } from "vitest";
import { rankPlaces, rankScore } from "../src/pipeline/rank.js";
import { defaultConfig } from "../src/config/schema.js";
import { builtPlace } from "./helpers.js";

const weights = defaultConfig().routing.rank;
const nowMs = Date.parse("2026-07-17T00:00:00.000Z");

describe("rankPlaces", () => {
  it("near가 있으면 가까운 장소가 먼저", () => {
    const near = builtPlace({ provider: "p", providerPlaceId: "1", name: "가까움", distanceMeters: 50 });
    const far = builtPlace({ provider: "p", providerPlaceId: "2", name: "멈", distanceMeters: 5000 });
    const ranked = rankPlaces([far, near], { weights, near: { latitude: 0, longitude: 0 }, nowMs });
    expect(ranked.map((r) => r.name)).toEqual(["가까움", "멈"]);
  });

  it("거리 동률이면 영업시간·신뢰도 높은 쪽이 먼저", () => {
    const withHours = builtPlace({
      provider: "p", providerPlaceId: "1", name: "정보많음", distanceMeters: 100,
      business: { openingHours: "Mo-Su 09:00-18:00" }, confidence: 0.9,
    });
    const bare = builtPlace({ provider: "p", providerPlaceId: "2", name: "정보없음", distanceMeters: 100, confidence: 0.3 });
    const ranked = rankPlaces([bare, withHours], { weights, near: { latitude: 0, longitude: 0 }, nowMs });
    expect(ranked[0]!.name).toBe("정보많음");
  });

  it("near가 없으면 거리 가중치를 빼고 재정규화한다", () => {
    const p = builtPlace({ provider: "p", providerPlaceId: "1", name: "X", confidence: 1, business: { openingHours: "24/7" } });
    const score = rankScore(p, { weights, nowMs });
    // 거리 신호 없음, openingHours=1·confidence=1·freshness=1 → 높은 점수
    expect(score).toBeGreaterThan(0.9);
    expect(score).toBeLessThanOrEqual(1);
  });

  it("동점은 입력 순서를 보존한다(안정 정렬)", () => {
    const a = builtPlace({ provider: "p", providerPlaceId: "1", name: "A" });
    const b = builtPlace({ provider: "p", providerPlaceId: "2", name: "B" });
    const ranked = rankPlaces([a, b], { weights, nowMs });
    expect(ranked.map((r) => r.name)).toEqual(["A", "B"]);
  });
});
