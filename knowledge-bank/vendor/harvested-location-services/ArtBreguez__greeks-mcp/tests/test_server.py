"""
Offline smoke test for the Greeks MCP server.

No network: httpx is driven by a MockTransport, so we assert the server builds
the right URLs, headers, and query params and maps errors sensibly. Run with:

    GREEKS_API_KEY=grk_test python test_server.py

Exits non-zero on the first failed assertion.
"""
import os
import sys

os.environ.setdefault("GREEKS_API_KEY", "grk_test_key")
os.environ.setdefault("GREEKS_BASE_URL", "https://api.example.test")

import httpx

from greeks_mcp import server

_last = {}


def _handler(request: httpx.Request) -> httpx.Response:
    _last["url"] = str(request.url)
    _last["path"] = request.url.path
    _last["params"] = dict(request.url.params)
    _last["headers"] = dict(request.headers)

    if request.url.path == "/api/analytics/greeks":
        if request.url.params.get("symbol") == "FORBIDDEN":
            return httpx.Response(403, text="plan does not include greeks")
        return httpx.Response(200, json={"symbol": request.url.params.get("symbol"),
                                         "contracts": []})
    if request.url.path == "/api/analytics/maxpain":
        return httpx.Response(200, json={"symbol": "AAPL", "results": []})
    if request.url.path == "/api/analytics/vex":
        return httpx.Response(200, json={"symbol": request.url.params.get("symbol"),
                                         "totalNetVEX": 0, "totalNetCharm": 0, "strikes": []})
    if request.url.path == "/api/analytics/vol-structure":
        return httpx.Response(200, json={"symbol": request.url.params.get("symbol"),
                                         "skew": [], "termStructure": [], "skewRead": "",
                                         "termRead": "", "termSlope": 0})
    if request.url.path == "/api/analytics/zero-dte":
        return httpx.Response(200, json={"symbol": request.url.params.get("symbol"),
                                         "isTrue0DTE": False, "pinRisk": "n/a", "read": ""})
    if request.url.path == "/api/analytics/gex-intraday":
        return httpx.Response(200, json={"symbol": request.url.params.get("symbol"),
                                         "regime": "positive", "flippedAt": 0, "points": []})
    if request.url.path == "/api/analytics/track-record":
        return httpx.Response(200, json={"days": 0, "outcomes": [], "updatedAt": 1})
    if request.url.path == "/health":
        return httpx.Response(200, json={"status": "ok"})
    if request.url.path == "/api/public/screener":
        return httpx.Response(200, json={"rows": [{"symbol": "SPY"}]})
    if request.url.path == "/api/public/gex-heatmap":
        return httpx.Response(200, json={"symbol": request.url.params.get("symbol")})
    if request.url.path == "/api/public/track-record":
        return httpx.Response(200, json={"updatedAt": 1, "records": []})
    return httpx.Response(404, text="not found")


# Patch the Client used inside server._get to use our mock transport.
_orig_client = httpx.Client


def _mock_client(*args, **kwargs):
    kwargs["transport"] = httpx.MockTransport(_handler)
    kwargs.pop("timeout", None)
    return _orig_client(**kwargs)


server.httpx.Client = _mock_client


def check(name, cond):
    status = "ok" if cond else "FAIL"
    print(f"  [{status}] {name}")
    if not cond:
        sys.exit(1)


