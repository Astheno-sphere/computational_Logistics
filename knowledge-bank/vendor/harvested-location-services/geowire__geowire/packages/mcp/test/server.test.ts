import { describe, it, expect } from "vitest";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { createGeoWire, type GeoWire } from "@geowirehq/core";
import { createNominatimProvider } from "@geowirehq/provider-nominatim";
import { createGoogleProvider } from "@geowirehq/provider-google";
import { createOsrmProvider } from "@geowirehq/provider-osrm";
import { createGeoWireMcpServer } from "../src/server.js";
import { TOOL_DEFS } from "../src/tools.js";

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
  rating: 4.2,
};

function routedFetch(): (url: string) => Promise<Response> {
  return async (url: string) => {
    const json = (b: unknown) => new Response(JSON.stringify(b), { headers: { "content-type": "application/json" } });
    if (url.includes(":searchText")) return json({ places: [GOOGLE_DETAILS] });
    if (url.includes("/places/")) return json(GOOGLE_DETAILS);
    if (url.includes("maps.googleapis")) return json({ status: "OK", results: [] });
    if (url.includes("/route/v1/"))
      return json({
        code: "Ok",
        routes: [{ distance: 9949.4, duration: 598.4, legs: [{ distance: 9949.4, duration: 598.4 }] }],
      });
    if (url.includes("nominatim")) return json(NOMI);
    return json({});
  };
}

function buildGeo(opts: { google?: boolean } = {}): GeoWire {
  const providers = [
    createNominatimProvider({ sleep: async () => {} }),
    createOsrmProvider(),
  ];
  if (opts.google) providers.push(createGoogleProvider({ apiKey: "test-key" }));
  return createGeoWire({
    providers,
    baseFetch: routedFetch(),
    config: { providers: { nominatim: { priority: 10 }, google: { priority: 1 } } },
  });
}

async function connectClient(geo: GeoWire): Promise<Client> {
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  const server = createGeoWireMcpServer(geo);
  await server.connect(serverTransport);
  const client = new Client({ name: "test-client", version: "0.0.0" });
  await client.connect(clientTransport);
  return client;
}

describe("GeoWire MCP 서버 — 도구 목록", () => {
  it("10개 도구를 노출한다", async () => {
    const client = await connectClient(buildGeo());
    const { tools } = await client.listTools();
    expect(tools.map((t) => t.name).sort()).toEqual([
      "analyze_area",
      "distance_matrix",
      "geocode_address",
      "get_demographics",
      "get_directions",
      "get_isochrone",
      "get_place",
      "list_geo_providers",
      "reverse_geocode",
      "search_places",
    ]);
  });

  it("inputSchema는 자동 생성되며 $schema가 없고 default 필드는 required가 아니다", () => {
    const search = TOOL_DEFS.find((t) => t.name === "search_places")!;
    expect(search.inputSchema.type).toBe("object");
    expect("$schema" in search.inputSchema).toBe(false);
    // limit은 default가 있으므로 required가 아니어야 한다
    expect(search.inputSchema.required ?? []).not.toContain("limit");
    expect(search.inputSchema.required ?? []).toContain("query");
  });

  it("도구 설명문에 사용 예시가 포함된다 (프롬프트 회귀 방지)", () => {
    for (const tool of TOOL_DEFS) {
      expect(tool.description!.length).toBeGreaterThan(40);
    }
    const search = TOOL_DEFS.find((t) => t.name === "search_places")!;
    expect(search.description).toContain("Example:");
  });
});

