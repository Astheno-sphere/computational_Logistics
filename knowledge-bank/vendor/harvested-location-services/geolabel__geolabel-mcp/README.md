# GeoLabel MCP Server

<!-- mcp-name: io.github.TylerCoxDruin/geolabel -->

Turn GPS coordinates into AI-ready location context — for Claude Desktop, Claude Code, and any MCP-compatible assistant.

## What it does

Send coordinates. Get back a place name, category, and real-time opening hours:

```json
{
  "label": "Walmart",
  "category": "supermarket",
  "is_open": true,
  "closes_at": "23:00",
  "opening_hours": "Mo-Su 06:00-23:00"
}
```

Claude can then answer: *"You're at Walmart, which closes in 47 minutes."*

---

## Quick setup

### 1. Get a GeoLabel API key

Free at [geolabel.dev](https://geolabel.dev) — 100 requests/day, no credit card required.

### 2. Add to your agent

Pick your client below.

---

#### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "geolabel": {
      "command": "uvx",
      "args": ["geolabel-mcp"],
      "env": {
        "GEOLABEL_API_KEY": "glk_your_key_here"
      }
    }
  }
}
```

Restart Claude Desktop. The GeoLabel tool will appear in the tools list.

#### Claude Code

```bash
claude mcp add geolabel -- uvx geolabel-mcp
export GEOLABEL_API_KEY=glk_your_key_here
```

#### Hermes Agent

Edit `~/.hermes/config.json`:

```json
{
  "mcpServers": {
    "geolabel": {
      "command": "uvx",
      "args": ["geolabel-mcp"],
      "env": {
        "GEOLABEL_API_KEY": "glk_your_key_here"
      }
    }
  }
}
```

See [Hermes Agent MCP docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp) for more.

#### OpenClaw

```bash
# Register the server
openclaw mcp set geolabel \
  --command uvx \
  --args geolabel-mcp \
  --env GEOLABEL_API_KEY=glk_your_key_here

# Verify it's registered
openclaw mcp list
```

See [OpenClaw MCP docs](https://docs.openclaw.ai/cli/mcp) for more.

---

### 3. Use it

```
You: I'm at 41.8827, -87.6233 — what's here and is it open?

Agent: You're at Planet Fitness (a gym). It's currently open and closes
       at 11:00 PM tonight — you have about 3 hours left.
```

---

## Tools

### `get_location_label`

Identifies the nearest named place within `radius` metres of the given coordinates.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lat` | float | required | Latitude (-90 to 90) |
| `lng` | float | required | Longitude (-180 to 180) |
| `radius` | int | 100 | Search radius in metres (max 500) |

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `place` | string \| null | Raw venue name from OpenStreetMap |
| `label` | string | Clean, display-ready name |
| `category` | string \| null | Stable type: `gym`, `supermarket`, `restaurant`, etc. |
| `distance_meters` | float \| null | Distance from your coordinates to the place |
| `is_open` | bool \| null | `true` open · `false` closed · `null` no hours data |
| `opens_at` | string \| null | Next opening time `HH:MM` (when closed) |
| `closes_at` | string \| null | Today's closing time `HH:MM` (when open) |
| `opening_hours` | string \| null | Raw OSM `opening_hours` string |
| `cached` | bool | Served from 10-min cache; hours always recalculated live |

---

## Alternative installation

```bash
# pip
pip install geolabel-mcp

# run directly
GEOLABEL_API_KEY=glk_xxx geolabel-mcp
```

### Claude Code

```bash
claude mcp add geolabel -- uvx geolabel-mcp
```

Then set your key:

```bash
# add to your shell profile or .env
export GEOLABEL_API_KEY=glk_your_key_here
```

---

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `GEOLABEL_API_KEY` | Yes | Your GeoLabel API key |
| `GEOLABEL_BASE_URL` | No | Override API base URL (default: `https://api.geolabel.dev`) |

---

## Privacy

GeoLabel strips coordinates from all server logs before they touch disk. No movement history is stored. Data is processed in real-time and immediately discarded. [Full privacy policy →](https://geolabel.dev/terms.html)

---

## License

MIT
