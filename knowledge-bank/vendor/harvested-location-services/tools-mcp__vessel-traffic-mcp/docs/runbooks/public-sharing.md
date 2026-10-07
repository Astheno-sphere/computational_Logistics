# Public Sharing Runbook

This runbook is the publication checklist for sharing
`vessel-traffic-mcp` with collaborators and MCP directories while
preserving the project's read-only, BYOK, and source-attribution
boundaries.

## 1. GitHub Repository

Canonical repository:

```text
https://github.com/tools-mcp/vessel-traffic-mcp
```

Agent discovery landing page:

```text
https://tools-mcp.github.io/vessel-traffic-mcp/
```

Repository settings to keep enabled:

- Public visibility.
- Issues.
- Discussions.
- Security advisories / private vulnerability reporting.
- GitHub Actions for the default fixture-backed CI gate.

Suggested GitHub topics:

```text
mcp, model-context-protocol, vessel-ais-mcp, ship-tracking-mcp,
marinetraffic-mcp, claude-mcp, chatgpt-mcp, codex-plugin, ais,
vessel-tracking, ship-tracking, maritime, shipping, logistics, byok,
aisstream, aishub, vesselfinder
```

Collaboration files:

- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/provider_request.yml`
- `.github/ISSUE_TEMPLATE/capture_review.yml`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`

## 2. MCP Registry

The root `server.json` is prepared for the official MCP Registry.
The server name is:

```text
io.github.tools-mcp/vessel-traffic-mcp
```

The package also declares the same value in `package.json` as
`mcpName` so registry ownership verification can be tied to the
published package.

Current state as of 2026-05-20:

- `mcp-publisher validate server.json` passes against the official
  registry validator.
- `mcp-publisher publish server.json` published
  `io.github.tools-mcp/vessel-traffic-mcp@0.1.0` to the MCP Registry.
- `@tools-mcp/vessel-traffic-mcp@0.1.0` is public on npm.
- `npm access get status @tools-mcp/vessel-traffic-mcp` reports
  `public`.
- `npm dist-tag ls @tools-mcp/vessel-traffic-mcp` reports
  `latest: 0.1.0`.
- `npm view @tools-mcp/vessel-traffic-mcp name version bin dist-tags
  repository.url --json` returns the published package metadata after
  npm registry propagation.

Publication note:

- MCP Registry publication under `io.github.tools-mcp/*` requires the
  authenticated GitHub identity to have public membership in the
  `tools-mcp` GitHub organization. That membership was made public
  before the successful registry publish.

Manual publication sequence already completed for npm:

1. In npm's web UI, create the `tools-mcp` organization and choose the
   free public-package plan. npm's official flow is profile menu →
   **Add an Organization**; the organization name becomes the package
   scope.
2. Verify local CLI membership:

   ```bash
   npm whoami
   npm org ls tools-mcp
   npm view @tools-mcp/vessel-traffic-mcp version --json
   ```

   The package lookup should return `E404` before first publish; the
   org lookup must not return `Scope not found`.
3. Publish the npm package:

   ```bash
   npm ci
   npm run lint
   npm test
   npm run build
   npm publish --access public
   ```

MCP Registry publication sequence completed after GitHub organization
membership visibility was approved:

```bash
tmp/bin/mcp-publisher login github
tmp/bin/mcp-publisher publish server.json
```

If a remote hosted MCP endpoint is published instead of npm, update
`server.json` with the official remote-server package shape and add
the public HTTPS `/mcp` URL only after `VESSEL_MCP_AUTH_TOKEN` and
TLS are configured.

## 3. Smithery

Use Smithery as a discovery/install surface after one of these is true:

- A stable public Streamable HTTP deployment exists and exposes:
  - `POST /mcp`, `GET /mcp`, `DELETE /mcp`, and `OPTIONS /mcp`.
  - `GET /.well-known/mcp/server-card.json` for crawler-safe tool and
    package metadata.
- A Smithery-compatible package bundle is intentionally released.

Submit only the public repository URL and safe install instructions.
Do not upload `.env`, credential profiles, HAR files, captures,
cookies, or provider keys.

Current state as of 2026-05-20:

- The local HTTP server now exposes a public
  `/.well-known/mcp/server-card.json` endpoint for directory crawlers.
  The card includes Smithery-compatible `serverInfo`,
  `authentication`, `tools`, `resources`, and `prompts` fields plus
  project-specific provenance metadata.
