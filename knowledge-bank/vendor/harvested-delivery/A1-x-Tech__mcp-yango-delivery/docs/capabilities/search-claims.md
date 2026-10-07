# Yango Delivery: Search claims — MCP tool

**Yango Delivery MCP tool:** Search claims by filters with pagination (sorted by creation date).

Technical name: `search_claims`

## What task it solves

> I want to search claims.

Search claims by filters with pagination (sorted by creation date).

## When to use it

Use this capability when you need “Search claims” without doing the same work manually in the Yango Delivery interface. It runs only when an AI client calls it.

## What to provide

- `offset` — **optional**. Offset for offset/limit pagination (default 0).
- `limit` — **optional**. How many claims to return (up to 1000).
- `claim_id` — **optional**. Filter by claim id.
- `phone` — **optional**. Filter by a phone number from the claim contacts.
- `status` — **optional**. Filter by status. Known statuses: new, estimating, estimating_failed, ready_for_approval, accepted, performer_lookup, performer_draft, performer_found, performer_not_found, pickup_arrived, ready_for_pickup_confirmation, pickuped, delivery_arrived, ready_for_delivery_confirmation, delivered, delivered_finish, pay_waiting, returning, return_arrived, ready_for_return_confirmation, returned, returned_finish, failed, cancelled, cancelled_with_payment, cancelled_by_taxi, cancelled_with_items_on_hands.
- `state` — **optional**. Status group: active, finished or delayed claims.
- `created_from` — **optional**. Created no earlier than (ISO-8601).
- `created_to` — **optional**. Created no later than (ISO-8601).
- `due_from` — **optional**. Courier arrival no earlier than (ISO-8601).
- `due_to` — **optional**. Courier arrival no later than (ISO-8601).
- `external_order_id` — **optional**. Filter by the external order id.
- `cursor` — **optional**. Cursor from the previous response — an alternative to offset/limit.

## What it returns

Returns claims (each shaped like get_claim) and a cursor for the next page.

## What changes in Yango Delivery

The tool reads Yango Delivery data and does not change it.

## Example request

> Search claims in Yango Delivery. Ask for any required identifiers that are missing.

## Errors and limitations

Pagination: either offset/limit, or cursor-based — pass the cursor from the previous response (other filters are then not needed).

Access also depends on token permissions, quotas, and upstream API limits.

## Related MCP tools

- [Accept a claim](./accept-claim.md) — `accept_claim`
- [Cancel a claim](./cancel-claim.md) — `cancel_claim`
- [Estimate delivery price](./check-price.md) — `check_price`
- [Create a delivery claim](./create-claim.md) — `create_claim`

## Technical details

- **Impact:** read-only
- **Group:** Delivery lifecycle
- **Description source:** `search_claims` registration in `src/tools/claims.ts`
- [Full technical reference](../TOOLS.md)
- [All MCP capabilities](./index.md)
