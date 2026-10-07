import type { Address, Contact, LatLng } from "@geowirehq/schema";
import type { ProviderPlace } from "@geowirehq/provider-sdk";
import { mapKakaoCategory } from "./category-map.js";

/** keyword.json document (관심 필드만, 전부 선택적 방어 파싱) */
export interface KakaoPlace {
  id?: string;
  place_name?: string;
  category_name?: string;
  category_group_code?: string;
  phone?: string;
  address_name?: string;
  road_address_name?: string;
  x?: string; // 경도(longitude)
  y?: string; // 위도(latitude)
  place_url?: string;
  distance?: string;
}

/** address.json / coord2address.json 의 주소 상세 (지번/도로명) */
interface KakaoAddrPart {
  address_name?: string;
  region_1depth_name?: string; // 시/도
  region_2depth_name?: string; // 시/군/구
  region_3depth_name?: string; // 읍/면/동
  zip_code?: string;
}
interface KakaoRoadPart extends KakaoAddrPart {
  road_name?: string;
  building_name?: string;
  zone_no?: string; // 우편번호(도로명)
}
export interface KakaoAddressDoc {
  address_name?: string;
  x?: string;
  y?: string;
  address?: KakaoAddrPart | null;
  road_address?: KakaoRoadPart | null;
}

/** 카카오 지번/도로명 파트를 표준 Address 구조화 필드로. */
function structuredAddress(a?: KakaoAddrPart | null, r?: KakaoRoadPart | null): Address {
  const address: Address = { country: "KR" };
  const formatted = r?.address_name || a?.address_name;
  if (formatted) address.formatted = formatted;
  const region1 = r?.region_1depth_name || a?.region_1depth_name;
  const region2 = r?.region_2depth_name || a?.region_2depth_name;
  const region3 = r?.region_3depth_name || a?.region_3depth_name;
  if (region1) address.region = region1;
  if (region2) address.city = region2;
  if (region3) address.district = region3;
  if (r?.road_name) address.street = r.road_name;
  const zip = r?.zone_no || a?.zip_code;
  if (zip) address.postalCode = zip;
  return address;
}

/** keyword.json document → ProviderPlace. 좌표·id·이름 없으면 null. */
export function parseKakaoPlace(raw: KakaoPlace): ProviderPlace | null {
  const longitude = Number(raw.x);
  const latitude = Number(raw.y);
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  if (!raw.id) return null;
  const name = raw.place_name?.trim();
  if (!name) return null;

  const place: ProviderPlace = {
    providerPlaceId: raw.id,
    name,
    categories: mapKakaoCategory(raw.category_group_code, raw.category_name),
    location: { latitude, longitude },
  };
  const formatted = raw.road_address_name || raw.address_name;
  if (formatted) place.address = { formatted, country: "KR" };

  const contact: Contact = {};
  if (raw.phone) contact.phone = raw.phone;
  if (raw.place_url) contact.website = raw.place_url;
  if (Object.keys(contact).length > 0) place.contact = contact;

  return place;
}

export function parseKakaoPlaces(docs: readonly KakaoPlace[] | undefined): ProviderPlace[] {
  const out: ProviderPlace[] = [];
  for (const raw of docs ?? []) {
    const p = parseKakaoPlace(raw);
    if (p) out.push(p);
  }
  return out;
}

/** address.json document → ProviderPlace (geocode). 좌표 없으면 null. */
export function parseKakaoAddress(raw: KakaoAddressDoc): ProviderPlace | null {
  const longitude = Number(raw.x);
  const latitude = Number(raw.y);
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  const address = structuredAddress(raw.address, raw.road_address);
  const name = address.formatted ?? raw.address_name ?? "주소";
  return {
    providerPlaceId: `addr:${latitude},${longitude}`,
    name,
    categories: [],
    location: { latitude, longitude },
    address,
  };
}

export function parseKakaoAddresses(docs: readonly KakaoAddressDoc[] | undefined): ProviderPlace[] {
  const out: ProviderPlace[] = [];
  for (const raw of docs ?? []) {
    const p = parseKakaoAddress(raw);
    if (p) out.push(p);
  }
  return out;
}

/** coord2address.json → ProviderPlace (reverse). 위치는 요청 좌표를 사용. */
export function parseKakaoReverse(
  docs: readonly KakaoAddressDoc[] | undefined,
  location: LatLng,
): ProviderPlace[] {
  const out: ProviderPlace[] = [];
  for (const raw of docs ?? []) {
    const address = structuredAddress(raw.address, raw.road_address);
    const name = address.formatted ?? "주소";
    out.push({
      providerPlaceId: `revgeo:${location.latitude},${location.longitude}`,
      name,
      categories: [],
      location,
      address,
    });
  }
  return out;
}
