# Product Hunt Draft

Product:

```text
Vessel Traffic MCP
```

Tagline:

```text
Vessel tracking and shipping schedules for AI agents
```

Website:

```text
https://github.com/tools-mcp/vessel-traffic-mcp
```

Topics:

```text
Developer Tools, Open Source, Artificial Intelligence, Logistics, Maps
```

Short description:

```text
An open-source MCP server that lets Claude, ChatGPT, Codex, and other AI clients query vessel identity, AIS-style positions, tracks, port calls, carrier schedules, vessel schedules, and delay heuristics with source attribution.
```

Maker comment:

```text
Hi Product Hunt,

I built Vessel Traffic MCP because maritime and logistics workflows often need a mix of vessel identity lookup, AIS-style position data, carrier schedules, and source verification.

The project is an MIT-licensed MCP server for Claude, ChatGPT, Codex, MCP Inspector, and other MCP clients.

What it supports:

- Vessel search by name, MMSI, IMO, and callsign
- Latest position lookup and map-area lookup
- Tracks and port calls
- Carrier schedules and vessel schedules
- Simple schedule delay heuristics
- Source provider and source URL in responses
- Public opt-in providers and BYOK commercial providers
- Fixture-backed tests with no live calls by default

The source-attribution piece is important: the goal is to route users back to the original service, not to hide the upstream provider.

I would appreciate feedback from people building AI-agent workflows, shipping/logistics tooling, and data-source integrations.
```

First comment follow-up:

````text
The quickest way to try it locally:

```bash
npm install -g @tools-mcp/vessel-traffic-mcp
VESSEL_MCP_TRANSPORT=stdio vessel-traffic-mcp
```

For a browser demo:

```bash
git clone https://github.com/tools-mcp/vessel-traffic-mcp.git
cd vessel-traffic-mcp
npm ci
npm run start:map
```

Then open http://127.0.0.1:8787 and search EVER GIVEN.
````

Screenshot checklist:

- Map UI showing `EVER GIVEN`.
- Current status, speed, course, freshness.
- Coordinates and observed time.
- Source provider and source URL button visible.
- Search results list visible.

Prepared screenshot:

```text
docs/marketing/assets/map-ui-ever-given.png
```
