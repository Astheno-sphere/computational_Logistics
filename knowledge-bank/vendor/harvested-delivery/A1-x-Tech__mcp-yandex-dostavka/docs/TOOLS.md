# Tools

For human-facing Russian pages organized by user tasks, open the
[MCP capability catalog](./capabilities/index.md).

Yandex Delivery is a **write API**: tools below create, accept and cancel real
deliveries. The server spans two independent contours — **express** (same-day
courier claims, `b2b.taxi.yandex.net`, `/b2b/cargo/integration/v2/*`) and
**platform** (NDD / pickup points, `b2b-authproxy.taxi.yandex.net`,
`/api/b2b/platform/*`). Tool inputs match the wire format (snake_case,
same values); the client picks the host, the Bearer token and the
query-vs-body placement, and injects the `request_id` idempotency token
for claim creation.

## Express contour (same-day claims)

| Tool | Description |
|---|---|
| `express_check_price` | Price estimation without creating a claim: `price` (decimal **string**), `currency_rules`, `distance_meters`, `eta` (minutes), `zone_id`. Route points take `[longitude, latitude]` coordinates and/or a `fullname` address. |
| `express_create_claim` | Creates a claim. It is **not** dispatched immediately: it goes through estimation (`new → estimating → ready_for_approval`) and must then be accepted with `express_accept_claim` — or pass `auto_accept: true`. `request_id` (query param, auto-minted UUID when omitted) makes the call idempotent. |
| `express_get_claim` | Full claim info: `status`, `version` (needed for accept/cancel), items, route points, `pricing`, `performer_info` (courier). Estimation errors may arrive as an `error_messages` array **inside a 200 response** — check both places. |
| `express_accept_claim` | Confirms an estimated claim and starts the courier search (`version` from `express_get_claim`). 409s: `inappropriate_status`, `old_version`, `offer_expired`, `offer_already_used`. |
| `express_cancel_info` | Cancellation terms — call before cancelling: `cancel_state` is `free`, `paid` (with `price`) or `unavailable`. |
| `express_cancel_claim` | Cancels a claim (even an accepted one). Pass the `cancel_state` obtained from `express_cancel_info`; `paid` incurs the cancellation fee. |
| `express_search_claims` | Search with filters (status, phone, period, `external_order_id`) and offset/limit (≤1000) **or** cursor pagination; returns `claims` + `cursor`. |
| `express_performer_position` | Live courier position for an active claim: `lat`, `lon`, unix `timestamp`, `speed` (m/s), `direction` (0–360°). |
| `express_tracking_links` | Public `sharing_link` per `destination` route point — safe to hand to the recipient. |

## Platform contour (NDD / pickup points)

| Tool | Description |
|---|---|
| `platform_list_pickup_points` | Pickup points, parcel lockers (`terminal`) and drop-off warehouses with filters (geo_id, coordinate ranges, payment methods…). An empty body returns **every** point — always pass at least one filter. Point `id` feeds `destination.platform_station` of `platform_create_offers`. |
| `platform_create_offers` | Calculates delivery options (offers) for an NDD order: `offers [{offer_id, expires_at, offer_details}]`. Destination is either a `platform_station` (pickup point) or a `custom_location` (courier to an address). 400 `no_delivery_options` = no options for the interval. |
| `platform_confirm_offer` | Books an offer — **creates the order**. Returns `request_id`, the order id for the info/history/cancel tools. Offers expire at `expires_at`. |
| `platform_get_request` | Order info: `state {status, description, timestamp, reason}`, contents, recipient, `courier_order_id`. |
| `platform_request_history` | Status-change history: `state_history [{status, description, timestamp, timestamp_utc, reason?}]`. |
| `platform_cancel_request` | Cancels an order (courier orders — until `DELIVERY_TRANSPORTATION_RECIPIENT`). Returns `status` `CREATED`/`SUCCESS`/`ERROR`. |

Notes:

- **Money formats differ per contour.** Express prices are decimal *strings*
  (`"350.00"` + ISO currency); platform prices are integers in kopecks
  (`unit_price`, `delivery_cost`).
- **Express claim statuses:** `new, estimating, ready_for_approval, accepted,
  performer_lookup, performer_found, performer_not_found, pickup_arrived,
  pickuped, delivery_arrived, delivered, returning, returned, failed,
  cancelled, cancelled_by_taxi`. The platform status model is only partially
  documented (`CREATED`, …, cancellation reasons like `SHOP_CANCELLED`).
- **Two error shapes on express:** non-2xx with `{code, message}` **and**, for
  claims/info, an `error_messages: [{code, message}]` array inside a 200
  response. Responses pass through verbatim, so check both.
- **Retries:** 429 is always retried with backoff (honoring `Retry-After`);
  5xx and network errors are retried only for reads and for claims/create
  (whose `request_id` token makes a replay safe). Other writes are never
  replayed automatically.
- **Express dimensions are meters/kg; platform dimensions are cm/grams.**

## Escape hatch

| Tool | Description |
|---|---|
| `raw_request` | Call any B2B API path of either contour directly (`contour` picks the host + token), for the ~30 endpoints without a dedicated tool: express `tariffs`, `points-eta`, `driver-voiceforwarding`, `proof-of-delivery/info`, `claims/edit`, `claims/bulk_info`, `journal`; platform `/merchant/*`, `/warehouses/*`, `/pickups/*`, `request/generate-labels`, `request/get-handover-act`, `pricing-calculator`, `location/detect`, … `query` becomes the query string, `body` is sent as JSON. A `path` that resolves to a foreign origin is rejected (SSRF guard), so the Bearer token cannot leak. |

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `YANDEX_DELIVERY_TOKEN` | yes* | — | Shared Bearer token for both contours (cabinet → «Интеграции» → «Получить токен»; survives forever, reset on password change). Treat it as a secret. |
| `YANDEX_DELIVERY_EXPRESS_TOKEN` | no | — | Express-contour override of the shared token. |
| `YANDEX_DELIVERY_PLATFORM_TOKEN` | no | — | Platform-contour override of the shared token. |
| `YANDEX_DELIVERY_EXPRESS_BASE_URL` | no | `https://b2b.taxi.yandex.net` | Express API root override. |
| `YANDEX_DELIVERY_PLATFORM_BASE_URL` | no | `https://b2b-authproxy.taxi.yandex.net` | Platform API root; set `https://b2b.taxi.tst.yandex.net` for the test contour. |
| `YANDEX_DELIVERY_LANG` | no | `ru` | `Accept-Language` header (required by the express methods). |
| `YANDEX_DELIVERY_TIMEOUT_MS` | no | `60000` | Per-request timeout, ms. |
| `YANDEX_DELIVERY_MAX_RETRIES` | no | `3` | Retries on transient errors (429 always; 5xx/network for reads). |

\* The shared token may be omitted when both per-contour tokens are set.