describe("GeoWire MCP 서버 — 도구 호출 (5개 전부)", () => {
  it("search_places: 텍스트 요약 + structuredContent를 반환한다", async () => {
    const client = await connectClient(buildGeo());
    const res = await client.callTool({ name: "search_places", arguments: { query: "서울시청" } });
    const content = res.content as Array<{ type: string; text: string }>;
    expect(content[0]!.text).toContain("서울시청");
    const structured = res.structuredContent as { results: unknown[]; meta: { strategy: string } };
    expect(structured.results).toHaveLength(1);
    expect(structured.meta.strategy).toBe("first-success");
    expect(res.isError).toBeFalsy();
  });

  it("geocode_address: 주소 → 좌표", async () => {
    const client = await connectClient(buildGeo());
    const res = await client.callTool({ name: "geocode_address", arguments: { address: "세종대로 110" } });
    const structured = res.structuredContent as { results: Array<{ location: { latitude: number } }> };
    expect(structured.results.length).toBeGreaterThan(0);
    expect(structured.results[0]!.location.latitude).toBeCloseTo(37.5665, 2);
  });

  it("reverse_geocode: 좌표 → 주소", async () => {
    const client = await connectClient(buildGeo());
    const res = await client.callTool({
      name: "reverse_geocode",
      arguments: { location: { latitude: 37.5665, longitude: 126.978 } },
    });
    const structured = res.structuredContent as { results: unknown[] };
    expect(structured.results.length).toBeGreaterThan(0);
  });

  it("get_place: provider 참조로 상세 조회 (google)", async () => {
    const client = await connectClient(buildGeo({ google: true }));
    const res = await client.callTool({ name: "get_place", arguments: { id: "google:ChIJgangnam" } });
    const structured = res.structuredContent as { place: { name: string } | null };
    expect(structured.place?.name).toBe("GS25 강남점");
  });

  it("get_directions: 경유지 길찾기 (osrm, 무키)", async () => {
    const client = await connectClient(buildGeo());
    const res = await client.callTool({
      name: "get_directions",
      arguments: {
        waypoints: [
          { latitude: 37.5665, longitude: 126.978 },
          { latitude: 37.4979, longitude: 127.0276 },
        ],
      },
    });
    const content = res.content as Array<{ type: string; text: string }>;
    expect(content[0]!.text).toContain("Route:");
    const structured = res.structuredContent as { routes: Array<{ provider: string; distanceMeters: number }> };
    expect(structured.routes[0]!.provider).toBe("osrm");
    expect(structured.routes[0]!.distanceMeters).toBe(9949.4);
  });

  it("list_geo_providers: 활성 공급자 목록", async () => {
    const client = await connectClient(buildGeo({ google: true }));
    const res = await client.callTool({ name: "list_geo_providers", arguments: {} });
    const structured = res.structuredContent as { providers: Array<{ id: string }> };
    expect(structured.providers.map((p) => p.id).sort()).toEqual(["google", "nominatim", "osrm"]);
  });
});

describe("GeoWire MCP 서버 — 에러 처리", () => {
  it("잘못된 인자는 자가 수정 가능한 에러 메시지를 낸다", async () => {
    const client = await connectClient(buildGeo());
    const res = await client.callTool({ name: "search_places", arguments: {} });
    expect(res.isError).toBe(true);
    const content = res.content as Array<{ text: string }>;
    expect(content[0]!.text).toContain("Invalid arguments for search_places");
    expect(content[0]!.text).toContain("query");
  });

  it("찾을 수 없는 place는 안내 메시지 (에러 아님)", async () => {
    const client = await connectClient(buildGeo());
    const res = await client.callTool({ name: "get_place", arguments: { id: "gwp_unknown" } });
    const content = res.content as Array<{ text: string }>;
    expect(content[0]!.text).toContain("No place found");
  });
});

describe("Zero-config (키 없는 nominatim + osrm) — DoD", () => {
  it("Google 키 없이도 search_places가 동작한다", async () => {
    const client = await connectClient(buildGeo()); // google 없음
    const res = await client.callTool({ name: "search_places", arguments: { query: "서울시청" } });
    const structured = res.structuredContent as { results: unknown[]; meta: { providersUsed: Array<{ provider: string }> } };
    expect(structured.results.length).toBeGreaterThan(0);
    expect(structured.meta.providersUsed[0]!.provider).toBe("nominatim");
  });

  it("list_geo_providers가 무키 기본(nominatim 검색 + osrm 길찾기)을 보고한다", async () => {
    const client = await connectClient(buildGeo());
    const res = await client.callTool({ name: "list_geo_providers", arguments: {} });
    const structured = res.structuredContent as { providers: Array<{ id: string }> };
    expect(structured.providers.map((p) => p.id).sort()).toEqual(["nominatim", "osrm"]);
  });
});
