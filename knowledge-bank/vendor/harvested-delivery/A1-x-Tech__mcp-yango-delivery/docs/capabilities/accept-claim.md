# Yango Delivery: Accept a claim — MCP tool

**Yango Delivery MCP tool:** Confirms a claim after successful estimation (status ready_for_approval) and starts the courier search — from this point the delivery is actually ordered.

Technical name: `accept_claim`

## What task it solves

> I want to accept a claim.

Confirms a claim after successful estimation (status ready_for_approval) and starts the courier search — from this point the delivery is actually ordered.

## When to use it

Use this capability when you need “Accept a claim” without doing the same work manually in the Yango Delivery interface. It runs only when an AI client calls it.

## What to provide

- `claim_id` — **required**. Claim id (claim_id, 32–64 characters) from the create_claim or search_claims response.
- `version` — **required**. Claim version from the latest get_claim response.

## What it returns

Returns compact JSON from the upstream API or a clear MCP tool error. The exact fields depend on the operation and are documented in the technical reference.

## What changes in Yango Delivery

The tool changes real Yango Delivery data as described above. The server does not promise an automatic rollback.

## Example request

> Accept a claim in Yango Delivery. Ask for any required identifiers that are missing.

## Errors and limitations

The priced offer inside a claim expires ~10 minutes after estimation, so accept promptly. version comes from get_claim. 409 errors: inappropriate_status (wrong claim status), old_version (stale version — re-read the claim), offer_expired (re-create the claim), state_mismatch.

Access also depends on token permissions, quotas, and upstream API limits.

## Related MCP tools

- [Cancel a claim](./cancel-claim.md) — `cancel_claim`
- [Estimate delivery price](./check-price.md) — `check_price`
- [Create a delivery claim](./create-claim.md) — `create_claim`
- [Get cancellation terms](./get-cancel-info.md) — `get_cancel_info`

## Technical details

- **Impact:** changes data
- **Group:** Delivery lifecycle
- **Description source:** `accept_claim` registration in `src/tools/claims.ts`
- [Full technical reference](../TOOLS.md)
- [All MCP capabilities](./index.md)
