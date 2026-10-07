# Yango Delivery: Create a delivery claim — MCP tool

**Yango Delivery MCP tool:** Creates a delivery claim.

Technical name: `create_claim`

## What task it solves

> I want to create a delivery claim.

Creates a delivery claim.

## When to use it

Use this capability when you need “Create a delivery claim” without doing the same work manually in the Yango Delivery interface. It runs only when an AI client calls it.

## What to provide

- `request_id` — **optional**. Idempotency token (1–128 characters, a query parameter). A UUID is generated automatically when omitted.
- `items` — **required**. Items to deliver.
- `route_points` — **required**. Route points (at least 2): a source and a destination at minimum.
- `client_requirements` — **optional**. Delivery requirements. Optional per the docs, but always passing taxi_class is safest.
- `emergency_contact` — **optional**. Contact to reach if there is a problem with the delivery.
- `callback_properties` — **optional**. Webhook for claim status changes.
- `due` — **optional**. Desired courier arrival time (ISO-8601), e.g. 2026-08-10T12:00:00+05:00.
- `comment` — **optional**. Comment for the courier (up to 7000 characters).
- `shipping_document` — **optional**. Accompanying shipping document reference.
- `skip_door_to_door` — **optional**. true — no door-to-door: hand over at the entrance.
- `skip_client_notify` — **optional**. true — do not send SMS/push notifications to the recipient.
- `skip_emergency_notify` — **optional**. true — do not notify the emergency contact.
- `skip_act` — **optional**. true — do not generate a handover act.
- `optional_return` — **optional**. true — the courier does not return items to the sender when hand-over fails.
- `same_day_data` — **optional**. Same-day delivery settings: {delivery_interval: {from, to}} (a non-Russia feature).
- `auto_accept` — **optional**. true — confirm the claim automatically after successful estimation (no accept_claim needed).

## What it returns

Returns id (claim_id), status, version, route_points, pricing, created_ts.

## What changes in Yango Delivery

The tool changes real Yango Delivery data as described above. The server does not promise an automatic rollback.

## Example request

> Create a delivery claim in Yango Delivery. Ask for any required identifiers that are missing.

## Errors and limitations

IMPORTANT: the claim is NOT dispatched immediately — it goes through estimation (status: new → estimating → ready_for_approval) and must then be confirmed with accept_claim, or pass auto_accept=true. Verify success via get_claim: estimation errors can arrive as an error_messages array inside a 200 response. request_id makes the call idempotent: a retry with the same request_id returns the same claim, not a duplicate.

Access also depends on token permissions, quotas, and upstream API limits.

## Related MCP tools

- [Accept a claim](./accept-claim.md) — `accept_claim`
- [Cancel a claim](./cancel-claim.md) — `cancel_claim`
- [Estimate delivery price](./check-price.md) — `check_price`
- [Get cancellation terms](./get-cancel-info.md) — `get_cancel_info`

## Technical details

- **Impact:** changes data
- **Group:** Delivery lifecycle
- **Description source:** `create_claim` registration in `src/tools/claims.ts`
- [Full technical reference](../TOOLS.md)
- [All MCP capabilities](./index.md)
