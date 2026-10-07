import type { Logger, Clock, FetchFn } from "@geowirehq/provider-sdk";
import type {
  Place,
  ProviderErrorCode,
  ProviderSkip,
  ProviderUsage,
  ResponseMeta,
  Strategy,
} from "@geowirehq/schema";
import { formatAddress } from "@geowirehq/schema";
import type { GeoWireConfig } from "../config/schema.js";
import type { ProviderRegistry } from "../registry.js";
import type { CacheAdapter } from "../cache/adapter.js";
import { cacheKey } from "../cache/memory.js";
import { CostTracker, applyBudget, estimateCost } from "../cost.js";
import { CircuitBreaker } from "../circuit-breaker.js";
import { planOperation } from "./plan.js";
import { executeOperation, type ExecuteDeps } from "./execute.js";
import { toPlace } from "./to-place.js";
import { dedup } from "./dedup/dedup.js";
import { rankPlaces } from "./rank.js";
import { applyPolicy } from "./policy.js";
import type { OperationSpec, ProviderInvocation } from "./types.js";

/** 파이프라인이 필요로 하는 GeoWire 인스턴스 표면 (순환 import 회피용 최소 인터페이스) */
export interface PipelineHost {
  readonly registry: ProviderRegistry;
  readonly config: GeoWireConfig;
  readonly logger: Logger;
  readonly now: Clock;
  readonly baseFetch: FetchFn;
  readonly cache: CacheAdapter;
  readonly costTracker: CostTracker;
  readonly circuitBreaker: CircuitBreaker;
}

export interface OperationResult {
  results: Place[];
  meta: ResponseMeta;
}

/** 자격증명·구조적 사유 → skipped, 실행 중 실패 → failed (설계 §7.1·P8) */
const SKIP_CODES = new Set<ProviderErrorCode>(["MISSING_CREDENTIALS", "UNSUPPORTED_CAPABILITY"]);

interface Classified {
  used: ProviderUsage[];
  skipped: ProviderSkip[];
  failed: ProviderSkip[];
  places: Place[];
}

function classify(invocations: ProviderInvocation[], spec: OperationSpec, nowMs: number): Classified {
  const used: ProviderUsage[] = [];
  const skipped: ProviderSkip[] = [];
  const failed: ProviderSkip[] = [];
  const places: Place[] = [];

  for (const inv of invocations) {
    if (inv.ok) {
      used.push({ provider: inv.id, resultCount: inv.places.length, latencyMs: inv.latencyMs });
      for (const pp of inv.places) places.push(toPlace(pp, inv.id, nowMs, spec.near));
    } else if (inv.error) {
      const isSkip = inv.skipped || SKIP_CODES.has(inv.error.code);
      (isSkip ? skipped : failed).push({ provider: inv.id, reason: inv.error.code });
    }
  }
  return { used, skipped, failed, places };
}

/**
 * 하나의 연산(search/geocode/reverse)을 파이프라인 전 단계에 통과시킨다 (설계 §7·§8):
 * cache 조회 → plan → 예산 게이트 → execute(서킷) → normalize(Place) →
 * dedup(merge, §7.3) → **merge→policy→cache 순서 고정**(§8.2): rank → limit →
 * policy(attribution·TTL 상한) → cache 저장 → meta 조립.
 */
