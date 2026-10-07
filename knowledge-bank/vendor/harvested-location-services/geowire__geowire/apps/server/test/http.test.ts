import { describe, it, expect, afterEach } from "vitest";
import { createGeoWire, type GeoWire } from "@geowirehq/core";
import { createNominatimProvider } from "@geowirehq/provider-nominatim";
import { createGoogleProvider } from "@geowirehq/provider-google";
import type { FastifyInstance } from "fastify";
import { buildServer } from "../src/app.js";

const NOMI = [
  {
    osm_type: "node",
    osm_id: 240109189,
    lat: "37.5665",
    lon: "126.9780",
    name: "서울시청",
    display_name: "서울시청, 세종대로, 중구, 서울",
    category: "office",
    type: "government",
    importance: 0.5,
    address: { city: "서울", country_code: "kr" },
  },
];
const GOOGLE_DETAILS = {
  id: "ChIJgangnam",
  displayName: { text: "GS25 강남점", languageCode: "ko" },
  formattedAddress: "서울 강남구 테헤란로 1",
  location: { latitude: 37.498, longitude: 127.028 },
  types: ["convenience_store"],
};

function routedFetch(): (url: string) => Promise<Response> {
  return async (url: string) => {
    const json = (b: unknown) => new Response(JSON.stringify(b), { headers: { "content-type": "application/json" } });
    if (url.includes(":searchText")) return json({ places: [GOOGLE_DETAILS] });
    if (url.includes("/places/")) return json(GOOGLE_DETAILS);
    if (url.includes("maps.googleapis")) return json({ status: "OK", results: [] });
    if (url.includes("nominatim")) return json(NOMI);
    return json({});
  };
}

function buildGeo(google = true): GeoWire {
  const providers = [createNominatimProvider({ sleep: async () => {} })];
  if (google) providers.push(createGoogleProvider({ apiKey: "test-key" }));
  return createGeoWire({
    providers,
    baseFetch: routedFetch(),
    config: { providers: { nominatim: { priority: 10 }, google: { priority: 1 } } },
  });
}

let servers: FastifyInstance[] = [];
async function makeServer(opts: { apiKeys?: string[]; google?: boolean } = {}): Promise<FastifyInstance> {
  const app = await buildServer({ geo: buildGeo(opts.google), apiKeys: opts.apiKeys });
  await app.ready();
  servers.push(app);
  return app;
}
afterEach(async () => {
  await Promise.all(servers.map((s) => s.close()));
  servers = [];
});

describe("REST 엔드포인트 (inject)", () => {
  it("POST /v1/places/search → 200 + results + meta", async () => {
    const app = await makeServer();
    const res = await app.inject({ method: "POST", url: "/v1/places/search", payload: { query: "서울시청" } });
    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.results).toHaveLength(1);
    expect(body.results[0].name).toBe("서울시청");
    expect(body.meta.strategy).toBe("first-success");
  });

  it("GET /v1/geocode?address= → 200", async () => {
    const app = await makeServer();
    const res = await app.inject({ method: "GET", url: "/v1/geocode?address=세종대로 110" });
    expect(res.statusCode).toBe(200);
    expect(res.json().results.length).toBeGreaterThan(0);
  });

  it("GET /v1/reverse-geocode?lat=&lon= → 200", async () => {
    const app = await makeServer();
    const res = await app.inject({ method: "GET", url: "/v1/reverse-geocode?lat=37.5665&lon=126.978" });
    expect(res.statusCode).toBe(200);
    expect(res.json().results.length).toBeGreaterThan(0);
  });

  it("GET /v1/places/* → provider 참조로 상세 (google)", async () => {
    const app = await makeServer();
    const res = await app.inject({ method: "GET", url: "/v1/places/google:ChIJgangnam" });
    expect(res.statusCode).toBe(200);
    expect(res.json().name).toBe("GS25 강남점");
  });

  it("GET /v1/places/* 없는 참조 → 404", async () => {
    const app = await makeServer();
    const res = await app.inject({ method: "GET", url: "/v1/places/gwp_missing" });
    expect(res.statusCode).toBe(404);
    expect(res.json().error.code).toBe("NOT_FOUND");
  });

  it("GET /v1/providers → 200 목록", async () => {
    const app = await makeServer();
    const res = await app.inject({ method: "GET", url: "/v1/providers" });
    expect(res.statusCode).toBe(200);
    expect(res.json().providers.map((p: { id: string }) => p.id).sort()).toEqual(["google", "nominatim"]);
  });

  it("GET /v1/health → 200 ok", async () => {
    const app = await makeServer();
    const res = await app.inject({ method: "GET", url: "/v1/health" });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toMatchObject({ status: "ok" });
  });

  it("잘못된 요청(query 누락) → 400 INVALID_REQUEST", async () => {
    const app = await makeServer();
    const res = await app.inject({ method: "POST", url: "/v1/places/search", payload: {} });
    expect(res.statusCode).toBe(400);
    expect(res.json().error.code).toBe("INVALID_REQUEST");
    expect(JSON.stringify(res.json().error.details)).toContain("query");
  });
});

