import type { ProviderManifest } from "@geowirehq/schema";

/**
 * Nominatim/OSM 공급자 선언. coverage 생략 = 글로벌.
 * policy: ODbL이므로 영속 저장 허용, 캐시 24h 상한, OSM attribution 필수.
 */
export const NOMINATIM_MANIFEST: ProviderManifest = {
  id: "nominatim",
  name: "Nominatim (OpenStreetMap)",
  capabilities: ["search", "geocode", "reverseGeocode"],
  authType: "none",
  // 기반 지도 데이터: 좌표·주소가 OSM의 권위 영역 (설계 §7.3 "좌표는 OSM").
  fieldAuthority: { location: 10, address: 8 },
  policy: {
    maxCacheTtlSeconds: 86_400,
    canStorePermanently: true,
    attributionRequired: "© OpenStreetMap contributors",
  },
  rateLimit: { requestsPerSecond: 1 },
};
