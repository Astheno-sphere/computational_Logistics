import { describe, it, expect } from "vitest";
import { defineProvider } from "@geowirehq/provider-sdk";
import type { GeoProvider } from "@geowirehq/provider-sdk";
import type { LatLng, DistanceMatrixRequest } from "@geowirehq/schema";
import { createGeoWire } from "../src/geowire.js";
import { manifest, fakeProvider } from "./helpers.js";

const SF = { latitude: 37.7749, longitude: -122.4194 };

function haversine(a: LatLng, b: LatLng): number {
  const R = 6_371_000;
  const d2r = Math.PI / 180;
  const dLat = (b.latitude - a.latitude) * d2r;
  const dLng = (b.longitude - a.longitude) * d2r;
  const x =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(a.latitude * d2r) * Math.cos(b.latitude * d2r) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(x));
}

/** 직선거리 기반으로 duration을 내는 distanceMatrix 공급자 (도달권 근사 검증용) */
function matrixProvider(speedMps = 13.9): GeoProvider {
  return defineProvider({
    manifest: manifest({
      id: "fakeosrm",
      capabilities: ["distanceMatrix"],
      policy: { maxCacheTtlSeconds: 86400, canStorePermanently: true, attributionRequired: "© OSM" },
    }),
    async distanceMatrix(req: DistanceMatrixRequest) {
      return {
        rows: req.origins.map((o) =>
          req.destinations.map((d) => {
            const m = haversine(o, d);
            return { distanceMeters: m, durationSeconds: m / speedMps };
          }),
        ),
      };
    },
  });
}

describe("getIsochrone (도달권 근사)", () => {
  it("도달권 폴리곤·면적·표본 통계를 만든다", async () => {
    const geo = createGeoWire({ providers: [matrixProvider()] });
    const res = await geo.getIsochrone({ origin: SF, minutes: 10, mode: "driving", bearings: 16 });
    const iso = res.isochrone!;
    expect(iso).not.toBeNull();
    // 폴리곤은 bearings + 1(닫힘) 점
    expect(iso.polygon.type).toBe("Polygon");
    expect(iso.polygon.coordinates[0]).toHaveLength(17);
    expect(iso.areaSqKm).toBeGreaterThan(0);
    expect(iso.reachableSamples).toBeGreaterThan(0);
    expect(iso.reachableSamples).toBeLessThanOrEqual(iso.sampleCount);
    expect(iso.provider).toBe("fakeosrm");
    expect(iso.attributions).toContain("© OSM");
    expect(iso.note).toContain("approximate");
  });

  it("예산이 커지면 도달 면적·표본이 늘어난다(단조 증가)", async () => {
    const geo = createGeoWire({ providers: [matrixProvider()] });
    const a = (await geo.getIsochrone({ origin: SF, minutes: 5, mode: "driving" })).isochrone!;
    const b = (await geo.getIsochrone({ origin: SF, minutes: 20, mode: "driving" })).isochrone!;
    expect(b.areaSqKm).toBeGreaterThan(a.areaSqKm);
    expect(b.reachableSamples).toBeGreaterThanOrEqual(a.reachableSamples);
  });

  it("distanceMatrix 공급자가 없으면 isochrone은 null(에러 아님)", async () => {
    const geo = createGeoWire({ providers: [fakeProvider({ id: "search-only", capabilities: ["search"], search: [] })] });
    const res = await geo.getIsochrone({ origin: SF, minutes: 10, mode: "driving" });
    expect(res.isochrone).toBeNull();
  });
});
