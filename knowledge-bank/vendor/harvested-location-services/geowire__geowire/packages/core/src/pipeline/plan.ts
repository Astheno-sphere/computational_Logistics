import type { Capability, CountryCode } from "@geowirehq/schema";
import type { GeoWireConfig, ProviderWeights } from "../config/schema.js";
import type { ProviderRegistry } from "../registry.js";
import { providerCallCost } from "../cost.js";
import { resolveStrategy } from "./normalize-request.js";
import type { OperationPlan, OperationSpec } from "./types.js";

/**
 * 주어진 순서 목록으로 후보를 필터·재정렬한다.
 * `order`에 있고 `available`에도 있는 것만, `order`의 순서대로.
 */
function reorderBy(available: string[], order: string[]): string[] {
  const set = new Set(available);
  return order.filter((id) => set.has(id));
}

/**
 * `cost-aware`: 호출 비용 오름차순(무료 먼저) 정렬. 동률은 priority 높은 순.
 * first-success와 결합하면 유료 공급자는 무료가 결과를 못 낼 때만 호출된다.
 */
function orderByCost(ids: string[], registry: ProviderRegistry, capability: Capability): string[] {
  return [...ids].sort((a, b) => {
    const ca = providerCallCost(a, capability, registry);
    const cb = providerCallCost(b, capability, registry);
    if (ca !== cb) return ca - cb;
    return (registry.get(b)?.priority ?? 0) - (registry.get(a)?.priority ?? 0);
  });
}

/**
 * `weighted`: priority·저비용·커버리지 일치를 가중합한 점수 내림차순 정렬.
 * 요청 국가를 커버하는 공급자(예: KR → Kakao/Naver)에 가점 → 국가 맞춤 라우팅.
 */
function orderByWeight(
  ids: string[],
  registry: ProviderRegistry,
  capability: Capability,
  country: CountryCode | undefined,
  w: ProviderWeights,
): string[] {
  const maxCost = Math.max(
    ...ids.map((id) => providerCallCost(id, capability, registry)),
    Number.EPSILON,
  );
  const maxPriority = Math.max(...ids.map((id) => registry.get(id)?.priority ?? 0), 1);
  const score = (id: string): number => {
    const rp = registry.get(id);
    const priorityNorm = (rp?.priority ?? 0) / maxPriority;
    const cheapNorm = 1 - providerCallCost(id, capability, registry) / maxCost;
    const coverage = rp?.provider.manifest.coverage;
    const coverageMatch = !country
      ? 0.5
      : !coverage || coverage.length === 0
        ? 0.5 // 글로벌 공급자는 중립
        : coverage.includes(country)
          ? 1
          : 0;
    return w.priority * priorityNorm + w.cost * cheapNorm + w.coverage * coverageMatch;
  };
  // 안정 정렬: 점수 동률은 입력(=priority) 순서 유지
  return ids
    .map((id, i) => ({ id, i, s: score(id) }))
    .sort((a, b) => b.s - a.s || a.i - b.i)
    .map((x) => x.id);
}

/**
 * 호출 계획을 세운다 (설계 §7.1 Plan):
 * capability 지원 → 국가별 라우팅 순서 → 요청 단위 provider 제한 → 전략 확정.
 *
 * 자격증명·예산 필터는 여기서 사전 제외하지 않는다 — 자격증명은 실행 시 `MISSING_CREDENTIALS`로,
 * 예산은 execute 직전 cost 게이트(M4)로 처리해 meta에 정확히 기록한다.
 */
export function planOperation(
  registry: ProviderRegistry,
  config: GeoWireConfig,
  spec: OperationSpec,
): OperationPlan {
  // 1. capability 지원 활성 provider (priority 정렬됨)
  let ids = registry.supporting(spec.capability).map((r) => r.id);

  // 2. 국가별 라우팅 순서 오버라이드
  if (spec.country) {
    const routed = config.routing.countries[spec.country]?.providers;
    if (routed && routed.length > 0) ids = reorderBy(ids, routed);
  }

  // 3. 요청 단위 provider 제한 (options.providers)
  const requested = spec.options?.providers;
  if (requested && requested.length > 0) ids = reorderBy(ids, requested);

  // 4. 전략별 순서 재정렬 (cost-aware/weighted). 실행은 first-success로 수렴한다.
  const strategy = resolveStrategy(config, spec.options, spec.country);
  if (strategy === "cost-aware") {
    ids = orderByCost(ids, registry, spec.capability);
  } else if (strategy === "weighted") {
    ids = orderByWeight(ids, registry, spec.capability, spec.country, config.routing.providerWeights);
  }

  return { strategy, providerIds: ids };
}
