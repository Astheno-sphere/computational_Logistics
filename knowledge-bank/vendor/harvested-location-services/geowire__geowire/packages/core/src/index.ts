// config
export {
  ProviderConfig,
  RankWeights,
  CountryRouting,
  RoutingConfig,
  BudgetConfig,
  CacheConfig,
  DedupConfig,
  GeoWireConfig,
  defaultConfig,
} from "./config/schema.js";
export {
  substituteEnv,
  substituteEnvInString,
  parseConfig,
  loadConfig,
  normalizeConfig,
} from "./config/load.js";
export type { EnvSubstitution } from "./config/load.js";
export { collectConfigWarnings } from "./config/warnings.js";
export type { ConfigWarning } from "./config/warnings.js";

// registry
export { ProviderRegistry } from "./registry.js";
export type { RegisteredProvider } from "./registry.js";

// ids
export { makePlaceId, parsePlaceRef } from "./ids.js";
export type { ProviderRef } from "./ids.js";

// geo + dedup + rank (공개 유틸)
export { haversineMeters } from "./geo.js";
export {
  normalizeName,
  jaroWinkler,
  pairScore,
  PAIR_WEIGHTS,
} from "./pipeline/dedup/similarity.js";
export { dedup } from "./pipeline/dedup/dedup.js";
export type { DedupOptions, DedupResult } from "./pipeline/dedup/dedup.js";
export {
  mergeCluster,
  DEFAULT_FIELD_STRENGTH,
} from "./pipeline/dedup/merge-fields.js";
export type { MergeContext } from "./pipeline/dedup/merge-fields.js";
export { rankScore, rankPlaces } from "./pipeline/rank.js";
export type { RankOptions } from "./pipeline/rank.js";

// cache
export type { CacheAdapter, CachedResponse } from "./cache/adapter.js";
export { MemoryCache, cacheKey } from "./cache/memory.js";
export type { MemoryCacheOptions } from "./cache/memory.js";

// cost + circuit breaker + policy
export {
  CostTracker,
  applyBudget,
  estimateCost,
  providerCallCost,
} from "./cost.js";
export type { BudgetDecision } from "./cost.js";
export { CircuitBreaker } from "./circuit-breaker.js";
export type { CircuitBreakerOptions } from "./circuit-breaker.js";
export { applyPolicy } from "./pipeline/policy.js";
export type { PolicyResult } from "./pipeline/policy.js";

// facade
export { GeoWire, createGeoWire } from "./geowire.js";
export type { CreateGeoWireOptions, ProviderInfo } from "./geowire.js";
