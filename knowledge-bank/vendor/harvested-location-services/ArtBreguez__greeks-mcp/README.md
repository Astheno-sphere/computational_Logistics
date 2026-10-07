# greeks-mcp

[![PyPI](https://img.shields.io/pypi/v/greeks-mcp.svg)](https://pypi.org/project/greeks-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/greeks-mcp.svg)](https://pypi.org/project/greeks-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Glama](https://glama.ai/mcp/servers/@ArtBreguez/greeks-mcp/badge)](https://glama.ai/mcp/servers/@ArtBreguez/greeks-mcp)

A [Model Context Protocol](https://modelcontextprotocol.io) server that exposes the
**[Greeks](https://greeks.pro) options-analytics API** as tools for any MCP client —
**Claude Desktop**, **Cursor**, Claude Code, and more. Ask your assistant for GEX,
Greeks, Max Pain, unusual flow or a full dashboard on any ticker and it pulls live
from the API.

Only **derived/computed analytics** are exposed — no raw market data is
redistributed.

## Quickstart

**1. Get an API key.** Sign up at [greeks.pro](https://greeks.pro) and create a key
— it looks like `grk_<48 hex>`. Public tools (screener, health, plans) work without
one.

**2. Add one block to your client config** and restart the client:

```json
{
  "mcpServers": {
    "greeks-analytics": {
      "command": "uvx",
      "args": ["greeks-mcp"],
      "env": { "GREEKS_API_KEY": "grk_your_key_here" }
    }
  }
}
```

That's it — the assistant now has all 17 tools. [`uv`](https://docs.astral.sh/uv/)
downloads and runs the published package on demand in an isolated environment, so
there's nothing to install or keep updated by hand.

Prefer pipx? `pipx install greeks-mcp`, then use `"command": "greeks-mcp"` with no
`args`.

### Docker

A `Dockerfile` is included for containerized runs. The server speaks stdio (what
MCP clients spawn), so run it interactively (`-i`):

```bash
docker build -t greeks-mcp .
docker run --rm -i -e GREEKS_API_KEY=grk_your_key_here greeks-mcp
```

The image starts and answers MCP introspection (initialize + `tools/list`) with
no key; `GREEKS_API_KEY` is only needed for the authenticated analytics tools.

To wire the container into an MCP client, set `"command": "docker"` with
`"args": ["run","--rm","-i","-e","GREEKS_API_KEY","greeks-mcp"]`.

### Where the config block goes

The same `mcpServers` block works in every MCP client — only the file location
differs.

| Client | Config file |
|---|---|
| Claude Desktop (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Claude Desktop (Windows) | `%APPDATA%\Claude\claude_desktop_config.json` |
| Cursor (global) | `~/.cursor/mcp.json` |
| Cursor (per-project) | `<project>/.cursor/mcp.json` |

Ready-to-copy configs live in [`examples/`](examples/). After reloading, the server
shows up under Cursor's Settings → *MCP* with a green dot and its 17 tools; type
`@greeks-analytics` in chat (or just ask for GEX/greeks/max pain) to use them.

## Tools

| Tool | Endpoint | Min plan | What it returns |
|---|---|---|---|
| `get_max_pain` | `/api/analytics/maxpain` | Free | Max Pain strike per expiration |
| `get_greeks` | `/api/analytics/greeks` | Trader | Δ Γ Θ V ρ, theo price, mispricing per contract |
| `get_gex` | `/api/analytics/gex` | Trader | GEX/DEX per strike, total Net GEX, Gamma Flip |
| `get_flow` | `/api/analytics/flow` | Trader | Unusual-activity signals |
| `get_vol_structure` | `/api/analytics/vol-structure` | Trader | IV skew + term structure with plain-English reads |
| `get_overview` | `/api/analytics/overview` | Pro | Full dashboard (sentiment, GEX, max pain, expected move, IV surface, term structure, top flow) |
| `get_vex` | `/api/analytics/vex` | Pro | Vanna & Charm exposure (2nd-order dealer Greeks) |
| `get_zero_dte` | `/api/analytics/zero-dte` | Pro | 0DTE focus panel — pin risk, gamma flip, max pain |
| `get_gex_intraday` | `/api/analytics/gex-intraday` | Pro | Intraday gamma-regime time-series + flip timing |
| `get_track_record_detail` | `/api/analytics/track-record` | Pro | Day-by-day level outcomes (the receipts behind the %) |
| `get_snapshot` | `/api/analytics/snapshot` | — | Compact analytics snapshot |
| `get_levels` | `/api/analytics/levels` | — | Options-derived support/resistance levels |
| `screener` | `/api/public/screener` | public | Watchlist screener — discover interesting symbols |
| `gex_heatmap` | `/api/public/gex-heatmap` | public | GEX-by-strike heatmap for a watchlist symbol |
| `track_record` | `/api/public/track-record` | public | Aggregated signal accuracy (~last 35 days) |
| `list_plans` | `/api/billing/plans` | public | Plans, prices, limits, routes |
| `health` | `/health` | public | Service health |

Most analytics tools take `symbol` (required) and optional `expiration` (a Unix
timestamp, or `"all"` for every expiration; omit for the nearest expiry).
`get_greeks` also accepts `range="atm"`, `moneyness="low,high"` and `limit`.
Two take different args: `get_gex_intraday` uses `date="YYYY-MM-DD"` (not
`expiration`), and `get_track_record_detail` takes an optional `symbol` only.

## Configuration

| Env var | Required | Default | Description |
|---|---|---|---|
| `GREEKS_API_KEY` | for `/api/analytics/*` | — | Your `grk_...` key. Public tools work without it. |
| `GREEKS_BASE_URL` | no | `https://api.greeks.pro` | API base URL |
| `GREEKS_TIMEOUT` | no | `30` | Per-request timeout (s) |
| `MCP_TRANSPORT` | no | `stdio` | `stdio` (for clients) or `http` |

## Run from source

Requires Python ≥ 3.10.

```bash
git clone https://github.com/ArtBreguez/greeks-mcp.git
cd greeks-mcp
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# stdio (what MCP clients spawn)
GREEKS_API_KEY=grk_... greeks-mcp        # or: python -m greeks_mcp

# or over HTTP
GREEKS_API_KEY=grk_... MCP_TRANSPORT=http greeks-mcp
```

## Development

```bash
# Inspect the tools interactively without a full client:
mcp dev src/greeks_mcp/server.py

# Tests (no network needed):
python tests/test_server.py     # tool wiring (URLs, params, headers, errors)
python tests/test_e2e.py        # spawns the server over stdio, calls all 17 tools
```

## Releasing (maintainers)

Published to PyPI via [Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
(OIDC — no API token stored). One-time setup:

1. On PyPI → *Account settings* → *Publishing* → add a pending publisher:
   project `greeks-mcp`, owner `ArtBreguez`, repo `greeks-mcp`, workflow
   `publish.yml`, environment `pypi`.
2. In GitHub repo settings → *Environments*, create an environment named `pypi`.

Then cut a release by bumping `version` in `pyproject.toml` + `__init__.py` and
pushing a tag:

```bash
git tag v0.1.0 && git push origin v0.1.0
```

The workflow builds the sdist+wheel, verifies the wheel installs and registers all
17 tools, and publishes.

## Notes

- **Plans & errors:** a `402`/`403` means your plan doesn't include that route (or
  you hit the symbol/rate limit). Call `list_plans` to see what each tier unlocks.
- **`expiration="all"`** returns every expiration — richer but slower. For heavy
  names prefer a specific expiration timestamp, or raise `GREEKS_TIMEOUT`.
- **Derived data only.** No raw market data (quotes, bid/ask, OI, contract prices)
  is redistributed — everything here is computed analytics.

## License

MIT — see [LICENSE](LICENSE).
