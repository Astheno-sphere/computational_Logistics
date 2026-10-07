import type { ProviderManifest } from "@geowirehq/schema";

/**
 * Baidu Maps(百度地图) 공급자 선언 (BYOK — Web 서비스 AK).
 * 중국(CN) 커버리지 특화. Web 서비스 API는 쿼터 기반(무료 등급 존재)이라 cost는 생략.
 * 좌표는 BD-09로 오지만 core에는 WGS84로 변환해 전달한다(coords.ts).
 * policy: 원본 영속 저장 금지(약관 보수적 적용), 캐시 24h 상한, 출처 표기.
 */
export const BAIDU_MANIFEST: ProviderManifest = {
  id: "baidu",
  name: "Baidu Maps (百度地图)",
  capabilities: ["search", "geocode", "reverseGeocode"],
  authType: "apiKey",
  coverage: ["CN"],
  // 국가별 보완: 중국 현지 상호·주소가 권위 영역.
  fieldAuthority: { name: 8, address: 7 },
  policy: {
    maxCacheTtlSeconds: 86_400,
    canStorePermanently: false,
    attributionRequired: "© Baidu",
  },
};
