# Tools

For task-oriented guidance, open the [MCP capability catalog](./capabilities/index.md). This page remains the technical reference for schemas and API responses.

Yango Delivery is a **write API**: the tools below create, accept and cancel
real deliveries. The server covers the express (claims) contour of the B2B API —
`https://b2b.taxi.yandex.net`, paths under `/b2b/cargo/integration/v2/*` — the
only contour documented for countries outside Russia. Tool inputs match the
wire format (snake_case, same values); the client picks the host, the Bearer
token and the query-vs-body placement, and injects the `request_id` idempotency
token for claim creation.

## Claim lifecycle

| Tool | Description |
|---|---|
| `check_price` | Price estimation without creating a claim — the pricing method for countries outside Russia: `price` (decimal **string**), `currency_rules`, `distance_meters`, `eta` (minutes), `zone_id`. Route points take `[longitude, latitude]` coordinates and/or a `fullname` address. |
| `create_claim` | Creates a claim. It is **not** dispatched immediately: it goes through estimation (`new → estimating → ready_for_approval`) and must then be accepted with `accept_claim` — or pass `auto_accept: true`. `request_id` (query param, auto-minted UUID when omitted) makes the call idempotent. |
| `get_claim` | Full claim info: `status`, `version` (needed for accept/cancel), items, route points, `pricing`, `performer_info` (courier). Estimation errors may arrive as an `error_messages` array **inside a 200 response** — check both places. |
| `accept_claim` | Confirms an estimated claim and starts the courier search (`version` from `get_claim`). The priced offer expires ~10 minutes after estimation. 409s: `inappropriate_status`, `old_version`, `offer_expired`, `state_mismatch`. |
| `get_cancel_info` | Cancellation terms — call before cancelling: `cancel_state` is `free`, `paid` (with `price`) or `unavailable`. |
| `cancel_claim` | Cancels a claim (even an accepted one). Pass the `cancel_state` obtained from `get_cancel_info`; `paid` incurs the cancellation fee. |
| `search_claims` | Search with filters (status, phone, period, `external_order_id`) and offset/limit (≤1000) **or** cursor pagination; returns `claims` + `cursor`. |

## Tracking & contact

| Tool | Description |
|---|---|
| `get_performer_position` | Live courier position for an active claim: `lat`, `lon`, unix `timestamp`, `speed` (m/s), `direction` (0–360°). |
| `get_tracking_links` | Public `sharing_link` per `destination` route point — safe to hand to the recipient. |
| `get_points_eta` | Expected arrival time per route point (`visited_at.expected`, `visit_status`) plus the current courier position; only while the claim is active and a courier is assigned. |
| `get_courier_phone` | Temporary forwarded phone number to call the courier: `phone`, `ext`, `ttl_seconds`. |
| `get_confirmation_code` | Pickup/delivery confirmation code for the current point: `code`, `attempts`. 404 also covers "issuing a code via the API is prohibited". |

Notes:

- **Money is decimal strings** (`"350.00"` + an ISO 4217 currency code), never
  numbers. Dimensions are meters, weights are kilograms.
- **Known claim statuses:** `new, estimating, estimating_failed,
  ready_for_approval, accepted, performer_lookup, performer_draft,
  performer_found, performer_not_found, pickup_arrived,
  ready_for_pickup_confirmation, pickuped, delivery_arrived,
  ready_for_delivery_confirmation, delivered, delivered_finish, pay_waiting,
  returning, return_arrived, ready_for_return_confirmation, returned,
  returned_finish, failed, cancelled, cancelled_with_payment,
  cancelled_by_taxi, cancelled_with_items_on_hands`. The docs reference a
  24-value enum without listing it in full — treat unknown values as possible.
- **Errors come in two shapes:** non-2xx with `{code, message}` **and**, for
  claims/info and claims/create, an `error_messages: [{code, message}]` array
  inside a 200 response. Responses pass through verbatim, so check both.
- **Retries:** 429 is always retried with backoff (honoring `Retry-After`);
  5xx and network errors are retried only for reads and for claims/create
  (whose `request_id` token makes a replay safe). Other writes are never
  replayed automatically.
- The Russia-only `offers/calculate` method and the platform (NDD /
  pickup-point) contour are **not** part of this server — they do not exist in
  the international documentation.

## Escape hatch

| Tool | Description |
|---|---|
| `raw_request` | Call any claims B2B API path directly, for the endpoints without a dedicated tool: `tariffs`, `delivery-methods`, `claims/proof-of-delivery/info`, `claims/edit`, `claims/apply-changes/request\|result`, `claims/return`, `claims/bulk_info`, `claims/journal`, … `query` becomes the query string, `body` is sent as JSON. A `path` that resolves to a foreign origin is rejected (SSRF guard), so the Bearer token cannot leak. |

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `YANGO_DELIVERY_TOKEN` | yes | — | OAuth Bearer token from the delivery cabinet (Integration tab → "Get token"; never expires, reset on password change). Treat it as a secret. |
| `YANGO_DELIVERY_BASE_URL` | no | `https://b2b.taxi.yandex.net` | API root override. |
| `YANGO_DELIVERY_LANG` | no | `en` | `Accept-Language` header value (required by most claim methods). |
| `YANGO_DELIVERY_TIMEOUT_MS` | no | `60000` | Per-request timeout, ms. |
| `YANGO_DELIVERY_MAX_RETRIES` | no | `3` | Retries on transient errors (429 always; 5xx/network for reads). |
