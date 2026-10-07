# Directory Submission Pack

Use this file to submit the project to MCP directories and curated lists.
Directory fields should always point to the public GitHub repository and npm
package, not to local paths or private captures.

## Submission Tracker

| Target | URL | Account Needed | Status | Notes |
| --- | --- | --- | --- | --- |
| Glama | https://glama.ai/ | Yes | Submitted for review | Submitted on 2026-05-27 through the logged-in browser `Add Server` flow. Glama server count changed from 25,463 to 25,464 after submission; public listing URL and score badge still return 404 until review/indexing completes. |
| FindMCP | https://findmcp.dev/ | Likely yes | Watch | `/submit` currently resolves to the public directory page; no direct submission endpoint found. |
| MCP Find | https://mcpfind.org/submit | GitHub | Submitted | PR opened on 2026-05-24: https://github.com/MCPFind/mcp-find/pull/47. Checks are `action_required` pending maintainer approval for fork workflows; Vercel also reports authorization required. |
| MCP.Directory | https://mcp.directory/ | No | Submitted | Submitted on 2026-05-20 via `/api/submit-server`; response: `Server submitted for review!`. |
| mcpservers.org | https://mcpservers.org/en/submit | No | Submitted | Submitted on 2026-05-20 as free listing; response id `2577`, status `pending`. |
| VaultPlane | https://www.vaultplane.com/ | No | Listed | Submitted on 2026-05-24 via `/api/servers/submit`; response id `2c842dfc-9040-4b78-a6a8-accd6c1df2d1`, status `pending`. Public page verified: https://www.vaultplane.com/server/vessel-traffic-mcp |
| ServerHub | https://www.serverhub.digital/ | No | Listed | Submitted on 2026-05-24 via `/api/submit`; response id `6297992d-9720-4f1c-930f-69f446f2a7e1`, status `approved`, quality score `63`. Public page verified: https://www.serverhub.digital/servers/vessel-traffic-mcp |
| MCPRepository | https://mcprepository.com/ | No | Queued | Submitted on 2026-05-24 with `npx --yes mcp-index https://github.com/tools-mcp/vessel-traffic-mcp`; expected URL: https://mcprepository.com/tools-mcp/vessel-traffic-mcp. Page still returned 404 immediately after submission because validation is queued. |
| Protodex / MCP Market | https://github.com/LuciferForge/mcp-directory | GitHub | Submitted | Issue opened on 2026-05-24: https://github.com/LuciferForge/mcp-directory/issues/9 |
| PulseMCP | https://www.pulsemcp.com/submit | Maybe | Blocked | Public request hit Cloudflare block on 2026-05-20; retry in browser if needed. |
| MCPCentral | https://mcpcentral.io/submit-server | Yes | Account required | Submit page redirects to sign-in. Current site recommends `mcp-publisher login github --registry https://registry.mcpcentral.io` before publish. |
| mcp.so | https://mcp.so/ | GitHub | Submitted | Issue opened on 2026-05-24: https://github.com/chatmcp/mcpso/issues/2482 |
| Smithery | https://smithery.ai/ | Yes | Blocked on public HTTPS | Server card is ready; remote submission needs a stable public HTTPS `/mcp` URL. |
| MCP Market | https://mcpmarket.com/submit | No | Manual retry | Search index confirms a GitHub URL submit form, but Chrome rendered a blank content area and `curl` received 403/429 on 2026-05-24. Retry manually in Chrome. |
| MCP Marketplace | https://mcp-marketplace.io/ | Yes | Ready | `LAUNCHGUIDE.md` is prepared. Marketplace docs say the submit form can auto-fill listing details from `LAUNCHGUIDE.md`; actual submission requires sign-in. |
| AllMCPservers.com | https://www.allmcpservers.com/ | No | Manual review | Homepage has a "Submit Official MCP" form with name, email, GitHub URL, category, and CAPTCHA. Do not bypass CAPTCHA; submit manually if desired. |
| MCP Server Hub | https://mcpserverhub.net/submit | No | Backlink required | Public submit form exists, but the page states free submission requires adding a backlink to their homepage. Do not submit unless that backlink is intentionally accepted. |
| MCPServerHub.com | https://mcpserverhub.com/submit | Tally | Manual form | Submit page embeds a Tally form. Browser/manual submission required. |
| Cline MCP Marketplace | https://github.com/cline/mcp-marketplace | GitHub | Ready after Cline test | `llms-install.md` and `assets/logo-400.png` are prepared. Do not open the issue until a real Cline setup test passes because the issue template requires confirming that Cline can set up the server using only README and/or `llms-install.md`. |
| Docker MCP Registry | https://github.com/docker/mcp-registry | GitHub | Tooling blocked | Existing Dockerfile is present, but local validation tooling is missing (`task`, `go`, and `docker` were not available). Do not submit a PR until `task validate -- --name <server_name>` and `task build -- --tools <server_name>` can run. |
| BestMCP / MCP Directory AI | https://bestmcp.dev/submit/ | No | Blocked | Canonical submit page exists, but `mcpdirectory.ai` DNS failed, direct POST returned 405, and Chrome rendered blank content on 2026-05-24. |
| MCP Server Spot | https://www.mcpserverspot.com/submit | No | Browser blocked | Form structure was found in the Next app, but Chrome rendered blank content on 2026-05-24. Retry manually. |
| punkpeye/awesome-mcp-servers | https://github.com/punkpeye/awesome-mcp-servers | GitHub | Submitted | PR opened on 2026-05-20: https://github.com/punkpeye/awesome-mcp-servers/pull/6664 |
| appcypher/awesome-mcp-servers | https://github.com/appcypher/awesome-mcp-servers | GitHub | Blocked | Fork branch `tools-mcp:add-vessel-traffic-mcp` is pushed, but upstream has disabled external pull requests and issues. |
| TensorBlock/awesome-mcp-servers | https://github.com/TensorBlock/awesome-mcp-servers | GitHub | Submitted | PR opened on 2026-05-24: https://github.com/TensorBlock/awesome-mcp-servers/pull/583 |
| YuzeHao2023/Awesome-MCP-Servers | https://github.com/YuzeHao2023/Awesome-MCP-Servers | GitHub | Submitted | PR opened on 2026-05-24: https://github.com/YuzeHao2023/Awesome-MCP-Servers/pull/258 |
| wong2/awesome-mcp-servers | https://github.com/wong2/awesome-mcp-servers | GitHub | Branch ready | Fork branch is pushed, but `gh pr create` returned `GraphQL: seokmogu does not have the correct permissions to execute CreatePullRequest`. Compare URL: https://github.com/wong2/awesome-mcp-servers/compare/main...seokmogu:awesome-mcp-servers-wong2:add-vessel-traffic-mcp |
| jaw9c/awesome-remote-mcp-servers | https://github.com/jaw9c/awesome-remote-mcp-servers | GitHub | Not fit yet | Remote-only list requires a production-grade public remote MCP endpoint; current package is local stdio-first. |
| awesome-mcp lists | GitHub search | GitHub | Ready | Submit only to maintained lists that accept PRs. |

