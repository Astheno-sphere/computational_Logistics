import { z } from "zod";
import type { FastifyInstance } from "fastify";
import type { GeoWire } from "@geowirehq/core";
import {
  SearchPlacesRequest,
  SearchPlacesResponse,
  Place,
  RouteRequest,
  RouteResponse,
  DistanceMatrixRequest,
  DistanceMatrixResponse,
  AreaInsightsRequest,
  AreaInsightsResponse,
  DemographicsResponse,
  IsochroneRequest,
  IsochroneResponse,
} from "@geowirehq/schema";
import type { Metrics } from "./metrics.js";

/** Zod → JSON Schema (OpenAPI 문서 전용; 검증은 core의 Zod가 담당). $schema 메타 제거 */
function jsonSchema(schema: z.ZodType): Record<string, unknown> {
  const js = z.toJSONSchema(schema, { target: "draft-7" }) as Record<string, unknown>;
  delete js.$schema;
  return js;
}

/** GET 쿼리스트링용 로컬 스키마 (문서 + 좌표/limit 강제 변환) */
const GeocodeQuery = z.object({
  address: z.string(),
  country: z.string().optional(),
  limit: z.coerce.number().int().min(1).max(20).optional(),
});
const ReverseQuery = z.object({
  lat: z.coerce.number(),
  lon: z.coerce.number(),
});

/** 오류 응답 스키마 (OpenAPI 문서용) */
const ERROR_SCHEMA = {
  type: "object",
  properties: {
    error: {
      type: "object",
      properties: {
        code: { type: "string" },
        message: { type: "string" },
        details: {},
      },
      required: ["code", "message"],
    },
  },
  required: ["error"],
} as const;

/**
 * REST 라우트를 등록한다 (설계 §9.2).
 * 검증은 core의 Zod가 수행하고, 여기 schema는 OpenAPI 문서 생성 전용이다.
 */
export function registerRoutes(app: FastifyInstance, geo: GeoWire, metrics: Metrics): void {
  app.post(
    "/v1/places/search",
    {
      schema: {
        tags: ["places"],
        summary: "자연어 + 좌표/지역 기반 장소 검색",
        body: jsonSchema(SearchPlacesRequest),
        response: { 200: jsonSchema(SearchPlacesResponse) },
      },
    },
    async (request) => {
      const result = await geo.searchPlaces(request.body);
      metrics.recordMeta(result.meta);
      return result;
    },
  );

  app.get(
    "/v1/places/*",
    {
      schema: {
        tags: ["places"],
        summary: "내부 ID 또는 provider 참조(provider:placeId)로 상세 조회",
        params: { type: "object", properties: { "*": { type: "string" } } },
        response: { 200: jsonSchema(Place), 404: ERROR_SCHEMA },
      },
    },
    async (request, reply) => {
      const id = (request.params as Record<string, string>)["*"] ?? "";
      const place = await geo.getPlace({ id });
      if (!place) {
        return reply.status(404).send({
          error: { code: "NOT_FOUND", message: `place not found: ${id}` },
        });
      }
      return place;
    },
  );

  app.get(
    "/v1/geocode",
    {
      schema: {
        tags: ["geocode"],
        summary: "주소 → 좌표 (+정규화 주소)",
        querystring: jsonSchema(GeocodeQuery),
        response: { 200: jsonSchema(SearchPlacesResponse) },
      },
    },
    async (request) => {
      const q = GeocodeQuery.parse(request.query);
      const result = await geo.geocode({ address: q.address, country: q.country, limit: q.limit });
      metrics.recordMeta(result.meta);
      return result;
    },
  );

  app.get(
    "/v1/reverse-geocode",
    {
      schema: {
        tags: ["geocode"],
        summary: "좌표 → 주소",
        querystring: jsonSchema(ReverseQuery),
        response: { 200: jsonSchema(SearchPlacesResponse) },
      },
    },
    async (request) => {
      const q = ReverseQuery.parse(request.query);
      const result = await geo.reverseGeocode({
        location: { latitude: q.lat, longitude: q.lon },
      });
      metrics.recordMeta(result.meta);
      return result;
    },
  );

  app.post(
    "/v1/directions",
    {
      schema: {
        tags: ["routing"],
        summary: "경유지 간 길찾기 (거리·시간·구간). 무키 OSRM",
        body: jsonSchema(RouteRequest),
        response: { 200: jsonSchema(RouteResponse) },
      },
    },
    async (request) => {
      const result = await geo.getRoute(request.body);
      metrics.recordMeta(result.meta);
      return result;
    },
  );

  app.post(
    "/v1/distance-matrix",
    {
      schema: {
        tags: ["routing"],
        summary: "원점×목적지 거리/시간 행렬. 무키 OSRM",
        body: jsonSchema(DistanceMatrixRequest),
        response: { 200: jsonSchema(DistanceMatrixResponse) },
      },
    },
    async (request) => {
      const result = await geo.getDistanceMatrix(request.body);
      metrics.recordMeta(result.meta);
      return result;
    },
  );

  app.post(
    "/v1/analyze-area",
    {
      schema: {
        tags: ["analysis"],
        summary: "지역/상권 분석 — 반경 내 업종별 밀도·경쟁·평점 지형",
        body: jsonSchema(AreaInsightsRequest),
        response: { 200: jsonSchema(AreaInsightsResponse) },
      },
    },
    async (request) => {
      const result = await geo.analyzeArea(request.body);
      metrics.recordMeta(result.meta);
      return result;
    },
  );

  app.post(
    "/v1/isochrone",
    {
      schema: {
        tags: ["analysis"],
        summary: "도달권(isochrone) — N분 내 도달 영역 폴리곤 (무키 OSRM)",
        body: jsonSchema(IsochroneRequest),
        response: { 200: jsonSchema(IsochroneResponse) },
      },
    },
    async (request) => {
      const result = await geo.getIsochrone(request.body);
      metrics.recordMeta(result.meta);
      return result;
    },
  );

  app.get(
    "/v1/demographics",
    {
      schema: {
        tags: ["analysis"],
        summary: "좌표가 속한 지역의 인구통계 (US Census 등)",
        querystring: jsonSchema(ReverseQuery),
        response: { 200: jsonSchema(DemographicsResponse) },
      },
    },
    async (request) => {
      const q = ReverseQuery.parse(request.query);
      const result = await geo.getDemographics({ location: { latitude: q.lat, longitude: q.lon } });
      metrics.recordMeta(result.meta);
      return result;
    },
  );

  app.get(
    "/v1/providers",
    { schema: { tags: ["meta"], summary: "활성 공급자·capability·상태" } },
    async () => ({ providers: geo.listProviders() }),
  );

  app.get(
    "/v1/health",
    { schema: { tags: ["meta"], summary: "헬스 체크" } },
    async () => {
      const enabled = geo.listProviders().filter((p) => p.enabled).length;
      return { status: "ok", providers: enabled };
    },
  );
}
