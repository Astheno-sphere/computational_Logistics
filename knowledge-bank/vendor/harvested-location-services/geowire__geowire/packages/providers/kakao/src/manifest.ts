import type { ProviderManifest } from "@geowirehq/schema";

/**
 * Kakao Local(카카오맵) 공급자 선언 (BYOK — REST API 키).
 * 한국(KR) 커버리지에 특화. Local API는 무료 쿼터 기반이라 cost는 생략(무료)한다.
 * policy: 카카오 약관상 원본 영속 저장은 보수적으로 금지, 캐시 24h 상한, 출처 표기.
 */
export const KAKAO_MANIFEST: ProviderManifest = {
  id: "kakao",
  name: "Kakao Local (카카오맵)",
  capabilities: ["search", "geocode", "reverseGeocode"],
  authType: "apiKey",
  coverage: ["KR"],
  // 국가별 보완: 한국 현지 상호·주소가 권위 영역.
  fieldAuthority: { name: 8, address: 7 },
  policy: {
    maxCacheTtlSeconds: 86_400,
    canStorePermanently: false,
    attributionRequired: "© Kakao",
  },
};
