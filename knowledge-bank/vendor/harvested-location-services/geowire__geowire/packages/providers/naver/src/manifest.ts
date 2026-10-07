import type { ProviderManifest } from "@geowirehq/schema";

/**
 * Naver 지역검색(Local Search) 공급자 선언 (BYOK — Client ID + Secret).
 * 한국(KR) 커버리지. 지역검색 API는 무료(쿼터)라 cost 생략.
 * 한계: 좌표 바이어스(near)·반경 없이 전국 키워드 검색이며 최대 5건(display=5),
 * 리버스 지오코딩 미지원(별도 NCP Maps API 필요) → capabilities는 search·geocode만.
 * policy: 원본 영속 저장 보수적으로 금지, 캐시 24h 상한, NAVER 출처 표기.
 */
export const NAVER_MANIFEST: ProviderManifest = {
  id: "naver",
  name: "Naver Local Search (네이버 지역검색)",
  capabilities: ["search", "geocode"],
  authType: "apiKey",
  coverage: ["KR"],
  // 국가별 보완: 한국 현지 상호·주소가 권위 영역.
  fieldAuthority: { name: 8, address: 7 },
  policy: {
    maxCacheTtlSeconds: 86_400,
    canStorePermanently: false,
    attributionRequired: "© NAVER",
  },
};
