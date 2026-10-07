import type { ProviderManifest } from "@geowirehq/schema";

/**
 * Google Maps Platform 공급자 선언 (BYOK).
 *
 * cost.perCall: Google 공식 SKU 단가(USD, 2024 기준) — 비용 추적의 첫 실데이터.
 *   - search: Text Search (New) $0.032
 *   - getPlace: Place Details (New) $0.017
 *   - geocode/reverseGeocode: Geocoding API $0.005
 *
 * policy: `maxCacheTtlSeconds: null` → 원본 응답 캐시 금지(약관).
 *   `canStorePermanently: false` → 원본 저장 차단. 단 **place ID(providerPlaceId)와
 *   내부 ID는 예외적으로 영속 저장 가능**하다(Google Maps Platform 약관 §3.2.3(b):
 *   place ID는 무기한 저장·갱신 목적 보관 허용). GeoWire는 이 경계를 core에서 강제한다.
 *
 * autocomplete은 좌표 없는 예측만 반환해 `ProviderPlace`(location 필수) 계약과 맞지 않아
 * v0.1 capability에서 제외한다(Place Autocomplete → v0.2에서 별도 예측 모델 도입).
 */
export const GOOGLE_MANIFEST: ProviderManifest = {
  id: "google",
  name: "Google Maps Platform",
  capabilities: ["search", "geocode", "reverseGeocode", "getPlace", "route", "distanceMatrix"],
  authType: "apiKey",
  cost: {
    currency: "USD",
    perCall: {
      search: 0.032,
      getPlace: 0.017,
      geocode: 0.005,
      reverseGeocode: 0.005,
      // Routes API: Compute Routes(Basic) $0.005/route, Route Matrix $0.005/element(원점×목적지)
      route: 0.005,
      distanceMatrix: 0.005,
    },
  },
  // 리뷰·사진·평점·영업시간·전화가 Google의 권위 영역 (설계 §7.3 "영업시간은 Google").
  // business에 rating/reviews/photos/openingHours가 묶여 있어 최고 가중.
  fieldAuthority: { business: 10, contact: 7, address: 4 },
  policy: {
    maxCacheTtlSeconds: null,
    canStorePermanently: false,
  },
};
