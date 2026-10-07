# Vessel Traffic MCP Launch Kit

This kit is for overseas directory submissions and community posts. Keep the
project position consistent: read-only MCP access to vessel and schedule data,
source attribution on every live/public response, and BYOK for commercial
providers.

## Canonical Links

- GitHub: https://github.com/tools-mcp/vessel-traffic-mcp
- npm: https://www.npmjs.com/package/@tools-mcp/vessel-traffic-mcp
- MCP Registry name: `io.github.tools-mcp/vessel-traffic-mcp`
- Local map UI: `npm run start:map`, then open `http://127.0.0.1:8787`
- HTTP server card: `GET /.well-known/mcp/server-card.json`

## One-Liners

Short:

```text
Open-source MCP server for vessel tracking, AIS-style positions, schedules, and source-attributed maritime data.
```

Directory summary:

```text
Vessel Traffic MCP is a read-only Model Context Protocol server for vessel identity lookup, AIS-style positions, tracks, port calls, carrier schedules, vessel schedules, and delay heuristics. It supports fixture-backed tests, opt-in public providers, BYOK commercial providers, and source URLs for verification.
```

Product tagline:

```text
Vessel tracking and shipping schedules for AI agents
```

## Long Description

```text
Vessel Traffic MCP connects Claude, ChatGPT, Codex, MCP Inspector, and other MCP clients to authorized maritime data sources through one normalized read-only tool surface.

It supports vessel search by name, MMSI, IMO, and callsign; latest position lookup; bounding-box lookup; recent tracks; port calls; carrier schedule search; vessel schedules; and schedule delay heuristics.

The project is built around source attribution. Live and public-provider responses expose source.provider and source.landingUrl so users can verify the original source and visit the service behind the data. Commercial providers are BYOK only, and the default test path uses sanitized fixtures without live calls or API keys.
```

## Install Snippet

```bash
git clone https://github.com/tools-mcp/vessel-traffic-mcp.git
cd vessel-traffic-mcp
npm ci
npm run build
VESSEL_MCP_TRANSPORT=stdio \
VESSEL_MCP_ENABLE_PUBLIC_PROVIDERS=myshiptracking,tradlinx,aisfriends \
npm start
```

MCP clients should point to the absolute path of `dist/index.js` and set:

```text
VESSEL_MCP_TRANSPORT=stdio
VESSEL_MCP_ENABLE_PUBLIC_PROVIDERS=myshiptracking,tradlinx,aisfriends
```

## Demo Script

Use this flow for screenshots, GIFs, and live demos:

1. Start the map UI:

   ```bash
   npm run start:map
   ```

2. Open `http://127.0.0.1:8787`.
3. Search `EVER GIVEN`.
4. Show the current state panel, coordinates, source provider, source URL, and map marker.
5. Open the source link to demonstrate attribution.
6. In an MCP client, ask:

   ```text
   Find the current position of EVER GIVEN. Include source.provider and source.landingUrl.
   ```

7. Ask:

   ```text
   Search carrier schedules from KRPUS to NLRTM and include the source URL.
   ```

## Ready Asset

Desktop map UI screenshot:

```text
docs/marketing/assets/map-ui-ever-given.png
```

Use it for Product Hunt, Reddit image posts, directory pages that accept
screenshots, and launch articles.

## Keywords

```text
mcp, model-context-protocol, vessel tracking, ship tracking, AIS, maritime, shipping, logistics, Claude, ChatGPT, Codex, BYOK, MarineTraffic, VesselFinder, AISStream, AISHub, schedules
```

## Safety Notes For Every Post

- Do not claim to bypass paywalls, CAPTCHA, Cloudflare, login, or provider terms.
- Do not say the project owns or redistributes upstream data.
- Do say that responses include source provider and source URL.
- Do say commercial providers are Bring Your Own Key.
- Do not paste API keys, cookies, HAR files, screenshots of logged-in dashboards, or raw captures.
