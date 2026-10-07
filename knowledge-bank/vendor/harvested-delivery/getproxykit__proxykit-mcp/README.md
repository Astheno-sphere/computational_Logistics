# proxykit-mcp [![ProxyKit-mcp MCP server – quality and maintenance score on Glama](https://glama.ai/mcp/servers/getproxykit/proxykit-mcp/badges/score.svg)](https://glama.ai/mcp/servers/getproxykit/proxykit-mcp)

**Model Context Protocol server for [ProxyKit](https://proxykit.net) — drive a local HTTP(S) debugging proxy from Claude, Cursor, and any MCP host.**

`proxykit-mcp` is a small stdio binary that exposes a running ProxyKit engine to
MCP clients. Every tool call is one HTTP call to the engine's control API on
`127.0.0.1` — the server holds no traffic of its own and talks to nothing off
your machine.

> "Mock the checkout endpoint to fail half the time." · "Summarize the last 500
> captured requests against my baseline." · "Add 800 ms of latency to
> /api/payments and replay the session."
>
> Typed into your editor, run against real traffic ProxyKit already captured.

- **Website:** https://proxykit.net
- **Setup guide (all hosts):** https://proxykit.net/mcp
- **CLI reference:** https://proxykit.net/docs

This repository is the public home of the `proxykit-mcp` server — its docs,
tool reference, and MCP registry metadata. The engine and desktop app are
[ProxyKit](https://proxykit.net), a proprietary product with a free tier.

---

## Install

The binary ships inside every ProxyKit CLI archive **and** inside the desktop
app. Pick whichever you already have.

### With Homebrew (CLI)

```bash
brew install getproxykit/tap/proxykit-cli
```

That puts `proxykit`, `proxy-engine`, and `proxykit-mcp` on your PATH.

### With WinGet (Windows)

```powershell
winget install ProxyKit.ProxyKitCLI
```

### From the desktop app

Download from https://proxykit.net/download. The binary is bundled at:

```
macOS    /Applications/ProxyKit.app/Contents/Resources/proxykit-mcp
Windows  C:\Program Files\ProxyKit\resources\proxykit-mcp.exe
Linux    (AppImage) squashfs-root/resources/proxykit-mcp
```

---

## Connect an MCP host

The engine writes a `control.token` file on startup; point the MCP server at
that file — **never paste the token into the config**. Add this to your host's
MCP config (`~/.cursor/mcp.json`, Claude Desktop's `claude_desktop_config.json`,
`.mcp.json`, …):

```jsonc
{
  "mcpServers": {
    "proxykit": {
      "command": "proxykit-mcp",
      "env": {
        "PROXYKIT_CONTROL_AUTH_TOKEN_FILE": "~/.config/ProxyKit/control.token",
        "PROXYKIT_MCP_TIER": "readonly"
      }
    }
  }
}
```

Start ProxyKit (desktop or `proxykit start --headless`), restart your MCP host,
and ask it: *"List my latest captured traffic in ProxyKit."*

Per-client paths and one-click install from the desktop app are documented at
**https://proxykit.net/mcp**.

### Environment variables

| Variable | Purpose |
|---|---|
| `PROXYKIT_CONTROL_AUTH_TOKEN_FILE` | Path to the engine's `control.token`. Preferred over the raw token. |
| `PROXYKIT_CONTROL_AUTH_TOKEN` | The token directly (use the `_FILE` form instead where possible). |
| `PROXYKIT_MCP_TIER` | Comma-separated allowlist: `readonly` (default), `mutate`, `capture`, `analysis`, `replay`. |
| `PROXYKIT_ENGINE_URL` | Engine control API. Defaults to `http://127.0.0.1:17171`. |

---

## Safety model

- **Local only.** The server calls `127.0.0.1:17171`. The engine binds loopback
  and rejects non-loopback callers.
- **Token-gated.** Every control call carries `X-Proxykit-Control-Token`. No
  token, no access.
- **Least privilege by tier.** `readonly` is the default and can only read.
  Anything that mutates rules, controls capture, or replays traffic is off
  until you opt its tier in — so an agent can't create a mock or clear your
  capture unless you explicitly allowed that tier.
- **Redacted at the source.** Response bodies are redacted server-side before
  they reach the agent.

---

## Tools

50 tools across five tiers. `readonly` is enabled by default; the rest are
opt-in via `PROXYKIT_MCP_TIER`.

### `readonly` — read state (default)

| Tool | Does |
|---|---|
| `proxy_status` | Is the proxy running, what port, TLS configured, buffer size |
| `list_traffic` | List captured requests; filter by method/URL/status, paged |
| `get_request` | Full headers + redacted body of one request |
| `search_traffic` | Substring search across captured URLs |
| `list_mock_rules` | Configured mock rules |
| `list_rewrite_rules` | Configured rewrite rules |
| `list_chaos_rules` | Configured chaos (latency/error injection) rules |
| `list_scripts` | Installed JS hook scripts |
| `list_sessions` | Named capture sessions |
| `get_session` | One session's manifest + baseline |
| `list_findings` | Privacy / schema / performance / lint findings |
| `get_findings_summary` | Finding counts by severity and category |
| `list_environments` | Environments and the active one (secrets redacted) |
| `list_paused_breakpoints` | Requests paused awaiting review |
| `list_rule_packs` | Installed rule packs |
| `get_ca_status` | Whether a CA root is available (public PEM only) |

### `mutate` — edit rules

`create_mock_rule`, `update_mock_rule`, `delete_mock_rule`, `toggle_mock_rule`,
`create_mock_from_request`, `create_rewrite_rule`, `update_rewrite_rule`,
`delete_rewrite_rule`, `toggle_rewrite_rule`, `create_chaos_rule`,
`update_chaos_rule`, `delete_chaos_rule`, `toggle_chaos_rule`,
`attach_environment`

### `capture` — control capture

`start_capture`, `stop_capture`, `clear_traffic`, `release_breakpoint`

### `analysis` — AI + findings workflows

`analyze_request`, `rescan_findings`, `dismiss_finding`, `restore_finding`,
`propose_redaction_rules`, `run_ai_workflow`, `compare_sessions`

### `replay` — sessions, replay, rule packs

`start_session`, `stop_session`, `delete_session`, `replay_session`,
`replay_request`, `import_rule_pack`, `install_rule_pack`, `export_rule_pack`,
`delete_rule_pack`

---

## License

**This repository** — the docs, `Dockerfile`, and registry metadata — is MIT
licensed (see [LICENSE](./LICENSE)); reuse it freely.

**ProxyKit itself** — the `proxykit-mcp` binary and the engine it drives — is
proprietary software © 2026 Seyed Ahmad Sarollahi, licensed under
https://proxykit.net/terms#license. Nothing in this repository grants any right
to the ProxyKit software; the binary is downloaded from the release server at
build time under its own terms.
