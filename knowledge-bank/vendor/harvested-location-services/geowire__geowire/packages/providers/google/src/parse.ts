import { CountryCode } from "@geowirehq/schema";
import type { Address, Business, Contact, Review } from "@geowirehq/schema";
import type { ProviderPlace } from "@geowirehq/provider-sdk";
import { mapGoogleTypes } from "./category-map.js";

/** Places API (New) review 리소스 (getPlace 상세에서만 요청) */
export interface GoogleReview {
  rating?: number;
  text?: { text?: string };
  originalText?: { text?: string };
  authorAttribution?: { displayName?: string };
  relativePublishTimeDescription?: string;
  publishTime?: string;
}

/** Places API (New) place 리소스의 관심 필드 (전부 선택적, 방어적 파싱) */
export interface GooglePlace {
  id?: string;
  displayName?: { text?: string; languageCode?: string };
  formattedAddress?: string;
  location?: { latitude?: number; longitude?: number };
  types?: string[];
  primaryType?: string;
  rating?: number;
  userRatingCount?: number;
  regularOpeningHours?: { weekdayDescriptions?: string[] };
  nationalPhoneNumber?: string;
  internationalPhoneNumber?: string;
  websiteUri?: string;
  priceLevel?: string;
  reviews?: GoogleReview[];
  addressComponents?: Array<{ longText?: string; shortText?: string; types?: string[] }>;
}

/** Google review → 표준 Review. 텍스트·평점 모두 없으면 null(잡음 제거) */
function parseGoogleReview(raw: GoogleReview): Review | null {
  const text = raw.text?.text?.trim() || raw.originalText?.text?.trim();
  const rating = typeof raw.rating === "number" ? clampRating(raw.rating) : undefined;
  if (!text && rating === undefined) return null;
  const review: Review = { source: "google" };
  if (text) review.text = text;
  if (rating !== undefined) review.rating = rating;
  const author = raw.authorAttribution?.displayName?.trim();
  if (author) review.author = author;
  if (raw.relativePublishTimeDescription) review.relativeTime = raw.relativePublishTimeDescription;
  if (raw.publishTime) review.time = raw.publishTime;
  return review;
}

/**
 * Google 주소 컴포넌트(타입 기반) 하나를 표준 Address 필드에 매핑한다.
 * Places API (New)의 `{longText,shortText}`와 Geocoding API의 `{long_name,short_name}`을
 * 공통 로직으로 처리하기 위한 헬퍼 — 두 경로가 동일한 구조화 결과를 내도록 보장한다.
 */
function applyAddressComponent(
  address: Address,
  long: string | undefined,
  short: string | undefined,
  types: readonly string[],
): void {
  if (types.includes("country") && short) {
    const cc = CountryCode.safeParse(short);
    if (cc.success) address.country = cc.data;
  } else if (types.includes("administrative_area_level_1") && long) {
    address.region = long;
  } else if (types.includes("locality") && long) {
    address.city = long;
  } else if (types.some((t) => t.startsWith("sublocality")) && long) {
    address.district = long;
  } else if (types.includes("route") && long) {
    address.street = long;
  } else if (types.includes("postal_code") && long) {
    address.postalCode = long;
  }
}

/** Places API (New) place → 표준 Address (formatted + 구조화 필드). */
function parsePlaceAddress(raw: GooglePlace): Address | undefined {
  const address: Address = {};
  if (raw.formattedAddress) address.formatted = raw.formattedAddress;
  for (const c of raw.addressComponents ?? []) {
    applyAddressComponent(address, c.longText, c.shortText, c.types ?? []);
  }
  return Object.keys(address).length > 0 ? address : undefined;
}

const PRICE_LEVEL: Record<string, number> = {
  PRICE_LEVEL_FREE: 0,
  PRICE_LEVEL_INEXPENSIVE: 1,
  PRICE_LEVEL_MODERATE: 2,
  PRICE_LEVEL_EXPENSIVE: 3,
  PRICE_LEVEL_VERY_EXPENSIVE: 4,
};

