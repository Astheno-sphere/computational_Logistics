# Yango Delivery: Get confirmation code — MCP tool

**Yango Delivery MCP tool:** Pickup/delivery confirmation code for the current point of the claim (when a code applies).

Technical name: `get_confirmation_code`

## What task it solves

> I want to get confirmation code.

Pickup/delivery confirmation code for the current point of the claim (when a code applies).

## When to use it

Use this capability when you need “Get confirmation code” without doing the same work manually in the Yango Delivery interface. It runs only when an AI client calls it.

## What to provide

- `claim_id` — **required**. Claim id (claim_id, 32–64 characters) from the create_claim or search_claims response.

## What it returns

Returns code (string) and attempts (remaining code entry attempts).

## What changes in Yango Delivery

The tool reads Yango Delivery data and does not change it.

## Example request

> Get confirmation code in Yango Delivery. Ask for any required identifiers that are missing.

## Errors and limitations

404 — claim not found or issuing a confirmation code via the API is prohibited.

Access also depends on token permissions, quotas, and upstream API limits.

## Related MCP tools

- [Get courier phone](./get-courier-phone.md) — `get_courier_phone`
- [Get courier position](./get-performer-position.md) — `get_performer_position`
- [Get per-point ETAs](./get-points-eta.md) — `get_points_eta`
- [Get tracking links](./get-tracking-links.md) — `get_tracking_links`

## Technical details

- **Impact:** read-only
- **Group:** Tracking and contact
- **Description source:** `get_confirmation_code` registration in `src/tools/tracking.ts`
- [Full technical reference](../TOOLS.md)
- [All MCP capabilities](./index.md)
