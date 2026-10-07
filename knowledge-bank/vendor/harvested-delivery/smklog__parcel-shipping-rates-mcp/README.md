<p align="center">
  <img src="https://smklog.com/assets/icon-192.png" width="88" alt="SMKlog">
</p>

<h1 align="center">SMKlog Parcel Shipping Rates — MCP Server</h1>

<p align="center">
  Live USPS, UPS, FedEx and DHL Express rates for a parcel sent from the US &mdash; domestic, or to Canada, the UK, Germany or Australia &mdash; described in plain words.<br>
  No scale. No account. No API key.
</p>

<p align="center">
  <code>https://quote-api.smklog.com/mcp</code> · streamable-http · MCP 2026-07-28, 2025-06-18, 2025-03-26
</p>

<p align="center">
  <a href="https://glama.ai/mcp/servers/smklog/parcel-shipping-rates-mcp"><img src="https://glama.ai/mcp/servers/smklog/parcel-shipping-rates-mcp/badges/score.svg" alt="Glama score"></a>
  <a href="https://github.com/smklog/parcel-shipping-rates-mcp/actions/workflows/test.yml"><img src="https://github.com/smklog/parcel-shipping-rates-mcp/actions/workflows/test.yml/badge.svg" alt="test"></a>
  <a href="https://smithery.ai/servers/smklog/parcel-shipping-rates"><img src="https://img.shields.io/badge/Smithery-smklog%2Fparcel--shipping--rates-a855f7" alt="Listed on Smithery"></a>
  <a href="https://registry.modelcontextprotocol.io/v0/servers?search=smklog"><img src="https://img.shields.io/badge/MCP%20registry-com.smklog%2Fparcel--shipping--rates-1f6feb" alt="In the official MCP registry"></a>
  <a href="https://github.com/smklog/parcel-shipping-rates-mcp/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT license"></a>
</p>

---

Most shipping APIs want a box: length, width, height, weight. People don't have
that — they have a thing on the table and a ZIP code to send it to. This server
takes the thing.

Describe **"a full-size acoustic guitar in its hard case"** and it estimates the
packed carton, prices it live across three carriers, and hands back services you
can actually buy — with the checkout total and, where the carrier publishes one,
its own counter price for the same parcel side by side, so you can always show a
person both numbers.

## What you can ask your assistant

- *"How much to ship a 12 lb box from 07922 to 90011?"*
- *"What would it cost to send a full-size acoustic guitar in a hard case from New Jersey to Los Angeles?"*
- *"Compare USPS, UPS and FedEx for a 5 lb box, Newark to Chicago — which is cheapest and which is fastest?"*
- *"Price a 24 × 18 × 12 in box at 22 lb going to 33101, then give me a link to buy the label."*
- *"Where is my package? Tracking 9400111899561234567890."*
- *"Did they pay for that label yet? Here is the session id you gave me."*
- *"What has a 5 lb box to Denver cost over the last few months?"*

## Tools

| Tool | What it does |
|---|---|
| **`get_parcel_quote`** | Live rates for one parcel from a US origin, domestic or to Canada, the UK, Germany or Australia, across USPS, UPS and FedEx, plus DHL Express to Germany and Australia. Plain-words description → estimated packed box; or pass exact dimensions and weight to skip the estimate. Returns up to five purchasable services with the checkout total (SMKlog fee inside), the carrier's counter price beside it where one is published, and the delivery window. |
| **`create_checkout_link`** | Prices the shipment and returns a payment session: the amount, a handoff URL that opens the SMKlog checkout prefilled with this shipment, and a `session_id`. The human confirms the contents certification and the carrier-adjustment consent there and pays on Stripe. |
| **`get_checkout_status`** | Where a payment session stands: `awaiting_checkout`, `checkout_started`, `paid`, `label_ready` (with the tracking number), `delivered` or `refunded`. Read from the order record, so it costs no carrier call and never carries names, addresses or emails. Sessions answer for 30 days. |
| **`track_parcel`** | Delivery status, scan events and the carrier's estimated delivery date for a shipment whose label was bought on smklog.com. Not a universal tracker for arbitrary numbers. |
| **`get_price_index`** | The monthly SMKlog parcel price index: six common boxes (1–20 lb) from Newark, NJ to five US cities, repriced through the same live pipeline that prices real shipments. Reading it spends no quote allowance. |

