# Vessel Traffic MCP

## Tagline

Read-only maritime and logistics tools for MCP clients.

## Description

Vessel Traffic MCP connects MCP-compatible AI clients to maritime and logistics
data through a read-only tool surface. It supports vessel identity lookup,
AIS-style positions, tracks, port calls, carrier schedules, vessel schedules,
and delay heuristics. The server is designed for local stdio use through npm,
with Streamable HTTP available for self-hosted deployments. Provider credentials
are BYOK and responses include source attribution.

## Setup Requirements

- `VESSEL_MCP_TRANSPORT` (required for local clients): set to `stdio`.
- `VESSEL_MCP_ENABLE_PUBLIC_PROVIDERS` (optional): comma-separated public
  provider list such as `myshiptracking,tradlinx`.
- Provider API keys (optional): configure only in the user's local MCP client
  environment. Do not commit provider credentials.

## Category

Data & Analytics

## Features

- Look up vessel identity and metadata from configured maritime providers.
- Retrieve AIS-style vessel positions with source attribution.
- Inspect vessel tracks, port calls, and schedule context.
- Query carrier schedules and vessel schedules for logistics workflows.
- Estimate delay signals from available vessel and schedule context.
- Run locally through npm with stdio transport.
- Self-host with Streamable HTTP when a public endpoint is needed.
- Keep all tools read-only.

## Getting Started

- "Find the latest known position for this vessel and cite the source."
- "Summarize recent port calls for this IMO number."
- "Check whether a vessel schedule appears delayed from available signals."
- Tool: `vessel_search` - Find vessel identity and metadata.
- Tool: `vessel_position` - Retrieve AIS-style position context.
- Tool: `vessel_track` - Retrieve vessel track context.
- Tool: `port_calls` - Retrieve port call context.
- Tool: `carrier_schedule_search` - Retrieve carrier schedule context.
- Tool: `vessel_schedule` - Retrieve vessel schedule context.
- Tool: `schedule_delay_predict` - Estimate delay signals from available data.

## Tags

mcp, maritime, logistics, vessel-tracking, ais, ship-tracking, schedules, port-calls, byok, typescript, npm, stdio, streamable-http, claude, chatgpt, cursor, cline, codex

## Documentation URL

https://github.com/tools-mcp/vessel-traffic-mcp#readme

## Health Check URL

Self-hosted HTTP deployments expose `GET /health`.
