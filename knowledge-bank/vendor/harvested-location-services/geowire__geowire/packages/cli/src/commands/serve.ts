import { buildServer } from "@geowirehq/server";
import type { GeoWire } from "@geowirehq/core";
import type { IO } from "../io.js";

export interface ServeArgs {
  geo: GeoWire;
  port?: number;
  host?: string;
  apiKeys?: string[];
  /** 테스트용: listen 후 즉시 반환하지 않고 서버 인스턴스를 콜백에 넘긴다 */
  onListen?: (info: { port: number; host: string }) => void;
}

/**
 * REST + MCP 서버를 기동한다 (설계 §9 `geowire` / `geowire serve`).
 * apps/server의 buildServer를 재사용해 CLI와 서버가 동일 동작을 공유한다.
 */
export async function runServe(args: ServeArgs, io: IO): Promise<number> {
  const app = await buildServer({ geo: args.geo, apiKeys: args.apiKeys });
  const port = args.port ?? 4980;
  const host = args.host ?? "0.0.0.0";
  await app.listen({ port, host });

  const shown = host === "0.0.0.0" ? "localhost" : host;
  io.out(`GeoWire server running on http://${shown}:${port}`);
  io.out(`  REST search : POST http://${shown}:${port}/v1/places/search`);
  io.out(`  API docs    : http://${shown}:${port}/docs`);
  io.out(`  MCP (HTTP)  : http://${shown}:${port}/mcp`);
  io.out(`  Metrics     : http://${shown}:${port}/metrics`);

  args.onListen?.({ port, host });
  return 0;
}
