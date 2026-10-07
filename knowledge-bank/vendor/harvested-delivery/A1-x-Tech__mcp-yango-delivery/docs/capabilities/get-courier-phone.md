# Yango Delivery: Get courier phone — MCP tool

**Yango Delivery MCP tool:** Temporary forwarded phone number to call the courier of an active claim: phone (e.g.

Technical name: `get_courier_phone`

## What task it solves

> I want to get courier phone.

Temporary forwarded phone number to call the courier of an active claim: phone (e.g.

## When to use it

Use this capability when you need “Get courier phone” without doing the same work manually in the Yango Delivery interface. It runs only when an AI client calls it.

## What to provide

- `claim_id` — **required**. Claim id (claim_id, 32–64 characters) from the create_claim or search_claims response.
- `point_id` — **optional**. Route point the contact person calls from (int64 point id).

## What it returns

Returns compact JSON from the upstream API or a clear MCP tool error. The exact fields depend on the operation and are documented in the technical reference.

## What changes in Yango Delivery

The tool reads Yango Delivery data and does not change it.

## Example request

> Get courier phone in Yango Delivery. Ask for any required identifiers that are missing.

## Errors and limitations

"+79099999998"), ext (extension, e.g. "0163") and ttl_seconds (how long the number stays operational). Errors: 400 invalid_point_phone; 404 — claim or courier not found; 409 inappropriate_status (the order is already completed).

Access also depends on token permissions, quotas, and upstream API limits.

## Related MCP tools

- [Get confirmation code](./get-confirmation-code.md) — `get_confirmation_code`
- [Get courier position](./get-performer-position.md) — `get_performer_position`
- [Get per-point ETAs](./get-points-eta.md) — `get_points_eta`
- [Get tracking links](./get-tracking-links.md) — `get_tracking_links`

## Technical details

- **Impact:** read-only
- **Group:** Tracking and contact
- **Description source:** `get_courier_phone` registration in `src/tools/tracking.ts`
- [Full technical reference](../TOOLS.md)
- [All MCP capabilities](./index.md)
