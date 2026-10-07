import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import type { DeliveryClient, HttpMethod } from "../client.js";
import { DESTRUCTIVE, fail, ok } from "./util.js";

export function registerRawTool(server: McpServer, client: DeliveryClient): void {
  server.registerTool(
    "raw_request",
    {
      title: "Произвольный вызов API Яндекс Доставки",
      // The delivery API has write endpoints and this tool can reach any of
      // them, so it carries the most conservative annotation.
      annotations: DESTRUCTIVE,
      description:
        "Запасной выход: прямой вызов любого метода B2B API Яндекс Доставки — для эндпоинтов без " +
        "выделенного инструмента (тарифы, points-eta, ярлыки/акты, мерчанты, склады, отгрузки, " +
        "proof-of-delivery и т.д.). contour выбирает контур и хост: express — b2b.taxi.yandex.net " +
        "(пути вида «b2b/cargo/integration/v2/...»), platform — b2b-authproxy.taxi.yandex.net " +
        "(пути вида «api/b2b/platform/...»). query — параметры строки запроса, body отправляется как " +
        "JSON. ОСТОРОЖНО: инструмент может выполнять и изменяющие операции; 5xx/сетевые ошибки " +
        "ретраятся только для GET.",
      inputSchema: {
        contour: z
          .enum(["express", "platform"])
          .describe("Контур API: express — экспресс-доставка (claims), platform — НДД/ПВЗ."),
        path: z
          .string()
          .min(1)
          .describe(
            'Относительный путь API, например "b2b/cargo/integration/v2/claims/info" или "api/b2b/platform/request/info".',
          ),
        method: z.enum(["GET", "POST"]).optional().describe("HTTP-метод; по умолчанию POST."),
        query: z
          .record(z.union([z.string(), z.number(), z.boolean()]))
          .optional()
          .describe('Query-параметры, например {"claim_id": "..."}.'),
        body: z.record(z.any()).optional().describe("JSON-тело запроса."),
      },
    },
    async ({ contour, path, method, query, body }) => {
      try {
        const m = (method ?? "POST") as HttpMethod;
        return ok(await client.request(contour, m, path, { query, body }));
      } catch (e) {
        return fail(e);
      }
    },
  );
}
