import { describe, it, expect } from "vitest";
import { applyPolicy } from "../src/pipeline/policy.js";
import { CostTracker, applyBudget, estimateCost } from "../src/cost.js";
import { CircuitBreaker } from "../src/circuit-breaker.js";
import { ProviderRegistry } from "../src/registry.js";
import { normalizeConfig } from "../src/config/load.js";
import { fakeProvider, builtPlace } from "./helpers.js";

function registry(providers: Parameters<typeof fakeProvider>[0][]) {
  return new ProviderRegistry(providers.map(fakeProvider), normalizeConfig({}));
}

describe("applyPolicy — attribution + 혼합 캐시 TTL", () => {
  it("기여 소스의 attribution을 각 Place와 전체에 주입한다", () => {
    const reg = registry([
      { id: "osm", policy: { maxCacheTtlSeconds: 86400, canStorePermanently: true, attributionRequired: "© OSM" } },
    ]);
    const places = [builtPlace({ provider: "osm", providerPlaceId: "1", name: "X" })];
    const res = applyPolicy(places, reg, 3600);
    expect(res.attributions).toEqual(["© OSM"]);
    expect(places[0]!.attributions).toEqual(["© OSM"]);
  });

  it("캐시 금지 소스(null)가 하나라도 있으면 전체 TTL은 null", () => {
    const reg = registry([
      { id: "osm", policy: { maxCacheTtlSeconds: 86400, canStorePermanently: true } },
      { id: "google", policy: { maxCacheTtlSeconds: null, canStorePermanently: false } },
    ]);
    // 한 Place가 두 소스로 병합된 상태
    const merged = builtPlace({ provider: "osm", providerPlaceId: "1", name: "X" });
    merged.sources.push({ provider: "google", providerPlaceId: "g1", fetchedAt: "2026-07-17T00:00:00.000Z" });
    const res = applyPolicy([merged], reg, 3600);
    expect(res.cacheTtlSeconds).toBeNull();
  });

  it("혼합 시 TTL은 기여 소스 상한과 기본값의 최솟값", () => {
    const reg = registry([
      { id: "a", policy: { maxCacheTtlSeconds: 7200, canStorePermanently: true } },
      { id: "b", policy: { maxCacheTtlSeconds: 1800, canStorePermanently: true } },
    ]);
    const p1 = builtPlace({ provider: "a", providerPlaceId: "1", name: "X" });
    const p2 = builtPlace({ provider: "b", providerPlaceId: "2", name: "Y" });
    const res = applyPolicy([p1, p2], reg, 3600);
    expect(res.cacheTtlSeconds).toBe(1800); // min(3600, 7200, 1800)
  });
});

describe("cost — estimate + budget gate", () => {
  const reg = registry([
    { id: "nominatim", cost: undefined },
    { id: "google", authType: "apiKey", cost: { currency: "USD", perCall: { search: 0.032 } } },
  ]);

  it("estimateCost는 manifest.cost 합산", () => {
    expect(estimateCost(["nominatim", "google"], "search", reg)).toBeCloseTo(0.032);
    expect(estimateCost(["nominatim"], "search", reg)).toBe(0);
  });

  it("perRequestMaxUSD 초과 유료 공급자는 제외하고 무료는 허용", () => {
    const t = new CostTracker();
    const d = applyBudget(["google", "nominatim"], "search", reg, { perRequestMaxUSD: 0.01 }, t);
    expect(d.skipped).toEqual(["google"]);
    expect(d.allowed).toEqual(["nominatim"]);
  });

  it("monthlyUSD 누적 초과 시 유료 제외", () => {
    const t = new CostTracker();
    t.record(49.99);
    const d = applyBudget(["google"], "search", reg, { monthlyUSD: 50 }, t);
    expect(d.skipped).toEqual(["google"]);
  });

  it("예산 내면 허용", () => {
    const t = new CostTracker();
    const d = applyBudget(["google", "nominatim"], "search", reg, { perRequestMaxUSD: 0.1 }, t);
    expect(d.allowed).toEqual(["google", "nominatim"]);
    expect(d.skipped).toEqual([]);
  });

  it("요청별 maxCostUSD가 config 상한과 무관하게 유료 공급자를 제외한다", () => {
    const t = new CostTracker();
    // config 예산은 없지만(넉넉), 요청 options.maxCostUSD=0.01 → google 제외
    const d = applyBudget(["google", "nominatim"], "search", reg, {}, t, 0.01);
    expect(d.skipped).toEqual(["google"]);
    expect(d.allowed).toEqual(["nominatim"]);
  });

  it("config 상한과 요청 maxCostUSD 중 더 낮은 값이 적용된다", () => {
    const t = new CostTracker();
    // config 0.1는 통과시키지만 요청 0.001이 더 엄격 → google 제외
    const d = applyBudget(["google"], "search", reg, { perRequestMaxUSD: 0.1 }, t, 0.001);
    expect(d.skipped).toEqual(["google"]);
  });
});

describe("CircuitBreaker", () => {
  it("연속 실패가 임계값에 도달하면 open", () => {
    let t = 0;
    const cb = new CircuitBreaker({ failureThreshold: 3, cooldownMs: 1000, now: () => t });
    expect(cb.isOpen("p")).toBe(false);
    cb.recordFailure("p", "TIMEOUT");
    cb.recordFailure("p", "TIMEOUT");
    expect(cb.isOpen("p")).toBe(false);
    cb.recordFailure("p", "TIMEOUT");
    expect(cb.isOpen("p")).toBe(true);
  });

  it("cooldown 경과 후 다시 닫힌다", () => {
    let t = 0;
    const cb = new CircuitBreaker({ failureThreshold: 1, cooldownMs: 1000, now: () => t });
    cb.recordFailure("p", "PROVIDER_UNAVAILABLE");
    expect(cb.isOpen("p")).toBe(true);
    t = 1000;
    expect(cb.isOpen("p")).toBe(false);
  });

  it("성공하면 연속 실패가 리셋된다", () => {
    const cb = new CircuitBreaker({ failureThreshold: 2, now: () => 0 });
    cb.recordFailure("p", "TIMEOUT");
    cb.recordSuccess("p");
    cb.recordFailure("p", "TIMEOUT");
    expect(cb.isOpen("p")).toBe(false); // 리셋됐으므로 1회만 카운트됨
  });

  it("요청·설정 오류 코드는 회로를 열지 않는다", () => {
    const cb = new CircuitBreaker({ failureThreshold: 1, now: () => 0 });
    cb.recordFailure("p", "INVALID_REQUEST");
    cb.recordFailure("p", "MISSING_CREDENTIALS");
    cb.recordFailure("p", "UNSUPPORTED_CAPABILITY");
    expect(cb.isOpen("p")).toBe(false);
  });
});
