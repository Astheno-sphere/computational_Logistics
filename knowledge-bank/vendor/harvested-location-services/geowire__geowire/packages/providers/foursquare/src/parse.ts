import { CountryCode } from "@geowirehq/schema";
import type { Address, Business, Contact } from "@geowirehq/schema";
import type { ProviderPlace } from "@geowirehq/provider-sdk";

/** Foursquare 사진 리소스 — 공개 CDN(prefix + 크기 + suffix). 키 불필요. */
interface FsqPhoto {
  prefix?: string;
  suffix?: string;
}

/** Foursquare Places(현행 API) place (관심 필드만) */
export interface FsqPlace {
  fsq_place_id?: string;
  name?: string;
  latitude?: number; // WGS84 (top-level, 현행 API)
  longitude?: number;
  location?: {
    formatted_address?: string;
    address?: string;
    locality?: string; // 시
    region?: string; // 주/도
    postcode?: string;
    country?: string; // ISO alpha-2
  };
  categories?: Array<{ name?: string }>;
  tel?: string;
  website?: string;
  rating?: number; // 0~10 스케일 (현행 API)
  price?: number; // 1(저렴)~4(고가)
  photos?: FsqPhoto[];
  popularity?: number; // 0~1 (유동인구 프록시)
}

/** Foursquare 사진 객체 → 원본 크기 공개 URL. prefix/suffix 없으면 null. */
function fsqPhotoUrl(p: FsqPhoto): string | null {
  if (!p.prefix || !p.suffix) return null;
  return `${p.prefix}original${p.suffix}`;
}

/** place → ProviderPlace. 좌표·id·이름 없으면 null. */
export function parseFsqPlace(raw: FsqPlace): ProviderPlace | null {
  if (typeof raw.latitude !== "number" || typeof raw.longitude !== "number") return null;
  if (!raw.fsq_place_id) return null;
  const name = raw.name?.trim();
  if (!name) return null;

  const place: ProviderPlace = {
    providerPlaceId: raw.fsq_place_id,
    name,
    categories: (raw.categories ?? [])
      .map((c) => c.name?.trim())
      .filter((n): n is string => !!n),
    location: { latitude: raw.latitude, longitude: raw.longitude },
  };

  const loc = raw.location;
  if (loc) {
    const address: Address = {};
    if (loc.formatted_address) address.formatted = loc.formatted_address;
    if (loc.address) address.street = loc.address;
    if (loc.locality) address.city = loc.locality;
    if (loc.region) address.region = loc.region;
    if (loc.postcode) address.postalCode = loc.postcode;
    if (loc.country) {
      const cc = CountryCode.safeParse(loc.country.toUpperCase());
      if (cc.success) address.country = cc.data;
    }
    if (Object.keys(address).length > 0) place.address = address;
  }

  const contact: Contact = {};
  if (raw.tel) contact.phone = raw.tel;
  if (raw.website) contact.website = raw.website;
  if (Object.keys(contact).length > 0) place.contact = contact;

  // 역할 소싱(POI 전문): 평점(0~10→0~5)·가격대·사진(공개 CDN URL).
  const business: Business = {};
  if (typeof raw.rating === "number") business.rating = Math.max(0, Math.min(5, raw.rating / 2));
  if (typeof raw.price === "number") business.priceLevel = Math.max(0, Math.min(4, Math.round(raw.price)));
  if (typeof raw.popularity === "number") business.popularity = Math.max(0, Math.min(1, raw.popularity));
  const photos = (raw.photos ?? []).map(fsqPhotoUrl).filter((u): u is string => u !== null);
  if (photos.length > 0) business.photos = photos;
  if (Object.keys(business).length > 0) place.business = business;

  return place;
}

export function parseFsqPlaces(results: readonly FsqPlace[] | undefined): ProviderPlace[] {
  const out: ProviderPlace[] = [];
  for (const raw of results ?? []) {
    const p = parseFsqPlace(raw);
    if (p) out.push(p);
  }
  return out;
}
