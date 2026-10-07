# Yango Delivery: Estimate delivery price — MCP tool

**Yango Delivery MCP tool:** Preliminary delivery cost estimate WITHOUT creating a claim — the pricing method for countries outside Russia.

Technical name: `check_price`

## What task it solves

> I want to estimate delivery price.

Preliminary delivery cost estimate WITHOUT creating a claim — the pricing method for countries outside Russia.

## When to use it

Use this capability when you need “Estimate delivery price” without doing the same work manually in the Yango Delivery interface. It runs only when an AI client calls it.

## What to provide

- `route_points` — **required**. Route points: coordinates and/or an address (at least one of the two per point).
- `items` — **required**. Items / cargo places.
- `requirements` — **optional**. Delivery requirements (class, body type, extra options).
- `skip_door_to_door` — **optional**. true — disable door-to-door delivery (default false).

## What it returns

Returns price (a decimal STRING, not a number!), currency_rules {code, sign, template}, distance_meters, eta (minutes) and zone_id.

## What changes in Yango Delivery

The tool reads Yango Delivery data and does not change it.

## Example request

> Estimate delivery price in Yango Delivery. Ask for any required identifiers that are missing.

## Errors and limitations

Route points take [longitude, latitude] coordinates and/or a full address string. Typical errors: 400 address_not_found (address not recognized), 409 estimating.cant_construct_route (no route between the points), 409 estimating.requirement_unavailable.

Access also depends on token permissions, quotas, and upstream API limits.

## Related MCP tools

- [Accept a claim](./accept-claim.md) — `accept_claim`
- [Cancel a claim](./cancel-claim.md) — `cancel_claim`
- [Create a delivery claim](./create-claim.md) — `create_claim`
- [Get cancellation terms](./get-cancel-info.md) — `get_cancel_info`

## Technical details

- **Impact:** read-only
- **Group:** Delivery lifecycle
- **Description source:** `check_price` registration in `src/tools/claims.ts`
- [Full technical reference](../TOOLS.md)
- [All MCP capabilities](./index.md)
