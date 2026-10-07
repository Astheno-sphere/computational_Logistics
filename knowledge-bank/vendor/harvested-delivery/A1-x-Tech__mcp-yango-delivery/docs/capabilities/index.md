# Yango Delivery MCP capabilities

This catalog contains 13 public pages—one for every registered MCP tool in `mcp-yango-delivery`. Each page starts with the user's task, explains the result, and states whether the call changes real data.

Use this catalog to choose a ready-made capability. Full parameter schemas and API response details remain in the [technical reference](../TOOLS.md).

## Delivery lifecycle

- [Accept a claim](./accept-claim.md) — Confirms a claim after successful estimation (status ready_for_approval) and starts the courier search — from this point the delivery is actually ordered. **Impact:** changes data.
- [Cancel a claim](./cancel-claim.md) — Cancels a claim (including an already accepted one). **Impact:** destructive operation.
- [Estimate delivery price](./check-price.md) — Preliminary delivery cost estimate WITHOUT creating a claim — the pricing method for countries outside Russia. **Impact:** read-only.
- [Create a delivery claim](./create-claim.md) — Creates a delivery claim. **Impact:** changes data.
- [Get cancellation terms](./get-cancel-info.md) — Cancellation terms for a claim — call BEFORE cancel_claim. **Impact:** read-only.
- [Get claim info](./get-claim.md) — Full claim information: status, version (needed for accept/cancel), items, route_points (with visit status), pricing {offer, final_price, currency}, performer_info (courier name, vehicle, transport type), eta, created_ts/updated_ts. **Impact:** read-only.
- [Search claims](./search-claims.md) — Search claims by filters with pagination (sorted by creation date). **Impact:** read-only.

## Tracking and contact

- [Get confirmation code](./get-confirmation-code.md) — Pickup/delivery confirmation code for the current point of the claim (when a code applies). **Impact:** read-only.
- [Get courier phone](./get-courier-phone.md) — Temporary forwarded phone number to call the courier of an active claim: phone (e.g. **Impact:** read-only.
- [Get courier position](./get-performer-position.md) — Current courier geoposition for an active claim: position {lat, lon, timestamp (unix), accuracy, speed (m/s), direction (0–360°, clockwise from north)} and route_points with sharing_link. **Impact:** read-only.
- [Get per-point ETAs](./get-points-eta.md) — Expected arrival times per route point plus the current courier position. **Impact:** read-only.
- [Get tracking links](./get-tracking-links.md) — Public courier tracking links — safe to share with the recipient. **Impact:** read-only.

## Additional API methods

- [Raw Yango Delivery API call](./raw-request.md) — Escape hatch: a direct call to any method of the Yango Delivery claims B2B API — for endpoints without a dedicated tool (tariffs, delivery-methods, claims/proof-of-delivery/info, claims/edit, claims/apply-changes, claims/return, claims/bulk_info, claims/journal, …). **Impact:** destructive operation.

## For maintainers and publishers

- [MCP capability documentation contract](../CAPABILITY-DOCUMENTATION.md)
- [Technical tool reference](../TOOLS.md)
- [GitHub repository](https://github.com/A1-x-Tech/mcp-yango-delivery)
