import { GeoProviderError } from "@geowirehq/provider-sdk";
import type {
  RouteRequest,
  DistanceMatrixRequest,
  DemographicsRequest,
  Route,
  DistanceMatrix,
  DemographicProfile,
  ResponseMeta,
  ProviderUsage,
  ProviderSkip,
} from "@geowirehq/schema";
import { makeContext, type ExecuteDeps } from "./execute.js";
import { providerCallCost } from "../cost.js";
import type { PipelineHost } from "./pipeline.js";
import type { RegisteredProvider } from "../registry.js";

/** 라우팅 per-provider 타임아웃 — 경로/행렬은 검색보다 여유(원거리 계산) */
const DEFAULT_PROVIDER_TIMEOUT_MS = 5000;

interface Dispatch {
  used: ProviderUsage[];
  skipped: ProviderSkip[];
  failed: ProviderSkip[];
  estimatedCostUSD: number;
  attributions: string[];
}

/**
 * 라우팅 계열 공통 first-success 실행기. 첫 non-empty 결과의 provider에서 멈춘다.
 * **비용 오름차순**으로 시도한다 — 무키 OSRM을 먼저, 유료(Google)는 무료가 답 못 할 때만
 * (GeoWire 비용 거버넌스: 키를 넣었다고 라우팅까지 자동 과금하지 않는다).
 * `providers` allowlist가 주어지면 그 공급자만 사용한다(예: 강제로 Google 라우팅).
 */
async function firstSuccess<T>(
  host: PipelineHost,
  capability: "route" | "distanceMatrix" | "demographics",
  timeoutMs: number,
  providers: string[] | undefined,
  call: (rp: RegisteredProvider, ctx: ReturnType<typeof makeContext>) => Promise<T | null>,
): Promise<{ result: T | null; meta: ResponseMeta }> {
  const deps: ExecuteDeps = {
    logger: host.logger,
    now: host.now,
    baseFetch: host.baseFetch,
    breaker: host.circuitBreaker,
  };
  const ctx = makeContext(deps, timeoutMs);
  const d: Dispatch = { used: [], skipped: [], failed: [], estimatedCostUSD: 0, attributions: [] };

  const allow = providers && providers.length > 0 ? new Set(providers) : undefined;
  const candidates = host.registry
    .supporting(capability)
    .filter((rp) => !allow || allow.has(rp.id))
    .sort(
      (a, b) =>
        providerCallCost(a.id, capability, host.registry) -
        providerCallCost(b.id, capability, host.registry),
    );

  let result: T | null = null;
  for (const rp of candidates) {
    const start = host.now();
    try {
      const out = await call(rp, ctx);
      const latencyMs = host.now() - start;
      if (out == null) {
        d.used.push({ provider: rp.id, resultCount: 0, latencyMs });
        continue;
      }
      host.circuitBreaker.recordSuccess(rp.id);
      d.used.push({ provider: rp.id, resultCount: 1, latencyMs });
      d.estimatedCostUSD += providerCallCost(rp.id, capability, host.registry);
      const attr = rp.provider.manifest.policy.attributionRequired;
      if (attr) d.attributions.push(attr);
      result = out;
      break; // first-success
    } catch (err) {
      const code =
        err instanceof GeoProviderError ? err.code : "PROVIDER_UNAVAILABLE";
      if (err instanceof GeoProviderError) host.circuitBreaker.recordFailure(rp.id, err.code);
      d.failed.push({ provider: rp.id, reason: code });
    }
  }

  const meta: ResponseMeta = {
    providersUsed: d.used,
    providersSkipped: d.skipped,
    providersFailed: d.failed,
    strategy: "first-success",
    attributions: [...new Set(d.attributions)],
  };
  if (d.estimatedCostUSD > 0) meta.estimatedCostUSD = d.estimatedCostUSD;
  return { result, meta };
}

/** 길찾기 실행 (설계: routing/v1). route capable 공급자를 우선순위로 first-success. */
export async function runRoute(
  host: PipelineHost,
  req: RouteRequest,
): Promise<{ routes: Route[]; meta: ResponseMeta }> {
  const timeoutMs = req.options?.timeoutMs ?? DEFAULT_PROVIDER_TIMEOUT_MS;
  const { result, meta } = await firstSuccess<Route[]>(
    host,
    "route",
    timeoutMs,
    req.options?.providers,
    async (rp, ctx) => {
      const fn = rp.provider.route;
      if (typeof fn !== "function") return null;
      const routes = await fn.call(rp.provider, req, ctx);
      if (!routes || routes.length === 0) return null;
      const attr = rp.provider.manifest.policy.attributionRequired;
      return routes.map((r) => ({
        ...r,
        provider: rp.id,
        attributions: attr ? [attr] : [],
      }));
    },
  );
  return { routes: result ?? [], meta };
}

/** 거리 행렬 실행. distanceMatrix capable 공급자를 우선순위로 first-success. */
export async function runDistanceMatrix(
  host: PipelineHost,
  req: DistanceMatrixRequest,
): Promise<{ matrix: DistanceMatrix | null; meta: ResponseMeta }> {
  const timeoutMs = req.options?.timeoutMs ?? DEFAULT_PROVIDER_TIMEOUT_MS;
  const { result, meta } = await firstSuccess<DistanceMatrix>(
    host,
    "distanceMatrix",
    timeoutMs,
    req.options?.providers,
    async (rp, ctx) => {
      const fn = rp.provider.distanceMatrix;
      if (typeof fn !== "function") return null;
      const m = await fn.call(rp.provider, req, ctx);
      if (!m) return null;
      const attr = rp.provider.manifest.policy.attributionRequired;
      return { ...m, provider: rp.id, attributions: attr ? [attr] : [] };
    },
  );
  return { matrix: result, meta };
}

/** 인구통계 실행. demographics capable 공급자를 first-success로(지역 커버 못 하면 다음). */
export async function runDemographics(
  host: PipelineHost,
  req: DemographicsRequest,
): Promise<{ profile: DemographicProfile | null; meta: ResponseMeta }> {
  const timeoutMs = req.options?.timeoutMs ?? DEFAULT_PROVIDER_TIMEOUT_MS;
  const { result, meta } = await firstSuccess<DemographicProfile>(
    host,
    "demographics",
    timeoutMs,
    req.options?.providers,
    async (rp, ctx) => {
      const fn = rp.provider.demographics;
      if (typeof fn !== "function") return null;
      const p = await fn.call(rp.provider, req, ctx);
      if (!p) return null;
      const attr = rp.provider.manifest.policy.attributionRequired;
      return { ...p, attributions: attr ? [attr] : [] };
    },
  );
  return { profile: result, meta };
}
