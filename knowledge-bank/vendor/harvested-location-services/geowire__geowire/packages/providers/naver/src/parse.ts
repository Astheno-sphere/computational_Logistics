import type { Contact } from "@geowirehq/schema";
import type { ProviderPlace } from "@geowirehq/provider-sdk";

/** 지역검색 item (관심 필드만) */
export interface NaverItem {
  title?: string; // <b> 하이라이트 태그 포함
  link?: string;
  category?: string; // "음식점>카페,디저트" 등
  description?: string;
  telephone?: string;
  address?: string; // 지번
  roadAddress?: string; // 도로명
  mapx?: string; // 경도 * 1e7 (정수 문자열)
  mapy?: string; // 위도 * 1e7
}

/** HTML 태그·기본 엔티티 제거 (지역검색 title은 <b>...</b>를 포함) */
export function stripHtml(s: string): string {
  return s
    .replace(/<[^>]+>/gu, "")
    .replace(/&amp;/gu, "&")
    .replace(/&lt;/gu, "<")
    .replace(/&gt;/gu, ">")
    .replace(/&quot;/gu, '"')
    .replace(/&#39;/gu, "'")
    .trim();
}

/**
 * 지역검색 mapx/mapy → WGS84 십진 도(度).
 * 현행 API는 WGS84를 10^7배한 정수(예: "1270286020" → 127.0286020)를 준다.
 * 방어적으로 이미 십진 도인 경우(|v|<1000)는 그대로 둔다.
 */
export function naverCoord(v?: string): number | undefined {
  if (v == null || v === "") return undefined;
  const n = Number(v);
  if (!Number.isFinite(n)) return undefined;
  return Math.abs(n) > 1000 ? n / 1e7 : n;
}

/** 지역검색 item → ProviderPlace. 좌표·이름 없거나 WGS84 범위 밖이면 null. */
export function parseNaverItem(raw: NaverItem): ProviderPlace | null {
  const longitude = naverCoord(raw.mapx);
  const latitude = naverCoord(raw.mapy);
  if (longitude == null || latitude == null) return null;
  if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return null;
  const name = raw.title ? stripHtml(raw.title) : undefined;
  if (!name) return null;

  const place: ProviderPlace = {
    providerPlaceId: `${raw.mapx},${raw.mapy}`,
    name,
    categories: raw.category
      ? raw.category
          .split(/[>,]/u)
          .map((c) => c.trim())
          .filter(Boolean)
      : [],
    location: { latitude, longitude },
  };
  const formatted = raw.roadAddress || raw.address;
  if (formatted) place.address = { formatted, country: "KR" };

  const contact: Contact = {};
  if (raw.telephone) contact.phone = raw.telephone;
  if (raw.link) contact.website = raw.link;
  if (Object.keys(contact).length > 0) place.contact = contact;

  return place;
}

export function parseNaverItems(items: readonly NaverItem[] | undefined): ProviderPlace[] {
  const out: ProviderPlace[] = [];
  for (const raw of items ?? []) {
    const p = parseNaverItem(raw);
    if (p) out.push(p);
  }
  return out;
}
