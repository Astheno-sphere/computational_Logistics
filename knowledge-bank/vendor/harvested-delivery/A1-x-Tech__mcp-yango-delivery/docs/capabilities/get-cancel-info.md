# Yango Delivery: Get cancellation terms — MCP tool

**Yango Delivery MCP tool:** Cancellation terms for a claim — call BEFORE cancel_claim.

Technical name: `get_cancel_info`

## What task it solves

> I want to get cancellation terms.

Cancellation terms for a claim — call BEFORE cancel_claim.

## When to use it

Use this capability when you need “Get cancellation terms” without doing the same work manually in the Yango Delivery interface. It runs only when an AI client calls it.

## What to provide

- `claim_id` — **required**. Claim id (claim_id, 32–64 characters) from the create_claim or search_claims response.

## What it returns

Returns cancel_state: free (free of charge), paid (a fee applies — price/price_with_vat and currency are returned) or unavailable (the claim can no longer be cancelled).

## What changes in Yango Delivery

The tool reads Yango Delivery data and does not change it.

## Example request

> Get cancellation terms in Yango Delivery. Ask for any required identifiers that are missing.

## Errors and limitations

Check required parameters, token permissions, and current upstream API limits.

Access also depends on token permissions, quotas, and upstream API limits.

## Related MCP tools

- [Accept a claim](./accept-claim.md) — `accept_claim`
- [Cancel a claim](./cancel-claim.md) — `cancel_claim`
- [Estimate delivery price](./check-price.md) — `check_price`
- [Create a delivery claim](./create-claim.md) — `create_claim`

## Technical details

- **Impact:** read-only
- **Group:** Delivery lifecycle
- **Description source:** `get_cancel_info` registration in `src/tools/claims.ts`
- [Full technical reference](../TOOLS.md)
- [All MCP capabilities](./index.md)
