import { GeoProviderError } from "@geowirehq/provider-sdk";
import type { GetPlaceRequest, Place } from "@geowirehq/schema";
import { parsePlaceRef } from "../ids.js";
import { makeContext, type ExecuteDeps } from "./execute.js";
import { toPlace } from "./to-place.js";
import { applyPolicy } from "./policy.js";
import type { PipelineHost } from "./pipeline.js";

/** get_place per-provider 타임아웃 (설계 §7.1) */
const DEFAULT_PROVIDER_TIMEOUT_MS = 3000;

/**
 * 단일 장소 상세 조회 (설계 §9.1 get_place).
 * `provider:providerPlaceId` 참조만 지원한다 — 내부 `gwp_` ID는 안정 해시라 역추적이
 * 불가능하므로 v0.1은 `null`을 돌려준다(호출자는 provider ref로 재조회).
 * 공급자 실패는 정규화된 `GeoProviderError`로 전파해 호출자(MCP/REST)가 사유를 노출하게 한다.
 */
export async function runGetPlace(
  host: PipelineHost,
  req: GetPlaceRequest,
): Promise<Place | null> {
  const parsed = parsePlaceRef(req.id);
  if (parsed.kind !== "ref") return null;

  const rp = host.registry.get(parsed.ref.provider);
  if (!rp || !rp.enabled) return null;
  const fn = rp.provider.getPlace;
  if (typeof fn !== "function") return null;

  const deps: ExecuteDeps = {
    logger: host.logger,
    now: host.now,
    baseFetch: host.baseFetch,
    breaker: host.circuitBreaker,
  };
  const ctx = makeContext(deps, req.options?.timeoutMs ?? DEFAULT_PROVIDER_TIMEOUT_MS);

  let pp;
  try {
    pp = await fn.call(rp.provider, { id: parsed.ref.providerPlaceId, options: req.options }, ctx);
  } catch (err) {
    if (err instanceof GeoProviderError) {
      host.circuitBreaker.recordFailure(rp.id, err.code);
      throw err;
    }
    throw new GeoProviderError("PROVIDER_UNAVAILABLE", `${rp.id}: ${String(err)}`, {
      provider: rp.id,
      cause: err,
    });
  }
  host.circuitBreaker.recordSuccess(rp.id);
  if (!pp) return null;

  const place = toPlace(pp, rp.id, host.now());
  applyPolicy([place], host.registry, host.config.cache.defaultTtlSeconds);
  return place;
}