describe("/metrics (prom-client)", () => {
  it("검색 후 provider 메트릭이 노출된다", async () => {
    const app = await makeServer();
    await app.inject({ method: "POST", url: "/v1/places/search", payload: { query: "서울시청" } });
    const res = await app.inject({ method: "GET", url: "/metrics" });
    expect(res.statusCode).toBe(200);
    expect(res.headers["content-type"]).toContain("text/plain");
    expect(res.body).toContain("geowire_provider_requests_total");
    expect(res.body).toContain('provider="nominatim"');
    expect(res.body).toContain("geowire_http_requests_total");
  });
});

describe("OpenAPI ↔ schema 동기화 (DoD)", () => {
  it("swagger 스펙이 schema 패키지의 SearchPlacesRequest 필드를 담는다", async () => {
    const app = await makeServer();
    // @fastify/swagger가 app.swagger()로 스펙을 노출
    const spec = (app as unknown as { swagger: () => Record<string, any> }).swagger();
    const searchOp = spec.paths["/v1/places/search"].post;
    const bodySchema = searchOp.requestBody.content["application/json"].schema;
    // schema 패키지의 SearchPlacesRequest에서 자동 생성 → query/near/limit 필드 존재
    expect(bodySchema.properties).toHaveProperty("query");
    expect(bodySchema.properties).toHaveProperty("near");
    expect(bodySchema.properties).toHaveProperty("limit");
    expect(bodySchema.required).toContain("query");
    // 응답 스키마도 연결됨
    expect(searchOp.responses["200"]).toBeDefined();
  });

  it("Swagger UI가 /docs에서 제공된다", async () => {
    const app = await makeServer();
    const res = await app.inject({ method: "GET", url: "/docs" });
    expect([200, 302]).toContain(res.statusCode);
  });
});

describe("Bearer 인증 (GEOWIRE_API_KEYS)", () => {
  it("키 설정 시 토큰 없으면 401, 있으면 200", async () => {
    const app = await makeServer({ apiKeys: ["secret-1"] });

    const noToken = await app.inject({ method: "POST", url: "/v1/places/search", payload: { query: "x" } });
    expect(noToken.statusCode).toBe(401);

    const withToken = await app.inject({
      method: "POST",
      url: "/v1/places/search",
      headers: { authorization: "Bearer secret-1" },
      payload: { query: "서울시청" },
    });
    expect(withToken.statusCode).toBe(200);
  });

  it("health는 인증 없이 접근 가능", async () => {
    const app = await makeServer({ apiKeys: ["secret-1"] });
    const res = await app.inject({ method: "GET", url: "/v1/health" });
    expect(res.statusCode).toBe(200);
  });
});

describe("MCP over HTTP (/mcp, 실제 listen + fetch)", () => {
  it("initialize JSON-RPC에 응답한다", async () => {
    const app = await makeServer();
    await app.listen({ port: 0, host: "127.0.0.1" });
    const address = app.server.address();
    const port = typeof address === "object" && address ? address.port : 0;

    const res = await fetch(`http://127.0.0.1:${port}/mcp`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json, text/event-stream" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 1,
        method: "initialize",
        params: { protocolVersion: "2024-11-05", capabilities: {}, clientInfo: { name: "t", version: "0" } },
      }),
    });
    expect(res.status).toBe(200);
    const text = await res.text();
    // JSON 또는 SSE(data: {...}) 형태 모두 jsonrpc 결과를 포함
    expect(text).toContain("geowire");
    expect(text).toContain("jsonrpc");
  });
});
