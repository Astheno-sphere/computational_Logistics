# Discoverability Metadata (F7.AC2)

This document explains the package, repository, and documentation
metadata that makes `vessel-traffic-mcp` searchable for the MCP and
plugin workflows the project targets.

It covers F7.AC2: *"Add package, repository, and documentation
metadata so the project is searchable for vessel AIS MCP, ship
tracking MCP, MarineTraffic MCP, Claude MCP, ChatGPT MCP, and Codex
plugin workflows."* This page extends that same contract to Gemini MCP
and search-style `search`/`fetch` agent workflows.

## Target search surfaces

A maritime/MCP operator searching for "how do I plug AIS data into
Claude / ChatGPT / Codex / Gemini" should be able to find this project
from any of these phrases:

- **vessel AIS MCP** — generic AIS-feed MCP servers
- **ship tracking MCP** — broader ship/vessel position MCP servers
- **MarineTraffic MCP** — operators who already have a MarineTraffic
  account and want BYOK access from MCP clients
- **Claude MCP** — Claude Desktop / Claude Code users browsing
  community MCP servers
- **ChatGPT MCP** — ChatGPT remote-MCP connector users
- **Codex plugin** — Codex / OpenAI plugin / Codex marketplace
  workflows
- **Gemini MCP** — Gemini CLI and Gemini Code Assist MCP setup
- **maritime MCP** and **shipping MCP** — broader logistics and carrier
  schedule workflows

The metadata below maps each search surface to a concrete
package/repository/docs field so the project stays findable as the
MCP ecosystem grows.

## `package.json` discoverability fields

| Field        | Why it exists                                                                 |
| ------------ | ----------------------------------------------------------------------------- |
| `keywords`   | npm/registry search hits for `vessel-ais-mcp`, `ship-tracking-mcp`, `marinetraffic-mcp`, `claude-mcp`, `chatgpt-mcp`, `codex-plugin`, `gemini-mcp`, `maritime-mcp`, `shipping-mcp`, `ais-mcp`, and generic `mcp`, `mcp-server`, `ais`, `vessel`, and `marinetraffic`. |
| `description`| Short one-liner that surfaces in npm/GitHub search snippets — mentions MCP, AIS, vessel/ship, Claude/ChatGPT/Codex, and BYOK. |
| `mcpName`    | Official MCP Registry namespace: `io.github.tools-mcp/vessel-traffic-mcp`. |
| `repository` | Git+HTTPS URL pointing at the canonical GitHub repo so registries can link back. |
| `homepage`   | Public landing URL (`#readme`) for project discovery. |
| `bugs`       | GitHub Issues URL so operators can file reproducible reports without needing to know the maintainer email. |
| `author`     | Maintainer attribution; cross-checks against `SECURITY.md` private-reporting channel. |
| `files`      | Explicit allowlist of artifacts that ship with the package. Keeps operator-sensitive directories (`captures/`, `state/`, `.env*`, raw fixtures) out by construction. |
| `publishConfig` | Forces public npm access for the first package release. |
| `prepublishOnly` | Runs deterministic verification before any `npm publish`. |

The package metadata is npm-publication ready under the
`@tools-mcp/vessel-traffic-mcp` npm organization scope: it does not set
`"private": true`, declares `publishConfig.access=public`, and gates
publication through `prepublishOnly`. Registry submission still waits
until the npm `tools-mcp` organization exists and the scoped package is
actually published.

## GitHub Topics

The README's *Topics* section lists the same discoverability phrases
in human-readable form so they can be set as
[GitHub Topics](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics)
on the repository page. Suggested topics:

- `mcp`
- `model-context-protocol`
- `vessel-ais-mcp`
- `ship-tracking-mcp`
- `marinetraffic-mcp`
- `claude-mcp`
- `chatgpt-mcp`
- `codex-plugin`
- `gemini-mcp`
- `maritime-mcp`
- `shipping-mcp`
- `ais-mcp`
- `mcp-server`
- `ais`
- `vessel-tracking`
- `marinetraffic`
- `byok`

