# Yango Delivery: Cancel a claim — MCP tool

**Yango Delivery MCP tool:** Cancels a claim (including an already accepted one).

Technical name: `cancel_claim`

## What task it solves

> I want to cancel a claim.

Cancels a claim (including an already accepted one).

## When to use it

Use this capability when you need “Cancel a claim” without doing the same work manually in the Yango Delivery interface. It runs only when an AI client calls it.

## What to provide

- `claim_id` — **required**. Claim id (claim_id, 32–64 characters) from the create_claim or search_claims response.
- `version` — **required**. Claim version from the latest get_claim response.
- `cancel_state` — **required**. Cancellation mode from get_cancel_info: free — no charge, paid — a fee applies.

## What it returns

Returns compact JSON from the upstream API or a clear MCP tool error. The exact fields depend on the operation and are documented in the technical reference.

## What changes in Yango Delivery

The source marks the entire “Cancel a claim” call as destructive. The exact effect depends on the selected action and is described below; review the parameters and reversibility before calling it.

## Example request

> Cancel a claim in Yango Delivery. Ask for any required identifiers that are missing. Show me the exact change and wait for confirmation first.

## Errors and limitations

Get the terms with get_cancel_info first and pass its cancel_state: with paid the cancellation fee is charged. version comes from get_claim. 409 errors: old_version, inappropriate_status, free_cancel_is_unavailable.

Access also depends on token permissions, quotas, and upstream API limits.

## Related MCP tools

- [Accept a claim](./accept-claim.md) — `accept_claim`
- [Estimate delivery price](./check-price.md) — `check_price`
- [Create a delivery claim](./create-claim.md) — `create_claim`
- [Get cancellation terms](./get-cancel-info.md) — `get_cancel_info`

## Technical details

- **Impact:** destructive operation
- **Group:** Delivery lifecycle
- **Description source:** `cancel_claim` registration in `src/tools/claims.ts`
- [Full technical reference](../TOOLS.md)
- [All MCP capabilities](./index.md)
