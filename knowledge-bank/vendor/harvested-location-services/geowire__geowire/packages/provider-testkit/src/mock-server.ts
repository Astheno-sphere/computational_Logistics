import {
  createRetryingFetch,
  noopLogger,
  type FetchFn,
  type ProviderContext,
} from "@geowirehq/provider-sdk";

/** JSON 응답 Response를 만든다 (content-type 자동) */
export function mockJson(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json", ...init.headers },
  });
}

/** 항상 주어진 JSON 바디를 200(또는 지정 status)으로 돌려주는 fetch — 매 호출 새 Response 생성 */
export function jsonFetch(body: unknown, init: ResponseInit = {}): FetchFn {
  return async () => mockJson(body, init);
}

/** 지정한 HTTP 상태로 응답하는 fetch (401/429/500 시뮬레이션) */
export function statusFetch(status: number, body: unknown = {}): FetchFn {
  return async () => mockJson(body, { status });
}

/**
 * 절대 정상 응답하지 않고 attempt 타임아웃 신호가 오면 abort하는 fetch.
 * `createRetryingFetch`의 per-attempt 타임아웃과 결합해 TIMEOUT 경로를 시뮬레이션한다.
 */
export function hangingFetch(): FetchFn {
  return (_url, init) =>
    new Promise((_resolve, reject) => {
      init?.signal?.addEventListener(
        "abort",
        () => reject(new DOMException("The operation was aborted", "AbortError")),
        { once: true },
      );
    });
}

/**
 * provider에 넘길 테스트용 ProviderContext를 만든다.
 * 실제 SDK의 `createRetryingFetch`를 그대로 써서 provider가 운영과 동일한 fetch를 받는다.
 */
export function createTestContext(
  baseFetch: FetchFn,
  options: { timeoutMs?: number; retries?: number; signal?: AbortSignal } = {},
): ProviderContext {
  const now = () => 0;
  const fetch = createRetryingFetch(
    { baseFetch, logger: noopLogger, now, signal: options.signal },
    { timeoutMs: options.timeoutMs ?? 1000, retries: options.retries ?? 0, backoffBaseMs: 1 },
  );
  return { fetch, logger: noopLogger, now, signal: options.signal };
}