## Common Fields

Name:

```text
Vessel Traffic MCP
```

Repository:

```text
https://github.com/tools-mcp/vessel-traffic-mcp
```

npm:

```text
https://www.npmjs.com/package/@tools-mcp/vessel-traffic-mcp
```

MCP Registry:

```text
io.github.tools-mcp/vessel-traffic-mcp
```

Category:

```text
Maritime, logistics, data, search, monitoring
```

Tags:

```text
mcp, ais, vessel-tracking, ship-tracking, maritime, logistics, byok, claude, chatgpt, codex
```

Short description:

```text
Read-only MCP server for vessel identity lookup, AIS-style positions, tracks, port calls, carrier schedules, vessel schedules, and delay heuristics with source attribution and BYOK provider support.
```

Install command:

```bash
npm install -g @tools-mcp/vessel-traffic-mcp
```

Local stdio command:

```bash
VESSEL_MCP_TRANSPORT=stdio vessel-traffic-mcp
```

Recommended env:

```text
VESSEL_MCP_TRANSPORT=stdio
VESSEL_MCP_ENABLE_PUBLIC_PROVIDERS=myshiptracking,tradlinx,aisfriends
```

## Glama

Listing URL:

```text
https://glama.ai/mcp/servers/tools-mcp/vessel-traffic-mcp
```

Submitted on 2026-05-27 through the logged-in Glama `Add MCP Server`
flow. The registry count increased from 25,463 to 25,464 after submission,
but the public listing and badge URL still returned 404 immediately after
submission.

Score badge markdown for awesome-list PRs:

```markdown
[![tools-mcp/vessel-traffic-mcp MCP server](https://glama.ai/mcp/servers/tools-mcp/vessel-traffic-mcp/badges/score.svg)](https://glama.ai/mcp/servers/tools-mcp/vessel-traffic-mcp)
```

