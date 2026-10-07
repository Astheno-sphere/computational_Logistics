import { z } from "zod";
import { LatLng } from "./place.js";
import { CountryCode } from "./country.js";

/**
 * 공급자 호출 전략 (설계 §7.2).
 * - `first-success`: 우선순위 순서로 하나씩, 첫 결과에서 정지.
 * - `merge`: 전부 병렬 호출 후 dedup 병합.
 * - `cost-aware`: 비용 오름차순(무료 먼저)으로 first-success — 유료 공급자는 무료가 답 못 할 때만.
 * - `weighted`: priority·cost·coverage 가중 점수 순서로 first-success (요청 국가에 맞춰 라우팅).
 * - `fastest`: 전부 병렬 호출, 결과를 가진 첫 응답(최저 지연)에서 즉시 반환. 지연 최적화.
 */
export const Strategy = z.enum(["first-success", "merge", "cost-aware", "weighted", "fastest"]);
export type Strategy = z.infer<typeof Strategy>;

/** 모든 요청에서 공통으로 오버라이드 가능한 옵션 */
export const RequestOptions = z.object({
  strategy: Strategy.optional(),
  /** 이 요청에서 사용할 공급자를 명시적으로 제한 */
  providers: z.array(z.string()).optional(),
  maxCostUSD: z.number().nonnegative().optional(),
  timeoutMs: z.number().int().positive().max(30_000).optional(),
  /** BCP 47 (예: "ko", "vi-VN") */
  language: z.string().optional(),
});
export type RequestOptions = z.infer<typeof RequestOptions>;

export const SearchPlacesRequest = z.object({
  query: z.string().min(1),
  near: LatLng.optional(),
  radiusMeters: z.number().positive().max(100_000).optional(),
  /** ISO 3166-1 alpha-2. 없으면 near 좌표로 추론 */
  country: CountryCode.optional(),
  categories: z.array(z.string()).optional(),
  openNow: z.boolean().optional(),
  limit: z.number().int().min(1).max(50).default(10),
  options: RequestOptions.optional(),
});
export type SearchPlacesRequest = z.infer<typeof SearchPlacesRequest>;

export const GeocodeRequest = z.object({
  address: z.string().min(1),
  country: CountryCode.optional(),
  limit: z.number().int().min(1).max(20).default(5),
  options: RequestOptions.optional(),
});
export type GeocodeRequest = z.infer<typeof GeocodeRequest>;

export const ReverseGeocodeRequest = z.object({
  location: LatLng,
  options: RequestOptions.optional(),
});
export type ReverseGeocodeRequest = z.infer<typeof ReverseGeocodeRequest>;

export const GetPlaceRequest = z.object({
  /** 내부 ID("gwp_...") 또는 "provider:providerPlaceId" 참조 */
  id: z.string().min(1),
  options: RequestOptions.optional(),
});
export type GetPlaceRequest = z.infer<typeof GetPlaceRequest>;

export const AutocompleteRequest = z.object({
  input: z.string().min(1),
  near: LatLng.optional(),
  country: CountryCode.optional(),
  limit: z.number().int().min(1).max(20).default(5),
  options: RequestOptions.optional(),
});
export type AutocompleteRequest = z.infer<typeof AutocompleteRequest>;
