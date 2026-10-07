import type { LatLng, SearchPlacesRequest } from "@geowirehq/schema";
import type { ProviderPlace } from "@geowirehq/provider-sdk";

const EARTH_RADIUS_M = 6_371_000;
const toRad = (d: number): number => (d * Math.PI) / 180;

/** 대권 거리(m) — 반경 필터·거리 정렬용 (core에 의존하지 않도록 자체 구현) */
export function haversineMeters(a: LatLng, b: LatLng): number {
  const dLat = toRad(b.latitude - a.latitude);
  const dLon = toRad(b.longitude - a.longitude);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.sin(dLon / 2) ** 2 * Math.cos(toRad(a.latitude)) * Math.cos(toRad(b.latitude));
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** 헤더 별칭 → 표준 필드. 여러 표기를 허용해 고객 CSV 스키마 편차를 흡수한다 */
const FIELD_ALIASES: Record<string, string[]> = {
  id: ["store_id", "id", "store_no", "code"],
  name: ["name", "store_name", "title"],
  address: ["address", "addr", "full_address"],
  phone: ["phone", "tel", "telephone", "phone_number"],
  website: ["website", "url", "homepage"],
  lat: ["latitude", "lat"],
  lon: ["longitude", "lon", "lng", "long"],
  hours: ["opening_hours", "hours", "opening", "open_hours"],
  categories: ["category", "categories", "type", "types"],
};

function pick(record: Record<string, string>, field: string): string | undefined {
  for (const alias of FIELD_ALIASES[field] ?? []) {
    const value = record[alias];
    if (value != null && value !== "") return value;
  }
  return undefined;
}

/** 이름 비교용 정규화 (부분일치 대소문자·유니코드 무시) */
function normalize(text: string): string {
  return text.normalize("NFKC").toLowerCase().trim();
}

/** CSV 레코드 하나를 ProviderPlace로. 좌표·이름 없으면 null */
export function recordToPlace(record: Record<string, string>, index: number): ProviderPlace | null {
  const name = pick(record, "name");
  if (!name) return null;
  const latitude = Number(pick(record, "lat"));
  const longitude = Number(pick(record, "lon"));
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  // WGS84 유효 범위 밖(예: 오타로 lat=200)은 버린다 — 거리 계산·viewbox 오염 방지.
  if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return null;

  const categoriesRaw = pick(record, "categories");
  const place: ProviderPlace = {
    providerPlaceId: pick(record, "id") ?? `row-${index}`,
    name,
    categories: categoriesRaw
      ? categoriesRaw.split(/[,;|]/).map((c) => c.trim()).filter(Boolean)
      : [],
    location: { latitude, longitude },
    confidence: 1, // 고객이 직접 관리하는 데이터 — 최고 신뢰
  };

  const address = pick(record, "address");
  if (address) place.address = { formatted: address };

  const phone = pick(record, "phone");
  const website = pick(record, "website");
  if (phone || website) {
    place.contact = {};
    if (phone) place.contact.phone = phone;
    if (website) place.contact.website = website;
  }

  const hours = pick(record, "hours");
  if (hours) place.business = { openingHours: hours };

  return place;
}

/**
 * 고객 매장을 메모리에 색인하고 이름 부분일치 + 반경 검색을 제공한다 (설계 §5 internal).
 * v0.1은 선형 스캔(수천 건 규모 가정). PostgreSQL/PostGIS 백엔드는 v0.3.
 */
export class StoreIndex {
  readonly places: ProviderPlace[];

  constructor(records: Record<string, string>[]) {
    this.places = records
      .map((r, i) => recordToPlace(r, i))
      .filter((p): p is ProviderPlace => p != null);
  }

  search(req: SearchPlacesRequest): ProviderPlace[] {
    const q = normalize(req.query);
    const wantCategories = req.categories?.length ? new Set(req.categories) : undefined;

    let matched = this.places.filter((p) => {
      if (!normalize(p.name).includes(q)) return false;
      if (wantCategories && !p.categories.some((c) => wantCategories.has(c))) return false;
      return true;
    });

    // 반경 필터 + 거리 계산 (near가 있을 때)
    if (req.near) {
      const near = req.near;
      matched = matched
        .map((p) => ({ ...p, distanceMeters: haversineMeters(near, p.location) }))
        .filter((p) => req.radiusMeters == null || p.distanceMeters <= req.radiusMeters)
        .sort((a, b) => a.distanceMeters - b.distanceMeters);
    }

    return matched.slice(0, req.limit ?? 10);
  }
}
