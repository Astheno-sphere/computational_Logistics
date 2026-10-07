import { GeoProviderError } from "./errors.js";

/** provider에 노출되는 최소 로거 (core는 pino 등을 이 형태로 어댑트해 주입) */
export interface Logger {
  debug(message: string, ...args: unknown[]): void;
  info(message: string, ...args: unknown[]): void;
  warn(message: string, ...args: unknown[]): void;
  error(message: string, ...args: unknown[]): void;
}

/** 테스트에서 시간을 주입할 수 있도록 추상화한 시계 (epoch ms) */
export type Clock = () => number;

export type FetchFn = (url: string, init?: RequestInit) => Promise<Response>;

/**
 * provider 어댑터가 받는 실행 컨텍스트.
 * **provider는 인프라(재시도·타임아웃·시계)를 직접 만들지 않는다** — core가 주입한
 * 이 컨텍스트만 쓴다. 덕분에 어댑터를 200줄 수준으로 얇게 유지할 수 있다.
 */
export interface ProviderContext {
  /** 타임아웃 + 429/5xx 지수 백오프 재시도가 내장된 fetch */
  fetch: FetchFn;
  logger: Logger;
  /** 현재 시각(epoch ms). 테스트 주입용 */
  now: Clock;
  /** 상위(요청 단위) 취소 신호. 넘어오면 fetch가 존중한다 */
  signal?: AbortSignal;
}

export interface RetryOptions {
  /** attempt 1회당 타임아웃(ms). 기본 3000 (설계 §7.1) */
  timeoutMs: number;
  /** 첫 시도 이후 추가 재시도 횟수. 기본 2 */
  retries: number;
  /** 지수 백오프 기준값(ms). 기본 200 → 200, 400, 800... */
  backoffBaseMs: number;
}

export const DEFAULT_RETRY: RetryOptions = {
  timeoutMs: 3000,
  retries: 2,
  backoffBaseMs: 200,
};

const RETRYABLE_STATUS = new Set([429, 500, 502, 503, 504]);

/**
 * 타임아웃 + 지수 백오프 재시도를 내장한 fetch 팩토리.
 * core가 provider별 설정으로 만들어 `ProviderContext.fetch`에 넣는다.
 *
 * - attempt마다 `timeoutMs` 타임아웃(`AbortSignal.timeout`)을 걸고 상위 signal과 합친다.
 * - 429/5xx 응답과 네트워크 오류는 `retries`회까지 백오프 후 재시도(`Retry-After` 존중).
 * - 상위 signal이 취소되면 즉시 `TIMEOUT`으로 중단(재시도 안 함).
 * - 재시도 소진 시 마지막 응답을 그대로 반환한다(4xx 등은 provider가 매핑하도록).
 */
export function createRetryingFetch(
  deps: { baseFetch?: FetchFn; logger: Logger; now: Clock; signal?: AbortSignal },
  options: Partial<RetryOptions> = {},
): FetchFn {
  const opts = { ...DEFAULT_RETRY, ...options };
  const baseFetch: FetchFn = deps.baseFetch ?? ((url, init) => fetch(url, init));

  return async function retryingFetch(url, init) {
    let lastError: unknown;
    for (let attempt = 0; attempt <= opts.retries; attempt++) {
      throwIfAborted(deps.signal);
      const timeout = AbortSignal.timeout(opts.timeoutMs);
      const signal = deps.signal ? AbortSignal.any([deps.signal, timeout]) : timeout;
      try {
        const res = await baseFetch(url, { ...init, signal });
        if (RETRYABLE_STATUS.has(res.status) && attempt < opts.retries) {
          const delay = retryAfterMs(res) ?? backoffMs(opts.backoffBaseMs, attempt);
          deps.logger.debug(
            `retrying ${url} after HTTP ${res.status} (attempt ${attempt + 1}/${opts.retries}, ${delay}ms)`,
          );
          await abortableDelay(delay, deps.signal);
          continue;
        }
        return res;
      } catch (err) {
        lastError = err;
        // 상위 signal에 의한 취소는 재시도하지 않는다
        if (deps.signal?.aborted) {
          throw new GeoProviderError("TIMEOUT", `request to ${url} was aborted`, {
            cause: err,
          });
        }
        if (attempt < opts.retries) {
          const delay = backoffMs(opts.backoffBaseMs, attempt);
          deps.logger.debug(
            `retrying ${url} after error (attempt ${attempt + 1}/${opts.retries}, ${delay}ms)`,
          );
          await abortableDelay(delay, deps.signal);
          continue;
        }
      }
    }
    // 재시도 소진 — 타임아웃/네트워크 오류를 정규화해 던진다
    throw new GeoProviderError(
      "TIMEOUT",
      `request to ${url} failed after ${opts.retries + 1} attempts`,
      { cause: lastError },
    );
  };
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new GeoProviderError("TIMEOUT", "request aborted by caller");
  }
}

/** 지터 없이 결정적 백오프 — 테스트 재현성을 위해 base * 2^attempt */
function backoffMs(base: number, attempt: number): number {
  return base * 2 ** attempt;
}

function retryAfterMs(res: Response): number | undefined {
  const header = res.headers.get("retry-after");
  if (!header) return undefined;
  const seconds = Number(header);
  return Number.isFinite(seconds) ? seconds * 1000 : undefined;
}

/** signal이 취소되면 즉시 resolve하는 대기 (매달린 타이머 방지) */
function abortableDelay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      resolve();
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

/** 아무것도 출력하지 않는 로거 (테스트·기본값용) */
export const noopLogger: Logger = {
  debug() {},
  info() {},
  warn() {},
  error() {},
};
