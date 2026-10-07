import type { FastifyInstance } from "fastify";

/** 인증 없이 접근 가능한 공개 경로 (헬스·메트릭·문서·MCP) */
const PUBLIC_PATHS = new Set(["/v1/health", "/metrics"]);

/**
 * 선택적 Bearer 인증 (설계 §9.2).
 * `GEOWIRE_API_KEYS`가 설정되면 `/v1/*`(health 제외)에 `Authorization: Bearer <key>`를 요구한다.
 * 설정이 없으면 인증을 걸지 않는다(zero-config 로컬 사용).
 */
export function registerAuth(app: FastifyInstance, apiKeys?: string[]): void {
  if (!apiKeys || apiKeys.length === 0) return;
  const keys = new Set(apiKeys);

  app.addHook("onRequest", async (request, reply) => {
    const path = request.url.split("?")[0] ?? "";
    if (!path.startsWith("/v1/") || PUBLIC_PATHS.has(path)) return;

    const header = request.headers.authorization;
    const token = header?.startsWith("Bearer ") ? header.slice(7) : undefined;
    if (!token || !keys.has(token)) {
      await reply.status(401).send({
        error: { code: "UNAUTHORIZED", message: "valid Bearer token required" },
      });
    }
  });
}
