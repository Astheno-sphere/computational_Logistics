# Yango Delivery: Raw Yango Delivery API call — MCP tool

**Yango Delivery MCP tool:** Escape hatch: a direct call to any method of the Yango Delivery claims B2B API — for endpoints without a dedicated tool (tariffs, delivery-methods, claims/proof-of-delivery/info, claims/edit, claims/apply-changes, claims/return, claims/bulk_info, claims/journal, …).

Technical name: `raw_request`

## What task it solves

> I want to raw Yango Delivery API call.

Escape hatch: a direct call to any method of the Yango Delivery claims B2B API — for endpoints without a dedicated tool (tariffs, delivery-methods, claims/proof-of-delivery/info, claims/edit, claims/apply-changes, claims/return, claims/bulk_info, claims/journal, …).

## When to use it

Use this capability when you need “Raw Yango Delivery API call” without doing the same work manually in the Yango Delivery interface. It runs only when an AI client calls it.

## What to provide

- `path` — **required**. Relative API path, e.g. "b2b/cargo/integration/v2/claims/bulk_info".
- `method` — **optional**. HTTP method; defaults to POST.
- `query` — **optional**. Query-string parameters, e.g. {"claim_id": "..."}.
- `body` — **optional**. JSON request body.

## What it returns

Returns compact JSON from the upstream API or a clear MCP tool error. The exact fields depend on the operation and are documented in the technical reference.

## What changes in Yango Delivery

The source marks the entire “Raw Yango Delivery API call” call as destructive. The exact effect depends on the selected action and is described below; review the parameters and reversibility before calling it.

## Example request

> Raw Yango Delivery API call in Yango Delivery. Ask for any required identifiers that are missing. Show me the exact change and wait for confirmation first.

## Errors and limitations

Paths are relative to the API root, e.g. "b2b/cargo/integration/v2/tariffs". query becomes the query string, body is sent as JSON. CAUTION: this tool can perform state-changing operations; 5xx/network errors are retried only for GETs.

Access also depends on token permissions, quotas, and upstream API limits.

## Related MCP tools

There are no other dedicated tools in this group.

## Technical details

- **Impact:** destructive operation
- **Group:** Additional API methods
- **Description source:** `raw_request` registration in `src/tools/raw.ts`
- [Full technical reference](../TOOLS.md)
- [All MCP capabilities](./index.md)
