# @dronelytics/mcp

[![dronelytics-mcp MCP server](https://glama.ai/mcp/servers/markpdxt/dronelytics-mcp/badges/score.svg)](https://glama.ai/mcp/servers/markpdxt/dronelytics-mcp)

MCP (Model Context Protocol) server for the [Dronelytics](https://dronelytics.io) drone mission planning platform. Enables AI assistants to query US drone airspace, plan missions, manage drone profiles, and export flight plans.

**The first drone platform built for AI agents.** [Learn more](https://dronelytics.io/mcp) | [Read why we built this](https://dronelytics.io/why-we-built-mcp-server-drone-airspace)

## Setup

### 1. Generate an API key

Go to **Settings > API Keys** in [hub.dronelytics.io](https://hub.dronelytics.io) and create a new key.

### 2. Configure your MCP client

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "dronelytics": {
      "command": "npx",
      "args": ["-y", "@dronelytics/mcp"],
      "env": {
        "DRONELYTICS_API_KEY": "dk_your_key_here"
      }
    }
  }
}
```

**Claude Code** (`.mcp.json` in your project or `~/.claude/.mcp.json` globally):

```json
{
  "mcpServers": {
    "dronelytics": {
      "command": "npx",
      "args": ["-y", "@dronelytics/mcp"],
      "env": {
        "DRONELYTICS_API_KEY": "dk_your_key_here"
      }
    }
  }
}
```

**Cursor / Windsurf** — same npx config in your MCP settings.

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DRONELYTICS_API_KEY` | Yes | — | Your API key (starts with `dk_`) |
| `DRONELYTICS_API_URL` | No | `https://hub.dronelytics.io/api/v1` | API base URL (override for local dev) |

## Tools (24)

### Airspace Intelligence
| Tool | Description |
|------|-------------|
| `check_airspace` | Query 11 FAA airspace layers at a lat/lng — returns flyability assessment |
| `get_active_tfrs` | List active TFRs near a location |
| `get_notams` | Get active NOTAMs near a location |
| `check_live_traffic` | Live ADS-B aircraft traffic near a location |
| `validate_flight` | Part 107 compliance check for location, altitude, and time |
| `preflight_briefing` | GO/CAUTION/NO-GO briefing for a saved mission |

### Mission Management
| Tool | Description |
|------|-------------|
| `list_missions` | List all user missions |
| `get_mission` | Get full mission with waypoints |
| `create_mission` | Create a new mission |
| `update_mission` | Update an existing mission |
| `delete_mission` | Delete a mission |
| `duplicate_mission` | Clone a mission |
| `share_mission` | Generate a public share link |
| `export_mission` | Export to KML, GPX, QGC, Litchi CSV, or WPML |
| `import_litchi` | Import a Litchi CSV file |

### Mission Generation
| Tool | Description |
|------|-------------|
| `list_cameras` | List camera presets for survey planning |
| `generate_grid_survey` | Generate grid/mapping survey from polygon |
| `generate_orbit_mission` | Generate orbit around a point of interest |
| `generate_panorama_mission` | Generate panorama capture grid |
| `generate_spiral_mission` | Generate spiral survey |
| `generate_corridor_mission` | Generate corridor mapping along a path |

### Drone Profiles
| Tool | Description |
|------|-------------|
| `list_drones` | List user's drone profiles |
| `create_drone` | Add a drone profile |
| `update_drone` | Update a drone profile |
| `delete_drone` | Remove a drone profile |

## Airspace Data

The `check_airspace` tool queries 11 FAA data layers in a single call:

- **UASFM ceiling** — maximum altitude grid from the FAA UAS Facility Map
- **Class airspace** — B, C, D, E2, E3, E4 controlled airspace boundaries
- **TFRs** — active Temporary Flight Restrictions (refreshed every 15 minutes)
- **NOTAMs** — Notices to Air Missions with proximity filtering
- **Special Use Airspace** — prohibited areas, restricted areas, MOAs, alert areas
- **NSUFRs** — National Security UAS Flight Restrictions
- **Stadiums** — stadium TFR zones within 3nm
- **FRIAs** — FAA-Recognized Identification Areas for recreational flyers
- **Airports** — nearby airports with distance and type
- **Mode C veil** — 30nm transponder requirement zones around major airports
- **Military training routes** — low-altitude military flight corridors

All data is sourced from FAA ArcGIS services and refreshed automatically.

## Example Prompts

- "Can I fly a drone at the Golden Gate Bridge?"
- "Plan a grid survey of this 10-acre field at 200ft with my DJI Mavic 3"
- "Give me a pre-flight briefing for my construction survey mission"
- "Export all my missions tagged 'client-project' to KML"
- "What airports are within 5nm of 37.7749, -122.4194?"
- "Validate a flight at 300ft at the Statue of Liberty at 2pm tomorrow"

## npm

```
npm install @dronelytics/mcp
```

https://www.npmjs.com/package/@dronelytics/mcp

## License

MIT
