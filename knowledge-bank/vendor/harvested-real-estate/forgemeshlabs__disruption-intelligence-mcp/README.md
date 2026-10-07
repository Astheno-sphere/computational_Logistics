# Disruption Intelligence MCP

[![M8ven Score](https://m8ven.ai/badge/mcp/forgemeshlabs-disruption-intelligence-mcp-pro7g7)](https://m8ven.ai/mcp/forgemeshlabs-disruption-intelligence-mcp-pro7g7)
[![mcpservers.org](https://mcpservers.org/badge.svg)](https://mcpservers.org/servers/forgemeshlabs/disruption-intelligence-mcp)

AI-native commercial disruption intelligence for MCP clients and x402-powered agents.

Disruption Intelligence MCP gives AI agents access to commercial disruption signals through an MCP server backed by the hosted Forgemesh API. It supports WARN/layoff intelligence, company context, geospatial territory disruption, location-only Ripple Index cards, Ripple Signals, Ripple Paths, Disruption Intelligence Ripple Reports, x402 payment challenge inspection, and economic signal workflows without exposing private scoring logic, ingestion systems, schemas, or infrastructure.

This package is a thin client around the hosted API:

`https://disruption.forgemesh.io`

Architecture:

`Agent/MCP client -> this MCP server -> hosted Disruption Intelligence API`

The MCP package does not contain engine internals, scoring logic, ingestion architecture, database schema, private topology, wallet addresses, or secrets.

## Install

```bash
npm install -g @forgemeshlabs/disruption-intelligence-mcp
```

Published package:

https://www.npmjs.com/package/@forgemeshlabs/disruption-intelligence-mcp

Source repo:

https://github.com/forgemeshlabs/disruption-intelligence-mcp

Local development:

```bash
npm install
npm run build
node dist/index.js
```

## Claude Desktop

Example config:

```json
{
  "mcpServers": {
    "disruption-intelligence": {
      "command": "npx",
      "args": ["@forgemeshlabs/disruption-intelligence-mcp"],
      "env": {
        "DISRUPTION_API_BASE": "https://disruption.forgemesh.io"
      }
    }
  }
}
```

See [examples/claude-desktop-config.json](examples/claude-desktop-config.json).

## Tools

| Tool | Endpoint | Cost behavior |
| --- | --- | --- |
| `get_api_status` | `GET /health` | Free |
| `get_discovery_metadata` | `GET /index.json`, `/llms.txt`, `/openapi.json`, `/.well-known/x402.json` | Free |
| `inspect_x402_challenge` | Unpaid request to a paid endpoint | Returns x402 challenge metadata |
| `analyze_territory_disruption` | `GET /territory/:zip/disruption?radius=` | Paid; challenge-first by default |
| `search_company_context` | `GET /companies/search?q=` | Paid; challenge-first by default |
| `get_company_risk_summary` | `GET /companies/:id/intelligence` | Paid; challenge-first by default |
| `get_event_severity` | `GET /events/:id/severity` | Paid; challenge-first by default; paid output includes confidence-rated `industry_classification` |
| `get_event_company_intel` | `GET /events/:id/company-intel` | Paid; challenge-first by default; paid output includes confidence-rated `industry_classification` |
| `get_event_timeline` | `GET /events/:id/timeline` | Paid; challenge-first by default |
| `search_gold_inventory` | `GET /ripple/search?q=` | Compatibility tool name; free Ripple inventory counts and unlock pricing only |
| `get_ripple_index` | `GET /ripple/index?q=&scope=&limit=` | Paid at $0.01; challenge-first by default; returns location-only Ripple index cards |
| `get_gold_signals` | `GET /ripple/signals?q=&limit=&state=` | Compatibility tool name; paid at $0.10; challenge-first by default; returns Ripple Signals after settlement |
| `get_gold_brief` | `GET /ripple/brief?q=&scope=&limit=` | Compatibility tool name; paid at $0.25; challenge-first by default; returns a Disruption Intelligence Ripple Report after settlement |
| `get_gold_sector_impacts` | `GET /ripple/signals/:id/sector-impacts` | Compatibility tool name; paid at $0.15; challenge-first by default; returns Ripple Paths after settlement |

## Ripple Output

Free Ripple search is intentionally inventory-only. It returns counts, freshness, and unlock pricing without exposing commercial angles, evidence categories, source mix, signal IDs, company names, or raw source records.

`get_ripple_index` unlocks a low-cost location-only index for choosing where to dig next. It can return signal IDs, event IDs, regions, states, signal types, freshness/depth/confidence/score bands, and unlock URLs, while withholding company names, employee counts, commercial angles, sector names, spend areas, source records, and impact paths.

Paid Ripple endpoints expose distilled commercial intelligence. `get_gold_signals` returns Ripple Signal summaries, confidence bands, compact evidence labels, and Ripple Path inventory with an unlock endpoint. `get_gold_sector_impacts` unlocks the deeper operational map for one signal, including downstream spend categories such as fuel, food service, uniforms, maintenance, IT, logistics, office supplies, telecom, insurance, legal, cleaning, travel, and related vendor categories.

## Industry Classification Output

Paid event-level API responses now include `industry_classification` when event context is available. The hosted API returns the industry label, NAICS fields when present, derivation method, confidence level, source text when relevant, and a coverage note. The MCP remains a thin client: it does not infer industries locally and does not rewrite hosted WARN data.

## Free vs Paid Behavior

Default mode is safe and non-settling. Free endpoints return API data directly. Paid endpoints are requested without payment credentials, so the hosted API can return an x402 `402 Payment Required` challenge.

When payment is required, this MCP returns structured payment instructions and challenge metadata instead of dumping an upstream error. It does not require a private key and does not settle payments.

Future paid execution should be opt-in and delegated to a trusted wallet or payment client.

## Configuration

```bash
DISRUPTION_API_BASE=https://disruption.forgemesh.io
```

No wallet private key is required or accepted by this package. Paid endpoint calls return x402 challenge metadata for an external wallet or payment client to settle.

## API Docs

API docs and product context:

https://github.com/forgemeshlabs/disruption-intelligence

Hosted API:

https://disruption.forgemesh.io

## Security Boundary

This repository is an agent-facing thin client wrapper around the hosted API. It intentionally excludes engine code, scoring formulas, ingestion internals, database details, operational topology, wallet addresses, private keys, and secrets.
