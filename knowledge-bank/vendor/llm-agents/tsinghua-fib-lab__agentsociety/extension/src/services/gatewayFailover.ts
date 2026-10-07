import type { AiCliGatewayUpstream } from './aiCliGatewayUpstream';

export const FAILOVER_FAILURE_THRESHOLD = 3;
export const FAILOVER_COOLDOWN_MS = 60_000;
export const FAILOVER_MAX_ATTEMPTS = 6;

export type CircuitBreakerState = {
  consecutiveFailures: number;
  openUntil: number;
};

export function shouldFailoverHttpStatus(status: number): boolean {
  return status === 0 || status === 408 || status === 429 || status >= 500;
}

export function isCircuitOpen(state: CircuitBreakerState | undefined, now = Date.now()): boolean {
  if (!state) {
    return false;
  }
  if (state.openUntil > now) {
    return true;
  }
  return false;
}

export function recordUpstreamFailure(
  map: Map<string, CircuitBreakerState>,
  baseUrl: string,
  now = Date.now()
): void {
  const key = baseUrl.trim();
  const prev = map.get(key) ?? { consecutiveFailures: 0, openUntil: 0 };
  const consecutiveFailures = prev.consecutiveFailures + 1;
  const openUntil =
    consecutiveFailures >= FAILOVER_FAILURE_THRESHOLD
      ? now + FAILOVER_COOLDOWN_MS
      : prev.openUntil;
  map.set(key, { consecutiveFailures, openUntil });
}

export function recordUpstreamSuccess(map: Map<string, CircuitBreakerState>, baseUrl: string): void {
  map.delete(baseUrl.trim());
}

export type CircuitBreakerHealth = 'healthy' | 'degraded' | 'unhealthy';

export function upstreamHealth(state: CircuitBreakerState | undefined): CircuitBreakerHealth {
  if (!state || state.consecutiveFailures === 0) {
    return 'healthy';
  }
  if (state.consecutiveFailures >= FAILOVER_FAILURE_THRESHOLD) {
    return 'unhealthy';
  }
  return 'degraded';
}

export function buildFailoverUpstreamOrder(
  upstreams: AiCliGatewayUpstream[],
  activeBaseUrl: string
): AiCliGatewayUpstream[] {
  const active = activeBaseUrl.trim();
  const seen = new Set<string>();
  const ordered: AiCliGatewayUpstream[] = [];
  for (const u of upstreams) {
    const key = `${u.baseUrl.trim()}|${u.apiKey.trim()}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    if (u.baseUrl.trim() === active) {
      ordered.unshift(u);
    } else {
      ordered.push(u);
    }
  }
  if (ordered.length === 0 && upstreams.length > 0) {
    return upstreams;
  }
  return ordered;
}