/** Places API (New) place → ProviderPlace. 좌표·id 없으면 null */
export function parseGooglePlace(raw: GooglePlace): ProviderPlace | null {
  const latitude = raw.location?.latitude;
  const longitude = raw.location?.longitude;
  if (typeof latitude !== "number" || typeof longitude !== "number") return null;
  if (!raw.id) return null;

  const name = raw.displayName?.text?.trim();
  const place: ProviderPlace = {
    providerPlaceId: raw.id,
    name: name && name.length > 0 ? name : (raw.formattedAddress ?? "Unknown"),
    categories: mapGoogleTypes(raw.types ?? (raw.primaryType ? [raw.primaryType] : [])),
    location: { latitude, longitude },
  };

  const lang = raw.displayName?.languageCode;
  if (name && lang) place.localizedNames = { [lang]: name };

  const address = parsePlaceAddress(raw);
  if (address) place.address = address;

  const contact: Contact = {};
  const phone = raw.nationalPhoneNumber ?? raw.internationalPhoneNumber;
  if (phone) contact.phone = phone;
  if (raw.websiteUri) contact.website = raw.websiteUri;
  if (Object.keys(contact).length > 0) place.contact = contact;

  const business: Business = {};
  if (typeof raw.rating === "number") business.rating = clampRating(raw.rating);
  if (typeof raw.userRatingCount === "number") business.reviewCount = raw.userRatingCount;
  if (raw.priceLevel && raw.priceLevel in PRICE_LEVEL) business.priceLevel = PRICE_LEVEL[raw.priceLevel];
  // 리뷰(역할 소싱: Google) — getPlace 상세에서만 옴. 원본이라 저장은 Policy Engine이 통제.
  const reviews = (raw.reviews ?? []).map(parseGoogleReview).filter((r): r is Review => r !== null);
  if (reviews.length > 0) business.reviews = reviews;
  // Google 영업시간은 사람이 읽는 문장(weekdayDescriptions)이라 OSM opening_hours 포맷과 다르다.
  // 손실 없는 변환이 불가하므로 business.openingHours는 채우지 않고 metadata로 보존한다(v0.2 파서 도입 전).
  if (Object.keys(business).length > 0) place.business = business;

  if (raw.regularOpeningHours?.weekdayDescriptions?.length) {
    place.metadata = { googleWeekdayDescriptions: raw.regularOpeningHours.weekdayDescriptions };
  }

  return place;
}

/** 여러 place → ProviderPlace[] */
export function parseGooglePlaces(places: readonly GooglePlace[] | undefined): ProviderPlace[] {
  const out: ProviderPlace[] = [];
  for (const raw of places ?? []) {
    const place = parseGooglePlace(raw);
    if (place) out.push(place);
  }
  return out;
}

/** Geocoding API result의 관심 필드 */
export interface GeocodeResult {
  place_id?: string;
  formatted_address?: string;
  geometry?: { location?: { lat?: number; lng?: number } };
  types?: string[];
  address_components?: Array<{ long_name?: string; short_name?: string; types?: string[] }>;
}

/** Geocoding API result → ProviderPlace. 좌표·place_id 없으면 null */
export function parseGeocodeResult(raw: GeocodeResult): ProviderPlace | null {
  const lat = raw.geometry?.location?.lat;
  const lng = raw.geometry?.location?.lng;
  if (typeof lat !== "number" || typeof lng !== "number") return null;
  if (!raw.place_id) return null;

  const place: ProviderPlace = {
    providerPlaceId: raw.place_id,
    name: pickGeocodeName(raw),
    categories: mapGoogleTypes(raw.types),
    location: { latitude: lat, longitude: lng },
  };

  const address = parseGeocodeAddress(raw);
  if (address) place.address = address;
  return place;
}

export function parseGeocodeResults(results: readonly GeocodeResult[] | undefined): ProviderPlace[] {
  const out: ProviderPlace[] = [];
  for (const raw of results ?? []) {
    const place = parseGeocodeResult(raw);
    if (place) out.push(place);
  }
  return out;
}

function pickGeocodeName(raw: GeocodeResult): string {
  const first = raw.address_components?.[0]?.long_name?.trim();
  if (first) return first;
  const seg = raw.formatted_address?.split(",")[0]?.trim();
  if (seg) return seg;
  return raw.formatted_address?.trim() || "Unknown";
}

function parseGeocodeAddress(raw: GeocodeResult): Address | undefined {
  const address: Address = {};
  if (raw.formatted_address) address.formatted = raw.formatted_address;
  for (const c of raw.address_components ?? []) {
    applyAddressComponent(address, c.long_name, c.short_name, c.types ?? []);
  }
  return Object.keys(address).length > 0 ? address : undefined;
}

function clampRating(value: number): number {
  return Math.max(0, Math.min(5, value));
}
