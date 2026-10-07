# royalmail-mcp

[![npm version](https://img.shields.io/npm/v/royalmail-mcp.svg)](https://www.npmjs.com/package/royalmail-mcp)
[![licence](https://img.shields.io/badge/licence-MIT-blue.svg)](./LICENSE)
[![node](https://img.shields.io/badge/node-%3E%3D18-brightgreen.svg)](https://nodejs.org/)
[![CI](https://github.com/catrinmdonnelly/royalmail-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/catrinmdonnelly/royalmail-mcp/actions/workflows/ci.yml)

Book, label, track and cancel Royal Mail and Parcelforce shipments from any MCP-compatible AI such as Claude, Cursor, or Windsurf.

Verified against the live Click & Drop API (April 2026). Booking, tracking and cancellation tested end-to-end. Label retrieval verified against the spec for OBA accounts.

## What it does

Exposes six tools to any AI that speaks MCP:

| Tool | What it does |
|------|--------------|
| `book_order`            | Create an order in Click & Drop. Returns an `orderIdentifier`. |
| `book_batch_and_label`  | Book many orders at once and get back a single merged PDF of every label, ready to print. |
| `get_label`             | Save the postage label to disk as a PDF. Requires an OBA account (see below). |
| `track_order`           | Current status, tracking number and despatch date. |
| `cancel_order`          | Cancel an order before it's manifested. No charge is applied. |
| `list_services`         | Every Royal Mail and Parcelforce service this MCP supports, with codes. |

Under the hood it talks to `https://api.parcel.royalmail.com/api/v1` using your Click & Drop API key.

## Example prompts

Once the MCP is installed in your AI client, you can say things like:

> *"Book a 1st class letter to Alex Taylor, 45 High Street, Manchester M1 1AA, 80 grams. Reference it ORDER-1842."*

> *"Ship these three orders via Tracked 48 and give me the orderIdentifiers."* (paste a list of addresses)

> *"Book Special Delivery by 1pm with £1,000 compensation to this address, then fetch the label."*

> *"Cancel order 1004. The customer sent the wrong postcode."*

> *"What's the cheapest signed-for service for a 500g parcel?"* (AI calls `list_services` and reasons)

> *"Track orders 1002, 1003 and 1004 and summarise where each one is."*

> *"Here are ten orders — book them all on Royal Mail Tracked 24 and give me one PDF I can print."* (AI calls `book_batch_and_label` and returns the path to a merged PDF.)

The AI handles address parsing, service selection and error recovery. You handle the business decisions.

## Workflow ideas for businesses

Plugged into any AI agent, this MCP can automate real shipping operations:

- **Daily order fulfilment.** Every morning, your AI reads new orders from Shopify, WooCommerce or a spreadsheet, books each one via Royal Mail at the right service level, and posts tracking numbers back to the customer.
- **Customer service triage.** When a customer emails "where's my parcel?", your AI calls `track_order`, summarises the latest status in plain English, and drafts a reply.
- **Returns handling.** A customer requests a return. Your AI reads the request, books the correct return service, and emails the printable label straight back, with no staff time involved.
- **Multi-carrier picking.** Installed alongside [apc-mcp](https://github.com/catrinmdonnelly/apc-mcp), your AI compares Royal Mail and APC at booking time and picks the cheapest or fastest option per destination.
- **Bulk fulfilment days.** For sale events or subscription-box drops, give your AI a CSV of hundreds of orders. It books them all at the right service and compensation tier in one run, then hands you a summary.
- **Checkout quotes.** When a customer asks for shipping cost at checkout, your AI picks the right service for the weight and postcode, calculates the price, and responds within seconds.

## Compatibility

Works with any MCP client that supports stdio transport:

- Claude Desktop
- Cursor
- Windsurf
- Claude Code
- Zed

ChatGPT, Smithery and other remote-only MCP clients need an HTTP transport, which isn't included yet. If that matters to you, open an issue so I can prioritise it.

## Install

```bash
npm install -g royalmail-mcp
```

Or run without installing:

```bash
npx royalmail-mcp
```

## Configuration

Get your API key from **Click & Drop → Settings → API credentials**, then set:

```
RM_API_KEY=your-royal-mail-api-key
RM_BASE_URL=https://api.parcel.royalmail.com/api/v1
```

Either in a `.env` file next to the server, or via your MCP client's config (see below).

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "royalmail": {
      "command": "npx",
      "args": ["-y", "royalmail-mcp"],
      "env": {
        "RM_API_KEY": "your-royal-mail-api-key"
      }
    }
  }
}
```

### Cursor

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "royalmail": {
      "command": "npx",
      "args": ["-y", "royalmail-mcp"],
      "env": {
        "RM_API_KEY": "your-royal-mail-api-key"
      }
    }
  }
}
```

## Supported services

| Key | Royal Mail service | Code |
|-----|--------------------|------|
| `first-class`              | 1st Class                          | `OLP1`      |
| `first-class-signed`       | Signed For 1st Class               | `OLP1SF`    |
| `second-class`             | 2nd Class                          | `OLP2`      |
| `tracked-24`               | Tracked 24                         | `TOLP24`    |
| `tracked-48`               | Tracked 48                         | `TOLP48`    |
| `special-delivery-750`     | Special Delivery by 1pm (£750)     | `SD1OLP`    |
| `special-delivery-1000`    | Special Delivery by 1pm (£1,000)   | `SD2OLP`    |
| `special-delivery-2500`    | Special Delivery by 1pm (£2,500)   | `SD3OLP`    |
| `parcelforce-24`           | Parcelforce express24              | `PFE24`     |
| `parcelforce-48`           | Parcelforce express48              | `PFE48`     |
| `international-tracked`    | International Tracked              | `ITROLP`    |

Plus 22 more, including signed-for variants, age-verification services, and Parcelforce international. Run `list_services` for the full list.

You can pass either the friendly key (`first-class`) or the raw Service Register code (`OLP1`). Both work. Which services your account can use depends on what's enabled in Click & Drop → Settings → Shipping services.

## Limitations

### Labels require an OBA account

`get_label` only works for customers on a Royal Mail **Online Business Account (OBA)**, the invoiced business account. Standard Pay-as-you-go Click & Drop accounts will get `403 Forbidden (Feature not available)` on `get_label`.

Booking, tracking and cancelling work on all account types. If you don't have an OBA you can still automate the order creation via this MCP, then print labels in the Click & Drop UI manually.

Register for OBA at [auth.parcel.royalmail.com/register/oba](https://auth.parcel.royalmail.com/register/oba).

### OBA users: enable auto-apply-postage

If you're on OBA, also tick **"Apply postage automatically on orders imported via API"** in Click & Drop → Settings. Without it, orders stay as drafts and `get_label` returns `"Label generation only available for orders with postage applied status"`.

## Security

Your API key grants full access to your Click & Drop account. Treat it like a password.

- Never commit `.env` to git. The `.gitignore` in this repo already excludes it.
- Don't paste your key into chat messages or shared documents.
- Rotate it at Click & Drop → Settings → API credentials if it's ever exposed.

## Privacy & data handling

This MCP runs entirely on your machine. No customer data, credentials or API traffic flows through any server owned or operated by the author.

The data path is:

- Shipping details you give your AI assistant go to your AI provider (e.g. Anthropic, if you're using Claude) under your account.
- Booking requests go to Royal Mail Click & Drop using your API key.
- Labels are saved to your local disk at `~/Downloads/parcel-toolkit/` (overridable via the `PARCEL_TOOLKIT_LABELS_DIR` env var).

If you're using this in a UK business, you are the data controller under UK GDPR. Practical recommendations:

1. Use Claude Team, Claude Enterprise, or the Claude API directly — not consumer Claude.ai — so a Data Processing Agreement with Anthropic is in place. On consumer tiers, turn off "Help improve Claude" in Privacy settings at minimum.
2. List Anthropic and Royal Mail as subprocessors in your privacy policy, the same way you would list a payment provider or email service.
3. Avoid using this tool for special-category data (health, biometric, children's data) without additional legal review.
4. This software is provided as-is under the MIT licence. The author is not a data processor and takes no responsibility for your compliance obligations — those sit with you as the data controller.

## Contributing

Issues and pull requests are welcome at [github.com/catrinmdonnelly/royalmail-mcp](https://github.com/catrinmdonnelly/royalmail-mcp). If Royal Mail changes their API, or you hit an edge case on your account type, please open an issue with the request body you sent and the response you got (scrub your API key first).

## Companion MCP

For APC Overnight, see [apc-mcp](https://github.com/catrinmdonnelly/apc-mcp).

## Disclaimer

This project is not affiliated with, endorsed by, or sponsored by Royal Mail Group Ltd. "Royal Mail", "Parcelforce" and "Click & Drop" are trademarks of their respective owners. Use at your own risk.

## Licence

MIT. See [LICENSE](LICENSE).
