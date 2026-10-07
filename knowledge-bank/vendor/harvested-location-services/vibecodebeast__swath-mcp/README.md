# Swath MCP Server

MCP server for [Swath API](https://swathapi.com) — **America's first AI-native storm intelligence API**. Radar-verified hail and damaging-wind swaths, and every property under them, inside Claude, ChatGPT, or any MCP client.

[![swath-mcp MCP server](https://glama.ai/mcp/servers/@vibecodebeast/swath-mcp/badges/score.svg)](https://glama.ai/mcp/servers/@vibecodebeast/swath-mcp)

## Tools

| Tool | What it does |
|---|---|
| `find_storms` | Radar-verified storms (hail ≥ threshold, wind) for an area/timeframe |
| `get_swath_report` | Every property under a swath — roof age, owner-occupancy, assessed value |
| `get_report_quote` | Exact credit cost of a report before you run it |
| `email_report` | Emails you the report summary |
| `lookup_property` | Storm history + parcel intel for one address |
| `create_monitor` / `list_monitors` | Watch a territory; webhook + email alerts on radar verification |
| `get_usage` | Credits used / remaining |
| `show_swath_map` | Gradient swath map image |

## Quick start (Claude Desktop)

```json
{
  "mcpServers": {
    "swath": {
      "command": "npx",
      "args": ["-y", "tsx", "/path/to/swath-mcp/src/index.ts"],
      "env": { "SWATH_API_KEY": "sk_..." }
    }
  }
}
```

No key yet? Every tool answers with a signup hint — get a free key (100 credits) at [swathapi.com](https://swathapi.com).

**claude.ai / ChatGPT users:** you don't need this repo — add the hosted connector instead: `https://swathapi.com/mcp` (OAuth, no key handling). See [swathapi.com/integrations](https://swathapi.com/integrations).

## Env

- `SWATH_API_KEY` — your API key (`sk_...`)
- `SWATH_API_URL` — API base (default `https://swathapi.com`)

## Data honesty

Hail is verified against NOAA MRMS radar; wind against measured NWS storm reports. No forecasts, no fabricated uptime — see [swathapi.com/status](https://swathapi.com/status).

Developed by [vibecodebeast.ai](https://vibecodebeast.ai).
