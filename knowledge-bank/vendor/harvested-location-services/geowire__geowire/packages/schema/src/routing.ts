import { z } from "zod";
import { LatLng } from "./place.js";
import { RequestOptions } from "./requests.js";

/**
 * 이동 수단 (OSRM 프로파일과 대응: driving/walking/cycling).
 * ⚠️ OSRM 공개 데모 서버(router.project-osrm.org)는 `driving`만 제공한다 —
 * walking/cycling은 self-host OSRM 또는 다른 라우팅 공급자가 필요하다.
 */
export const TravelMode = z.enum(["driving", "walking", "cycling"]);
export type TravelMode = z.infer<typeof TravelMode>;

/** GeoJSON LineString (경로 지오메트리). 좌표는 [경도, 위도] 순서(GeoJSON 규약). */
export const LineString = z.object({
  type: z.literal("LineString"),
  coordinates: z.array(z.tuple([z.number(), z.number()])),
});
export type LineString = z.infer<typeof LineString>;

/** GeoJSON Polygon (도달권 등 영역). 외곽 링 하나 이상, 좌표는 [경도, 위도]. */
export const Polygon = z.object({
  type: z.literal("Polygon"),
  coordinates: z.array(z.array(z.tuple([z.number(), z.number()]))),
});
export type Polygon = z.infer<typeof Polygon>;

/** 연속한 두 경유지 사이 구간 */
export const RouteLeg = z.object({
  distanceMeters: z.number().nonnegative(),
  durationSeconds: z.number().nonnegative(),
});
export type RouteLeg = z.infer<typeof RouteLeg>;

/**
 * 경유지들을 잇는 하나의 경로 (설계: routing/v1).
 * `legs`는 경유지 쌍별 구간, 총합은 `distanceMeters`/`durationSeconds`.
 */
export const Route = z.object({
  distanceMeters: z.number().nonnegative(),
  durationSeconds: z.number().nonnegative(),
  legs: z.array(RouteLeg),
  /** 전체 경로 폴리라인 (요청 시). 지도 렌더링용 */
  geometry: LineString.optional(),
  /** 이 경로를 만든 공급자 id (예: "osrm") */
  provider: z.string().min(1),
  /** 표시 의무 문자열 (Policy Engine 주입) */
  attributions: z.array(z.string()).default([]),
});
export type Route = z.infer<typeof Route>;

export const RouteRequest = z.object({
  /** 출발→(경유)→도착. 최소 2개 */
  waypoints: z.array(LatLng).min(2),
  mode: TravelMode.default("driving"),
  /** 대안 경로도 요청할지 (공급자가 지원하면) */
  alternatives: z.boolean().default(false),
  /** 경로 폴리라인 포함 여부 */
  geometry: z.boolean().default(false),
  options: RequestOptions.optional(),
});
export type RouteRequest = z.infer<typeof RouteRequest>;

/**
 * 원점×목적지 거리/시간 행렬의 한 칸.
 * 도달 불가 쌍은 두 필드 모두 생략(null 대신 부재로 표현).
 */
export const DistanceMatrixCell = z.object({
  distanceMeters: z.number().nonnegative().optional(),
  durationSeconds: z.number().nonnegative().optional(),
});
export type DistanceMatrixCell = z.infer<typeof DistanceMatrixCell>;

export const DistanceMatrixRequest = z.object({
  origins: z.array(LatLng).min(1),
  destinations: z.array(LatLng).min(1),
  mode: TravelMode.default("driving"),
  options: RequestOptions.optional(),
});
export type DistanceMatrixRequest = z.infer<typeof DistanceMatrixRequest>;

/** `rows[i][j]` = origins[i] → destinations[j] 거리/시간 */
export const DistanceMatrix = z.object({
  rows: z.array(z.array(DistanceMatrixCell)),
  provider: z.string().min(1),
  attributions: z.array(z.string()).default([]),
});
export type DistanceMatrix = z.infer<typeof DistanceMatrix>;
