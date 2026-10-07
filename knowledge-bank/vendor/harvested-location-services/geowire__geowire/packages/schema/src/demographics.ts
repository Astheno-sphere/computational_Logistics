import { z } from "zod";
import { LatLng } from "./place.js";
import { RequestOptions } from "./requests.js";

/** 금액 + 통화 (공급자·국가별 통화가 다르므로 명시) */
export const MoneyAmount = z.object({
  amount: z.number(),
  /** ISO 4217 (예: "USD", "KRW") */
  currency: z.string().length(3),
});
export type MoneyAmount = z.infer<typeof MoneyAmount>;

/**
 * 특정 지점이 속한 행정구역의 인구통계 프로파일 (설계: demographics/v1).
 * POI가 아니라 **지역 통계** — 상권 분석에 인구·소득·가구 맥락을 더한다.
 * 값은 전부 선택적(공급자·지역별 가용성 차이). 통화가 있는 값은 MoneyAmount로.
 */
export const DemographicProfile = z.object({
  /** 사람이 읽는 지역명 (예: "Census Tract 201.01, San Francisco County, California") */
  areaName: z.string(),
  /** 통계 집계 단위 (예: "tract", "blockgroup", "county", "adm2") */
  areaLevel: z.string(),
  /** 총 인구 */
  population: z.number().int().nonnegative().optional(),
  /** 중위 연령(세) */
  medianAgeYears: z.number().nonnegative().optional(),
  /** 중위 가구소득 */
  medianHouseholdIncome: MoneyAmount.optional(),
  /** 가구 수 */
  households: z.number().int().nonnegative().optional(),
  /** 평균 가구원 수 */
  avgHouseholdSize: z.number().nonnegative().optional(),
  /** 인구밀도(제곱킬로미터당) — 공급자가 면적을 줄 때만 */
  populationDensityPerSqKm: z.number().nonnegative().optional(),
  /** 출처 공급자 id (예: "census") */
  source: z.string().min(1),
  /** 표시 의무 문자열 */
  attributions: z.array(z.string()).default([]),
});
export type DemographicProfile = z.infer<typeof DemographicProfile>;

export const DemographicsRequest = z.object({
  location: LatLng,
  options: RequestOptions.optional(),
});
export type DemographicsRequest = z.infer<typeof DemographicsRequest>;
