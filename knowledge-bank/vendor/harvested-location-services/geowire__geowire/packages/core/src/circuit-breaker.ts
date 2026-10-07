import type { Clock } from "@geowirehq/provider-sdk";
import type { ProviderErrorCode } from "@geowirehq/schema";

export interface CircuitBreakerOptions {
  /** 연속 실패 임계값 — 도달 시 회로 open. 기본 5 */
  failureThreshold?: number;
  /** open 유지 시간(ms). 경과 후 재시도 허용. 기본 30_000 */
  cooldownMs?: number;
  now?: Clock;
}

/**
 * 이번 요청만의 문제(요청·설정 오류)는 회로를 열지 않는다 — 반복 회피 대상이 아니다.
 * 공급자 자체의 지속적 장애(타임아웃·불가·한도·인증)만 카운트한다.
 */
const COUNTED_FAILURES = new Set<ProviderErrorCode>([
  "TIMEOUT",
  "PROVIDER_UNAVAILABLE",
  "RATE_LIMITED",
  "QUOTA_EXCEEDED",
  "AUTH_FAILED",
]);

interface State {
  consecutiveFailures: number;
  openUntilMs: number;
}

/**
 * 공급자별 서킷 브레이커 (설계 §7.1 Execute).
 * 연속 실패가 임계값에 도달하면 회로를 열어 cooldown 동안 해당 공급자를 호출에서 제외한다.
 * 성공하면 즉시 회로를 닫는다(연속 실패 리셋). 상태는 프로세스 메모리에 유지된다.
 */
export class CircuitBreaker {
  private readonly states = new Map<string, State>();
  private readonly threshold: number;
  private readonly cooldownMs: number;
  private readonly now: Clock;

  constructor(options: CircuitBreakerOptions = {}) {
    this.threshold = options.failureThreshold ?? 5;
    this.cooldownMs = options.cooldownMs ?? 30_000;
    this.now = options.now ?? Date.now;
  }

  /** 지금 이 공급자가 회로 open 상태(호출 제외)인지 */
  isOpen(providerId: string): boolean {
    const state = this.states.get(providerId);
    if (!state) return false;
    if (this.now() < state.openUntilMs) return true;
    return false;
  }

  recordSuccess(providerId: string): void {
    this.states.delete(providerId);
  }

  recordFailure(providerId: string, code: ProviderErrorCode): void {
    if (!COUNTED_FAILURES.has(code)) return;
    const state = this.states.get(providerId) ?? { consecutiveFailures: 0, openUntilMs: 0 };
    state.consecutiveFailures += 1;
    if (state.consecutiveFailures >= this.threshold) {
      state.openUntilMs = this.now() + this.cooldownMs;
    }
    this.states.set(providerId, state);
  }
}
