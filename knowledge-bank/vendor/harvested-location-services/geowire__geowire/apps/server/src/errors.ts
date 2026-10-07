import { z } from "zod";
import { GeoProviderError } from "@geowirehq/provider-sdk";
import type { FastifyError, FastifyReply, FastifyRequest } from "fastify";

/** 정규화된 오류 응답 봉투 */
export interface ErrorBody {
  error: { code: string; message: string; details?: unknown };
}

/** GeoProviderError.code → HTTP 상태 */
function statusForProviderError(code: string): number {
  switch (code) {
    case "INVALID_REQUEST":
      return 400;
    case "AUTH_FAILED":
    case "MISSING_CREDENTIALS":
      return 502; // 게이트웨이가 상류 공급자 인증에 실패
    case "RATE_LIMITED":
    case "QUOTA_EXCEEDED":
      return 429;
    case "TIMEOUT":
      return 504;
    default:
      return 502;
  }
}

/**
 * 통합 Fastify 에러 핸들러.
 * ZodError → 400(자가 수정 가능한 필드 메시지), GeoProviderError → 상태 매핑, 그 외 → 500.
 */
export function errorHandler(
  error: FastifyError,
  _request: FastifyRequest,
  reply: FastifyReply,
): void {
  if (error instanceof z.ZodError) {
    const details = error.issues.map((i) => ({
      path: i.path.join(".") || "(root)",
      message: i.message,
    }));
    reply.status(400).send({
      error: { code: "INVALID_REQUEST", message: "요청 검증 실패", details },
    } satisfies ErrorBody);
    return;
  }
  if (error instanceof GeoProviderError) {
    reply.status(statusForProviderError(error.code)).send({
      error: { code: error.code, message: error.message },
    } satisfies ErrorBody);
    return;
  }
  const status = typeof error.statusCode === "number" ? error.statusCode : 500;
  reply.status(status).send({
    error: { code: "INTERNAL", message: error.message || "Internal Server Error" },
  } satisfies ErrorBody);
}
