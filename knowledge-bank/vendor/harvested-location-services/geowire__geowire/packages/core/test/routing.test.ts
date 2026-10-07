import { describe, it, expect } from "vitest";
import { createGeoWire } from "../src/geowire.js";
import { fakeProvider } from "./helpers.js";

const ROUTE = {
  distanceMeters: 9949.4,
  durationSeconds: 598.4,
  legs: [{ distanceMeters: 9949.4, durationSeconds: 598.4 }],
};
const TWO_WAY = [
  { latitude: 37.5665, longitude: 126.978 },
  { latitude: 37.4979, longitude: 127.0276 },
];

describe("getRoute (길찾기 디스패치)", () => {
  it("route capable 공급자에서 경로를 얻고 provider·attribution을 주입한다", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({
          id: "osrm",
          capabilities: ["route"],
          policy: { maxCacheTtlSeconds: 86400, canStorePermanently: true, attributionRequired: "© OSM (OSRM)" },
          routeResult: [ROUTE],
        }),
      ],
    });
    const res = await geo.getRoute({ waypoints: TWO_WAY });
    expect(res.routes).toHaveLength(1);
    expect(res.routes[0]!.distanceMeters).toBe(9949.4);
    expect(res.routes[0]!.provider).toBe("osrm");
    expect(res.routes[0]!.attributions).toEqual(["© OSM (OSRM)"]);
    expect(res.meta.strategy).toBe("first-success");
    expect(res.meta.providersUsed.map((u) => u.provider)).toEqual(["osrm"]);
    expect(res.meta.attributions).toEqual(["© OSM (OSRM)"]);
  });

  it("첫 공급자가 빈 결과면 다음 공급자로 폴백한다", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({ id: "empty-router", capabilities: ["route"], routeResult: [] }),
        fakeProvider({ id: "osrm", capabilities: ["route"], routeResult: [ROUTE] }),
      ],
      config: {
        providers: {
          "empty-router": { enabled: true, priority: 100 },
          osrm: { enabled: true, priority: 0 },
        },
      },
    });
    const res = await geo.getRoute({ waypoints: TWO_WAY });
    expect(res.routes[0]!.provider).toBe("osrm");
    // 빈 공급자는 used(resultCount 0)로 기록
    expect(res.meta.providersUsed).toContainEqual(
      expect.objectContaining({ provider: "empty-router", resultCount: 0 }),
    );
  });

  it("첫 공급자가 실패하면 failed에 기록하고 다음으로 폴백한다", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({ id: "broken", capabilities: ["route"], failWith: "PROVIDER_UNAVAILABLE" }),
        fakeProvider({ id: "osrm", capabilities: ["route"], routeResult: [ROUTE] }),
      ],
      config: {
        providers: { broken: { enabled: true, priority: 100 }, osrm: { enabled: true, priority: 0 } },
      },
    });
    const res = await geo.getRoute({ waypoints: TWO_WAY });
    expect(res.routes[0]!.provider).toBe("osrm");
    expect(res.meta.providersFailed).toContainEqual({ provider: "broken", reason: "PROVIDER_UNAVAILABLE" });
  });

  it("비용 오름차순으로 무료(osrm) 우선, 유료(google)는 폴백 — 키 넣어도 자동 과금 안 함", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({
          id: "google",
          capabilities: ["route"],
          cost: { currency: "USD", perCall: { route: 0.005 } },
          routeResult: [{ ...ROUTE, distanceMeters: 111 }],
        }),
        fakeProvider({ id: "osrm", capabilities: ["route"], routeResult: [{ ...ROUTE, distanceMeters: 999 }] }),
      ],
      // google에 더 높은 priority를 줘도 비용이 우선 → osrm 먼저
      config: {
        providers: { google: { enabled: true, priority: 100 }, osrm: { enabled: true, priority: 0 } },
      },
    });
    const res = await geo.getRoute({ waypoints: TWO_WAY });
    expect(res.routes[0]!.provider).toBe("osrm");
    expect(res.routes[0]!.distanceMeters).toBe(999);
    expect(res.meta.estimatedCostUSD).toBeUndefined(); // 무료만 사용
  });

  it("options.providers로 유료 Google 라우팅을 강제할 수 있다", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({
          id: "google",
          capabilities: ["route"],
          cost: { currency: "USD", perCall: { route: 0.005 } },
          routeResult: [{ ...ROUTE, distanceMeters: 111 }],
        }),
        fakeProvider({ id: "osrm", capabilities: ["route"], routeResult: [{ ...ROUTE, distanceMeters: 999 }] }),
      ],
    });
    const res = await geo.getRoute({ waypoints: TWO_WAY, options: { providers: ["google"] } });
    expect(res.routes[0]!.provider).toBe("google");
    expect(res.routes[0]!.distanceMeters).toBe(111);
    expect(res.meta.estimatedCostUSD).toBeCloseTo(0.005);
  });

  it("route 공급자가 없으면 빈 경로를 반환한다(에러 아님)", async () => {
    const geo = createGeoWire({
      providers: [fakeProvider({ id: "search-only", capabilities: ["search"], search: [] })],
    });
    const res = await geo.getRoute({ waypoints: TWO_WAY });
    expect(res.routes).toEqual([]);
    expect(res.meta.providersUsed).toEqual([]);
  });
});

describe("getDistanceMatrix (거리 행렬 디스패치)", () => {
  const MATRIX = {
    rows: [
      [
        { distanceMeters: 9949.4, durationSeconds: 598.4 },
        { distanceMeters: 10857.4, durationSeconds: 700.1 },
      ],
    ],
  };

  it("distanceMatrix capable 공급자에서 행렬을 얻는다", async () => {
    const geo = createGeoWire({
      providers: [
        fakeProvider({
          id: "osrm",
          capabilities: ["distanceMatrix"],
          policy: { maxCacheTtlSeconds: 86400, canStorePermanently: true, attributionRequired: "© OSM (OSRM)" },
          matrixResult: MATRIX,
        }),
      ],
    });
    const res = await geo.getDistanceMatrix({
      origins: [{ latitude: 37.57, longitude: 126.98 }],
      destinations: [
        { latitude: 37.49, longitude: 127.02 },
        { latitude: 37.51, longitude: 127.05 },
      ],
    });
    expect(res.matrix.provider).toBe("osrm");
    expect(res.matrix.rows[0]![0]!.distanceMeters).toBe(9949.4);
    expect(res.matrix.attributions).toEqual(["© OSM (OSRM)"]);
  });

  it("distanceMatrix 공급자가 없으면 에러를 던진다", async () => {
    const geo = createGeoWire({
      providers: [fakeProvider({ id: "search-only", capabilities: ["search"], search: [] })],
    });
    await expect(
      geo.getDistanceMatrix({
        origins: [{ latitude: 0, longitude: 0 }],
        destinations: [{ latitude: 1, longitude: 1 }],
      }),
    ).rejects.toThrow();
  });
});
