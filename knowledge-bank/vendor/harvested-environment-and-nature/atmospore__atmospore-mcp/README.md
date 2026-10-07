# atmospore-mcp

[MCP server](https://modelcontextprotocol.io) for [Atmospore](https://atmospore.com).
Lets Claude (and other AI assistants supporting MCP) answer questions about pollen
forecasts at any point on Earth.

## What it does

Adds four tools to Claude:

| Tool | Use it for |
|---|---|
| `get_pollen(lat, lon, forecast_days)` | "What's the pollen forecast in Oslo this week?" |
| `get_top_species(lat, lon, limit)` | "What pollen is highest in Bergen right now?" |
| `get_area_average(lat, lon, radius_km, forecast_days)` | "Is tree or grass pollen worse in London this week?" |
| `list_supported_species()` | "What species do you cover?" |

And one resource:
- `atmospore://help` — usage notes browsable from Claude Desktop

Coordinates work anywhere on the planet — the model has global coverage at ~28 km resolution.

## Install

```bash
pip install atmospore-mcp
```

## Setup in Claude Desktop

1. Get a free Atmospore API key at [atmospore.com/account](https://atmospore.com/account)
   (100 calls/day, no credit card required).
2. Edit your Claude Desktop config:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%/Claude/claude_desktop_config.json`
3. Add Atmospore as an MCP server:

```json
{
  "mcpServers": {
    "atmospore": {
      "command": "atmospore-mcp",
      "env": {
        "ATMOSPORE_API_KEY": "ak_your_key_here"
      }
    }
  }
}
```

4. Restart Claude Desktop.
5. Ask Claude: "what's the pollen in Oslo today?" — it'll call the tool and report back.

## Example prompts

- "What's the pollen forecast for Oslo this week?"
- "Is tree or grass pollen worse in Stockholm right now?"
- "I'm allergic to birch — when is birch pollen peaking in Bergen?"
- "Compare pollen levels in London and Copenhagen today."

## Quotas

Each tool call hits the Atmospore API and counts against your key's daily quota. The free
tier (100 calls/day) covers casual use — typical Claude conversations fire 1–5 tool calls.
Heavy users (~5+ pollen conversations/day) will want the [paid plan](https://atmospore.com/plans).

When you hit the quota the tool returns a structured `quota_exceeded` response and Claude
will tell you in plain language: *"You've hit your Atmospore daily limit. Upgrade at
[atmospore.com/plans](https://atmospore.com/plans)."*

## Develop locally

```bash
git clone https://github.com/atmospore/atmospore-mcp
cd atmospore-mcp
pip install -e ".[test]"
pytest
ATMOSPORE_API_KEY=ak_... atmospore-mcp  # runs the server on stdio
```

## Related

- [atmospore](https://github.com/atmospore/atmospore-python) — the underlying Python client this server wraps.
- [atmospore.com](https://atmospore.com) — the hosted forecast and developer dashboard.

## License

MIT.
