"""Shared entry points behind the MCP server and the Grasshopper Hops app.

Both front ends call these functions, so a tool in Claude and a component in Grasshopper give the
same answer. Inputs and outputs are plain JSON-able data.
"""
import json
import os
import sys
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ("skills/osm-network/scripts", "skills/vrp-solve/scripts", "skills/opt-model/scripts",
          "skills/gh-datatree/scripts"):
    sys.path.insert(0, os.path.join(ROOT, p))

import osm_network as on  # noqa: E402
import vrp_solve as vs  # noqa: E402


@lru_cache(maxsize=8)
def graph(source, dem=None):
    """Build once per (file or place name, DEM). A path that exists is read offline; anything else is
    treated as a place name and downloaded (needs network access to OSM)."""
    if os.path.exists(source):
        return on.build(osm=source, dem=dem)
    return on.build(place=source, dem=dem)


def local_xyz(G, nodes, origin=None):
    """Node ids -> (x, y, z) in metres relative to `origin` (default: the graph's south-west corner),
    the frame Rhino models usually use; z is elevation."""
    if origin is None:
        origin = (min(d["x"] for _, d in G.nodes(data=True)), min(d["y"] for _, d in G.nodes(data=True)))
    return [(G.nodes[n]["x"] - origin[0], G.nodes[n]["y"] - origin[1], G.nodes[n].get("elevation", 0.0))
            for n in nodes]


def network_summary(source, dem=None):
    return on.summary(graph(source, dem))


def route(source, origin_lon, origin_lat, dest_lon, dest_lat, weight="travel_time", dem=None):
    G = graph(source, dem)
    r = on.route(G, on.nearest(G, origin_lon, origin_lat), on.nearest(G, dest_lon, dest_lat), weight)
    r["points"] = local_xyz(G, r["nodes"])
    return r


def solve_vrp(source, problem, solver="both", seconds=2.0, dem=None):
    """problem: dict or JSON text in the vrp-solve format. Returns plans with per-vehicle point lists."""
    G = graph(source, dem)
    prob = json.loads(problem) if isinstance(problem, str) else problem
    plans = vs.solve(G, prob, solver, seconds)
    for p in plans:
        for r in p.get("routes", []):
            r["points"] = local_xyz(G, r["node_path"])
    return plans


def solve_model(model, data, solver="auto"):
    import opt_cli
    return opt_cli.run(model, json.loads(data) if isinstance(data, str) else data, solver)


def diagnose_tree(probe):
    import tree_diagnose as td
    findings = td.diagnose(json.loads(probe) if isinstance(probe, str) else probe)
    return {"findings": findings, "report": td.report(findings)}
