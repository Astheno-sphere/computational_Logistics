import {
  defineProvider,
  errorFromHttpStatus,
  GeoProviderError,
  type GeoProvider,
  type ProviderContext,
  type ProviderRoute,
  type ProviderDistanceMatrix,
} from "@geowirehq/provider-sdk";
import type {
  LatLng,
  RouteRequest,
  DistanceMatrixRequest,
  TravelMode,
  RouteLeg,
  DistanceMatrixCell,
} from "@geowirehq/schema";
import { OSRM_MANIFEST } from "./manifest.js";

const DEFAULT_BASE_URL = "https://router.project-osrm.org";

/** TravelMode → OSRM 프로파일. 데모 서버는 driving만 실제 제공. */
const PROFILE: Record<TravelMode, string> = {
  driving: "driving",
  walking: "walking",
  cycling: "cycling",
};

export interface OsrmOptions {
  /** OSRM 서버 베이스 URL. 기본은 공개 데모(router.project-osrm.org) */
  baseUrl?: string;
}

/** OSRM는 `경도,위도` 순서(GeoJSON 규약)를 쓴다 — LatLng를 뒤집어 문자열로 */
function coord(p: LatLng): string {
  return `${p.longitude},${p.latitude}`;
}

/** OSRM 응답의 code가 Ok가 아니면 정규화된 에러/빈결과로 처리 */
function assertRoutable(code: string | undefined, provider: string): "ok" | "empty" {
  if (code === "Ok") return "ok";
  // 경로/도로 없음은 에러가 아니라 "결과 없음"(폴백 유도)
  if (code === "NoRoute" || code === "NoSegment" || code === "NoTrip") return "empty";
  throw new GeoProviderError("PROVIDER_UNAVAILABLE", `OSRM: ${code ?? "unknown error"}`, {
    provider,
  });
}

interface OsrmRoute {
  distance?: number;
  duration?: number;
  legs?: Array<{ distance?: number; duration?: number }>;
  geometry?: { type?: string; coordinates?: Array<[number, number]> };
}

/**
 * OSRM 공급자 — 길찾기(route) + 거리행렬(distanceMatrix). 무키.
 * 좌표는 WGS84 그대로 사용(경도,위도 순서로만 변환).
 */
export function createOsrmProvider(options: OsrmOptions = {}): GeoProvider {
  const baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");

  async function getJson(url: string, ctx: ProviderContext): Promise<Record<string, unknown>> {
    const res = await ctx.fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) throw errorFromHttpStatus(res.status, { provider: "osrm" });
    return (await res.json()) as Record<string, unknown>;
  }

  return defineProvider({
    manifest: OSRM_MANIFEST,

    async route(req: RouteRequest, ctx): Promise<ProviderRoute[]> {
      const profile = PROFILE[req.mode];
      const coords = req.waypoints.map(coord).join(";");
      const url = new URL(`${baseUrl}/route/v1/${profile}/${coords}`);
      url.searchParams.set("overview", req.geometry ? "full" : "false");
      if (req.geometry) url.searchParams.set("geometries", "geojson");
      url.searchParams.set("steps", "false");
      url.searchParams.set("alternatives", req.alternatives ? "true" : "false");

      const json = await getJson(url.toString(), ctx);
      if (assertRoutable(json.code as string | undefined, "osrm") === "empty") return [];

      const routes = (json.routes as OsrmRoute[] | undefined) ?? [];
      return routes.map((r) => parseOsrmRoute(r, req.geometry));
    },

    async distanceMatrix(
      req: DistanceMatrixRequest,
      ctx,
    ): Promise<ProviderDistanceMatrix> {
      const profile = PROFILE[req.mode];
      const all = [...req.origins, ...req.destinations];
      const coords = all.map(coord).join(";");
      const srcIdx = req.origins.map((_, i) => i).join(";");
      const dstIdx = req.destinations.map((_, i) => i + req.origins.length).join(";");
      const url = new URL(`${baseUrl}/table/v1/${profile}/${coords}`);
      url.searchParams.set("sources", srcIdx);
      url.searchParams.set("destinations", dstIdx);
      url.searchParams.set("annotations", "duration,distance");

      const json = await getJson(url.toString(), ctx);
      if (assertRoutable(json.code as string | undefined, "osrm") === "empty") {
        // 전부 도달 불가 → 빈 셀 행렬
        return {
          rows: req.origins.map(() => req.destinations.map(() => ({}))),
        };
      }
      const durations = (json.durations as Array<Array<number | null>> | undefined) ?? [];
      const distances = (json.distances as Array<Array<number | null>> | undefined) ?? [];
      const rows: DistanceMatrixCell[][] = req.origins.map((_, i) =>
        req.destinations.map((_, j) => {
          const cell: DistanceMatrixCell = {};
          const dur = durations[i]?.[j];
          const dist = distances[i]?.[j];
          if (typeof dur === "number") cell.durationSeconds = dur;
          if (typeof dist === "number") cell.distanceMeters = dist;
          return cell;
        }),
      );
      return { rows };
    },
  });
}

/** OSRM route → ProviderRoute */
function parseOsrmRoute(r: OsrmRoute, wantGeometry: boolean): ProviderRoute {
  const legs: RouteLeg[] = (r.legs ?? []).map((l) => ({
    distanceMeters: l.distance ?? 0,
    durationSeconds: l.duration ?? 0,
  }));
  const out: ProviderRoute = {
    distanceMeters: r.distance ?? 0,
    durationSeconds: r.duration ?? 0,
    legs,
  };
  if (wantGeometry && r.geometry?.type === "LineString" && Array.isArray(r.geometry.coordinates)) {
    out.geometry = { type: "LineString", coordinates: r.geometry.coordinates };
  }
  return out;
}
