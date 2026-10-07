import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import type { DeliveryClient, HttpMethod } from "../client.js";
import { DESTRUCTIVE, fail, ok } from "./util.js";

export function registerRawTool(server: McpServer, client: DeliveryClient): void {
  server.registerTool(
    "raw_request",
    {
      title: "Raw Yango Delivery API call",
      // The delivery API has write endpoints and this tool can reach any of
      // them, so it carries the most conservative annotation.
      annotations: DESTRUCTIVE,
      description:
        "Escape hatch: a direct call to any method of the Yango Delivery claims B2B API — for " +
        "endpoints without a dedicated tool (tariffs, delivery-methods, claims/proof-of-delivery/info, " +
        "claims/edit, claims/apply-changes, claims/return, claims/bulk_info, claims/journal, …). " +
        'Paths are relative to the API root, e.g. "b2b/cargo/integration/v2/tariffs". query becomes ' +
        "the query string, body is sent as JSON. CAUTION: this tool can perform state-changing " +
        "operations; 5xx/network errors are retried only for GETs.",
      inputSchema: {
        path: z
          .string()
          .min(1)
          .describe('Relative API path, e.g. "b2b/cargo/integration/v2/claims/bulk_info".'),
        method: z.enum(["GET", "POST"]).optional().describe("HTTP method; defaults to POST."),
        query: z
          .record(z.union([z.string(), z.number(), z.boolean()]))
          .optional()
          .describe('Query-string parameters, e.g. {"claim_id": "..."}.'),
        body: z.record(z.any()).optional().describe("JSON request body."),
      },
    },
    async ({ path, method, query, body }) => {
      try {
        const m = (method ?? "POST") as HttpMethod;
        return ok(await client.request(m, path, { query, body }));
      } catch (e) {
        return fail(e);
      }
    },
  );
}
