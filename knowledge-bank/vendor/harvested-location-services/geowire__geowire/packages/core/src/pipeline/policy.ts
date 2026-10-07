import type { Place } from "@geowirehq/schema";
import type { ProviderRegistry } from "../registry.js";

export interface PolicyResult {
  /** 결과 전체의 attribution 합집합 (meta.attributions) */
  attributions: string[];
  /** 캐시 허용 TTL(초). null = 캐시 금지 */
  cacheTtlSeconds: number | null;
}

/**
 * Policy Engine (설계 §8.2).
 * 병합이 끝난 결과(provenance 온전)에 대해:
 * 1. 기여한 모든 소스의 attribution을 각 Place와 전체 meta에 주입한다.
 * 2. **혼합 결과의 캐시 정책 = 가장 엄격한 소스 정책** (불변식):
 *    기여 소스 중 `maxCacheTtlSeconds=null`(캐시 금지)이 하나라도 있으면 전체 캐시 금지,
 *    아니면 기여 소스 상한들과 기본 TTL의 **최솟값**을 쓴다.
 *
 * canStorePermanently는 영속 저장(v0.3) 판단용이며 임시 캐시(v0.1)에는 관여하지 않는다.
 */
export function applyPolicy(
  places: Place[],
  registry: ProviderRegistry,
  defaultTtlSeconds: number,
): PolicyResult {
  const allAttributions = new Set<string>();
  const contributingProviders = new Set<string>();

  for (const place of places) {
    const placeAttrs = new Set<string>();
    for (const src of place.sources) {
      contributingProviders.add(src.provider);
      const attr = registry.get(src.provider)?.provider.manifest.policy.attributionRequired;
      if (attr) {
        placeAttrs.add(attr);
        allAttributions.add(attr);
      }
    }
    place.attributions = [...placeAttrs];
  }

  let cacheTtlSeconds: number | null = defaultTtlSeconds;
  for (const providerId of contributingProviders) {
    const policy = registry.get(providerId)?.provider.manifest.policy;
    if (!policy) continue;
    if (policy.maxCacheTtlSeconds === null) {
      cacheTtlSeconds = null; // 캐시 금지 소스가 하나라도 있으면 전체 금지
      break;
    }
    cacheTtlSeconds = Math.min(cacheTtlSeconds, policy.maxCacheTtlSeconds);
  }

  return { attributions: [...allAttributions], cacheTtlSeconds };
}
