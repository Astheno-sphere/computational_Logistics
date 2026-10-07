import { CountryCode } from "@geowirehq/schema";
import type { Address } from "@geowirehq/schema";
import type { ProviderPlace } from "@geowirehq/provider-sdk";
import { mapCategory } from "./category-map.js";

/** Nominatim jsonv2 결과 한 건의 관심 필드 (전부 선택적으로 방어적 파싱) */
export interface NominatimResult {
  osm_type?: string;
  osm_id?: number;
  place_id?: number;
  lat?: string;
  lon?: string;
  name?: string;
  display_name?: string;
  category?: string;
  type?: string;
  importance?: number;
  addresstype?: string;
  address?: Record<string, string>;
}

/**
 * Nominatim 결과 한 건을 `ProviderPlace`로 정규화한다.
 * 좌표나 안정 식별자가 없으면 `null`을 돌려주고, 호출부가 필터링한다.
 */
export function parseResult(raw: NominatimResult): ProviderPlace | null {
  const latitude = Number(raw.lat);
  const longitude = Number(raw.lon);
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;

  const providerPlaceId = stableId(raw);
  if (!providerPlaceId) return null;

  const place: ProviderPlace = {
    providerPlaceId,
    name: pickName(raw),
    categories: mapCategory(raw.category, raw.type),
    location: { latitude, longitude },
  };

  const address = parseAddress(raw);
  if (address) place.address = address;
  if (typeof raw.importance === "number" && Number.isFinite(raw.importance)) {
    place.confidence = clamp01(raw.importance);
  }
  return place;
}

/** 결과 배열/단건을 모두 받아 유효한 ProviderPlace 목록으로 변환 */
export function parseResults(raw: unknown): ProviderPlace[] {
  const items = Array.isArray(raw) ? raw : raw != null ? [raw] : [];
  const places: ProviderPlace[] = [];
  for (const item of items) {
    const place = parseResult(item as NominatimResult);
    if (place) places.push(place);
  }
  return places;
}

function stableId(raw: NominatimResult): string | null {
  if (raw.osm_type && raw.osm_id != null) return `${raw.osm_type}/${raw.osm_id}`;
  if (raw.place_id != null) return `place/${raw.place_id}`;
  return null;
}

function pickName(raw: NominatimResult): string {
  const named = raw.name?.trim();
  if (named) return named;
  const byType = raw.addresstype ? raw.address?.[raw.addresstype]?.trim() : undefined;
  if (byType) return byType;
  const first = firstSegment(raw.display_name);
  if (first) return first;
  return raw.display_name?.trim() || "Unknown";
}

function firstSegment(displayName?: string): string | undefined {
  return displayName?.split(",")[0]?.trim() || undefined;
}

function parseAddress(raw: NominatimResult): Address | undefined {
  const a = raw.address;
  const country = a?.country_code ? CountryCode.safeParse(a.country_code) : undefined;
  const address: Address = {};
  if (raw.display_name) address.formatted = raw.display_name;
  if (country?.success) address.country = country.data;
  if (a?.state) address.region = a.state;
  const city = a?.city ?? a?.town ?? a?.village ?? a?.municipality;
  if (city) address.city = city;
  const district = a?.suburb ?? a?.city_district ?? a?.district;
  if (district) address.district = district;
  if (a?.road) address.street = a.road;
  if (a?.postcode) address.postalCode = a.postcode;
  return Object.keys(address).length > 0 ? address : undefined;
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}
