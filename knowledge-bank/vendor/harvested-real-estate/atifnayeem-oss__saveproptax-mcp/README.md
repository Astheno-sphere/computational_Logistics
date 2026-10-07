# SavePropTax MCP server

A remote MCP server and an open HTTP API for California property tax appeals.

Ask it whether a home is over-assessed. If recent comparable sales support a
lower value, it prepares the county's own Proposition 8 decline-in-value review
form and emails a signing link to the homeowner. The owner signs and pays a flat
$29. Checking is free, keyless, and can only ever lower a tax bill, never raise
it.

There is nothing to install. The server is hosted:

```
https://saveproptax.com/mcp
```

Streamable HTTP, no authentication, stateless.

## Add it to a client

**Claude:** Settings, then Connectors, then Add custom connector, and paste the
URL above.

**ChatGPT:** Settings, then Connectors (or Apps), then add an MCP server by URL,
where your plan supports custom connectors.

**Claude Code:**

```bash
claude mcp add --transport http saveproptax https://saveproptax.com/mcp
```

**Any MCP client:** point a streamable-HTTP transport at the URL. No token.

## Tools

| Tool | Arguments | What it does |
| --- | --- | --- |
| `check_property_tax_savings` | `address` (required), `unit` | Free check of one California home. Returns a status, the current assessment, an opinion of value from recent comparable sales, and estimated annual savings. A qualifying result carries a `continueToken`. |
| `start_filing` | `continueToken`, `ownerName`, `ownerPhone`, `ownerEmail` | Prepares the county form and emails the signing link to the owner. The link is never returned to the client. |
| `get_filing_status` | `docId` | Coarse status only: `awaiting_signature`, `awaiting_payment`, `filed`, `delivered`, `unknown`. No personal information. |

## The rule that shapes everything

**An agent never handles the signature or the money.** The signing link goes to
the owner's inbox. The owner reviews the county's own form, signs it, and pays.
The worst an anonymous caller can do is spend a free check and send a real
homeowner a legitimate link to their own property.

## HTTP API

The same capability without MCP. Keyless.

```bash
curl -s https://saveproptax.com/api/agent/check \
  -H 'Content-Type: application/json' \
  -d '{"address": "123 Main St, Walnut Creek"}'
```

A qualifying response:

```json
{
  "status": "qualifies",
  "message": "This property qualifies: recent comparable sales support a value of $915,000 against the $1,024,000 assessment, an estimated $1,204 per year in tax savings; filing costs a flat $29 and the owner signs and pays.",
  "property": { "address": "123 MAIN ST, WALNUT CREEK CA", "county": "Contra Costa" },
  "estimate": { "assessment": 1024000, "opinion": 915000, "estimatedAnnualSavings": 1204 },
  "filing": { "feeUsd": 29, "deadline": "November 30, 2026" },
  "continueToken": "eyJ...valid 24 hours",
  "cached": false,
  "checkedAt": "2026-08-19T18:00:00.000Z"
}
```

Then hand the token and the owner's details to prepare:

```bash
curl -s https://saveproptax.com/api/agent/prepare \
  -H 'Content-Type: application/json' \
  -d '{
    "continueToken": "eyJ...",
    "ownerName": "Jane Homeowner",
    "ownerPhone": "925 555 0100",
    "ownerEmail": "jane@example.com"
  }'
```

```json
{ "docId": "d0c1d2...", "status": "awaiting_signature",
  "statusUrl": "https://saveproptax.com/api/agent/status?doc=d0c1d2...",
  "ownerEmailSent": true }
```

Poll the status endpoint for progress:

```bash
curl -s 'https://saveproptax.com/api/agent/status?doc=d0c1d2...'
```

### Every status to handle

| status | meaning |
| --- | --- |
| `qualifies` | Comparable sales support a defensibly lower value, savings exceed $500 a year, and the county window is open. The only status carrying a `continueToken`. |
| `fair_assessment` | Sales do not support a value below the current assessment this year. |
| `not_enough_data` | Too few closely matched recent sales for a defensible filing. |
| `not_residential` | The parcel's county record is not residential. |
| `window_closed` | The county's review window has closed; `filing.reopens` says when it returns. |
| `county_not_served` | A California county not covered yet. |
| `already_filed` | A review request was already filed for this property this year. |
| `address_not_found` | Retry with the city included. |
| `needs_more_info` | The message says what is missing, for example a unit number. |
| `busy` | Heavy load: fresh checks briefly paused, cached answers still serve. Retry shortly. |

Every `message` is a relayable one-sentence explanation you can pass to your user
as written.

### Optional key

```bash
curl -s https://saveproptax.com/api/agent/register \
  -H 'Content-Type: application/json' \
  -d '{"agentName": "MyAssistant", "contactEmail": "dev@example.com"}'
```

Returns a key immediately, no approval step. Send it as the `x-agent-key` header
for double the fresh-check headroom and named attribution. Anonymous use works
fine; registration is identity, not permission.

## Rate limits

- **Per-address cache, 24 hours.** Repeat checks are instant, cost us nothing,
  and come back marked `cached: true`. Cached answers are never rate limited.
- **Hourly fresh-check budget.** Fresh checks buy real records and sales data,
  so they share an hourly pool. Under load, fresh checks answer `busy` while
  cached answers still serve. The pipeline never degrades to a cheaper valuation
  method; it only delays.
- **Prepare gating.** Requires a token from a real check, and is limited to
  three signing links per owner inbox per day.

## Coverage

Alameda, Contra Costa, Los Angeles, Marin, Napa, Placer, Riverside, Sacramento,
San Benito, San Bernardino, San Francisco, San Joaquin, San Mateo, Santa Clara,
Santa Cruz, Solano, Sutter, and Yolo counties. Windows are seasonal per county;
current deadlines are at <https://saveproptax.com/counties.html>.

## More

- Full reference: <https://saveproptax.com/agents>
- OpenAPI: <https://saveproptax.com/openapi.json>
- llms.txt: <https://saveproptax.com/llms.txt>
- Registry metadata: [`server.json`](./server.json)
- Partnerships and volume arrangements: support@saveproptax.com

SavePropTax prepares review requests from public records and the county's own
forms; owners review and sign them. We are not a law firm, and nothing here is
legal or tax advice. Reductions are decided solely by the County Assessor.

## License

MIT. See [LICENSE](./LICENSE). The license covers this repository's contents;
the hosted service is governed by the terms at
<https://saveproptax.com/legal.html>.

## Run locally (stdio)

The hosted server needs no install. For stdio-only MCP clients, this repo ships a
dependency-free bridge (Node 18+):

```json
{
  "mcpServers": {
    "saveproptax": {
      "command": "node",
      "args": ["bridge.js"]
    }
  }
}
```

Or with Docker: `docker build -t saveproptax-mcp . && docker run -i saveproptax-mcp`.
Introspection is answered locally; tool calls are forwarded to saveproptax.com/mcp.
