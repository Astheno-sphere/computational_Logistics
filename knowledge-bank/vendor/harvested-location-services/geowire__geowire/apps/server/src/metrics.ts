import { Registry, Counter, Histogram, collectDefaultMetrics } from "prom-client";
import type { ResponseMeta } from "@geowirehq/schema";

/**
 * Prometheus 메트릭 (설계 §8.3, §7 /metrics).
 * provider별 요청/지연/상태 + 누적 비용 + HTTP 요청 카운터를 노출한다.
 */
export interface Metrics {
  registry: Registry;
  /** 응답 meta에서 provider별 사용/실패/스킵·지연·비용을 기록 */
  recordMeta(meta: ResponseMeta): void;
  /** HTTP 요청 1건 기록 */
  recordHttp(method: string, route: string, status: number): void;
}

export function createMetrics(): Metrics {
  const registry = new Registry();
  collectDefaultMetrics({ register: registry });

  const providerRequests = new Counter({
    name: "geowire_provider_requests_total",
    help: "공급자 호출 결과 수 (status: used|failed|skipped)",
    labelNames: ["provider", "status"] as const,
    registers: [registry],
  });

  const providerLatency = new Histogram({
    name: "geowire_provider_latency_seconds",
    help: "공급자 호출 지연(초)",
    labelNames: ["provider"] as const,
    buckets: [0.05, 0.1, 0.25, 0.5, 1, 2, 5],
    registers: [registry],
  });

  const costTotal = new Counter({
    name: "geowire_cost_usd_total",
    help: "누적 예상 비용(USD)",
    registers: [registry],
  });

  const httpRequests = new Counter({
    name: "geowire_http_requests_total",
    help: "HTTP 요청 수",
    labelNames: ["method", "route", "status"] as const,
    registers: [registry],
  });

  return {
    registry,
    recordMeta(meta) {
      for (const u of meta.providersUsed) {
        providerRequests.inc({ provider: u.provider, status: "used" });
        providerLatency.observe({ provider: u.provider }, u.latencyMs / 1000);
      }
      for (const s of meta.providersFailed) {
        providerRequests.inc({ provider: s.provider, status: "failed" });
      }
      for (const s of meta.providersSkipped) {
        providerRequests.inc({ provider: s.provider, status: "skipped" });
      }
      if (meta.estimatedCostUSD) costTotal.inc(meta.estimatedCostUSD);
    },
    recordHttp(method, route, status) {
      httpRequests.inc({ method, route, status: String(status) });
    },
  };
}
