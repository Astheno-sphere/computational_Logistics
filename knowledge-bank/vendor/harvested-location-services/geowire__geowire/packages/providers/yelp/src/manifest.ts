import type { ProviderManifest } from "@geowirehq/schema";

/**
 * Yelp Fusion 공급자 선언 (BYOK — API 키, 무료 티어 존재).
 * 미국·서구권 비즈니스 데이터의 정본: 평점(0~5)·리뷰 수·가격대·카테고리가 강점.
 * capabilities: search + getPlace (POI 중심 API — 지오코딩/라우팅 없음).
 * 역할 소싱: business(평점·리뷰·가격)에 강한 권위. Google 다음, Foursquare보다 위.
 * policy: Yelp 콘텐츠는 표시용(영속 저장 금지·출처 표기 필수), 캐시 24h 상한.
 */
export const YELP_MANIFEST: ProviderManifest = {
  id: "yelp",
  name: "Yelp Fusion",
  capabilities: ["search", "getPlace"],
  authType: "apiKey",
  // Yelp 주요 시장(북미·서유럽·오세아니아). 가중 라우팅의 coverage 가점 근거.
  coverage: [
    "US", "CA", "GB", "IE", "AU", "NZ", "FR", "DE", "IT", "ES",
    "NL", "AT", "BE", "CH", "DK", "SE", "NO", "FI", "PL", "PT",
  ],
  fieldAuthority: { business: 8, contact: 5 },
  policy: {
    maxCacheTtlSeconds: 86_400,
    canStorePermanently: false,
    attributionRequired: "Powered by Yelp",
  },
};
