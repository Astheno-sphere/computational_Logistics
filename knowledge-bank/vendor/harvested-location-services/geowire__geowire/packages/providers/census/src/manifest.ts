import type { ProviderManifest } from "@geowirehq/schema";

/**
 * US Census Bureau 공급자 선언 (BYOK — 무료 API 키).
 * 좌표 → Census Geocoder(무키)로 tract 해석 → ACS 5년 추정치(키 필요) 조회.
 * coverage US. 공공데이터라 영속 저장 허용, 캐시는 길게(연 단위로 안정).
 * 무료 키 발급: https://api.census.gov/data/key_signup.html
 */
export const CENSUS_MANIFEST: ProviderManifest = {
  id: "census",
  name: "US Census Bureau (ACS)",
  capabilities: ["demographics"],
  authType: "apiKey",
  coverage: ["US"],
  policy: {
    maxCacheTtlSeconds: 2_592_000, // 30일 — ACS는 연 단위 갱신이라 길게 캐시 가능
    canStorePermanently: true,
    attributionRequired: "Source: U.S. Census Bureau, American Community Survey (ACS)",
  },
};
