import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import type { DeliveryClient } from "../client.js";
import {
  cargoTypeEnum,
  claimId,
  DESTRUCTIVE,
  fail,
  ok,
  READ_ONLY,
  rfc3339Date,
  taxiClassEnum,
  WRITE,
} from "./util.js";

/**
 * Known claim statuses (for descriptions; the search filter is a plain string).
 * The docs reference a 24-value enum without listing it in full — this list is
 * partially extrapolated, so treat unknown statuses as possible.
 */
const CLAIM_STATUSES =
  "new, estimating, estimating_failed, ready_for_approval, accepted, performer_lookup, " +
  "performer_draft, performer_found, performer_not_found, pickup_arrived, " +
  "ready_for_pickup_confirmation, pickuped, delivery_arrived, ready_for_delivery_confirmation, " +
  "delivered, delivered_finish, pay_waiting, returning, return_arrived, " +
  "ready_for_return_confirmation, returned, returned_finish, failed, cancelled, " +
  "cancelled_with_payment, cancelled_by_taxi, cancelled_with_items_on_hands";

export function registerClaimsTools(server: McpServer, client: DeliveryClient): void {
  server.registerTool(
    "check_price",
    {
      title: "Estimate delivery price",
      annotations: READ_ONLY,
      description:
        "Preliminary delivery cost estimate WITHOUT creating a claim — the pricing method for " +
        "countries outside Russia. Returns price (a decimal STRING, not a number!), currency_rules " +
        "{code, sign, template}, distance_meters, eta (minutes) and zone_id. Route points take " +
        "[longitude, latitude] coordinates and/or a full address string. Typical errors: " +
        "400 address_not_found (address not recognized), 409 estimating.cant_construct_route " +
        "(no route between the points), 409 estimating.requirement_unavailable.",
      inputSchema: {
        route_points: z
          .array(
            z
              .object({
                id: z.number().int().optional().describe("Point id (referenced by the items' pickup_point/dropoff_point)."),
                coordinates: z
                  .array(z.number())
                  .length(2)
                  .optional()
                  .describe("Point coordinates as [longitude, latitude], e.g. [69.279737, 41.311151]."),
                fullname: z
                  .string()
                  .optional()
                  .describe('Full address as a string, e.g. "Tashkent, Amir Timur Avenue, 107".'),
              })
              .passthrough(),
          )
          .min(1)
          .describe("Route points: coordinates and/or an address (at least one of the two per point)."),
        items: z
          .array(
            z
              .object({
                quantity: z.number().int().min(1).describe("Number of item units."),
                size: z
                  .object({
                    length: z.number().describe("Length, meters."),
                    width: z.number().describe("Width, meters."),
                    height: z.number().describe("Height, meters."),
                  })
                  .optional()
                  .describe("Dimensions of one unit, in METERS."),
                weight: z.number().optional().describe("Weight of one unit, kg."),
                pickup_point: z.number().int().optional().describe("Pickup point id from route_points."),
                dropoff_point: z.number().int().optional().describe("Drop-off point id from route_points."),
              })
              .passthrough(),
          )
          .min(1)
          .describe("Items / cargo places."),
        requirements: z
          .object({
            taxi_class: taxiClassEnum().optional().describe("Delivery class: courier, express or cargo."),
            cargo_type: cargoTypeEnum().optional().describe("Vehicle body type for cargo: van, lcv_m, lcv_l."),
          })
          .passthrough()
          .optional()
          .describe("Delivery requirements (class, body type, extra options)."),
        skip_door_to_door: z
          .boolean()
          .optional()
          .describe("true — disable door-to-door delivery (default false)."),
      },
    },
    async (body) => {
      try {
        return ok(await client.checkPrice(body));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "create_claim",
    {
      title: "Create a delivery claim",
      annotations: WRITE,
      description:
        "Creates a delivery claim. IMPORTANT: the claim is NOT dispatched immediately — it goes " +
        "through estimation (status: new → estimating → ready_for_approval) and must then be " +
        "confirmed with accept_claim, or pass auto_accept=true. Returns id (claim_id), status, " +
        "version, route_points, pricing, created_ts. Verify success via get_claim: estimation " +
        "errors can arrive as an error_messages array inside a 200 response. request_id makes the " +
        "call idempotent: a retry with the same request_id returns the same claim, not a duplicate.",
      inputSchema: {
        request_id: z
          .string()
          .min(1)
          .max(128)
          .optional()
          .describe(
            "Idempotency token (1–128 characters, a query parameter). A UUID is generated automatically when omitted.",
          ),
        items: z
          .array(
            z
              .object({
                title: z.string().describe("Item name."),
                quantity: z.number().int().min(1).describe("Number of units."),
                cost_value: z.string().describe('Price per unit as a decimal string, e.g. "350.00".'),
                cost_currency: z.string().describe('ISO 4217 currency code, e.g. "UZS".'),
                pickup_point: z.number().int().optional().describe("point_id of the pickup point from route_points."),
                dropoff_point: z.number().int().optional().describe("point_id of the drop-off point from route_points."),
                weight: z.number().optional().describe("Weight of one unit, kg."),
                size: z
                  .object({
                    length: z.number().describe("Length, meters."),
                    width: z.number().describe("Width, meters."),
                    height: z.number().describe("Height, meters."),
                  })
                  .optional()
                  .describe("Dimensions of one unit, meters."),
                extra_id: z.string().optional().describe("External SKU / item id in the merchant's system."),
              })
              .passthrough(),
          )
          .min(1)
          .describe("Items to deliver."),
        route_points: z
          .array(
            z
              .object({
                point_id: z.number().int().describe("Point id, unique within the claim."),
                type: z
                  .enum(["source", "destination", "return"])
                  .describe("Point type: source — pickup, destination — hand-over, return — return point."),
                visit_order: z.number().int().min(1).describe("Visit order, starting from 1."),
                contact: z
                  .object({
                    name: z.string().describe("Contact person name."),
                    phone: z.string().describe("Phone in international format, e.g. +998901234567."),
                    email: z.string().optional().describe("Contact person email."),
                  })
                  .passthrough()
                  .describe("Contact at the point."),
                address: z
                  .object({
                    fullname: z.string().describe("Full address as a string."),
                    coordinates: z
                      .array(z.number())
                      .length(2)
                      .optional()
                      .describe("Coordinates [longitude, latitude] — improve geocoding accuracy."),
                  })
                  .passthrough()
                  .describe("Point address."),
              })
              .passthrough(),
          )
          .min(2)
          .describe("Route points (at least 2): a source and a destination at minimum."),
        client_requirements: z
          .object({
            taxi_class: taxiClassEnum().describe("Delivery class: courier, express or cargo."),
            cargo_type: cargoTypeEnum().optional().describe("Vehicle body type (for cargo): van, lcv_m, lcv_l."),
            cargo_loaders: z.number().int().min(0).optional().describe("Number of loaders (for cargo)."),
            pro_courier: z.boolean().optional().describe("true — experienced (pro) courier."),
          })
          .passthrough()
          .optional()
          .describe("Delivery requirements. Optional per the docs, but always passing taxi_class is safest."),
        emergency_contact: z
          .object({
            name: z.string().describe("Contact name."),
            phone: z.string().describe("Contact phone."),
          })
          .passthrough()
          .optional()
          .describe("Contact to reach if there is a problem with the delivery."),
        callback_properties: z
          .object({
            callback_url: z.string().describe("URL that receives claim status-change notifications."),
          })
          .passthrough()
          .optional()
          .describe("Webhook for claim status changes."),
        due: rfc3339Date()
          .optional()
          .describe("Desired courier arrival time (ISO-8601), e.g. 2026-08-10T12:00:00+05:00."),
        comment: z.string().max(7000).optional().describe("Comment for the courier (up to 7000 characters)."),
        shipping_document: z.string().optional().describe("Accompanying shipping document reference."),
        skip_door_to_door: z.boolean().optional().describe("true — no door-to-door: hand over at the entrance."),
        skip_client_notify: z.boolean().optional().describe("true — do not send SMS/push notifications to the recipient."),
        skip_emergency_notify: z.boolean().optional().describe("true — do not notify the emergency contact."),
        skip_act: z.boolean().optional().describe("true — do not generate a handover act."),
        optional_return: z
          .boolean()
          .optional()
          .describe("true — the courier does not return items to the sender when hand-over fails."),
        same_day_data: z
          .record(z.any())
          .optional()
          .describe("Same-day delivery settings: {delivery_interval: {from, to}} (a non-Russia feature)."),
        auto_accept: z
          .boolean()
          .optional()
          .describe("true — confirm the claim automatically after successful estimation (no accept_claim needed)."),
      },
    },
    async ({ request_id, ...body }) => {
      try {
        return ok(await client.createClaim({ request_id, body }));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "get_claim",
    {
      title: "Get claim info",
      annotations: READ_ONLY,
      description:
        "Full claim information: status, version (needed for accept/cancel), items, route_points " +
        "(with visit status), pricing {offer, final_price, currency}, performer_info (courier name, " +
        `vehicle, transport type), eta, created_ts/updated_ts. Known statuses: ${CLAIM_STATUSES}. ` +
        "CAUTION: estimation errors can arrive as an error_messages array [{code, message}] inside " +
        "a successful 200 response — check both the HTTP error and this field.",
      inputSchema: {
        claim_id: claimId(),
      },
    },
    async ({ claim_id }) => {
      try {
        return ok(await client.getClaim(claim_id));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "accept_claim",
    {
      title: "Accept a claim",
      annotations: WRITE,
      description:
        "Confirms a claim after successful estimation (status ready_for_approval) and starts the " +
        "courier search — from this point the delivery is actually ordered. The priced offer inside " +
        "a claim expires ~10 minutes after estimation, so accept promptly. version comes from " +
        "get_claim. 409 errors: inappropriate_status (wrong claim status), old_version (stale " +
        "version — re-read the claim), offer_expired (re-create the claim), state_mismatch.",
      inputSchema: {
        claim_id: claimId(),
        version: z.number().int().describe("Claim version from the latest get_claim response."),
      },
    },
    async ({ claim_id, version }) => {
      try {
        return ok(await client.acceptClaim({ claim_id, version }));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "get_cancel_info",
    {
      title: "Get cancellation terms",
      annotations: READ_ONLY,
      description:
        "Cancellation terms for a claim — call BEFORE cancel_claim. Returns cancel_state: " +
        "free (free of charge), paid (a fee applies — price/price_with_vat and currency are " +
        "returned) or unavailable (the claim can no longer be cancelled).",
      inputSchema: {
        claim_id: claimId(),
      },
    },
    async ({ claim_id }) => {
      try {
        return ok(await client.cancelInfo(claim_id));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "cancel_claim",
    {
      title: "Cancel a claim",
      annotations: DESTRUCTIVE,
      description:
        "Cancels a claim (including an already accepted one). Get the terms with get_cancel_info " +
        "first and pass its cancel_state: with paid the cancellation fee is charged. version comes " +
        "from get_claim. 409 errors: old_version, inappropriate_status, free_cancel_is_unavailable.",
      inputSchema: {
        claim_id: claimId(),
        version: z.number().int().describe("Claim version from the latest get_claim response."),
        cancel_state: z
          .enum(["free", "paid"])
          .describe("Cancellation mode from get_cancel_info: free — no charge, paid — a fee applies."),
      },
    },
    async ({ claim_id, version, cancel_state }) => {
      try {
        return ok(await client.cancelClaim({ claim_id, version, cancel_state }));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "search_claims",
    {
      title: "Search claims",
      annotations: READ_ONLY,
      description:
        "Search claims by filters with pagination (sorted by creation date). Returns claims (each " +
        "shaped like get_claim) and a cursor for the next page. Pagination: either offset/limit, " +
        "or cursor-based — pass the cursor from the previous response (other filters are then " +
        "not needed).",
      inputSchema: {
        offset: z.number().int().min(0).optional().describe("Offset for offset/limit pagination (default 0)."),
        limit: z.number().int().min(0).max(1000).optional().describe("How many claims to return (up to 1000)."),
        claim_id: z.string().optional().describe("Filter by claim id."),
        phone: z.string().max(30).optional().describe("Filter by a phone number from the claim contacts."),
        status: z
          .string()
          .optional()
          .describe(`Filter by status. Known statuses: ${CLAIM_STATUSES}.`),
        state: z
          .enum(["active", "finished", "delayed"])
          .optional()
          .describe("Status group: active, finished or delayed claims."),
        created_from: rfc3339Date().optional().describe("Created no earlier than (ISO-8601)."),
        created_to: rfc3339Date().optional().describe("Created no later than (ISO-8601)."),
        due_from: rfc3339Date().optional().describe("Courier arrival no earlier than (ISO-8601)."),
        due_to: rfc3339Date().optional().describe("Courier arrival no later than (ISO-8601)."),
        external_order_id: z.string().max(512).optional().describe("Filter by the external order id."),
        cursor: z
          .string()
          .optional()
          .describe("Cursor from the previous response — an alternative to offset/limit."),
      },
    },
    async (filters) => {
      try {
        return ok(await client.searchClaims(filters));
      } catch (e) {
        return fail(e);
      }
    },
  );
}
