import type { Capability } from "@geowirehq/schema";
import type { ProviderRegistry } from "./registry.js";
import type { BudgetConfig } from "./config/schema.js";

/** provider가 이 capability 1회 호출에 청구하는 예상 비용(USD). 없으면 0(무료) */
export function providerCallCost(
  providerId: string,
  capability: Capability,
  registry: ProviderRegistry,
): number {
  const cost = registry.get(providerId)?.provider.manifest.cost;
  return cost?.perCall[capability] ?? 0;
}

/** 여러 provider의 이 capability 호출 비용 합 */
export function estimateCost(
  providerIds: readonly string[],
  capability: Capability,
  registry: ProviderRegistry,
): number {
  return providerIds.reduce((sum, id) => sum + providerCallCost(id, capability, registry), 0);
}

export interface BudgetDecision {
  /** 예산 내에서 호출 허용된 provider (원래 순서 유지) */
  allowed: string[];
  /** 예산 초과로 제외된 provider (meta.providersSkipped → QUOTA_EXCEEDED) */
  skipped: string[];
}

/**
 * 이번 달 누적 유료 API 비용을 추적한다 (설계 §8.3).
 * v0.1은 프로세스 메모리 카운터 — Redis 공유 카운터·월 롤오버는 v0.2.
 * ⚠️ 알려진 한계: 예산 체크(applyBudget)와 record 사이 async 인터리브로 동시 요청이
 * 월 상한을 소폭 초과할 수 있다(낙관적 추적). 원자적 예약/차감은 v0.2 Redis에서 해결.
 */
export class CostTracker {
  private spent = 0;

  /** 이번 달 누적 사용액(USD) */
  get monthlyUSD(): number {
    return this.spent;
  }

  /** 실제 사용한 비용을 누적 기록 */
  record(usd: number): void {
    this.spent += usd;
  }

  reset(): void {
    this.spent = 0;
  }
}

/**
 * 예산 게이트 (설계 §8.3): 유료 공급자가 요청당/월간 예산을 초과하면 제외하고 무료로 폴백한다.
 * 우선순위 순서로 누적 비용을 더하며, 초과를 유발하는 유료 공급자만 QUOTA_EXCEEDED로 제외한다.
 * 무료(cost 0) 공급자는 항상 허용된다 — zero-config(nominatim) 경로를 예산이 막지 않도록.
 */
export function applyBudget(
  providerIds: readonly string[],
  capability: Capability,
  registry: ProviderRegistry,
  budget: BudgetConfig,
  tracker: CostTracker,
  /** 요청별 상한(RequestOptions.maxCostUSD). config 상한과 함께 더 낮은 값이 적용된다 */
  requestMaxUSD?: number,
): BudgetDecision {
  const allowed: string[] = [];
  const skipped: string[] = [];
  let requestCost = 0;

  // config.perRequestMaxUSD와 요청별 options.maxCostUSD 중 더 엄격한(작은) 값을 적용
  const perRequestCaps = [budget.perRequestMaxUSD, requestMaxUSD].filter(
    (v): v is number => v != null,
  );
  const perRequestCap = perRequestCaps.length > 0 ? Math.min(...perRequestCaps) : null;

  for (const id of providerIds) {
    const cost = providerCallCost(id, capability, registry);
    if (cost === 0) {
      allowed.push(id);
      continue;
    }
    const overPerRequest = perRequestCap != null && requestCost + cost > perRequestCap;
    const overMonthly =
      budget.monthlyUSD != null && tracker.monthlyUSD + requestCost + cost > budget.monthlyUSD;
    if (overPerRequest || overMonthly) {
      skipped.push(id);
    } else {
      allowed.push(id);
      requestCost += cost;
    }
  }

  return { allowed, skipped };
}
