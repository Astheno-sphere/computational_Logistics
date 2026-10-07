# Yango Delivery: Get courier position — MCP tool

**Yango Delivery MCP tool:** Current courier geoposition for an active claim: position {lat, lon, timestamp (unix), accuracy, speed (m/s), direction (0–360°, clockwise from north)} and route_points with sharing_link.

Technical name: `get_performer_position`

## What task it solves

> I want to get courier position.

Current courier geoposition for an active claim: position {lat, lon, timestamp (unix), accuracy, speed (m/s), direction (0–360°, clockwise from north)} and route_points with sharing_link.

## When to use it

Use this capability when you need “Get courier position” without doing the same work manually in the Yango Delivery interface. It runs only when an AI client calls it.

## What to provide

- `claim_id` — **required**. Claim id (claim_id, 32–64 characters) from the create_claim or search_claims response.

## What it returns

Returns compact JSON from the upstream API or a clear MCP tool error. The exact fields depend on the operation and are documented in the technical reference.

## What changes in Yango Delivery

The tool reads Yango Delivery data and does not change it.

## Example request

> Get courier position in Yango Delivery. Ask for any required identifiers that are missing.

## Errors and limitations

Errors: 404 — claim or courier position not found, 409 — the claim is not active or no courier is assigned.

Access also depends on token permissions, quotas, and upstream API limits.

## Related MCP tools

- [Get confirmation code](./get-confirmation-code.md) — `get_confirmation_code`
- [Get courier phone](./get-courier-phone.md) — `get_courier_phone`
- [Get per-point ETAs](./get-points-eta.md) — `get_points_eta`
- [Get tracking links](./get-tracking-links.md) — `get_tracking_links`

## Technical details

- **Impact:** read-only
- **Group:** Tracking and contact
- **Description source:** `get_performer_position` registration in `src/tools/tracking.ts`
- [Full technical reference](../TOOLS.md)
- [All MCP capabilities](./index.md)
