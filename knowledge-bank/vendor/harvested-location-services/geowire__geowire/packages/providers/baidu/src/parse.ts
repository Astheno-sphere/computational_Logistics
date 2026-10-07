import type { Address, Contact, LatLng } from "@geowirehq/schema";
import type { ProviderPlace } from "@geowirehq/provider-sdk";
import { bd09ToWgs84 } from "./coords.js";

/** place/v2/search 결과 한 건 (scope=2 상세 포함) */
export interface BaiduPlace {
  name?: string;
  location?: { lat?: number; lng?: number }; // BD-09
  address?: string;
  telephone?: string;
  uid?: string;
  detail_info?: { tag?: string; detail_url?: string };
}

/** geocoding v3 result */
export interface BaiduGeocode {
  location?: { lat?: number; lng?: number }; // BD-09
  level?: string;
  precise?: number;
  confidence?: number;
}

/** reverse_geocoding v3 result */
export interface BaiduReverse {
  formatted_address?: string;
  addressComponent?: {
    country?: string;
    province?: string;
    city?: string;
    district?: string;
    town?: string;
    street?: string;
    street_number?: string;
    adcode?: string;
    country_code?: number;
  };
}

/** detail_info.tag("美食;中餐厅") → 카테고리 배열 */
function parseTags(tag?: string): string[] {
  return tag
    ? tag
        .split(/[;,>]/u)
        .map((t) => t.trim())
        .filter(Boolean)
    : [];
}

/** place → ProviderPlace. BD-09 좌표를 WGS84로 변환. 좌표·uid·이름 없으면 null. */
export function parseBaiduPlace(raw: BaiduPlace): ProviderPlace | null {
  if (raw.location?.lat == null || raw.location?.lng == null) return null;
  if (!raw.uid) return null;
  const name = raw.name?.trim();
  if (!name) return null;

  const place: ProviderPlace = {
    providerPlaceId: raw.uid,
    name,
    categories: parseTags(raw.detail_info?.tag),
    location: bd09ToWgs84(raw.location.lng, raw.location.lat),
  };
  if (raw.address) place.address = { formatted: raw.address, country: "CN" };

  const contact: Contact = {};
  if (raw.telephone) contact.phone = raw.telephone;
  if (raw.detail_info?.detail_url) contact.website = raw.detail_info.detail_url;
  if (Object.keys(contact).length > 0) place.contact = contact;

  return place;
}

export function parseBaiduPlaces(results: readonly BaiduPlace[] | undefined): ProviderPlace[] {
  const out: ProviderPlace[] = [];
  for (const raw of results ?? []) {
    const p = parseBaiduPlace(raw);
    if (p) out.push(p);
  }
  return out;
}

/** geocoding result → ProviderPlace(단수). 입력 주소를 이름으로 사용. */
export function parseBaiduGeocode(result: BaiduGeocode | undefined, address: string): ProviderPlace[] {
  if (!result || result.location?.lat == null || result.location?.lng == null) return [];
  const loc = bd09ToWgs84(result.location.lng, result.location.lat);
  return [
    {
      providerPlaceId: `addr:${loc.latitude},${loc.longitude}`,
      name: address,
      categories: [],
      location: loc,
      address: { formatted: address, country: "CN" },
    },
  ];
}

/** reverse result → ProviderPlace. 위치는 요청 좌표(WGS84)를 사용. */
export function parseBaiduReverse(result: BaiduReverse | undefined, location: LatLng): ProviderPlace[] {
  if (!result) return [];
  const c = result.addressComponent;
  const address: Address = { country: "CN" };
  if (result.formatted_address) address.formatted = result.formatted_address;
  if (c?.province) address.region = c.province;
  if (c?.city) address.city = c.city;
  if (c?.district) address.district = c.district;
  if (c?.street) address.street = c.street;
  if (c?.adcode) address.postalCode = c.adcode;
  return [
    {
      providerPlaceId: `revgeo:${location.latitude},${location.longitude}`,
      name: result.formatted_address ?? "地址",
      categories: [],
      location,
      address,
    },
  ];
}
