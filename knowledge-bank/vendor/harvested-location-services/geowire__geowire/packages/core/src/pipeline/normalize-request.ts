import type { CountryCode, LatLng, RequestOptions, Strategy } from "@geowirehq/schema";
import type { GeoWireConfig } from "../config/schema.js";

/**
 * 국가를 확정한다. 명시된 country가 우선.
 *
 * near 좌표 → 국가 역추론은 오프라인 국가 경계 데이터가 필요해 v0.1 범위 밖이다.
 * (설계 §7.2 Normalize의 "국가 추론"은 v0.3 국가별 라우팅과 함께 도입.)
 * 지금은 명시 country만 라우팅에 반영하고, near는 거리 계산·provider 전달에만 쓴다.
 */
export function resolveCountry(
  explicit: CountryCode | undefined,
  _near: LatLng | undefined,
): CountryCode | undefined {
  return explicit;
}

/**
 * 전략을 확정한다: 요청 옵션 > 국가별 라우팅 > 전역 기본값 (설계 §7.2·§8.1).
 */
export function resolveStrategy(
  config: GeoWireConfig,
  options: RequestOptions | undefined,
  country: CountryCode | undefined,
): Strategy {
  if (options?.strategy) return options.strategy;
  if (country) {
    const countryStrategy = config.routing.countries[country]?.strategy;
    if (countryStrategy) return countryStrategy;
  }
  return config.routing.defaultStrategy;
}