## Things worth knowing before you wire it in

**A quote is a real carrier call and costs real money to produce.** Call
`get_parcel_quote` once per shipment, not once per variation you are curious
about. The server is rate limited per client and will say so plainly rather than
silently degrading.

**Origin is the United States.** Domestic lanes and US-origin exports. A lane
that starts somewhere else is out of scope, and the server will tell you instead
of inventing a number.

**Prices are checkout totals with the SMKlog fee inside.** The fee is itemized
only on the checkout receipt; what comes back beside a rate is the carrier's own
counter price for the same parcel, where one is published — what the person
would pay walking into the carrier's counter instead. The total is what they pay.

**Parcels only, one label per box.** A shipment past parcel limits or described
as a pallet or freight load comes back as `mode: not_a_parcel` with no rates:
SMKlog sells parcel labels and does not arrange pallet or freight shipments.
`quantity` counts units of the item: units that fit one box are priced as that
box, while units that need more than one box — or a `quantity` above 1 sent with
exact dimensions, which describe one box — come back as `mode: multiple_boxes`
with no rates, so quote each box on its own.

**Nothing here buys a label on its own.** `create_checkout_link` produces a URL;
a human completes the purchase, certifies the contents and consents to carrier
adjustments. An agent cannot spend someone's money through this server.

## Connect

```json
{
  "mcpServers": {
    "smklog": {
      "type": "http",
      "url": "https://quote-api.smklog.com/mcp"
    }
  }
}
```

No key, no OAuth, no signup. Quoting, tracking and the price index are all open.

### Over stdio

For a client that only launches local commands — Claude Desktop, Cursor, an
MCP inspector, a Docker-based runner — this repository is a thin stdio bridge
to the same endpoint. No dependencies, no build step, no keys:

```json
{
  "mcpServers": {
    "smklog": {
      "command": "npx",
      "args": ["-y", "github:smklog/parcel-shipping-rates-mcp"]
    }
  }
}
```

Or with Docker:

```sh
docker build -t smklog-parcel-shipping-rates-mcp https://github.com/smklog/parcel-shipping-rates-mcp.git
docker run -i --rm smklog-parcel-shipping-rates-mcp
```

The bridge forwards every JSON-RPC message to `https://quote-api.smklog.com/mcp`
and writes the answer back, one JSON object per line. It also mirrors the
2026-07-28 routing envelope into HTTP headers (`MCP-Protocol-Version`,
`Mcp-Method`, `Mcp-Name`) and, on the legacy path, sends the version
`initialize` negotiated, so both protocol eras work through it. If the endpoint cannot be
reached it still answers `initialize` and `tools/list` from the snapshot shipped
here (`initialize.json`, `tools.json`), so you can see what is offered; tool
calls need the network. `npm test` drives it end to end.

Also installable from [Smithery](https://smithery.ai/servers/smklog/parcel-shipping-rates)
and listed in the [official MCP registry](https://registry.modelcontextprotocol.io/v0/servers?search=smklog)
as `com.smklog/parcel-shipping-rates`.

Other ways in, if MCP is not your transport:
[OpenAPI](https://quote-api.smklog.com/openapi.json) ·
[A2A agent card](https://quote-api.smklog.com/.well-known/agent-card.json) ·
[API docs](https://smklog.com/api) ·
[llms.txt](https://smklog.com/llms.txt)

## Who runs it

[SMKlog](https://smklog.com) sells US shipping labels. The same pricing pipeline
that answers this server answers the website — there is no separate "API rate".
Questions, bugs and odd results: **info@smklog.com**.
