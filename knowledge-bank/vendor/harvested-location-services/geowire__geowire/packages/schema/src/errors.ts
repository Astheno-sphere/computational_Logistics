import { z } from "zod";

/**
 * 모든 공급자 예외의 정규화 분류 (설계 §6.3).
 * fallback·서킷브레이커·meta.providersSkipped 의 판단 근거가 된다.
 */
export const ProviderErrorCode = z.enum([
  "MISSING_CREDENTIALS",
  "AUTH_FAILED",
  "RATE_LIMITED",
  "QUOTA_EXCEEDED",
  "TIMEOUT",
  "PROVIDER_UNAVAILABLE",
  "INVALID_REQUEST",
  "UNSUPPORTED_CAPABILITY",
]);
export type ProviderErrorCode = z.infer<typeof ProviderErrorCode>;
