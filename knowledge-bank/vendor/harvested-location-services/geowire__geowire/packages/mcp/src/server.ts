import { createRequire } from "node:module";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import type { GeoWire } from "@geowirehq/core";
import { TOOL_DEFS, dispatchTool } from "./tools.js";

/**
 * 패키지 버전을 실제 package.json에서 읽는다 — MCP 클라이언트가 `serverInfo.version`으로
 * 표시하는 값이라 하드코딩하면 릴리스마다 어긋난다(과거 0.1.0으로 고정돼 있었음).
 */
const { version: VERSION } = createRequire(import.meta.url)("../package.json") as {
  version: string;
};

/**
 * GeoWire MCP 서버를 만든다 (설계 §9.1 — MCP는 1등 시민 인터페이스).
 * `TOOL_DEFS`의 도구들을 노출하고, 호출을 주입된 GeoWire 퍼사드로 위임한다.
 * 전송(stdio/HTTP)은 호출자가 `server.connect(transport)`로 연결한다.
 */
export function createGeoWireMcpServer(geo: GeoWire): Server {
  const server = new Server(
    { name: "geowire", version: VERSION },
    { capabilities: { tools: {} } },
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOL_DEFS }));

  server.setRequestHandler(CallToolRequestSchema, async (request) =>
    dispatchTool(geo, request.params.name, (request.params.arguments ?? {}) as Record<string, unknown>),
  );

  return server;
}
