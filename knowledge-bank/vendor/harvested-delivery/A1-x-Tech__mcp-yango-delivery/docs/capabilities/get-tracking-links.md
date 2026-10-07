# Yango Delivery: Get tracking links — MCP tool

**Yango Delivery MCP tool:** Public courier tracking links — safe to share with the recipient.

Technical name: `get_tracking_links`

## What task it solves

> I want to get tracking links.

Public courier tracking links — safe to share with the recipient.

## When to use it

Use this capability when you need “Get tracking links” without doing the same work manually in the Yango Delivery interface. It runs only when an AI client calls it.

## What to provide

- `claim_id` — **required**. Claim id (claim_id, 32–64 characters) from the create_claim or search_claims response.

## What it returns

Returns route_points [{id, type, visit_order, sharing_link}]; sharing_link is available only for type=destination points.

## What changes in Yango Delivery

The tool reads Yango Delivery data and does not change it.

## Example request

> Get tracking links in Yango Delivery. Ask for any required identifiers that are missing.

## Errors and limitations

409 errors: inappropriate_status, unknown_tracking_links.

Access also depends on token permissions, quotas, and upstream API limits.

## Related MCP tools

- [Get confirmation code](./get-confirmation-code.md) — `get_confirmation_code`
- [Get courier phone](./get-courier-phone.md) — `get_courier_phone`
- [Get courier position](./get-performer-position.md) — `get_performer_position`
- [Get per-point ETAs](./get-points-eta.md) — `get_points_eta`

## Technical details

- **Impact:** read-only
- **Group:** Tracking and contact
- **Description source:** `get_tracking_links` registration in `src/tools/tracking.ts`
- [Full technical reference](../TOOLS.md)
- [All MCP capabilities](./index.md)
