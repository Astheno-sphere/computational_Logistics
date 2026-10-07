# Yango Delivery: Get claim info — MCP tool

**Yango Delivery MCP tool:** Full claim information: status, version (needed for accept/cancel), items, route_points (with visit status), pricing {offer, final_price, currency}, performer_info (courier name, vehicle, transport type), eta, created_ts/updated_ts.

Technical name: `get_claim`

## What task it solves

> I want to get claim info.

Full claim information: status, version (needed for accept/cancel), items, route_points (with visit status), pricing {offer, final_price, currency}, performer_info (courier name, vehicle, transport type), eta, created_ts/updated_ts.

## When to use it

Use this capability when you need “Get claim info” without doing the same work manually in the Yango Delivery interface. It runs only when an AI client calls it.

## What to provide

- `claim_id` — **required**. Claim id (claim_id, 32–64 characters) from the create_claim or search_claims response.

## What it returns

Returns compact JSON from the upstream API or a clear MCP tool error. The exact fields depend on the operation and are documented in the technical reference.

## What changes in Yango Delivery

The tool reads Yango Delivery data and does not change it.

## Example request

> Get claim info in Yango Delivery. Ask for any required identifiers that are missing.

## Errors and limitations

Known statuses: new, estimating, estimating_failed, ready_for_approval, accepted, performer_lookup, performer_draft, performer_found, performer_not_found, pickup_arrived, ready_for_pickup_confirmation, pickuped, delivery_arrived, ready_for_delivery_confirmation, delivered, delivered_finish, pay_waiting, returning, return_arrived, ready_for_return_confirmation, returned, returned_finish, failed, cancelled, cancelled_with_payment, cancelled_by_taxi, cancelled_with_items_on_hands. CAUTION: estimation errors can arrive as an error_messages array [{code, message}] inside a successful 200 response — check both the HTTP error and this field.

Access also depends on token permissions, quotas, and upstream API limits.

## Related MCP tools

- [Accept a claim](./accept-claim.md) — `accept_claim`
- [Cancel a claim](./cancel-claim.md) — `cancel_claim`
- [Estimate delivery price](./check-price.md) — `check_price`
- [Create a delivery claim](./create-claim.md) — `create_claim`

## Technical details

- **Impact:** read-only
- **Group:** Delivery lifecycle
- **Description source:** `get_claim` registration in `src/tools/claims.ts`
- [Full technical reference](../TOOLS.md)
- [All MCP capabilities](./index.md)
