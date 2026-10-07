<!--
  AUTO-GENERATED from the Off-Nadir Delta contract registry
  (src/lib/api/toolRegistry.ts + src/lib/api/mcpResources.ts) by
  scripts/gen-contract-artifacts.mjs in the Off-Nadir Delta application repo.

  DO NOT EDIT BY HAND — `node scripts/gen-contract-artifacts.mjs --check` fails on drift,
  and scripts/publish-distribution.sh refuses to publish a stale copy.
-->

# Off-Nadir Delta MCP

**From first signal to satellite evidence.** Give an AI agent a live intelligence workflow:
discover an event, verify the reporting, identify what evidence is missing, determine whether a
satellite can actually resolve it, and produce a collection-ready plan.

Real-time event and geospatial intelligence for OSINT, geopolitical risk, and GEOINT work —
source-linked, geolocated, and current, not a training snapshot.

`22` tools · MCP server version `3.3.0` · [full reference](https://offnadir-delta.com/docs/mcp)

## What it does

Seeing the event is easy. Knowing what you can *prove* — and what evidence is still missing — is
the product. Delta:

- monitors emerging world events and geolocates them
- checks claims against source-linked open data, and reports the source breadth behind each one
- assesses whether the event is observable from space, at what resolution, and by which sensor
- returns a collection-ready recommendation: what to collect, where, and when

## Connect

### Hosted server — recommended

No install. Point any MCP client at the remote endpoint and approve once over OAuth 2.1
(Dynamic Client Registration is supported, so most clients need only the URL):

```
https://offnadir-delta.com/api/v1/mcp
```

In the Claude or ChatGPT apps: **Settings → Connectors → Add custom connector**, paste that URL.
Cursor and VS Code have one-click installs on the [docs page](https://offnadir-delta.com/docs/mcp).

Claude Code:

```bash
claude mcp add --transport http off-nadir-delta https://offnadir-delta.com/api/v1/mcp
```

### This package — local stdio

Use this when your client cannot do remote OAuth, or you would rather hold an API key in an
environment variable and pin a version. Get a key at
[offnadir-delta.com/account/api](https://offnadir-delta.com/account/api).

```json
{
  "mcpServers": {
    "off-nadir-delta": {
      "command": "npx",
      "args": ["-y", "offnadir-delta-mcp"],
      "env": { "OFFNADIR_DELTA_API_KEY": "ond_..." }
    }
  }
}
```

Docker:

```bash
docker run -i --rm -e OFFNADIR_DELTA_API_KEY=ond_... offnadir-delta-mcp
```

The package forwards `tools/call` to the hosted server with your key. `tools/list` answers
locally from a generated catalog, so registries can introspect it without credentials.

### First call — free

11 of the 22 tools cost nothing, so the first thing you run is free:

> Give me the latest Daily World Brief. Lead with the three most significant developments,
> explain why each matters, and cite the supporting signals.

Then try the full signal-to-satellite workflow:

> Find the highest-priority observable event from the last 24 hours, verify the reporting, and
> recommend the best available satellite collection plan.

## Tools

### Discover

What is happening, what changed, and what today looks like.

| Tool | What it does | Cost |
| --- | --- | --- |
| `query_signals` | Geolocated world events from global news media, AI-enriched with severity/GEOINT scores and collection recommendations. | 3 tok |
| `get_world_brief` | AI world brief: daily (prior UTC day, all plans) or weekly/monthly by plan. | free |
| `query_developments` | What actually CHANGED about the events in an area, not which articles are new. | 3 tok |
| `get_event_thread` | One event end to end: state plus every change in order — the "new event or update" distinction a feed cannot make. | free |
| `search_entities` | Find a named place (airport, base, plant, port, dam, strait…) in any language or by IATA/ICAO code. | 1 tok |
| `get_entity` | What has happened at one place: the registry record plus its most recent linked events, each with HOW it was linked. | 1 tok |
| `get_related_events` | The relations recorded for one event: others at the same registry facility, naming the same place, or stored as the same campaign, each saying what is shared; plus reports merged into it. | 1 tok |

### Plan

Whether a satellite can resolve it, which one, and when it next passes.

| Tool | What it does | Cost |
| --- | --- | --- |
| `search_imagery` | Search the imagery catalog over an area and window. | 2 tok |
| `plan_event_imagery` | The deterministic imagery plan for ONE event: checks BOTH sensors exactly once — sentinel-1-grd (SAR, the only look that survives cloud and night) and sentinel-2-l2a — against the event footprint and a pre/post window. | 4 tok |
| `rank_imaging_priority` | WHERE, and with what class of satellite, observation is most worthwhile now: composite IMPORTANCE crossed with the SPEC CLASS the required resolution demands — coarse, hr (free Sentinel-class) or vhr. | 1 tok |
| `predict_satellite_passes` | WHEN a place can next be imaged and by WHAT: 13 free-systematic and commercial-taskable families. | 2 tok |

### Analyze

Turn reporting into a cited assessment you can audit afterwards.

| Tool | What it does | Cost |
| --- | --- | --- |
| `assess_signal` | AI remote-sensing deep-dive for one signal: what to observe, sensors, a collection window. | 5/15 tok |
| `ask_analyst` | Ask the Delta Analyst an OSINT/GEOINT question; returns a structured brief. | 5–123 tok |
| `get_analyst_job` | Status and result of an ask_analyst run. | free |

### Watch

Stand up continuous coverage and be told only when the answer changes. Creating and listing cost nothing — you are metered only when a check actually fires, or a new acquisition is actually measured.

| Tool | What it does | Cost |
| --- | --- | --- |
| `list_watches` | The Watchlist as one list, each entry with a state bucket. | free |
| `list_notifications` | What changed across the Watchlist, newest first: one row per change a watch reported, with read state. | free |
| `get_watch` | One watch end to end: target, state, latest change, measurements with recent series, standing-order questions, and for an event watch its stage, developments and thread, plus this account's notes. | free |
| `create_watch` | Add a target to the Watchlist. | free |
| `update_watch` | Pause, resume or close a watch. | free |
| `delete_watch` | Delete a watch and its underlying resources — bound monitored areas with their history, and standing orders. | free |
| `add_note` | Add a note to a watch, start a thread, or reply. | free |

### Account

Pre-flight your token balance before a metered call.

| Tool | What it does | Cost |
| --- | --- | --- |
| `get_usage` | The calling key's remaining token balance and plan capabilities. | free |

## Pricing and metering

Usage-based Delta tokens, identical over REST and MCP. Costs above are generated from the same
constant the biller reads, and every metered result carries the exact charge it incurred — so
you never have to trust a number in a README. Free tools never touch the balance.

`ask_analyst` is **hybrid-async**: it enqueues a run and returns a `job_id` immediately; poll
`get_analyst_job` (free — the run is charged once, on completion). Most questions finish in
~30–90s; a brief with satellite-imagery lookups or many sources can take 2–3 minutes.

The API and the MCP server are available on **every plan, including Free** — the only gate is
your token balance. Call `get_usage` (free) to pre-flight. Current limits and package prices:
[offnadir-delta.com/pricing](https://offnadir-delta.com/pricing).

## Authentication

Two credentials are accepted on the hosted endpoint:

- **OAuth 2.1** with PKCE and Dynamic Client Registration — for interactive clients
- **Bearer API key** (`Authorization: Bearer ond_...`) — for servers, CI, and this stdio package

Keys are shown once at creation, hashed at rest, and revocable at any time from
[/account/api](https://offnadir-delta.com/account/api).

## Resources

| Resource | Description |
| --- | --- |
| `brief://latest` | The most recent AI-synthesized Daily World Brief (JSON). Free. |
| `signals://schema` | JSON Schema of the public Signal shape returned by query_signals / /api/v1/signals. |
| `usage://current` | Remaining token balance and plan capabilities for the calling key. Free. |
| `status://current` | How current the data is (ingestion/enrichment frontier), the Daily World Brief status, and an Operational/Delayed/Degraded roll-up. Free. |
| `brief://{date}` | The Daily World Brief for a specific UTC date (YYYY-MM-DD). Free. |
| `watch://{watch_id}` | A Watchlist entry with its current state, latest meaningful change, measurements, (for event watches) the full event thread, and the notes kept against it. The same body get_watch returns. Free. |

## Links

- [Tool reference, setup, and one-click installs](https://offnadir-delta.com/docs/mcp)
- [REST API reference](https://offnadir-delta.com/docs/api) · [OpenAPI](https://offnadir-delta.com/api/v1/openapi.json)
- [Changelog and compatibility policy](https://offnadir-delta.com/docs/changelog)
- [Live server version probe](https://offnadir-delta.com/api/v1/version) (no auth, no tokens)

## License

Apache-2.0