## Documentation cross-links

Discoverability is not only the package manifest. The following docs
form a connected graph so a visitor landing on README from any
search engine can reach the operator/security/contribution surfaces
in one click:

- [`docs/index.html`](./index.html) — static GitHub Pages landing page
  for agent search, install snippets, golden prompts, robots metadata,
  sitemap metadata, and ChatGPT/Codex/Claude/Gemini discovery phrases.
- [`README.md`](../README.md) — open-source positioning, MCP feature
  summary, and links into every runbook.
- [`SECURITY.md`](../SECURITY.md) — private vulnerability reporting.
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — hard rules and PR
  workflow.
- [`AGENTS.md`](../AGENTS.md) — non-negotiable project rules
  (read-only tools, BYOK redaction, sanitized captures only).
- [`docs/PRD.md`](./PRD.md) and [`docs/TDD.md`](./TDD.md) — product
  and technical design.
- [`docs/provider-catalog.md`](./provider-catalog.md) — provider
  inventory covering MarineTraffic, VesselFinder, AISStream, AISHub,
  Spire, and others, with auth class, cost/quota, and capture
  eligibility.
- [`docs/runbooks/clients.md`](./runbooks/clients.md) — Claude
  Desktop, Claude Code, ChatGPT remote MCP, and MCP Inspector setup
  instructions.
- [`docs/runbooks/codex.md`](./runbooks/codex.md) — F7.AC3 Codex CLI
  MCP wiring (`~/.codex/config.toml`), Streamable HTTP path, and the
  current Codex plugin manifest / marketplace readiness state.
- [`docs/runbooks/release-checklist.md`](./runbooks/release-checklist.md)
  — release gate that verifies these metadata fields stay current.

## How this is verified

Discoverability metadata is covered by deterministic tests in
`test/discoverability-metadata.test.js`. The suite asserts:

1. Every discoverability phrase from this document is present as a
   normalized `package.json` keyword.
2. `repository`, `homepage`, `bugs`, and `author` are non-empty and
   point at the canonical GitHub URL.
3. `files` allowlists only safe artifacts (`dist`, `README.md`,
  `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, `AGENTS.md`,
  `server.json`, `glama.json`, `docs`)
   and never lists operator-sensitive paths.
4. The metadata contains no credential-shaped strings.
5. README links back here and surfaces the Topics section.
6. `docs/index.html`, `docs/robots.txt`, and `docs/sitemap.xml` expose
   the public landing page at `https://tools-mcp.github.io/vessel-traffic-mcp/`.
7. F7.AC2 and the F7 parent feature are `status: implemented`, while
   `package.json` remains npm-publication ready with public access and
   a `prepublishOnly` verification gate.

The test runs as part of the default `npm test` gate, so any change
that drifts the metadata out of alignment with this contract fails CI
before release.

## Directory Metadata

The repository also ships these directory-facing files:

- `server.json` — official MCP Registry metadata using the
  `io.github.tools-mcp/vessel-traffic-mcp` name.
- `docs/index.html`, `docs/robots.txt`, and `docs/sitemap.xml` —
  GitHub Pages static search surface for assistant agents and crawlers.
- `glama.json` — Glama directory maintainer metadata using the
  `seokmogu` GitHub username for organization-repository verification.
- `GET /.well-known/mcp/server-card.json` on the Streamable HTTP
  transport — crawler-safe package, tool, transport, and provenance
  metadata for directories such as Smithery once a public HTTPS
  deployment exists.
- `.github/ISSUE_TEMPLATE/*` and `.github/PULL_REQUEST_TEMPLATE.md`
  — collaboration entry points for public contributors.

The operational checklist for publishing to GitHub, the MCP Registry,
Smithery, Glama, PulseMCP, and other MCP directories lives in
`docs/runbooks/public-sharing.md`.
