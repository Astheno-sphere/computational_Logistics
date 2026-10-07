# Vessel Traffic MCP install guide for AI clients

## Repository

https://github.com/tools-mcp/vessel-traffic-mcp

## Agent discovery page

https://tools-mcp.github.io/vessel-traffic-mcp/

## What this server does

Vessel Traffic MCP is a read-only MCP server for maritime and logistics
workflows. It exposes tools for vessel identity lookup, AIS-style positions,
tracks, port calls, carrier schedules, vessel schedules, and delay heuristics.
Responses include source attribution and the server is designed for BYOK
provider credentials.

## Recommended local install

Use the published npm package:

```bash
npm install -g @tools-mcp/vessel-traffic-mcp
```

Run as a stdio MCP server:

```bash
VESSEL_MCP_TRANSPORT=stdio vessel-traffic-mcp
```

## MCP client config

Use this config for clients that accept JSON server definitions:

```json
{
  "mcpServers": {
    "vessel-traffic-mcp": {
      "command": "npx",
      "args": ["-y", "@tools-mcp/vessel-traffic-mcp"],
      "env": {
        "VESSEL_MCP_TRANSPORT": "stdio",
        "VESSEL_MCP_ENABLE_PUBLIC_PROVIDERS": "myshiptracking,tradlinx,aisfriends"
      }
    }
  }
}
```

## Environment variables

- `VESSEL_MCP_TRANSPORT`: set to `stdio` for local MCP clients.
- `VESSEL_MCP_ENABLE_PUBLIC_PROVIDERS`: optional comma-separated provider list.
- Provider API keys are optional and should stay in the user's local MCP client
  environment. Do not commit provider credentials.

## Smoke test

After installing dependencies from a clone, run:

```bash
npm run build
VESSEL_MCP_TRANSPORT=stdio node dist/index.js
```

Then connect from the MCP client and list tools. The server should expose
read-only vessel, position, track, port call, carrier schedule, vessel
schedule, delay heuristic, and search/fetch connector tools.

For search-style agent products, a good smoke test is:

```text
Use Vessel Traffic MCP. Search for EVER GIVEN, fetch the best result,
and include source.provider, source.landingUrl, observedAt, retrievedAt,
freshnessSeconds, confidence, coverage caveats, and a not-for-navigation note.
```

## Notes for Cline marketplace review

- The server is local-first and works over stdio via npm.
- Streamable HTTP is available for self-hosted deployments.
- The server is read-only; it does not mutate provider systems.
- Do not claim real-time navigation reliability. Availability depends on the
  configured provider and provider terms.
