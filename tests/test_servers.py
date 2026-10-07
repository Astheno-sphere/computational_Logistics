"""Both connectivity front ends, driven the way real clients drive them."""
import asyncio
import json

from conftest import GRID, ROOT

PROB = (ROOT / "skills/vrp-solve/examples/deliveries.json").read_text()


# ---- MCP: the SDK's in-memory Client, same calls an MCP host makes -----------------------------------
def mcp_call(name, args):
    from mcp import Client
    import mcp_server

    async def go():
        async with Client(mcp_server.mcp, raise_exceptions=True) as c:
            tools = {t.name for t in (await c.list_tools()).tools}
            res = await c.call_tool(name, args)
            return tools, res
    return asyncio.run(go())


def payload(res):
    sc = res.structured_content
    return sc.get("result", sc) if isinstance(sc, dict) else json.loads(res.content[0].text)


def test_mcp_lists_all_tools_and_routes():
    tools, res = mcp_call("route", {"source": GRID, "origin_lon": 7.1592, "origin_lat": 62.7375,
                                     "dest_lon": 7.1826, "dest_lat": 62.7483, "weight": "length"})
    assert {"network_summary", "route", "solve_vrp", "solve_model", "diagnose_tree"} <= tools
    r = payload(res)
    assert r["length_m"] > 2000 and len(r["points"]) == len(r["nodes"])


def test_mcp_solve_model_cross_checks_solvers():
    data = (ROOT / "skills/opt-model/examples/facility_location.json").read_text()
    _, res = mcp_call("solve_model", {"model": "facility_location", "data": data, "solver": "all"})
    assert payload(res)["solvers_agree"]


def test_mcp_diagnose_tree():
    probe = (ROOT / "skills/gh-datatree/examples/probe_example.json").read_text()
    _, res = mcp_call("diagnose_tree", {"probe": probe})
    assert "CROSS_PRODUCT" in payload(res)["report"]


# ---- Hops: the JSON Grasshopper posts to a Hops server (ghhops-server 1.5:
# inputs arrive keyed "{0}", list outputs are keyed "0", tree outputs keep our "{v}" keys) ---------------------------------------------------
def hops_input(name, values, type_="System.String"):
    """Grasshopper JSON-encodes every value, text included."""
    return {"ParamName": name, "InnerTree": {"{0}": [{"type": type_, "data": json.dumps(v)}
                                                for v in values]}}


def outputs(res):
    ok, body = res
    assert ok, body
    data = json.loads(body)
    assert not data.get("errors"), data
    return {v["ParamName"]: v["InnerTree"] for v in data["values"]}


def test_hops_registers_components_with_metadata():
    import hops_app
    ok, meta = hops_app.hops.query("/cl/vrp")
    meta = json.loads(meta)
    assert ok and [i["Name"] for i in meta["Inputs"]] == ["OSM", "Problem", "Solver"]


def test_hops_route_returns_points_and_totals():
    import hops_app
    body = {"pointer": "/cl/route", "values": [
        hops_input("OSM", [GRID]), hops_input("FromLon", [7.1592], "System.Double"),
        hops_input("FromLat", [62.7375], "System.Double"), hops_input("ToLon", [7.1826], "System.Double"),
        hops_input("ToLat", [62.7483], "System.Double"), hops_input("Weight", ["length"])]}
    out = outputs(hops_app.hops.solve("/cl/route", json.dumps(body)))
    pts = out["Points"]["0"]
    assert pts[0]["type"] == "Rhino.Geometry.Point3d" and len(pts) >= 2
    assert float(out["Length"]["0"][0]["data"]) > 2000


def test_hops_vrp_returns_one_branch_per_vehicle():
    import hops_app
    body = {"pointer": "/cl/vrp", "values": [hops_input("OSM", [GRID]), hops_input("Problem", [PROB]),
                                             hops_input("Solver", ["pyvrp"])]}
    out = outputs(hops_app.hops.solve("/cl/vrp", json.dumps(body)))
    raw = out["Report"]["0"][0]["data"]
    report = json.loads(json.loads(raw) if raw.startswith('"') else raw)   # Hops JSON-encodes strings
    assert sorted(out["Routes"]) == ["{%d}" % v for v in range(report["vehicles_used"])]
    assert report["violations"] == []


def test_mcp_server_runs_over_stdio_as_a_subprocess():
    """How Claude Code and other hosts start it: a child process speaking JSON-RPC on stdin/stdout."""
    import sys
    from mcp import Client, StdioServerParameters

    async def go():
        params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "servers/mcp_server.py")])
        async with Client(params) as c:
            res = await c.call_tool("network_summary", {"source": GRID})
            return payload(res)
    s = asyncio.run(go())
    assert s["nodes"] == 49 and s["strongly_connected"]
