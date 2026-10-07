<div align="center">

# 🌿 touch-grass

**The Claude Code plugin that reminds you to go outside.**

Weather-aware · sunset-aware · session-aware · never interrupts your flow.

[![CI](https://github.com/nalediym/touch-grass/actions/workflows/ci.yml/badge.svg)](https://github.com/nalediym/touch-grass/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/github/license/nalediym/touch-grass?style=flat-square&color=22c55e)](https://github.com/nalediym/touch-grass/blob/main/LICENSE)
[![Stars](https://img.shields.io/github/stars/nalediym/touch-grass?style=flat-square&color=22c55e)](https://github.com/nalediym/touch-grass/stargazers)
[![Last commit](https://img.shields.io/github/last-commit/nalediym/touch-grass?style=flat-square&color=22c55e)](https://github.com/nalediym/touch-grass/commits/main)
[![MCP](https://img.shields.io/badge/MCP-server-blueviolet?style=flat-square)](https://modelcontextprotocol.io)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-ff9500?style=flat-square)](https://claude.com/claude-code)
[![Glama TDQS](https://glama.ai/mcp/servers/nalediym/touch-grass/badges/score.svg)](https://glama.ai/mcp/servers/nalediym/touch-grass)

[Install](#install) · [How it works](#how-it-works) · [Tools](#mcp-tools) · [Privacy](#privacy) · [Site](https://touch-grass-xi.vercel.app)

</div>

---

<div align="center">
  <img src="https://raw.githubusercontent.com/nalediym/touch-grass/main/plugin/docs/demo.gif" alt="touch-grass demo — SessionStart hook injects live weather, sunset timing, and streak state; the agent nudges the user outside at a natural pause and logs the activity via the MCP server" width="860" />
</div>

## Why this exists

Pomodoro timers interrupt your flow. Calendar blocks get ignored. The best time to step away from your editor is a moving target that depends on the weather, the time of day, your streak, and what you're in the middle of — none of which a dumb interval timer knows.

**Your AI coding agent already knows when you hit a natural pause.** It finished the feature. It's waiting for you to answer a question. The tests went green. That's the right moment to nudge — not every 25 minutes on the dot.

touch-grass turns your agent into a context-aware break buddy. A SessionStart hook feeds it live weather and sunset timing at the top of every session. A skill teaches it tiger-mom tone (warm, specific, never preachy). An MCP server lets it log when you actually went outside. You keep your flow. It keeps you honest.

## What it does

Like a Pomodoro timer, but it knows the weather, your sunset time, and your coding streak — and it talks to your AI agent instead of interrupting you.

- **SessionStart hook** injects live weather, sunset timing, and streak state into your agent's context every time a Claude Code session starts.
- **MCP server** exposes four tools your agent (Claude Code, Cursor, Claude Desktop, Codex) can call on demand.
- **Skill** teaches the agent when to nudge, when to stay quiet, and what tone to use (tiger mom, not preachy).

It's a Claude Code pomodoro replacement for people who'd rather have their coding agent tell them to go outside than have a screen-blocking timer break their flow.

## Install

**Claude Code** (full experience — hook + MCP + skill):

```bash
/plugin install nalediym/touch-grass
```

That's it. Open a new session — the hook fires, the context drops in, your agent takes it from there.

<details>
<summary><strong>Other MCP clients</strong> (Cursor, Claude Desktop, Codex) — MCP tools only, no proactive hook</summary>

```bash
git clone https://github.com/nalediym/touch-grass
cd touch-grass/plugin/mcp-server && npm install
```

Then add to your client's MCP config:

```json
{
  "mcpServers": {
    "touch-grass": {
      "command": "node",
      "args": ["/absolute/path/to/touch-grass/plugin/mcp-server/index.mjs"]
    }
  }
}
```

You get the four MCP tools but lose the SessionStart hook, which is Claude Code specific. Your agent will only bring up grass when you explicitly ask about it.

</details>

## How it works

![How it works](https://raw.githubusercontent.com/nalediym/touch-grass/main/docs/flowchart.svg)

<details><summary>Mermaid source</summary>

```mermaid
flowchart LR
  A[Claude Code<br/>session starts] --> B[SessionStart hook fires]
  B --> C[ip-api.com<br/>location]
  B --> D[open-meteo.com<br/>weather + sunset]
  B --> E[~/.touch-grass/state.json<br/>streak + sessions]
  C --> F[Context injection]
  D --> F
  E --> F
  F --> G[Agent<br/>decides when to nudge]
  G -.calls.-> H[MCP tools]
  H --> E
```

</details>

On session start, a hook script runs. It detects your location from your public IP (cached 24h), fetches current weather and sunset time from open-meteo, reads your local streak file, and synthesises a short context block for the agent. The agent reads it, sits on it, and at a natural pause — feature done, bug fixed, waiting for input — nudges you outside with language that matches the actual conditions.

When you confirm you went outside, the agent calls `log_touch_grass` via the MCP server, which increments your streak in the local state file.

## MCP tools

| Tool | Purpose | Returns |
|---|---|---|
| `check_grass_conditions` | Weather, temperature, minutes until sunset, and the user's streak state. Decision context. | JSON block with `weather`, `sunset`, `isNice`, `minutesToSunset`, `state` |
| `suggest_activity` | Random activity recommendation, weighted by time of day. Golden hour gets sunset-specific suggestions. | Plain text like `"🌅 catch the sunset"` |
| `log_touch_grass` | Records that the user went outside. Updates their streak. Call only when confirmed. | Confirmation with new streak count |
| `get_stats` | Raw session telemetry and streak history. | JSON block |

All four are callable from any MCP-compatible agent. In Claude Code, the agent mostly uses them via the context the hook injects — you rarely need to call them manually.

## Example prompts

The plugin works ambiently, but these phrasings work well if you want to bring it up yourself:

- *"Should I touch grass right now?"*
- *"What's my streak?"*
- *"Remind me to go outside before sunset."*
- *"I just went for a walk, log it."*
- *"Is it nice out?"*

## Privacy

Everything is local-first.

- **Stored on your machine:** `~/.touch-grass/state.json` (streak, session counts, last touched date) and `~/.touch-grass/config.json` (cached location, weather threshold).
- **Leaves your machine:** your public IP is sent to `ip-api.com` once every 24 hours to resolve city coordinates, and those coordinates are sent to `api.open-meteo.com` on each session start to get weather and sunset.
- **Never leaves your machine:** your streak, your activity notes, your coding schedule, your prompts, anything from your Claude Code session.

No accounts. No API keys. No telemetry. No analytics. No auth. If you want to disable network access entirely, pin `"location"` manually in `~/.touch-grass/config.json` and the IP lookup never fires.

## Configuration

<details>
<summary>Override defaults in <code>~/.touch-grass/config.json</code></summary>

```json
{
  "location": {
    "lat": 40.7128,
    "lon": -74.0060,
    "city": "New York",
    "timezone": "America/New_York",
    "fetchedAt": 9999999999999
  },
  "niceWeatherThresholdC": 15,
  "breakIntervalHours": 2,
  "enabled": true,
  "customActivities": [
    { "label": "walk to the corner store", "emoji": "🛒" },
    { "label": "sit on the fire escape", "emoji": "🪜" }
  ]
}
```

| Key | Default | Description |
|---|---|---|
| `location` | auto (ip-api) | Pin to a specific location. Set `fetchedAt` to a future timestamp to disable auto-refresh. |
| `niceWeatherThresholdC` | `15` | Temperature (°C) below which weather isn't considered "nice." |
| `breakIntervalHours` | `2` | After this many hours of continuous coding, nudges get firmer. |
| `enabled` | `true` | Set to `false` to silence the hook without uninstalling. |
| `customActivities` | `null` | Replace the default activity list with your own. Each entry is `{ "label": "...", "emoji": "..." }` or just a plain string. Supporter perk. |

</details>

## Troubleshooting

<details>
<summary><strong>I installed the plugin but my agent doesn't mention grass at session start.</strong></summary>

Run the hook by hand to confirm it works:

```bash
node plugin/hooks/session-start.mjs
```

You should see a JSON object with `hookSpecificOutput.additionalContext` containing the nudge. If `additionalContext` is an empty string, the hook couldn't reach `ip-api.com` or `open-meteo.com` — check your network. If the hook is fine but Claude Code never calls it, the plugin isn't wired up — re-run `/plugin install nalediym/touch-grass` in a fresh session.

</details>

<details>
<summary><strong>How do I know the hook actually fired in my last session?</strong></summary>

Check `~/.touch-grass/state.json`. The `sessionStart`, `lastSessionStart`, and `totalCodingSessions` fields update every time the hook runs. If `sessionStart` is older than your most recent `claude` invocation, the hook isn't running.

</details>

<details>
<summary><strong>ip-api.com is blocked on my network. Can I still use this?</strong></summary>

Yes. Pin your location manually in `~/.touch-grass/config.json`:

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

The high `fetchedAt` timestamp prevents the 24h cache from expiring, so the IP lookup never fires. Weather will still be fetched from `open-meteo.com`.

</details>

<details>
<summary><strong>How do I disable the nudges without uninstalling?</strong></summary>

Set `"enabled": false` in `~/.touch-grass/config.json`. The hook still writes session telemetry but emits empty context, so the agent stops seeing grass reminders.

</details>

<details>
<summary><strong>How do I reset my streak?</strong></summary>

Delete or edit `~/.touch-grass/state.json`. The file will be recreated on the next session with defaults.

</details>

<details>
<summary><strong>How do I uninstall?</strong></summary>

```bash
/plugin uninstall touch-grass
rm -rf ~/.touch-grass
```

The `~/.touch-grass` directory only holds your state and cached location — safe to delete.

</details>

## Development

```bash
git clone https://github.com/nalediym/touch-grass
cd touch-grass/plugin/mcp-server && npm install

# Test the hook directly (outputs JSON context)
node ../hooks/session-start.mjs

# Test the MCP server with the inspector
npx @modelcontextprotocol/inspector node ./index.mjs
```

Three moving parts:

- **`plugin/hooks/session-start.mjs`** — zero-dep Node script. Called by Claude Code on session start. Outputs JSON to stdout.
- **`plugin/mcp-server/index.mjs`** — MCP server. Uses `@modelcontextprotocol/sdk`. stdio transport.
- **`plugin/lib/grass.mjs`** and **`plugin/lib/nudge.mjs`** — shared logic (weather, sunset, state, nudge text).

The hook and the MCP server read from the same state file, so they stay in sync.

## Related

- [Claude Code plugin docs](https://docs.claude.com/claude-code/plugins)
- [Model Context Protocol](https://modelcontextprotocol.io)
- [open-meteo.com](https://open-meteo.com) — free, keyless weather API
- [ip-api.com](https://ip-api.com) — free, keyless IP geolocation

## License

[MIT](./LICENSE) · Built in the shade.

----

[![touch-grass MCP server](https://glama.ai/mcp/servers/nalediym/touch-grass/badges/card.svg)](https://glama.ai/mcp/servers/nalediym/touch-grass)

---

<div align="center">
  <sub>Your screen will be here when you get back. 🌱</sub>
</div>


## Support

touch-grass is free and MIT-licensed. If it's helped you step away from the screen, consider supporting it:

**[Support on Polar →](https://polar.sh/nalediym)** — $9 one-time. Your name goes in the supporters list, you get priority issues, and you unlock custom activity lists in config.

[![Polar](https://img.shields.io/badge/support-polar.sh-blue?style=flat-square)](https://polar.sh/nalediym)
[![GitHub Sponsors](https://img.shields.io/badge/sponsor-github-pink?style=flat-square)](https://github.com/sponsors/nalediym)

## Supporters

*Be the first. [Support on Polar →](https://polar.sh/nalediym)*
