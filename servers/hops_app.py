#!/usr/bin/env python3
"""Asthenosphere as Grasshopper components through Hops (McNeel's ghhops-server).

    python servers/hops_app.py            # serves http://localhost:5000
In Grasshopper: add a Hops component, set its path to http://localhost:5000/cl/route (or /cl/vrp,
/cl/diagnose, /cl/pathways). Inputs and outputs appear as component parameters. Route points come back as
Rhino points in metres relative to the network's south-west corner; VRP routes come back as a data
tree with one branch per vehicle, {0}, {1}, ... ready for Polyline.
"""
import json
import os
import sys

import ghhops_server as hs
import rhino3dm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402

hops = hs.Hops()


def _pts(xyz):
    return [rhino3dm.Point3d(x, y, z) for x, y, z in xyz]


@hops.component(
    "/cl/route",
    name="CL Route",
    nickname="Route",
    description="Fastest, shortest or least-energy route on the OSM road network",
    inputs=[
        hs.HopsString("OSM", "O", "OSM file path or place name"),
        hs.HopsNumber("FromLon", "FLo", "Origin longitude"),
        hs.HopsNumber("FromLat", "FLa", "Origin latitude"),
        hs.HopsNumber("ToLon", "TLo", "Destination longitude"),
        hs.HopsNumber("ToLat", "TLa", "Destination latitude"),
        hs.HopsString("Weight", "W", "travel_time, length or energy_kwh", default="travel_time"),
    ],
    outputs=[
        hs.HopsPoint("Points", "P", "Route vertices (local metres, z = elevation)", hs.HopsParamAccess.LIST),
        hs.HopsNumber("Length", "L", "metres"),
        hs.HopsNumber("Time", "T", "seconds"),
        hs.HopsNumber("Energy", "E", "kWh"),
    ],
)
def cl_route(osm, flon, flat, tlon, tlat, weight="travel_time"):
    r = core.route(osm, flon, flat, tlon, tlat, weight)
    return _pts(r["points"]), r["length_m"], r["travel_time_s"], r["energy_kwh"]


@hops.component(
    "/cl/vrp",
    name="CL VRP",
    nickname="VRP",
    description="Vehicle routing with capacity and time windows; one branch per vehicle",
    inputs=[
        hs.HopsString("OSM", "O", "OSM file path or place name"),
        hs.HopsString("Problem", "P", "vrp-solve problem as JSON text"),
        hs.HopsString("Solver", "S", "pyvrp, ortools or both", default="pyvrp"),
    ],
    outputs=[
        hs.HopsPoint("Routes", "R", "Route vertices, branch {v} per vehicle", hs.HopsParamAccess.TREE),
        hs.HopsNumber("Cost", "C", "Total cost in the objective's unit"),
        hs.HopsString("Report", "Rep", "Full plan as JSON (stops, arrivals, loads, violations)"),
    ],
)
def cl_vrp(osm, problem, solver="pyvrp"):
    plan = core.solve_vrp(osm, problem, solver)[0]
    if not plan.get("feasible"):
        return {"{0}": []}, -1.0, json.dumps(plan)
    tree = {"{%d}" % v: _pts(r["points"]) for v, r in enumerate(plan["routes"])}
    report = {k: v for k, v in plan.items() if k != "routes"}
    report["routes"] = [{k: v for k, v in r.items() if k not in ("points", "node_path")} for r in plan["routes"]]
    return tree, plan["total_cost"], json.dumps(report)


@hops.component(
    "/cl/diagnose",
    name="CL Tree Doctor",
    nickname="TreeDoc",
    description="Diagnose data-tree problems from a gh_tree_probe JSON dump",
    inputs=[hs.HopsString("Probe", "P", "JSON from gh_tree_probe.probe()")],
    outputs=[hs.HopsString("Report", "R", "Findings and fixes")],
)
def cl_diagnose(probe):
    return core.diagnose_tree(probe)["report"]


@hops.component(
    "/cl/pathways",
    name="CL Pathways",
    nickname="Pathways",
    description="CO2 pathways of a policy package across futures; one branch per future",
    inputs=[
        hs.HopsString("Package", "P", "best, no_policy or a study package id such as P12", default="best"),
        hs.HopsInteger("Futures", "F", "Number of sampled futures", default=20),
        hs.HopsNumber("Target", "T", "2050 CO2 relative to 2025 that counts as success", default=0.2),
    ],
    outputs=[
        hs.HopsNumber("Years", "Y", "Years of the pathway, 2025-2050"),
        hs.HopsNumber("CO2", "C", "CO2 relative to 2025, branch {f} per future", hs.HopsParamAccess.TREE),
        hs.HopsBoolean("Success", "S", "True where the future meets the target"),
        hs.HopsString("Report", "R", "Package, robustness and target as JSON"),
    ],
)
def cl_pathways(package="best", futures=20, target=0.2):
    r = core.pathways(package, int(futures), float(target))
    report = {k: r[k] for k in ("package", "target", "robustness")}
    return r["years"], r["tree"], r["success"], json.dumps(report)


if __name__ == "__main__":
    hops.start(debug=False)
