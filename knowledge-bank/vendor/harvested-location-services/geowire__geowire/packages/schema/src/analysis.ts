import { z } from "zod";
import { LatLng, Place } from "./place.js";
import { RequestOptions } from "./requests.js";
import { DemographicProfile } from "./demographics.js";

/**
 * 지역/상권 분석 요청 (설계: analysis/v1).
 * 중심점 + 반경 안에서 지정한 업종(categories)들을 검색해 밀도·경쟁·평점 지형을 집계한다.
 * "여기에 카페 열면 경쟁이 얼마나 될까?" 같은 상권 판단을 한 번의 호출로.
 */
export const AreaInsightsRequest = z.object({
  center: LatLng,
  radiusMeters: z.number().positive().max(50_000),
  /** 분석할 업종/검색어 (예: ["cafe"], ["cafe","bakery","convenience store"]) */
  categories: z.array(z.string().min(1)).min(1).max(10),
  /** 업종별 최대 수집 수 (밀도·평점 표본) */
  limitPerCategory: z.number().int().min(1).max(50).default(50),
  options: RequestOptions.optional(),
});
export type AreaInsightsRequest = z.infer<typeof AreaInsightsRequest>;

/** 평점/가격 등 수치 필드의 요약 통계 */
export const StatSummary = z.object({
  count: z.number().int().nonnegative(),
  average: z.number(),
  min: z.number(),
  max: z.number(),
});
export type StatSummary = z.infer<typeof StatSummary>;

/** 한 업종의 상권 지표 */
export const CategoryInsight = z.object({
  /** 요청한 업종/검색어 */
  category: z.string(),
  /** 반경 내 발견 수 (중복 제거 후) */
  count: z.number().int().nonnegative(),
  /** 제곱킬로미터당 밀도 */
  densityPerSqKm: z.number().nonnegative(),
  /** 평점 요약 (평점 데이터가 있는 공급자에 한함) */
  rating: StatSummary.optional(),
  /** 가격대 요약 (0~4) */
  priceLevel: StatSummary.optional(),
  /**
   * 활동/유동인구 **프록시** — 실측이 아니다. Foursquare popularity 평균과
   * 총 리뷰 수(engagement)에서 파생. 진짜 방문량은 유료 데이터가 필요하다.
   */
  activity: z
    .object({
      /** 평균 인기도 0~1 (popularity 있는 장소 기준) */
      avgPopularity: z.number().min(0).max(1).optional(),
      /** 리뷰 수 합계 (관심도 신호) */
      totalReviews: z.number().int().nonnegative(),
      /** 프록시임을 명시하는 라벨 */
      note: z.string(),
    })
    .optional(),
  /** 대표 상위 장소 (평점 우선, 없으면 거리순) */
  topPlaces: z.array(Place),
});
export type CategoryInsight = z.infer<typeof CategoryInsight>;

/** 지역/상권 분석 결과 */
export const AreaInsights = z.object({
  center: LatLng,
  radiusMeters: z.number().positive(),
  /** 분석 반경의 면적(제곱킬로미터) */
  areaSqKm: z.number().positive(),
  /** 전 업종 합산(중복 제거) 장소 수 */
  totalPlaces: z.number().int().nonnegative(),
  /** 전체 밀도(제곱킬로미터당) */
  densityPerSqKm: z.number().nonnegative(),
  /** 업종별 지표 (요청 순서 유지) */
  categories: z.array(CategoryInsight),
  /** 전체 평점 요약 */
  rating: StatSummary.optional(),
  /** 중심점이 속한 지역의 인구통계 (demographics 공급자가 커버할 때만) */
  demographics: DemographicProfile.optional(),
});
export type AreaInsights = z.infer<typeof AreaInsights>;
