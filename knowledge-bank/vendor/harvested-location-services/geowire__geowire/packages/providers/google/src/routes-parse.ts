import type { TravelMode } from "@geowirehq/schema";
import type { ProviderRoute, ProviderDistanceMatrix } from "@geowirehq/provider-sdk";

/** GeoWire TravelMode → Google Routes API travelMode */
export const GOOGLE_TRAVEL_MODE: Record<TravelMode, string> = {
  driving: "DRIVE",
  walking: "WALK",
  cycling: "BICYCLE",
};

/** Google duration은 "560s"·"560.4s" 문자열 → 초(number). 실패 시 0 */
export function parseDuration(d: string | undefined): number {
  if (!d) return 0;
  const n = Number.parseFloat(d.replace(/s$/, ""));
  return Number.isFinite(n) ? n : 0;
}

interface GoogleRoute {
  distanceMeters?: number;
  duration?: string;
  legs?: Array<{ distanceMeters?: number; duration?: string }>;
  polyline?: {
    geoJsonLinestring?: { type?: string; coordinates?: Array<[number, number]> };
  };
}

/** Google Routes route → ProviderRoute */
export function parseGoogleRoute(raw: GoogleRoute): ProviderRoute {
  const legs = (raw.legs ?? []).map((l) => ({
    distanceMeters: l.distanceMeters ?? 0,
    durationSeconds: parseDuration(l.duration),
  }));
  const out: ProviderRoute = {
    distanceMeters: raw.distanceMeters ?? 0,
    durationSeconds: parseDuration(raw.duration),
    legs,
  };
  const gj = raw.polyline?.geoJsonLinestring;
  if (gj?.type === "LineString" && Array.isArray(gj.coordinates)) {
    out.geometry = { type: "LineString", coordinates: gj.coordinates };
  }
  return out;
}

export function parseGoogleRoutes(routes: readonly GoogleRoute[] | undefined): ProviderRoute[] {
  return (routes ?? []).map(parseGoogleRoute);
}

/** Route Matrix의 개별 원소 (원점×목적지 좌표는 인덱스로 참조) */
export interface GoogleMatrixElement {
  originIndex?: number;
  destinationIndex?: number;
  distanceMeters?: number;
  duration?: string;
  condition?: string; // "ROUTE_EXISTS" | "ROUTE_NOT_FOUND"
}

/**
 * Route Matrix 원소 목록 → ProviderDistanceMatrix.
 * 원소는 순서 없이 도착할 수 있어 originIndex/destinationIndex로 배치한다.
 * condition이 ROUTE_EXISTS가 아니면 셀을 비운다.
 */
export function parseGoogleMatrix(
  elements: readonly GoogleMatrixElement[] | undefined,
  nOrigins: number,
  nDestinations: number,
): ProviderDistanceMatrix {
  const rows = Array.from({ length: nOrigins }, () =>
    Array.from({ length: nDestinations }, () => ({}) as { distanceMeters?: number; durationSeconds?: number }),
  );
  for (const el of elements ?? []) {
    const i = el.originIndex;
    const j = el.destinationIndex;
    if (i == null || j == null || i >= nOrigins || j >= nDestinations) continue;
    if (el.condition && el.condition !== "ROUTE_EXISTS") continue;
    const cell: { distanceMeters?: number; durationSeconds?: number } = {};
    if (typeof el.distanceMeters === "number") cell.distanceMeters = el.distanceMeters;
    const dur = parseDuration(el.duration);
    if (el.duration) cell.durationSeconds = dur;
    rows[i]![j] = cell;
  }
  return { rows };
}
