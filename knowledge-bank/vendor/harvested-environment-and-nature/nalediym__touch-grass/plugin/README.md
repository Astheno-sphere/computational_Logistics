# touch-grass

A Claude Code plugin + MCP server that reminds AI agents to remind their coders to touch grass.

## What it does

At every session start, it:
1. Detects your location via IP
2. Fetches current weather and sunset time from open-meteo
3. Reads your grass-touching streak from `~/.touch-grass/state.json`
4. Injects a context block into the conversation telling the agent *when* and *how* to nudge you

When the agent calls the MCP server's `log_touch_grass` tool, your streak updates.

## Components

```
plugin/
├── .claude-plugin/plugin.json    # Plugin manifest (hooks + MCP)
├── hooks/session-start.mjs       # SessionStart hook (zero deps)
├── mcp-server/
│   ├── index.mjs                 # MCP server (uses @modelcontextprotocol/sdk)
│   └── package.json
├── lib/
│   ├── grass.mjs                 # Weather, sunset, state — shared by hook + MCP
│   └── nudge.mjs                 # Nudge message generation
└── skills/touch-grass/SKILL.md   # Tells the agent how to nudge
```

## Install

### Option 1: Claude Code plugin (recommended)

From the repo root:

```bash
cd plugin/mcp-server && npm install && cd ../..
/plugin install ./plugin
```

### Option 2: Manual (any MCP-compatible agent: Cursor, Claude Desktop, etc.)

```bash
cd plugin/mcp-server && npm install
```

Then add to your agent's MCP config:

```json
{
  "mcpServers": {
    "touch-grass": {
      "command": "node",
      "args": ["/absolute/path/to/plugin/mcp-server/index.mjs"]
    }
  }
}
```

The SessionStart hook is Claude Code specific — other agents will only get the MCP tools.

## Data and privacy

Everything is stored locally in `~/.touch-grass/`:
- `state.json` — streak, session counts, last touched date
- `config.json` — cached location (24h), weather thresholds

Nothing leaves your machine except:
- IP geolocation lookup to `ipapi.co` (once per 24h, cached)
- Weather lookup to `api.open-meteo.com` (on each session start)

Both are free, no API keys, no account.

## Tools exposed to the agent

| Tool | Purpose |
|---|---|
| `check_grass_conditions` | Weather, sunset timing, streak state — the decision context |
| `suggest_activity` | Specific activity recommendation |
| `log_touch_grass` | Record a grass-touching session (updates streak) |
| `get_stats` | Raw stats |

## Configuration

Edit `~/.touch-grass/config.json`:

```json
{
  "location": null,
  "niceWeatherThresholdC": 15,
  "breakIntervalHours": 2,
  "enabled": true
}
```

Set `location` manually to override IP detection:

```json
{
  "location": {
    "lat": 40.7128,
    "lon": -74.0060,
    "city": "New York",
    "timezone": "America/New_York",
    "fetchedAt": 9999999999999
  }
}
```

## Test locally

```bash
# Run the hook directly — should print a JSON blob with nudge text
node plugin/hooks/session-start.mjs

# Run the MCP server
node plugin/mcp-server/index.mjs
# Then send a ListTools request via stdin (use MCP Inspector: npx @modelcontextprotocol/inspector)
```
