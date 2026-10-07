# AddressIntel MCP server

A read-only [Model Context Protocol](https://modelcontextprotocol.io) server that puts
SF Peninsula building-permit and parcel-buildability data inside Claude, ChatGPT, or any
other MCP-capable agent.

It is a thin client over the public AddressIntel API, so it inherits that API's auth,
rate limits and tier ceilings. Every tool is a `GET`. Nothing here can write.

## Tools

| Tool | What it answers |
|---|---|
| `search_permits` | What construction has actually been permitted at an address or in a city? Filters on city, keyword (address, project type, scope description, contractor, architect, permit number) and minimum valuation. |
| `list_sb9_inventory` | Which active listings can be split or duplexed under SB 9, and what blocks the ones that can't? |
| `list_adu_leads` | Which parcels have room for an ADU, and how many units / how much square footage? |
| `list_redevelopment_leads` | Which parcels are underbuilt against their allowable envelope (scrape-and-rebuild or expansion)? |
| `list_market_signals` | Which listings score highest for teardown or flip potential? |
| `get_property_intelligence` | Full scores and comparable sales for one property id. |

The permit and parcel tools are the differentiated half: permit-level detail and
parcel-level buildability for the Peninsula, rather than a nationwide owner list.

## Install

No install step: `npx` fetches it on demand.

### Claude Code

```bash
claude mcp add addressintel \
  -e ADDRESSINTEL_API_KEY=your_key \
  -- npx -y addressintel-mcp
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "addressintel": {
      "command": "npx",
      "args": ["-y", "addressintel-mcp"],
      "env": {
        "ADDRESSINTEL_API_KEY": "your_key"
      }
    }
  }
}
```

### From source

For working on the server itself:

```bash
git clone https://github.com/RantumBits/addressintel-mcp.git
cd addressintel-mcp
npm install
npm run build     # emits dist/index.js
```

Then point the client at `node /absolute/path/to/addressintel-mcp/dist/index.js` instead of
the `npx` command above.

Restart the client, then ask it something like *"what demolition permits were issued in
Menlo Park this year?"* or *"which Palo Alto listings are SB 9 eligible?"*

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `ADDRESSINTEL_API_KEY` | `demo` | Without a key the server uses the public demo tier: 10 requests/minute, 5 rows per call. Grab a free key at https://addressintel.co/developers for 30/min and 25 rows; the key is emailed to the address you enter. |
| `ADDRESSINTEL_API_BASE` | `https://addressintel.co/api` | Point at a local dev server (`http://localhost:3000/api`) when working on the API. |

## Development

```bash
npm run dev       # run from source over stdio
node test_mcp.mjs # smoke test: connect, list tools, call one
```

Tools are declared in one table in `src/index.ts`. Each entry carries its zod schema and
its advertised JSON Schema side by side, so adding a tool means adding one entry, and the
two shapes cannot drift apart.