- The static GitHub Pages landing page lives in `docs/index.html` and
  targets agent/search discovery phrases such as vessel AIS MCP, ship
  tracking MCP, ChatGPT MCP, Codex MCP, Claude MCP, and Gemini MCP.
- npm stdio installation is public through
  `@tools-mcp/vessel-traffic-mcp@0.1.0`.
- Smithery remote submission still waits for a stable public HTTPS
  deployment URL. Do not submit a localhost URL.

## 4. Glama

The root `glama.json` includes the `seokmogu` GitHub username so Glama
can verify maintainer authority for the `tools-mcp` organization
repository. Use it when submitting the repo to Glama's MCP directory.
Submitted through the logged-in Glama `Add MCP Server` flow on 2026-05-27.
The registry server count increased from 25,463 to 25,464 after submission,
but the public listing URL and score badge still returned 404 immediately
after submission until Glama completes review/indexing.

Awesome-list badge markdown:

```markdown
[![tools-mcp/vessel-traffic-mcp MCP server](https://glama.ai/mcp/servers/tools-mcp/vessel-traffic-mcp/badges/score.svg)](https://glama.ai/mcp/servers/tools-mcp/vessel-traffic-mcp)
```

Submission payload:

```text
Repository: https://github.com/tools-mcp/vessel-traffic-mcp
Name: vessel-traffic-mcp
Summary: Read-only MCP server for vessel identity lookup, AIS-style
positions, tracks, port calls, carrier schedules, vessel schedules, and delay
heuristics with source attribution and BYOK provider support.
Install: see README.md and llms.txt
```

## 5. PulseMCP And Other Directories

Current state as of 2026-05-20:

- PulseMCP should be tracked as automatic-ingestion pending because the
  project is already published in the official MCP Registry.
- If the project does not appear after the directory's registry sync
  window, use the listing text below and the public GitHub URL for a
  manual submission or support request.

Use the same short listing text for PulseMCP, MCPServers.com,
awesome-MCP lists, Reddit `r/mcp`, Hacker News, and similar discovery
surfaces:

```text
Vessel Traffic MCP is an MIT-licensed, read-only Model Context Protocol
server for vessel identity, AIS-style position lookup, carrier
schedules, vessel schedules, and delay heuristics. It supports
fixture-backed local testing, opt-in public providers, and BYOK
commercial providers. Responses expose source.provider and
source.landingUrl so users can verify and visit the original data
source.

GitHub: https://github.com/tools-mcp/vessel-traffic-mcp
```

Recommended tags:

```text
mcp, ais, ship-tracking, vessel-tracking, maritime, logistics, byok,
claude, chatgpt, codex, gemini
```

Detailed overseas launch copy, directory submission fields, Product
Hunt text, and community-specific drafts live in:

- [`docs/marketing/launch-kit.md`](../marketing/launch-kit.md)
- [`docs/marketing/help-us-spread.md`](../marketing/help-us-spread.md)
- [`docs/marketing/directory-submissions.md`](../marketing/directory-submissions.md)
- [`docs/marketing/community-posts.md`](../marketing/community-posts.md)
- [`docs/marketing/product-hunt.md`](../marketing/product-hunt.md)
- [`docs/marketing/outreach-status.md`](../marketing/outreach-status.md)

## 6. Launch Checklist

Before posting anywhere:

- `git status --short` is clean.
- `npm run lint`, `npm test`, and `npm run build` pass.
- `README.md`, `llms.txt`, `CONTRIBUTING.md`, and `SECURITY.md` are
  current.
- `docs/index.html`, `docs/robots.txt`, and `docs/sitemap.xml` point at
  the public agent landing page.
- `server.json` and `package.json#mcpName` use the
  `io.github.tools-mcp/vessel-traffic-mcp` namespace.
- No tracked file contains API keys, bearer tokens, cookies, raw HAR
  files, private captures, `.env*`, or credential profiles.
- GitHub topics, issue templates, PR template, and Discussions are
  enabled.

## 7. Identity And Contributor Privacy

The public repository should present `tools-mcp` as the project
identity. New commits should use a neutral author such as:

```text
tools-mcp-bot <tools-mcp-bot@users.noreply.github.com>
```

GitHub may still show historical commit authors in the contributor
graph if old commits were authored by a personal account. Avoid adding
personal usernames to docs, examples, registry metadata, or directory
submissions. Do not rewrite public Git history unless maintainers
explicitly decide the disruption is worth it.
