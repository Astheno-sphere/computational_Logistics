# Outreach Status

Snapshot date: 2026-05-28 KST

## Current Public Surfaces

- GitHub: https://github.com/tools-mcp/vessel-traffic-mcp
- Agent landing page: https://tools-mcp.github.io/vessel-traffic-mcp/
- GitHub release: https://github.com/tools-mcp/vessel-traffic-mcp/releases/tag/v0.1.0
- npm: https://www.npmjs.com/package/@tools-mcp/vessel-traffic-mcp
- MCP Registry: `io.github.tools-mcp/vessel-traffic-mcp`

## Community Enablement

- README now links to a sharing kit for people who can forward the project to
  MCP, logistics, shipping, and trade audiences:
  [`docs/marketing/help-us-spread.md`](./help-us-spread.md).
- The sharing kit gives 3-minute, 15-minute, and 1-hour contribution options
  plus copy/paste Korean and English outreach text.
- Pinned help wanted issue for community sharing:
  https://github.com/tools-mcp/vessel-traffic-mcp/issues/7
- Public feedback discussion:
  https://github.com/tools-mcp/vessel-traffic-mcp/discussions/8

## Current Metrics

- GitHub Traffic API, last 14 days: 651 clones, 190 unique cloners.
- GitHub Traffic API, last 14 days: 15 views, 6 unique visitors.
- npm downloads, 2026-05-15 through 2026-05-23: 66.
- GitHub stars/forks/watchers: 0/0/0 at the time of this snapshot.

GitHub clone traffic does not identify who cloned the repository. It only
reports aggregate clone counts and unique cloners for the recent traffic
window.

## Completed Distribution Work

- A static agent discovery page now targets ChatGPT, Codex, Claude, Gemini,
  vessel AIS MCP, ship tracking MCP, and BYOK maritime provider searches:
  https://tools-mcp.github.io/vessel-traffic-mcp/
- The MCP server exposes read-only `search` and `fetch` wrappers for
  search-style agent connector flows, in addition to the vessel-specific tools.
- npm package `@tools-mcp/vessel-traffic-mcp@0.1.0` is public.
- Official MCP Registry entry is active.
- GitHub topics are configured for MCP, vessel AIS, ship tracking, maritime,
  logistics, Claude, ChatGPT, Codex, and BYOK discovery.
- GitHub release `v0.1.0` was created after `npm run lint`, `npm test`, and
  `npm run build` passed.
- MCP.Directory submission was already sent.
- mcpservers.org submission was already sent and is pending review.
- ServerHub listing is live:
  https://www.serverhub.digital/servers/vessel-traffic-mcp
- VaultPlane listing is live:
  https://www.vaultplane.com/server/vessel-traffic-mcp
- MCPRepository submission is queued for validation:
  https://mcprepository.com/tools-mcp/vessel-traffic-mcp
- Protodex / MCP Market issue submission is open:
  https://github.com/LuciferForge/mcp-directory/issues/9
- `punkpeye/awesome-mcp-servers` PR is open:
  https://github.com/punkpeye/awesome-mcp-servers/pull/6664
- `TensorBlock/awesome-mcp-servers` PR is open:
  https://github.com/TensorBlock/awesome-mcp-servers/pull/583
- `YuzeHao2023/Awesome-MCP-Servers` PR is open:
  https://github.com/YuzeHao2023/Awesome-MCP-Servers/pull/258
- MCP Find PR is open:
  https://github.com/MCPFind/mcp-find/pull/47
  Its GitHub Actions status is `action_required` because fork workflows require
  maintainer approval; the visible Vercel failure is an authorization gate, not
  a catalog YAML validation failure.
- mcp.so issue submission is open:
  https://github.com/chatmcp/mcpso/issues/2482

## Active Blockers

- Glama was submitted through the logged-in `Add MCP Server` flow on
  2026-05-27. The registry server count increased from 25,463 to 25,464 after
  submission, but the public listing URL and score badge URL still return 404
  until review/indexing completes.
- The awesome-mcp-servers PR now keeps the Glama score badge immediately after
  the server link and has the `has-glama` label:
  `[![tools-mcp/vessel-traffic-mcp MCP server](https://glama.ai/mcp/servers/tools-mcp/vessel-traffic-mcp/badges/score.svg)](https://glama.ai/mcp/servers/tools-mcp/vessel-traffic-mcp)`.
- MCPCentral submission requires sign-in and should be handled with the
  official `mcp-publisher` flow against `https://registry.mcpcentral.io`.
- PulseMCP manual submission previously hit Cloudflare and should be retried in
  a logged-in browser session if automatic registry ingestion does not pick up
  the project.
- Smithery submission should wait for a stable public HTTPS `/mcp` endpoint.
- Cline MCP Marketplace should wait until a real Cline setup test passes,
  because its issue template requires confirming that Cline can set up the
  server using only README and/or `llms-install.md`.
- Docker MCP Registry should wait until local `task`, `go`, and Docker tooling
  are available for the required validation/build commands.
- MCP Market, AllMCPservers.com, MCP Server Hub, BestMCP, and MCP Server Spot
  need manual browser/account/CAPTCHA/backlink handling rather than API
  submission.

## Community Posting Targets

High fit:

- Hacker News Show HN.
- Reddit `r/mcp`, `r/MCPservers`, `r/opensource`, `r/SideProject`.
- DEV Community or Hashnode article.
- Product Hunt after a visible demo GIF or hosted endpoint exists.
- OKKY, GeekNews, Velog, and Korean logistics/maritime communities.

Posting rule:

- Avoid identical cross-posting. Keep the core link and claim set consistent,
  but tailor the opening and feedback ask to each community.
- Do not claim real-time navigation reliability.
- Do not claim provider data ownership or paywall/CAPTCHA bypass.
- Emphasize read-only MCP tools, source attribution, BYOK, and sanitized tests.
