# Yango Delivery: Get per-point ETAs — MCP tool

**Yango Delivery MCP tool:** Expected arrival times per route point plus the current courier position.

Technical name: `get_points_eta`

## What task it solves

> I want to get per-point ETAs.

Expected arrival times per route point plus the current courier position.

## When to use it

Use this capability when you need “Get per-point ETAs” without doing the same work manually in the Yango Delivery interface. It runs only when an AI client calls it.

## What to provide

- `claim_id` — **required**. Claim id (claim_id, 32–64 characters) from the create_claim or search_claims response.

## What it returns

Returns route_points [{id, address, type, visit_order, visit_status (pending|arrived|visited|skipped), visited_at {expected, expected_waiting_time_sec, actual}}] and performer_position.

## What changes in Yango Delivery

The tool reads Yango Delivery data and does not change it.

## Example request

> Get per-point ETAs in Yango Delivery. Ask for any required identifiers that are missing.

## Errors and limitations

Works only while the claim is active and a courier is assigned. Errors: 404 not_found; 409 — the claim is inactive, has no courier, or the courier position is unknown.

Access also depends on token permissions, quotas, and upstream API limits.

## Related MCP tools

- [Get confirmation code](./get-confirmation-code.md) — `get_confirmation_code`
- [Get courier phone](./get-courier-phone.md) — `get_courier_phone`
- [Get courier position](./get-performer-position.md) — `get_performer_position`
- [Get tracking links](./get-tracking-links.md) — `get_tracking_links`

## Technical details

- **Impact:** read-only
- **Group:** Tracking and contact
- **Description source:** `get_points_eta` registration in `src/tools/tracking.ts`
- [Full technical reference](../TOOLS.md)
- [All MCP capabilities](./index.md)
