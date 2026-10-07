import type { ProviderManifest } from "@geowirehq/schema";

/**
 * OSRM(Open Source Routing Machine) 공급자 선언 — 길찾기·거리행렬의 무키 기본값.
 * 검색에 nominatim이 있듯, 라우팅엔 OSRM이 GeoWire의 "키 없이 동작" 기본이다.
 * coverage 생략 = 글로벌. OSM 데이터 기반이므로 ODbL attribution 필수.
 * ⚠️ 공개 데모 서버(router.project-osrm.org)는 `driving` 프로파일만·요청 레이트 제한 존재 —
 * 운영에선 self-host OSRM(baseUrl 오버라이드)을 권장한다.
 */
export const OSRM_MANIFEST: ProviderManifest = {
  id: "osrm",
  name: "OSRM (OpenStreetMap routing)",
  capabilities: ["route", "distanceMatrix"],
  authType: "none",
  policy: {
    maxCacheTtlSeconds: 86_400,
    canStorePermanently: true,
    attributionRequired: "© OpenStreetMap contributors (routing via OSRM)",
  },
  rateLimit: { requestsPerSecond: 1 },
};