def run():
    print("greeks-mcp smoke test")

    # 1. symbol is upper-cased and API key header is attached
    server.get_greeks(symbol="aapl")
    check("greeks path", _last["path"] == "/api/analytics/greeks")
    check("symbol upper-cased", _last["params"]["symbol"] == "AAPL")
    check("api key header sent", _last["headers"].get("x-api-key") == server.API_KEY)
    check("no blank expiration sent", "expiration" not in _last["params"])

    # 2. optional params flow through; None/empty are dropped
    server.get_greeks(symbol="SPY", expiration="all", range="atm", limit=5)
    check("expiration passed", _last["params"]["expiration"] == "all")
    check("range passed", _last["params"]["range"] == "atm")
    check("limit passed", _last["params"]["limit"] == "5")
    check("moneyness dropped when None", "moneyness" not in _last["params"])

    # 3. max pain
    out = server.get_max_pain(symbol="AAPL")
    check("maxpain path", _last["path"] == "/api/analytics/maxpain")
    check("maxpain returns json", isinstance(out, dict) and "results" in out)

    # 4. health (public)
    h = server.health()
    check("health ok", h.get("status") == "ok")

    # 5. empty symbol rejected before any HTTP call
    try:
        server.get_greeks(symbol="  ")
        check("empty symbol rejected", False)
    except server.GreeksAPIError:
        check("empty symbol rejected", True)

    # 6. non-2xx mapped to a helpful error
    try:
        server.get_greeks(symbol="FORBIDDEN")
        check("403 raises", False)
    except server.GreeksAPIError as exc:
        check("403 raises", "403" in str(exc) and "plan" in str(exc).lower())

    # 7. missing API key surfaces a clear message
    saved = server.API_KEY
    server.API_KEY = ""
    try:
        server.health()
        # health() doesn't need the key header, but _headers() is only called on
        # keyed calls; force a keyed call instead:
        server.get_greeks(symbol="AAPL")
        check("missing key rejected", False)
    except server.GreeksAPIError as exc:
        check("missing key rejected", "GREEKS_API_KEY" in str(exc))
    finally:
        server.API_KEY = saved

    # 8. the 3 public data tools work and require no key
    saved = server.API_KEY
    server.API_KEY = ""  # public tools must not need a key
    try:
        sc = server.screener()
        check("screener path", _last["path"] == "/api/public/screener")
        check("screener returns json", isinstance(sc, dict) and "rows" in sc)

        hm = server.gex_heatmap(symbol="spy")
        check("gex_heatmap path", _last["path"] == "/api/public/gex-heatmap")
        check("gex_heatmap symbol upper-cased", _last["params"]["symbol"] == "SPY")
        check("gex_heatmap default expiry dropped", "expiry" not in _last["params"])

        tr = server.track_record()
        check("track_record path", _last["path"] == "/api/public/track-record")
        check("track_record returns json", isinstance(tr, dict) and "records" in tr)
    finally:
        server.API_KEY = saved

    # 8b. the 5 new analytics tools build the right URLs/params
    server.get_vex(symbol="spy", expiration="all")
    check("vex path", _last["path"] == "/api/analytics/vex")
    check("vex symbol upper-cased", _last["params"]["symbol"] == "SPY")
    check("vex expiration passed", _last["params"]["expiration"] == "all")

    server.get_vol_structure(symbol="qqq")
    check("vol-structure path", _last["path"] == "/api/analytics/vol-structure")
    check("vol-structure no blank expiration", "expiration" not in _last["params"])

    server.get_zero_dte(symbol="spy")
    check("zero-dte path", _last["path"] == "/api/analytics/zero-dte")
    check("zero-dte sends no expiration", "expiration" not in _last["params"])

    server.get_gex_intraday(symbol="spy", date="2026-08-10")
    check("gex-intraday path", _last["path"] == "/api/analytics/gex-intraday")
    check("gex-intraday date passed", _last["params"]["date"] == "2026-08-10")
    check("gex-intraday uses date not expiration", "expiration" not in _last["params"])

    server.get_track_record_detail(symbol="aapl")
    check("track-record-detail path", _last["path"] == "/api/analytics/track-record")
    check("track-record-detail symbol upper-cased", _last["params"]["symbol"] == "AAPL")
    server.get_track_record_detail()
    check("track-record-detail symbol optional", "symbol" not in _last["params"])

    # 9. all expected tools are registered
    import asyncio
    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    expected = {
        "get_max_pain", "get_greeks", "get_gex", "get_flow", "get_overview",
        "get_snapshot", "get_levels", "list_plans", "health",
        "screener", "gex_heatmap", "track_record",
        "get_vex", "get_vol_structure", "get_zero_dte", "get_gex_intraday",
        "get_track_record_detail",
    }
    check(f"all {len(expected)} tools registered", expected <= names)

    print("all checks passed")


if __name__ == "__main__":
    run()
