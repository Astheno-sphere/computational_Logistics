import { z } from "zod";
import { CountryCode } from "./country.js";

/** WGS84 좌표. GeoJSON Point와 상호 변환 가능 (spec: place-schema §location). */
export const LatLng = z.object({
  latitude: z.number().min(-90).max(90),
  longitude: z.number().min(-180).max(180),
});
export type LatLng = z.infer<typeof LatLng>;

export const Address = z.object({
  /** 공급자가 제공한 표시용 전체 주소 */
  formatted: z.string().optional(),
  /** ISO 3166-1 alpha-2 (예: "KR", "VN") */
  country: CountryCode.optional(),
  region: z.string().optional(),
  city: z.string().optional(),
  district: z.string().optional(),
  street: z.string().optional(),
  postalCode: z.string().optional(),
});
export type Address = z.infer<typeof Address>;

let _regionNames: Intl.DisplayNames | undefined;
/** ISO 3166-1 alpha-2 → 영어 국가명 (Intl.DisplayNames, 실패 시 코드 그대로) */
function countryName(code: string): string {
  try {
    _regionNames ??= new Intl.DisplayNames(["en"], { type: "region" });
    return _regionNames.of(code) ?? code;
  } catch {
    return code;
  }
}

/**
 * 구조화 필드로 **공급자 무관 표준 표시 주소**를 조립한다 (구체 → 광역 순).
 * `street, district, city, region, postalCode`(존재하는 것만)를 `, `로 잇고 국가명을 덧붙인다.
 * 구조화 파트(비국가)가 2개 미만이면 undefined를 반환해 호출부가 공급자 원문을 유지하도록 한다
 * (빈약한 구조화로 더 나쁜 문자열을 만들지 않기 위함).
 */
export function formatAddress(a: Address): string | undefined {
  const local = [a.street, a.district, a.city, a.region, a.postalCode].filter(
    (v): v is string => typeof v === "string" && v.trim().length > 0,
  );
  if (local.length < 2) return undefined;
  const parts = a.country ? [...local, countryName(a.country)] : local;
  return parts.join(", ");
}

export const Contact = z.object({
  phone: z.string().optional(),
  website: z.url().optional(),
});
export type Contact = z.infer<typeof Contact>;

/**
 * 개별 리뷰 (역할 기반 소싱: 리뷰는 Google이 권위 소스).
 * 원본 텍스트는 공급자 약관상 캐시 불가일 수 있어 Policy Engine의
 * `canStorePermanently`가 저장 여부를 강제한다(Google 원본 = 저장 금지).
 */
export const Review = z.object({
  author: z.string().optional(),
  /** 0.0~5.0 정규화 */
  rating: z.number().min(0).max(5).optional(),
  text: z.string().optional(),
  /** 사람이 읽는 상대 시각 (예: "2주 전") — 공급자 원문 */
  relativeTime: z.string().optional(),
  time: z.iso.datetime().optional(),
  /** 리뷰 출처 공급자 id (예: "google") — 병합 시 혼선 방지 */
  source: z.string().optional(),
});
export type Review = z.infer<typeof Review>;

export const Business = z.object({
  /** OSM opening_hours 포맷 (예: "Mo-Su 00:00-24:00") */
  openingHours: z.string().optional(),
  /** 0(무료)~4(최고가) */
  priceLevel: z.number().int().min(0).max(4).optional(),
  /** 0.0~5.0 정규화. 공급자별 스케일은 어댑터가 변환 */
  rating: z.number().min(0).max(5).optional(),
  reviewCount: z.number().int().nonnegative().optional(),
  /** 대표 리뷰 표본 (역할 소싱: Google). 원본이라 캐시는 Policy Engine이 통제 */
  reviews: z.array(Review).optional(),
  /** 사진 URL (역할 소싱: Foursquare 등 공개 CDN URL) */
  photos: z.array(z.url()).optional(),
  /**
   * 인기도 0~1 (역할 소싱: Foursquare popularity). 유동인구의 **프록시**이지 실측이 아니다 —
   * 진짜 방문량은 별도 유료 데이터(SafeGraph/Placer 등)가 필요하다.
   */
  popularity: z.number().min(0).max(1).optional(),
});
export type Business = z.infer<typeof Business>;

/**
 * 장소 정보의 출처. 항상 배열로 유지 — 다중 공급자 병합의 기반.
 * `fields`는 이 소스가 기여한 필드 경로 목록 (병합 추적: "영업시간은 google, 좌표는 osm").
 */
export const PlaceSource = z.object({
  provider: z.string().min(1),
  providerPlaceId: z.string().min(1),
  fetchedAt: z.iso.datetime(),
  confidence: z.number().min(0).max(1).optional(),
  fields: z.array(z.string()).optional(),
});
export type PlaceSource = z.infer<typeof PlaceSource>;

/** GeoWire 내부 Place ID 접두사 */
export const PLACE_ID_PREFIX = "gwp_";

/**
 * GeoWire 통합 Place 스키마 (spec: place-schema/v1).
 * 모든 공급자 응답은 이 형태로 정규화된다.
 */
export const Place = z.object({
  /** 안정적 내부 ID. 병합 후에도 유지된다 */
  id: z.string().regex(/^gwp_[A-Za-z0-9_-]+$/, "id must start with 'gwp_'"),
  name: z.string().min(1),
  /** BCP 47 언어 태그 → 현지어 이름 (예: { ko: "본가", vi: "..." }) */
  localizedNames: z.record(z.string(), z.string()).optional(),
  /** GeoWire 표준 카테고리 (OSM 태그 체계 기반 평탄화) */
  categories: z.array(z.string()),
  location: LatLng,
  address: Address.optional(),
  contact: Contact.optional(),
  business: Business.optional(),
  /** 검색 기준점으로부터의 거리 (near가 주어진 경우) */
  distanceMeters: z.number().nonnegative().optional(),
  /** 병합·검증 후 종합 신뢰도 */
  confidence: z.number().min(0).max(1).optional(),
  /** 최소 1개 — 출처 없는 장소는 존재하지 않는다 */
  sources: z.array(PlaceSource).min(1),
  /** 표시 의무 문자열. Policy Engine이 주입 (예: "© OpenStreetMap contributors") */
  attributions: z.array(z.string()),
  metadata: z.record(z.string(), z.unknown()).optional(),
});
export type Place = z.infer<typeof Place>;
