import Fastify, { type FastifyInstance } from "fastify";
import fastifySwagger from "@fastify/swagger";
import fastifySwaggerUi from "@fastify/swagger-ui";
import type { GeoWire } from "@geowirehq/core";
import { registerRoutes } from "./routes.js";
import { createMetrics } from "./metrics.js";
import { registerAuth } from "./auth.js";
import { registerMcp } from "./mcp.js";
import { errorHandler } from "./errors.js";

export interface BuildOptions {
  geo: GeoWire;
  /** 설정 시 /v1/*(health 제외)에 Bearer 인증 요구 */
  apiKeys?: string[];
  /** /mcp 마운트 여부. 기본 true */
  enableMcp?: boolean;
}

/**
 * GeoWire REST 서버를 조립한다 (설계 §9.2).
 * 검증·직렬화는 core의 Zod가 담당하므로 fastify 스키마는 **OpenAPI 문서 전용**이다
 * (validator/serializer를 passthrough로 우회) — 스키마 패키지와 문서가 자동 동기화된다.
 */
export async function buildServer(opts: BuildOptions): Promise<FastifyInstance> {
  const app = Fastify({ logger: false });

  app.setValidatorCompiler(() => (data) => ({ value: data }));
  app.setSerializerCompiler(() => (data) => JSON.stringify(data));

  await app.register(fastifySwagger, {
    openapi: {
      openapi: "3.1.0",
      info: {
        title: "GeoWire API",
        version: "0.1.0",
        description:
          "지도·장소 데이터 게이트웨이. 여러 공급자(nominatim/google/internal)를 통합해 " +
          "검색·지오코딩·병합·중복제거·정책 적용을 단일 API로 제공한다.",
      },
      tags: [
        { name: "places", description: "장소 검색·상세" },
        { name: "geocode", description: "주소↔좌표 변환" },
        { name: "routing", description: "길찾기·거리행렬" },
        { name: "analysis", description: "지역·상권 분석" },
        { name: "meta", description: "공급자·헬스" },
      ],
    },
  });
  await app.register(fastifySwaggerUi, { routePrefix: "/docs" });

  const metrics = createMetrics();
  registerAuth(app, opts.apiKeys);
  app.setErrorHandler(errorHandler);

  app.addHook("onResponse", async (request, reply) => {
    metrics.recordHttp(request.method, request.routeOptions?.url ?? "unknown", reply.statusCode);
  });

  registerRoutes(app, opts.geo, metrics);

  app.get("/metrics", { schema: { hide: true } }, async (_request, reply) => {
    reply.header("Content-Type", metrics.registry.contentType);
    return metrics.registry.metrics();
  });

  if (opts.enableMcp !== false) registerMcp(app, opts.geo);

  return app;
}
