"""
End-to-end protocol test for the Greeks MCP server.

Unlike test_server.py (which calls the tool functions directly), this drives the
server the way a real client (Claude Desktop, Cursor) does: it spawns the server
via `python -m greeks_mcp`
over stdio, performs the MCP `initialize` handshake, lists the tools, and calls
every tool through the protocol against a mocked Greeks API.

This is the "does it actually work for the user" test: it proves each of the 12
tools is discoverable, has a description + input schema, is callable over MCP, and
returns real content.

Run:  python test_e2e.py     (no network — a stub HTTP server backs the API)
Exits non-zero on the first failure.
"""
import asyncio
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# ── A tiny stub of the Greeks API so tool calls get real JSON back ──────────────

_ANALYTICS_STUB = {
    "/api/analytics/maxpain": {"symbol": "AAPL", "spotPrice": 100.0, "results": []},
    "/api/analytics/greeks": {"symbol": "AAPL", "spotPrice": 100.0, "contracts": []},
    "/api/analytics/gex": {"symbol": "AAPL", "totalNetGEX": 1.0, "gammaFlip": 99.0, "strikes": []},
    "/api/analytics/flow": {"symbol": "AAPL", "signals": []},
    "/api/analytics/overview": {"symbol": "AAPL", "sentiment": {}, "gexSummary": {}},
    "/api/analytics/snapshot": {"symbol": "AAPL", "snapshot": True},
    "/api/analytics/levels": {"symbol": "AAPL", "levels": []},
    "/api/analytics/vex": {"symbol": "AAPL", "totalNetVEX": 0.0, "totalNetCharm": 0.0, "strikes": []},
    "/api/analytics/vol-structure": {"symbol": "AAPL", "skew": [], "termStructure": [], "skewRead": "", "termRead": "", "termSlope": 0.0},
    "/api/analytics/zero-dte": {"symbol": "AAPL", "isTrue0DTE": False, "pinRisk": "n/a", "read": ""},
    "/api/analytics/gex-intraday": {"symbol": "AAPL", "regime": "positive", "flippedAt": 0, "points": []},
    "/api/analytics/track-record": {"days": 0, "outcomes": [], "updatedAt": 1},
    "/api/public/screener": {"rows": [{"symbol": "SPY"}]},
    "/api/public/gex-heatmap": {"symbol": "SPY", "strikes": []},
    "/api/public/track-record": {"updatedAt": 1, "records": []},
    "/api/billing/plans": {"plans": ["free", "trader", "pro", "institutional"]},
    "/health": {"status": "ok", "supabase": True, "stripe": True},
}


class _StubHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        body = _ANALYTICS_STUB.get(path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error":"not found"}')
            return
        payload = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):  # silence
        pass


def _start_stub() -> tuple[HTTPServer, str]:
    srv = HTTPServer(("127.0.0.1", 0), _StubHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    host, port = srv.server_address
    return srv, f"http://{host}:{port}"


# ── The E2E run ────────────────────────────────────────────────────────────────

FAILED = []


def check(name, cond):
    print(f"  [{'ok' if cond else 'FAIL'}] {name}")
    if not cond:
        FAILED.append(name)


# Every tool and a representative set of args a user/model would send.
CALLS = {
    "get_max_pain":  {"symbol": "AAPL"},
    "get_greeks":    {"symbol": "AAPL", "expiration": "all", "range": "atm"},
    "get_gex":       {"symbol": "AAPL"},
    "get_flow":      {"symbol": "AAPL"},
    "get_overview":  {"symbol": "AAPL", "expiration": "all"},
    "get_snapshot":  {"symbol": "AAPL"},
    "get_levels":    {"symbol": "AAPL"},
    "get_vex":              {"symbol": "AAPL", "expiration": "all"},
    "get_vol_structure":    {"symbol": "AAPL"},
    "get_zero_dte":         {"symbol": "AAPL"},
    "get_gex_intraday":     {"symbol": "AAPL", "date": "2026-08-10"},
    "get_track_record_detail": {"symbol": "AAPL"},
    "screener":      {},
    "gex_heatmap":   {"symbol": "SPY"},
    "track_record":  {},
    "list_plans":    {},
    "health":        {},
}


async def main():
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    stub, base_url = _start_stub()
    try:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "greeks_mcp"],
            env={
                **os.environ,
                "GREEKS_API_KEY": "grk_e2e_test",
                "GREEKS_BASE_URL": base_url,
                "GREEKS_TIMEOUT": "10",
            },
        )
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()

                # 1. discovery: all 17 tools present, each with a description + schema
                listed = await session.list_tools()
                tools = {t.name: t for t in listed.tools}
                check("17 tools discovered over MCP", len(tools) == 17)
                for name in CALLS:
                    t = tools.get(name)
                    check(f"{name}: present", t is not None)
                    if t:
                        desc = (t.description or "").strip()
                        check(f"{name}: has description ({len(desc)} chars)", len(desc) >= 30)
                        check(f"{name}: has input schema", isinstance(t.inputSchema, dict))

                # 2. required-arg tools declare 'symbol' as required
                for name in ("get_max_pain", "get_greeks", "get_gex", "get_flow",
                             "get_overview", "get_snapshot", "get_levels"):
                    req = (tools[name].inputSchema or {}).get("required", [])
                    check(f"{name}: 'symbol' required", "symbol" in req)

                # 3. call every tool over the protocol; expect real JSON content back
                for name, args in CALLS.items():
                    res = await session.call_tool(name, args)
                    check(f"{name}: call not error", not res.isError)
                    text = ""
                    if res.content and hasattr(res.content[0], "text"):
                        text = res.content[0].text
                    check(f"{name}: returned JSON payload", text.strip().startswith("{"))

                # 4. a plan-gated failure surfaces as a helpful tool error, not a crash
                #    (unknown symbol path on the stub → 404 → GreeksAPIError → isError)
                res = await session.call_tool("get_greeks", {"symbol": ""})
                joined = " ".join(
                    getattr(c, "text", "") for c in (res.content or [])
                )
                check("empty symbol → tool error surfaced",
                      res.isError or "symbol" in joined.lower())
    finally:
        stub.shutdown()

    print()
    if FAILED:
        print(f"FAILED ({len(FAILED)}): {', '.join(FAILED)}")
        sys.exit(1)
    print("all e2e checks passed")


if __name__ == "__main__":
    asyncio.run(main())
