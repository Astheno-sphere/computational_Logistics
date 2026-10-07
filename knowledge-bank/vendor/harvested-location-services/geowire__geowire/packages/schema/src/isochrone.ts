import { z } from "zod";
import { LatLng } from "./place.js";
import { TravelMode, Polygon } from "./routing.js";
import { RequestOptions } from "./requests.js";

/**
 * 도달권(isochrone) 요청 (설계: isochrone/v1).
 * 출발점에서 주어진 이동시간 내에 도달 가능한 영역을 근사한다 —
 * "차로 15분 내 어디까지?" 상권/입지 분석의 핵심.
 */
export const IsochroneRequest = z.object({
  origin: LatLng,
  mode: TravelMode.default("driving"),
  /** 이동시간 예산(분) */
  minutes: z.number().positive().max(60),
  /** 폴리곤 방향 해상도(방위 개수). 클수록 매끄럽지만 거리행렬 샘플이 늘어난다 */
  bearings: z.number().int().min(8).max(24).default(16),
  options: RequestOptions.optional(),
});
export type IsochroneRequest = z.infer<typeof IsochroneRequest>;

/**
 * 도달권 결과. `polygon`은 방위별 프론티어 점을 이은 GeoJSON Polygon(근사).
 * 실제 도달경계가 아니라 **표본 기반 근사**임을 명시한다(별도 isochrone 엔진 없이
 * 거리행렬로 구성). 정밀 도달권은 전용 엔진(ORS/Mapbox/Valhalla)이 필요하다.
 */
export const Isochrone = z.object({
  origin: LatLng,
  mode: TravelMode,
  minutes: z.number().positive(),
  polygon: Polygon,
  /** 근사 도달 면적(제곱킬로미터) */
  areaSqKm: z.number().nonnegative(),
  /** 도달 가능으로 판정된 표본 수 / 전체 표본 수 */
  reachableSamples: z.number().int().nonnegative(),
  sampleCount: z.number().int().nonnegative(),
  /** 이동시간을 계산한 공급자 id (예: "osrm") */
  provider: z.string().min(1),
  attributions: z.array(z.string()).default([]),
  /** 근사 방식임을 알리는 라벨 */
  note: z.string(),
});
export type Isochrone = z.infer<typeof Isochrone>;