Use:

```text
Repository: https://github.com/tools-mcp/vessel-traffic-mcp
Name: Vessel Traffic MCP
Summary: Read-only MCP server for vessel AIS-style position data, carrier schedules, vessel schedules, and delay heuristics with source attribution and BYOK provider support.
Install: npm install -g @tools-mcp/vessel-traffic-mcp
```

The root `glama.json` already declares:

```json
{
  "$schema": "https://glama.ai/mcp/schemas/server.json",
  "maintainers": ["seokmogu", "tools-mcp"]
}
```

## FindMCP / MCP.Directory / mcpservers.org

Use the common fields above. If a long description is accepted, use the long
description from `docs/marketing/launch-kit.md`.

## MCP Find

Add this entry to `community-servers.yml`:

```yaml
  - name: "Vessel Traffic MCP"
    github_url: "https://github.com/tools-mcp/vessel-traffic-mcp"
    package_name: "@tools-mcp/vessel-traffic-mcp"
    description: "Read-only MCP server for vessel identity lookup, AIS-style positions, tracks, port calls, carrier schedules, vessel schedules, and delay heuristics with source attribution and BYOK provider support."
    package_type: "npm"
    category: "other"
```

Submitted:

```text
https://github.com/MCPFind/mcp-find/pull/47
```

## mcp.so

Use this GitHub issue title in `chatmcp/mcpso`:

```text
[Submit] Vessel Traffic MCP - Read-only maritime AIS and schedule tools
```

Use the common fields above plus the package and registry links.

Submitted:

```text
https://github.com/chatmcp/mcpso/issues/2482
```

## PulseMCP

Check whether the server appears after MCP Registry ingestion. If not, submit:

```text
Official MCP Registry name: io.github.tools-mcp/vessel-traffic-mcp
GitHub: https://github.com/tools-mcp/vessel-traffic-mcp
npm: https://www.npmjs.com/package/@tools-mcp/vessel-traffic-mcp
```

## Smithery

Current state:

- Stdio npm package is public.
- Streamable HTTP implementation exists.
- `GET /.well-known/mcp/server-card.json` exists and includes
  `serverInfo`, `authentication`, `tools`, `resources`, and `prompts`.
- Submission should wait until a stable public HTTPS URL is deployed.

When the public URL exists:

```text
Remote MCP URL: https://<public-host>/mcp
Server card: https://<public-host>/.well-known/mcp/server-card.json
Repository: https://github.com/tools-mcp/vessel-traffic-mcp
```

## Awesome List PR Entry

Use this bullet when submitting to curated GitHub lists:

```markdown
- [Vessel Traffic MCP](https://github.com/tools-mcp/vessel-traffic-mcp) - Read-only MCP server for vessel identity lookup, AIS-style positions, tracks, port calls, carrier schedules, vessel schedules, and delay heuristics with source attribution and BYOK provider support.
```

Submitted:

```text
punkpeye/awesome-mcp-servers: https://github.com/punkpeye/awesome-mcp-servers/pull/6664
TensorBlock/awesome-mcp-servers: https://github.com/TensorBlock/awesome-mcp-servers/pull/583
YuzeHao2023/Awesome-MCP-Servers: https://github.com/YuzeHao2023/Awesome-MCP-Servers/pull/258
```

For `appcypher/awesome-mcp-servers`, the fork branch is ready, but the
upstream repository currently blocks external pull requests and issues:

```text
https://github.com/appcypher/awesome-mcp-servers/compare/main...tools-mcp:awesome-mcp-servers:add-vessel-traffic-mcp
```

For `wong2/awesome-mcp-servers`, the fork branch is ready but PR creation
failed through the GitHub API because the fork/owner head was not accepted:

```text
https://github.com/wong2/awesome-mcp-servers/compare/main...seokmogu:awesome-mcp-servers-wong2:add-vessel-traffic-mcp
```

## mcp-submit Dry Run

`npx --yes mcp-submit --dry-run` on 2026-05-23 detected this package as
`io.github.tools-mcp/vessel-traffic-mcp v0.1.0 (0 tools, stdio)`.

Do not run the tool unfiltered:

- Official MCP Registry, MCPCentral, and Docker MCP Registry providers are
  currently marked ready by detection, but their implementation returns
  integration-pending failures.
- `punkpeye/awesome-mcp-servers` is already submitted with the Glama badge.
- `appcypher/awesome-mcp-servers` is already blocked by upstream PR settings.
- Browser providers use the system `open` command; use Chrome manually instead.
