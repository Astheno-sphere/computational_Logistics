import type { ProviderErrorCode } from "@geowirehq/schema";

/**
 * core 바깥으로 나가는 모든 공급자 예외의 정규화 표현.
 * fallback·서킷브레이커·`meta.providersSkipped`/`providersFailed`의 판단 근거가 되므로,
 * provider 어댑터는 raw 예외를 반드시 이 타입으로 변환해서 던진다 (설계 §6.3).
 */
export class GeoProviderError extends Error {
  /** 정규화된 실패 분류 (`@geowirehq/schema`의 ProviderErrorCode) */
  readonly code: ProviderErrorCode;
  /** 실패한 공급자 슬러그. core가 채워 넣기도 한다 */
  readonly provider?: string;
  /** 원본 HTTP 상태 (있으면) */
  readonly status?: number;
  /** 재시도로 회복 가능한 유형인지 (RATE_LIMITED·TIMEOUT·PROVIDER_UNAVAILABLE) */
  readonly retryable: boolean;

  constructor(
    code: ProviderErrorCode,
    message: string,
    options: { provider?: string; status?: number; cause?: unknown } = {},
  ) {
    super(message, { cause: options.cause });
    this.name = "GeoProviderError";
    this.code = code;
    this.provider = options.provider;
    this.status = options.status;
    this.retryable = RETRYABLE_CODES.has(code);
  }
}

const RETRYABLE_CODES = new Set<ProviderErrorCode>([
  "RATE_LIMITED",
  "TIMEOUT",
  "PROVIDER_UNAVAILABLE",
]);

/** 재시도해도 의미 있는(일시적) 실패 코드인지 판별 */
export function isRetryableCode(code: ProviderErrorCode): boolean {
  return RETRYABLE_CODES.has(code);
}

/**
 * HTTP 상태 코드를 정규화된 ProviderErrorCode로 매핑한다.
 * provider 어댑터가 `if (!res.ok) throw errorFromHttpStatus(res.status, ...)` 형태로 사용.
 */
export function errorFromHttpStatus(
  status: number,
  options: { provider?: string; message?: string; cause?: unknown } = {},
): GeoProviderError {
  const code = codeFromStatus(status);
  const message =
    options.message ?? `${options.provider ?? "provider"} responded with HTTP ${status}`;
  return new GeoProviderError(code, message, {
    provider: options.provider,
    status,
    cause: options.cause,
  });
}

function codeFromStatus(status: number): ProviderErrorCode {
  if (status === 401 || status === 403) return "AUTH_FAILED";
  if (status === 429) return "RATE_LIMITED";
  if (status === 408 || status === 504) return "TIMEOUT";
  if (status === 400 || status === 422) return "INVALID_REQUEST";
  if (status === 501) return "UNSUPPORTED_CAPABILITY";
  // 5xx(그 외)·기타 → 일시적 불가로 간주
  return "PROVIDER_UNAVAILABLE";
}
