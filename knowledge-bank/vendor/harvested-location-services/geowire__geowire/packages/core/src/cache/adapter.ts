import type { Place, ResponseMeta } from "@geowirehq/schema";

/** 캐시에 저장되는 응답 스냅샷 (meta.cache는 조회 시점에 덧씌운다) */
export interface CachedResponse {
  results: Place[];
  meta: ResponseMeta;
  /** 저장 시 적용된 TTL(초) — 조회 시 meta.cache.ttlSeconds로 노출 */
  ttlSeconds: number;
}

/**
 * 캐시 어댑터 계약 (설계 §8.4 Temporary Cache).
 * v0.1은 memory 구현만 제공하며 redis 등은 이 인터페이스를 구현해 v0.2에서 추가한다.
 * TTL 상한은 Policy Engine이 계산해 넘긴다 — 어댑터는 만료만 담당한다.
 */
export interface CacheAdapter {
  get(key: string): Promise<CachedResponse | undefined>;
  set(key: string, value: CachedResponse): Promise<void>;
  delete(key: string): Promise<void>;
  clear(): Promise<void>;
}
