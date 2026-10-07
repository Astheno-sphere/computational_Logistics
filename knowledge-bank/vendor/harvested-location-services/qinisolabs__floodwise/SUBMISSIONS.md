# floodwise — directory submissions

Track where floodwise is listed. The MCP Registry entry (via `mcp-publisher`) is the canonical source;
Glama and mcp.so auto-ingest from it.

| Directory | How | Status |
| --- | --- | --- |
| MCP Registry (official) | `mcp-publisher publish` (see PUBLISH.md §4) | ☐ |
| Glama | Free "Add Server" form, or auto-ingest from the registry. Never add billing. | ☐ |
| mcp.so | Auto-ingests from the registry; submit manually if not picked up. | ☐ |
| awesome-mcp-servers | Manual PR (Location Services). | ✅ merged 2026-06-19 |
| Smithery | `smithery.yaml` present; HTTP-only form — list as stdio/npx. | ☐ |

## Notes

- floodwise is an **England**, area-level, long-term flood-risk lookup over open Environment Agency data
  (OGL v3.0). Lead listings with those limits — it is not insurance/underwriting/property-level advice.
- Description (≤100 chars): *England flood-risk by postcode for AI agents — verified Environment Agency data, not guesses.*
- No API keys, stateless, stdio/npx.
