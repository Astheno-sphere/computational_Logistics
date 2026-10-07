# <img src="./assets/a1-logo.svg" alt="A1" width="40"> Yango Delivery MCP

**English** | [Русский](./README.ru.md)

[![npm](https://img.shields.io/npm/v/mcp-yango-delivery)](https://www.npmjs.com/package/mcp-yango-delivery)
[![Glama](https://glama.ai/mcp/servers/A1-x-Tech/mcp-yango-delivery/badges/score.svg)](https://glama.ai/mcp/servers/A1-x-Tech/mcp-yango-delivery)
[![CI](https://github.com/A1-x-Tech/mcp-yango-delivery/actions/workflows/ci.yml/badge.svg)](https://github.com/A1-x-Tech/mcp-yango-delivery/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)

**A1 Yango Delivery MCP** connects an AI app to a corporate Yango Delivery account. Estimate an express delivery, order a courier, track the route and share a tracking link with the recipient using ordinary language.

This server works with the international Express Claims API. It does not support next-day delivery, pickup points or parcel lockers.

- **13 tools.** Seven for the delivery lifecycle, five for tracking and courier contact, plus one direct API request tool.
- **Estimate before ordering.** Check the current price, route distance and ETA without creating a delivery claim.
- **Create and order separately.** A claim can be prepared and reviewed before courier search starts.
- **Follow an active delivery.** Get its status, courier position, point ETAs, temporary phone number, confirmation code and recipient tracking link.

Start with:

> Estimate delivery of a 2 kg parcel from [pickup address] to [delivery address].

[Connect the server](#quick-start) · [Explore use cases](#what-you-can-ask-it-to-do) · [Open technical documentation](#technical-documentation)

---

## See it work in a minute

> **You:** Estimate delivery of a 2 kg parcel from our warehouse to the customer's address.
>
> **Assistant:** I returned the current price, route distance and ETA. No delivery claim was created.
>
> **You:** Create the claim and stop before ordering the courier.
>
> **Assistant:** The claim has been created. I will show its id, price, status and version before acceptance.
>
> **You:** Accept the offer.
>
> **Assistant:** The claim has been accepted and courier search has started.
>
> **You:** Send me the recipient's tracking link.
>
> **Assistant:** I returned the public tracking link for the destination.

> Price, availability, status and cancellation terms always come from the connected delivery account and the current API response.

## Contents

- [Quick start](#quick-start)
- [What you can ask it to do](#what-you-can-ask-it-to-do)
- [How a delivery becomes real](#how-a-delivery-becomes-real)
- [What changes in the account](#what-changes-in-the-account)
- [Getting access](#getting-access)
- [Configuration](#configuration)
- [Data and telemetry](#data-and-telemetry)
- [Limits and background work](#limits-and-background-work)
- [Technical documentation](#technical-documentation)
- [Support](#support)

## Quick start

You need Node.js 20+, a Yango Delivery corporate account and an integration token.

1. [Get an integration token](#getting-access).
2. Add the server to your AI app using one of the instructions below.
3. Start with a price estimate:

   > Estimate delivery of a 2 kg parcel from [pickup address] to [delivery address].

<details open>
<summary><strong>Codex</strong></summary>

<br>

**In the app:**

1. Open **Settings → MCP servers**.
2. Select **Add server**.
3. Choose **STDIO**, then enter the launch command `npx -y mcp-yango-delivery@latest` and the `YANGO_DELIVERY_TOKEN` environment variable with your token.

4. Select **Save**, then **Restart**.

**From the command line:**

```bash
codex mcp add yango-delivery \
  --env YANGO_DELIVERY_TOKEN=your_token \
  -- npx -y mcp-yango-delivery@latest
```

Check the connection:

```bash
codex mcp list
```

[Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)

</details>

<details>
<summary><strong>Claude Code</strong></summary>

<br>

```bash
claude mcp add \
  --env YANGO_DELIVERY_TOKEN=your_token \
  --transport stdio \
  --scope user \
  yango-delivery \
  -- npx -y mcp-yango-delivery@latest
```

Check the connection:

```bash
claude mcp list
```

[Claude Code MCP documentation](https://code.claude.com/docs/en/mcp)

</details>

<details>
<summary><strong>Claude Desktop</strong></summary>

<br>

The current official path is **Settings → Extensions**. For a custom desktop extension, open **Advanced settings → Extension Developer → Install Extension…**, select a `.mcpb` file and follow the prompts.

This repository currently publishes an npm stdio package and does not contain a `.mcpb` bundle. For Claude Desktop builds that still support local configuration, use the following JSON stdio configuration as a fallback:

```json
{
  "mcpServers": {
    "yango-delivery": {
      "command": "npx",
      "args": ["-y", "mcp-yango-delivery@latest"],
      "env": {
        "YANGO_DELIVERY_TOKEN": "your_token"
      }
    }
  }
}
```

In those builds, save it to `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS or `%APPDATA%\Claude\claude_desktop_config.json` on Windows.

[Claude Desktop MCP documentation](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)

</details>

<details>
<summary><strong>Cursor</strong></summary>

<br>

Add a user-level server to `~/.cursor/mcp.json` on macOS/Linux or `%USERPROFILE%\.cursor\mcp.json` on Windows:

```json
{
  "mcpServers": {
    "yango-delivery": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "mcp-yango-delivery@latest"],
      "env": {
        "YANGO_DELIVERY_TOKEN": "your_token"
      }
    }
  }
}
```

[Cursor MCP documentation](https://cursor.com/docs/mcp)

</details>

<details>
<summary><strong>VS Code</strong></summary>

<br>

Run **MCP: Open User Configuration** from the Command Palette and add:

```json
{
  "servers": {
    "yango-delivery": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "mcp-yango-delivery@latest"],
      "env": {
        "YANGO_DELIVERY_TOKEN": "${input:yango_delivery_token}"
      }
    }
  },
  "inputs": [
    {
      "type": "promptString",
      "id": "yango_delivery_token",
      "description": "Yango Delivery integration token",
      "password": true
    }
  ]
}
```

Check the server with **MCP: List Servers**.

[VS Code MCP documentation](https://code.visualstudio.com/docs/agent-customization/mcp-servers)

</details>

## What you can ask it to do

### Estimate an express delivery

- Calculate the current price, route distance and ETA without creating a claim.
- Estimate courier, express or cargo service for the supplied addresses, weight and dimensions.
- Check whether the API can build the route and satisfy the requested vehicle or delivery requirements.

### Prepare and order a courier

- Create a claim with sender and recipient contacts, route points, items and delivery requirements.
- Review the returned price, status and claim version before ordering.
- Accept a claim after successful estimation and start courier search.
- Find a claim by id, phone number, status, date or external order id.

### Track the delivery and contact the courier

- Get the current courier position and ETA for each route point.
- Generate a public tracking link for the recipient.
- Get a temporary forwarded phone number for the courier.
- Get a pickup or delivery confirmation code when the current claim supports one.

### Check and cancel a delivery

- Check whether cancellation is free, paid or no longer available.
- Cancel a claim using its current version and the cancellation mode returned by the API.

### Use additional API methods

`raw_request` covers methods without a dedicated tool, including tariffs, delivery methods, proof of delivery, claim editing and return operations. It can create or change real data, so it is intended for technical users who understand the upstream API.

Complete schemas, response fields and status details are available in the [tool reference](docs/TOOLS.md).

## How a delivery becomes real

1. **Estimate.** A price check returns the current offer, distance and ETA without creating anything.
2. **Create.** A claim is added to the account and moves through estimation. By default, no courier is ordered yet.
3. **Review.** Read the latest claim status, price and version. A successful claim becomes ready for approval.
4. **Accept.** Acceptance starts courier search. From this point, the delivery is ordered and can lead to a real charge.
5. **Track.** Once a courier is assigned, the server can return the position, ETA, contact details and recipient link.

The priced offer usually expires about ten minutes after estimation. If `auto_accept: true` is passed when creating a claim, the separate review and acceptance step is skipped and the courier can be ordered automatically.

## What changes in the account

The server exposes MCP annotations for reading, writing and destructive actions. The AI client decides when and how to ask for confirmation.

| Action | Result | Changes the account |
|---|---|---:|
| Price estimate | Returns the current price, distance and ETA | No |
| Read, search and tracking tools | Returns claim, courier and cancellation information | No |
| Create a claim | Adds a real claim, but does not order a courier by default | Yes |
| Accept a claim | Starts courier search and can lead to a charge | Yes |
| Cancel a claim | Cancels the delivery; a cancellation fee may apply | Yes |
| `raw_request` | Calls another API method, including possible writes | Depends on the method |

Claim creation uses a unique `request_id`, so repeating it with the same id returns the same claim. Acceptance and cancellation are not automatically repeated after a network error or a 5xx response because the operation may already have succeeded. Read the current claim before trying again.

## Getting access

1. Register as a corporate Yango Delivery client and sign the delivery-service contract.
2. Open the **Integration** tab in the delivery account.
3. Select **Get token**.
4. Add the token to the AI client as `YANGO_DELIVERY_TOKEN`.

The token is tied to the corporate account. It does not expire by itself, but changing the account password resets it.

> The integration token is stored as plain text in the AI client's local configuration. Treat it like a password and never commit a configuration containing a real token.

## Configuration

| Variable | Required | Default | Description |
|---|---:|---|---|
| `YANGO_DELIVERY_TOKEN` | yes | — | Bearer token from the delivery account |
| `YANGO_DELIVERY_BASE_URL` | no | `https://b2b.taxi.yandex.net` | API root override |
| `YANGO_DELIVERY_LANG` | no | `en` | Value of the `Accept-Language` header |
| `YANGO_DELIVERY_TIMEOUT_MS` | no | `60000` | Timeout for one request, in milliseconds |
| `YANGO_DELIVERY_MAX_RETRIES` | no | `3` | Maximum retries for temporary failures; writes are not replayed unless they are idempotent |
| `ASKADS_TELEMETRY` | no | enabled | `0`, `false`, `off` or `no` disables anonymous telemetry |

## Data and telemetry

### Requests to Yango Delivery

The server runs on your machine and sends claim data directly to `b2b.taxi.yandex.net`. The integration token is attached only to requests to the configured API host. Even `raw_request` accepts a relative path and blocks requests that resolve to another host.

### Anonymous telemetry

By default, the server sends technical events to `usage.gistrec.cloud`: server start, called tool name and a fixed reason code when startup fails.

Events contain a random installation id, package version, AI client name and version, Node.js version and operating system. **The integration token, claim data, tool arguments and prompts are not read or sent.** Telemetry has a two-second timeout and does not block a tool call.

To disable telemetry, add:

```text
ASKADS_TELEMETRY=0
```

The implementation is in [`src/telemetry.ts`](src/telemetry.ts).

## Limits and background work

- **There is no documented sandbox.** Treat claim creation and acceptance as production operations.
- **The offer is time-limited.** The priced offer usually expires about ten minutes after estimation; read the current claim before acceptance.
- **Tracking requires an active claim.** Position, ETA, contact details and tracking links may be unavailable until a courier is assigned or after the claim is completed.
- **Numeric API quotas are not published.** When the API returns 429, the server follows `Retry-After` when present and retries up to `YANGO_DELIVERY_MAX_RETRIES`.
- **There is no background monitoring.** The server works only when called from the AI app. If the app supports scheduled tasks, it can check an active claim periodically.
- **There is no automatic rollback.** After an uncertain acceptance or cancellation result, read the claim before repeating the action.

## Technical documentation

- [MCP capability catalog](./docs/capabilities/index.md) — task-oriented pages for every tool.
- [All tools](docs/TOOLS.md) — input schemas, responses, statuses and errors.
- [Development](docs/DEVELOPMENT.md) — local setup and project checks.
- [Publishing](docs/PUBLISHING.md) — package release and MCP catalog listing.
- [npm package](https://www.npmjs.com/package/mcp-yango-delivery) — the published `mcp-yango-delivery` package.
- [Yango/Yandex Delivery API](https://yandex.com/support/delivery-profile/en/api/express/overview) — upstream method documentation.

## Support

Found a bug or missing a use case? [Create an issue](https://github.com/A1-x-Tech/mcp-yango-delivery/issues) or message us on [Telegram](https://t.me/a1_mcp).

<br>

<p align="center">
  <img src="https://github.com/ztemerbekov/a1-yandex-kit-skills/raw/main/assets/images/mona-hifive-yandex-kit-warm.gif" alt="Две Моны дают пять" width="256">
</p>

<p align="center">
  You made it to the end!
</p>
