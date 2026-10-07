import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import type { DeliveryClient } from "../client.js";
import { claimId, fail, ok, READ_ONLY } from "./util.js";

export function registerTrackingTools(server: McpServer, client: DeliveryClient): void {
  server.registerTool(
    "get_performer_position",
    {
      title: "Get courier position",
      annotations: READ_ONLY,
      description:
        "Current courier geoposition for an active claim: position {lat, lon, timestamp (unix), " +
        "accuracy, speed (m/s), direction (0–360°, clockwise from north)} and route_points with " +
        "sharing_link. Errors: 404 — claim or courier position not found, 409 — the claim is not " +
        "active or no courier is assigned.",
      inputSchema: {
        claim_id: claimId(),
      },
    },
    async ({ claim_id }) => {
      try {
        return ok(await client.performerPosition(claim_id));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "get_tracking_links",
    {
      title: "Get tracking links",
      annotations: READ_ONLY,
      description:
        "Public courier tracking links — safe to share with the recipient. Returns route_points " +
        "[{id, type, visit_order, sharing_link}]; sharing_link is available only for " +
        "type=destination points. 409 errors: inappropriate_status, unknown_tracking_links.",
      inputSchema: {
        claim_id: claimId(),
      },
    },
    async ({ claim_id }) => {
      try {
        return ok(await client.trackingLinks(claim_id));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "get_points_eta",
    {
      title: "Get per-point ETAs",
      annotations: READ_ONLY,
      description:
        "Expected arrival times per route point plus the current courier position. Works only " +
        "while the claim is active and a courier is assigned. Returns route_points [{id, address, " +
        "type, visit_order, visit_status (pending|arrived|visited|skipped), visited_at {expected, " +
        "expected_waiting_time_sec, actual}}] and performer_position. Errors: 404 not_found; " +
        "409 — the claim is inactive, has no courier, or the courier position is unknown.",
      inputSchema: {
        claim_id: claimId(),
      },
    },
    async ({ claim_id }) => {
      try {
        return ok(await client.pointsEta(claim_id));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "get_courier_phone",
    {
      title: "Get courier phone",
      annotations: READ_ONLY,
      description:
        "Temporary forwarded phone number to call the courier of an active claim: phone " +
        '(e.g. "+79099999998"), ext (extension, e.g. "0163") and ttl_seconds (how long the number ' +
        "stays operational). Errors: 400 invalid_point_phone; 404 — claim or courier not found; " +
        "409 inappropriate_status (the order is already completed).",
      inputSchema: {
        claim_id: claimId(),
        point_id: z
          .number()
          .int()
          .optional()
          .describe("Route point the contact person calls from (int64 point id)."),
      },
    },
    async ({ claim_id, point_id }) => {
      try {
        return ok(await client.courierPhone({ claim_id, point_id }));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "get_confirmation_code",
    {
      title: "Get confirmation code",
      annotations: READ_ONLY,
      description:
        "Pickup/delivery confirmation code for the current point of the claim (when a code " +
        "applies). Returns code (string) and attempts (remaining code entry attempts). " +
        "404 — claim not found or issuing a confirmation code via the API is prohibited.",
      inputSchema: {
        claim_id: claimId(),
      },
    },
    async ({ claim_id }) => {
      try {
        return ok(await client.confirmationCode(claim_id));
      } catch (e) {
        return fail(e);
      }
    },
  );
}
