import { z } from "zod";
import { Place } from "./place.js";
import { ProviderErrorCode } from "./errors.js";
import { Strategy } from "./requests.js";
import { Route, DistanceMatrix } from "./routing.js";
import { AreaInsights } from "./analysis.js";
import { DemographicProfile } from "./demographics.js";
import { Isochrone } from "./isochrone.js";

export const ProviderUsage = z.object({
  provider: z.string(),
  resultCount: z.number().int().nonnegative(),
  latencyMs: z.number().nonnegative(),
});
export type ProviderUsage = z.infer<typeof ProviderUsage>;

export const ProviderSkip = z.object({
  provider: z.string(),
  reason: ProviderErrorCode,
});
export type ProviderSkip = z.infer<typeof ProviderSkip>;

/**
 * 응답 봉투의 meta 블록 — 투명성 원칙(P8)의 구현.
 * 어떤 공급자를 썼고, 무엇을 건너뛰었고, 비용이 얼마인지 항상 노출한다.
 */
export const ResponseMeta = z.object({
  providersUsed: z.array(ProviderUsage),
  providersSkipped: z.array(ProviderSkip).default([]),
  providersFailed: z.array(ProviderSkip).default([]),
  strategy: Strategy,
  dedup: z
    .object({
      before: z.number().int().nonnegative(),
      after: z.number().int().nonnegative(),
    })
    .optional(),
  cache: z
    .object({
      hit: z.boolean(),
      ttlSeconds: z.number().int().nonnegative().optional(),
    })
    .optional(),
  estimatedCostUSD: z.number().nonnegative().optional(),
  attributions: z.array(z.string()).default([]),
});
export type ResponseMeta = z.infer<typeof ResponseMeta>;

export const SearchPlacesResponse = z.object({
  results: z.array(Place),
  meta: ResponseMeta,
});
export type SearchPlacesResponse = z.infer<typeof SearchPlacesResponse>;

/** 길찾기 응답 봉투 — 검색과 동일한 투명성 meta를 공유한다 */
export const RouteResponse = z.object({
  routes: z.array(Route),
  meta: ResponseMeta,
});
export type RouteResponse = z.infer<typeof RouteResponse>;

/** 거리 행렬 응답 봉투 */
export const DistanceMatrixResponse = z.object({
  matrix: DistanceMatrix,
  meta: ResponseMeta,
});
export type DistanceMatrixResponse = z.infer<typeof DistanceMatrixResponse>;

/** 지역/상권 분석 응답 봉투 */
export const AreaInsightsResponse = z.object({
  insights: AreaInsights,
  meta: ResponseMeta,
});
export type AreaInsightsResponse = z.infer<typeof AreaInsightsResponse>;

/** 인구통계 응답 봉투. 공급자가 지역을 못 커버하면 profile은 null */
export const DemographicsResponse = z.object({
  profile: DemographicProfile.nullable(),
  meta: ResponseMeta,
});
export type DemographicsResponse = z.infer<typeof DemographicsResponse>;

/** 도달권 응답 봉투. 이동시간을 계산할 공급자가 없으면 isochrone은 null */
export const IsochroneResponse = z.object({
  isochrone: Isochrone.nullable(),
  meta: ResponseMeta,
});
export type IsochroneResponse = z.infer<typeof IsochroneResponse>;
