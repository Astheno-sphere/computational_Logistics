import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { createGeoWireMcpServer } from "@geowirehq/mcp";
import type { FastifyInstance } from "fastify";
import type { GeoWire } from "@geowirehq/core";

/**
 * MCP를 Streamable HTTP로 같은 프로세스에 마운트한다 (설계 §9.2, `/mcp`).
 * stateless 모드(`sessionIdGenerator: undefined`) — 요청마다 서버·transport를 새로 만들어
 * 세션 상태 없이 JSON-RPC를 처리한다. REST와 MCP가 하나의 게이트웨이를 공유한다.
 */
export function registerMcp(app: FastifyInstance, geo: GeoWire): void {
  app.post("/mcp", async (request, reply) => {
    const server = createGeoWireMcpServer(geo);
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });

    reply.raw.on("close", () => {
      void transport.close();
      void server.close();
    });

    await server.connect(transport);
    reply.hijack(); // fastify가 응답을 보내지 않게 하고 transport가 직접 쓴다
    await transport.handleRequest(request.raw, reply.raw, request.body);
  });
}
