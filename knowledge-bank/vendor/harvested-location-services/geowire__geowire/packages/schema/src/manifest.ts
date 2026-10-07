import { z } from "zod";
import { CountryCode } from "./country.js";

/** 공급자가 지원할 수 있는 기능 (spec: provider-manifest/v1) */
export const Capability = z.enum([
  "search",
  "autocomplete",
  "geocode",
  "reverseGeocode",
  "getPlace",
  "route",
  "distanceMatrix",
  "demographics",
]);
export type Capability = z.infer<typeof Capability>;

/**
 * 병합 시 값을 하나만 고르는(단일 소스) 필드군. 역할 기반 필드 소싱의 대상이다
 * (설계 §7.3 "영업시간은 Google, 좌표는 OSM"). `categories`·`localizedNames`는
 * 합집합 병합이라 여기 포함하지 않는다. `business`는 rating/영업시간/리뷰/사진을 묶는다.
 */
export const FieldRole = z.enum(["name", "location", "address", "contact", "business"]);
export type FieldRole = z.infer<typeof FieldRole>;

/**
 * GeoWire Provider Manifest (spec: provider-manifest/v1).
 * 공급자의 capability·커버리지·비용 모델·데이터 정책을 기계가 읽는 형식으로 선언한다.
 * `policy`는 Policy Engine이 캐시 TTL 상한·영속 저장·표시 의무를 강제하는 근거다.
 */
export const ProviderManifest = z.object({
  /** 소문자 슬러그 (예: "nominatim", "google") */
  id: z.string().regex(/^[a-z][a-z0-9-]*$/),
  name: z.string().min(1),
  capabilities: z.array(Capability).min(1),
  authType: z.enum(["apiKey", "oauth", "none"]),
  /** ISO 3166-1 alpha-2 국가코드 목록. 비어 있으면 글로벌 */
  coverage: z.array(CountryCode).optional(),
  /** 비용 기반 라우팅(cost-aware)의 데이터원 */
  cost: z
    .object({
      currency: z.literal("USD"),
      perCall: z.partialRecord(Capability, z.number().nonnegative()),
    })
    .optional(),
  /**
   * 역할 기반 필드 소싱: 이 공급자가 **어느 필드를 권위 있게 제공하는가**를 선언한다.
   * 값이 클수록 병합 시 그 필드를 이 공급자에서 가져올 확률이 높다(설계 §7.3).
   * 예) OSM `{location:10, address:8}`(기반 지도), Google `{business:10}`(리뷰·평점·사진),
   * Foursquare `{business:6}`(POI 속성), Kakao/Naver/Baidu `{name:8, address:7}`(국가별 현지명).
   * 미선언 필드는 provider priority → source confidence 순으로 결정된다(하위 호환).
   */
  fieldAuthority: z.partialRecord(FieldRole, z.number().nonnegative()).optional(),
  /** 공급자 약관의 기계화 — GeoWire의 핵심 차별점 */
  policy: z.object({
    /** null = 캐시 금지 */
    maxCacheTtlSeconds: z.number().int().nonnegative().nullable(),
    /** false면 providerPlaceId + 내부 ID 외 원본 저장 차단 */
    canStorePermanently: z.boolean(),
    attributionRequired: z.string().optional(),
  }),
  rateLimit: z
    .object({
      requestsPerSecond: z.number().positive().optional(),
    })
    .optional(),
});
export type ProviderManifest = z.infer<typeof ProviderManifest>;
