import { z } from "zod";
import { CountryCode, Strategy } from "@geowirehq/schema";

/**
 * 개별 공급자 설정 (설계 §8.1).
 * 알려지지 않은 키(apiKey·source·baseUrl 등 공급자별 옵션)는 통과시킨다 — 이 값들은
 * provider 인스턴스를 만드는 팩토리(CLI/server) 레이어가 사용하고, core registry는
 * `enabled`·`priority`만 해석한다. core는 이미 생성된 provider 인스턴스를 주입받으므로
 * 자격증명은 provider 내부에 캡슐화되어 있고, 없을 때의 skip은 실행 시점 `MISSING_CREDENTIALS`로 처리된다.
 */
export const ProviderConfig = z.looseObject({
  /** 이 공급자를 활성화할지. 기본 true */
  enabled: z.boolean().default(true),
  /** 라우팅·랭킹 우선순위 (높을수록 우선). 고객 자체 데이터(internal)는 100 권장 */
  priority: z.number().int().optional(),
});
export type ProviderConfig = z.infer<typeof ProviderConfig>;

/** 랭킹 가중치 (설계 §7.4). 합이 100일 필요는 없다 — 상대 비율만 의미 있음 */
export const RankWeights = z.object({
  distance: z.number().nonnegative().default(40),
  openingHours: z.number().nonnegative().default(25),
  providerConfidence: z.number().nonnegative().default(20),
  freshness: z.number().nonnegative().default(15),
});
export type RankWeights = z.infer<typeof RankWeights>;

/** 국가별 라우팅 오버라이드 */
export const CountryRouting = z.object({
  /** 이 국가에서 사용할 공급자 순서(우선순위). 비면 전역 순서 */
  providers: z.array(z.string()).optional(),
  strategy: Strategy.optional(),
});
export type CountryRouting = z.infer<typeof CountryRouting>;

/** `weighted` 전략의 공급자 순서 결정 가중치 (합이 1일 필요는 없음, 상대 비율로만 사용) */
export const ProviderWeights = z.object({
  /** 높은 priority 선호 */
  priority: z.number().nonnegative().default(0.5),
  /** 저비용(무료) 선호 */
  cost: z.number().nonnegative().default(0.3),
  /** 요청 국가를 커버하는 공급자 선호 */
  coverage: z.number().nonnegative().default(0.2),
});
export type ProviderWeights = z.infer<typeof ProviderWeights>;

export const RoutingConfig = z.object({
  defaultStrategy: Strategy.default("first-success"),
  /** ISO 3166-1 alpha-2 → 라우팅 오버라이드 */
  countries: z.record(CountryCode, CountryRouting).default({}),
  rank: RankWeights.prefault({}),
  /** `weighted` 전략의 공급자 순서 가중치 */
  providerWeights: ProviderWeights.prefault({}),
});
export type RoutingConfig = z.infer<typeof RoutingConfig>;

export const BudgetConfig = z.object({
  monthlyUSD: z.number().nonnegative().optional(),
  perRequestMaxUSD: z.number().nonnegative().optional(),
});
export type BudgetConfig = z.infer<typeof BudgetConfig>;

/** 캐시 설정. v0.1은 memory만 실제 구현 — redis는 v0.2(스키마가 미구현을 광고하지 않는다) */
export const CacheConfig = z.object({
  adapter: z.literal("memory").default("memory"),
  /** 항목 최대 개수 (LRU 방출 기준). 기본 1000 */
  maxEntries: z.number().int().positive().default(1000),
  /** provider policy 상한 아래에서 쓰는 기본 TTL(초). 기본 3600 */
  defaultTtlSeconds: z.number().int().nonnegative().default(3600),
});
export type CacheConfig = z.infer<typeof CacheConfig>;

/** 중복 제거 임계값 (설계 §7.3) */
export const DedupConfig = z.object({
  /** 이 점수 이상이면 병합 */
  mergeThreshold: z.number().min(0).max(1).default(0.75),
  /** [possibleThreshold, mergeThreshold) 구간은 병합하지 않고 표기만 (v0.2 possibleDuplicates) */
  possibleThreshold: z.number().min(0).max(1).default(0.6),
});
export type DedupConfig = z.infer<typeof DedupConfig>;

/**
 * GeoWire 통합 설정 스키마 (설계 §8.1).
 * **모든 필드에 기본값이 있어 `GeoWireConfig.parse({})`가 성공한다 — Zero-config(P1)의 근간.**
 */
export const GeoWireConfig = z.object({
  providers: z.record(z.string(), ProviderConfig).default({}),
  routing: RoutingConfig.prefault({}),
  budget: BudgetConfig.prefault({}),
  cache: CacheConfig.prefault({}),
  dedup: DedupConfig.prefault({}),
});
export type GeoWireConfig = z.infer<typeof GeoWireConfig>;

/** 설정 없이도 완전히 유효한 기본 config를 만든다 (Zero-config 경로) */
export function defaultConfig(): GeoWireConfig {
  return GeoWireConfig.parse({});
}