export async function runOperation(
  host: PipelineHost,
  spec: OperationSpec,
): Promise<OperationResult> {
  // 0. 캐시 조회 (정규화된 요청 해시)
  const key = cacheKey(spec.capability, spec.request);
  const cached = await host.cache.get(key);
  if (cached) {
    return {
      results: cached.results,
      meta: { ...cached.meta, cache: { hit: true, ttlSeconds: cached.ttlSeconds } },
    };
  }

  // 1. 계획
  const plan = planOperation(host.registry, host.config, spec);

  // 2. 예산 게이트 — 초과 유료 공급자를 QUOTA_EXCEEDED로 제외
  const budget = applyBudget(
    plan.providerIds,
    spec.capability,
    host.registry,
    host.config.budget,
    host.costTracker,
    spec.options?.maxCostUSD,
  );
  const budgetSkipped: ProviderSkip[] = budget.skipped.map((provider) => ({
    provider,
    reason: "QUOTA_EXCEEDED" as ProviderErrorCode,
  }));

  // 3. 실행 (서킷 브레이커 주입)
  const deps: ExecuteDeps = {
    logger: host.logger,
    now: host.now,
    baseFetch: host.baseFetch,
    breaker: host.circuitBreaker,
  };
  const invocations = await executeOperation(
    host.registry,
    { strategy: plan.strategy, providerIds: budget.allowed },
    spec,
    deps,
  );

  // 4. 정규화 + 분류
  const nowMs = host.now();
  const { used, skipped, failed, places } = classify(invocations, spec, nowMs);

  // 4b. 반경 하드 필터 — radiusMeters가 지정되면 near 기준 반경을 벗어난 결과를 제외한다.
  // 공급자의 위치 편향(bias)이 느슨해 반경 밖 결과가 새는 것을 계약 수준에서 막는다.
  // 좌표가 없어 거리 미상(distanceMeters == null)인 결과는 보존한다.
  const inRadius =
    spec.radiusMeters != null
      ? places.filter((p) => p.distanceMeters == null || p.distanceMeters <= spec.radiusMeters!)
      : places;

  // 5. dedup (merge 전략만)
  let working = inRadius;
  let dedupMeta: { before: number; after: number } | undefined;
  if (plan.strategy === "merge") {
    const res = dedup(inRadius, {
      mergeThreshold: host.config.dedup.mergeThreshold,
      providerRank: (id) => host.registry.get(id)?.priority ?? 0,
      // 역할 기반 필드 소싱: 각 공급자가 manifest에 선언한 필드 권위를 병합에 주입한다.
      fieldAuthority: (id, field) => {
        const authority = host.registry.get(id)?.provider.manifest.fieldAuthority;
        return authority ? (authority as Record<string, number>)[field] : undefined;
      },
    });
    working = res.merged;
    dedupMeta = { before: res.before, after: res.after };
  }

  // 6. rank → limit
  const ranked = rankPlaces(working, {
    weights: host.config.routing.rank,
    near: spec.near,
    nowMs,
  });
  const limited = spec.limit != null ? ranked.slice(0, spec.limit) : ranked;

  // 7. policy: attribution 주입 + 혼합 캐시 TTL 상한 (merge→policy→cache 순서)
  const policy = applyPolicy(limited, host.registry, host.config.cache.defaultTtlSeconds);

  // 7b. 표시 주소 통일: 구조화 필드로 공급자 무관 표준 formatted를 재생성한다
  // (OSM display_name vs Google formattedAddress처럼 스타일이 달라지는 것을 방지).
  // 구조화 필드가 빈약하면 formatAddress가 undefined → 공급자 원문 유지.
  const results = limited.map(standardizeAddress);

  // 8. 비용 집계 (실제 사용한 공급자 기준) + 사용량 누적
  const usedIds = used.map((u) => u.provider);
  const estimatedCostUSD = estimateCost(usedIds, spec.capability, host.registry);
  if (estimatedCostUSD > 0) host.costTracker.record(estimatedCostUSD);

  // 9. meta 조립
  const meta: ResponseMeta = {
    providersUsed: used,
    providersSkipped: [...skipped, ...budgetSkipped],
    providersFailed: failed,
    strategy: plan.strategy as Strategy,
    attributions: policy.attributions,
    cache: { hit: false },
  };
  if (dedupMeta) meta.dedup = dedupMeta;
  if (estimatedCostUSD > 0) meta.estimatedCostUSD = estimatedCostUSD;

  // 10. 캐시 저장 (policy 허용 + 성공 응답일 때만).
  // 아무 공급자도 성공하지 못한 응답(전부 실패/스킵)은 캐시하지 않는다 — 장애를 캐시에 굳히지 않도록.
  if (policy.cacheTtlSeconds != null && used.length > 0) {
    await host.cache.set(key, { results, meta, ttlSeconds: policy.cacheTtlSeconds });
  }

  return { results, meta };
}

/** Place의 address.formatted를 구조화 필드 기반 표준 형식으로 재생성한다(충분할 때만). */
function standardizeAddress(place: Place): Place {
  if (!place.address) return place;
  const std = formatAddress(place.address);
  if (std == null || std === place.address.formatted) return place;
  return { ...place, address: { ...place.address, formatted: std } };
}
