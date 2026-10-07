#!/usr/bin/env python3
"""Vehicle routing on a real road network: capacities, time windows, service times.

Costs come from the osm-network graph (shortest paths by length, time or energy), not straight
lines. Solved with PyVRP (hybrid genetic search, state of the art for CVRP/VRPTW); OR-Tools is an
independent second solver for cross-checking.

Input JSON (see ../examples/deliveries.json):
  {"depot": {"lon":..,"lat":.., "tw": [0, 28800]},
   "clients": [{"name":"A","lon":..,"lat":..,"demand":3,"service_s":120,"tw":[0, 3600]}, ...],
   "vehicles": {"count": 2, "capacity": 10},
   "objective": "travel_time" | "length" | "energy_kwh"}
CLI:
  python vrp_solve.py --osm grid_molde.osm --problem deliveries.json [--solver pyvrp|ortools|both]
"""
import argparse
import json
import os
import sys

import networkx as nx

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "osm-network", "scripts"))
import osm_network as on  # noqa: E402

# PyVRP needs integers. Scale so rounding is far below anything that matters.
SCALE = {"length": 1, "travel_time": 1, "energy_kwh": 1000}   # metres, seconds, watt-hours


def cost_matrices(G, nodes, objective):
    """All-pairs costs between stop nodes along the road network.
    Returns (objective matrix as float, duration matrix in s, node paths)."""
    n = len(nodes)
    obj = [[0.0] * n for _ in range(n)]
    dur = [[0.0] * n for _ in range(n)]
    paths = {}
    for i, a in enumerate(nodes):
        for j, b in enumerate(nodes):
            if i == j:
                continue
            r = on.route(G, a, b, objective)
            obj[i][j] = r[{"length": "length_m", "travel_time": "travel_time_s", "energy_kwh": "energy_kwh"}[objective]]
            dur[i][j] = r["travel_time_s"]
            paths[(i, j)] = r["nodes"]
    return obj, dur, paths


def _int(m, scale, shift=0):
    return [[int(round(x * scale)) + (shift if i != j else 0) for j, x in enumerate(row)] for i, row in enumerate(m)]


def energy_shift(obj):
    """Energy legs can be negative downhill. Solvers want non-negative arc costs, so add a constant
    to every leg. Every feasible plan with the same number of legs shifts by the same amount, so
    ranking is unchanged for a fixed fleet use; we report true energy from the unshifted matrix."""
    low = min(x for i, row in enumerate(obj) for j, x in enumerate(row) if i != j)
    return max(0.0, -low)


def solve_pyvrp(prob, obj, dur, seconds=2.0, seed=0):
    from pyvrp import Model
    from pyvrp.stop import MaxRuntime
    scale = SCALE[prob.get("objective", "travel_time")]
    shift = energy_shift(obj)
    D = _int([[x + shift if i != j else 0 for j, x in enumerate(r)] for i, r in enumerate(obj)], scale)
    T = _int(dur, 1)
    m = Model()
    locs = [m.add_location(x=0, y=0) for _ in range(len(obj))]  # coordinates unused: explicit edges
    dep = prob["depot"]
    depot = m.add_depot(locs[0], tw_early=dep.get("tw", [0, 10 ** 9])[0], tw_late=dep.get("tw", [0, 10 ** 9])[1])
    v = prob["vehicles"]
    m.add_vehicle_type(num_available=v["count"], capacity=v["capacity"], start_depot=depot, end_depot=depot,
                       tw_early=dep.get("tw", [0, 10 ** 9])[0], tw_late=dep.get("tw", [0, 10 ** 9])[1],
                       unit_distance_cost=1, unit_duration_cost=0)
    for k, c in enumerate(prob["clients"], start=1):
        tw = c.get("tw", [0, 10 ** 9])
        m.add_client(locs[k], delivery=c.get("demand", 0), service_duration=c.get("service_s", 0),
                     tw_early=tw[0], tw_late=tw[1], name=c.get("name", str(k)))
    for i in range(len(obj)):
        for j in range(len(obj)):
            if i != j:
                m.add_edge(locs[i], locs[j], distance=D[i][j], duration=T[i][j])
    res = m.solve(stop=MaxRuntime(seconds), seed=seed, display=False)
    if not res.best.is_feasible():
        return {"solver": "pyvrp", "feasible": False}
    # activities: depot, clients..., depot; a client activity's idx is its 0-based add order
    routes = [[a.idx + 1 for a in r if a.is_client()] for r in res.best.routes()]
    return {"solver": "pyvrp", "feasible": True, "routes": routes}


def solve_ortools(prob, obj, dur, seconds=2):
    """Runs OR-Tools in a subprocess. OR-Tools bundles its own HiGHS, which cannot share a process
    with the `highspy` package that Pyomo (opt-model) uses: whichever loads second fails to import.
    Isolating it keeps both skills usable in one session (notebook, agent, test run)."""
    import subprocess
    payload = json.dumps({"prob": prob, "obj": obj, "dur": dur, "seconds": seconds})
    r = subprocess.run([sys.executable, os.path.abspath(__file__), "--ortools-worker"], input=payload,
                       capture_output=True, text=True, timeout=seconds + 60)
    if r.returncode:
        raise RuntimeError("OR-Tools worker failed: " + r.stderr.strip()[-400:])
    return json.loads(r.stdout)


def _ortools_core(prob, obj, dur, seconds=2):
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    scale = SCALE[prob.get("objective", "travel_time")]
    shift = energy_shift(obj)
    D = _int([[x + shift if i != j else 0 for j, x in enumerate(r)] for i, r in enumerate(obj)], scale)
    n, v = len(obj), prob["vehicles"]
    mgr = pywrapcp.RoutingIndexManager(n, v["count"], 0)
    rt = pywrapcp.RoutingModel(mgr)
    cost_cb = rt.RegisterTransitCallback(lambda a, b: D[mgr.IndexToNode(a)][mgr.IndexToNode(b)])
    rt.SetArcCostEvaluatorOfAllVehicles(cost_cb)
    demand = [0] + [c.get("demand", 0) for c in prob["clients"]]
    dem_cb = rt.RegisterUnaryTransitCallback(lambda a: demand[mgr.IndexToNode(a)])
    rt.AddDimensionWithVehicleCapacity(dem_cb, 0, [v["capacity"]] * v["count"], True, "load")
    service = [0] + [c.get("service_s", 0) for c in prob["clients"]]
    time_cb = rt.RegisterTransitCallback(
        lambda a, b: int(round(dur[mgr.IndexToNode(a)][mgr.IndexToNode(b)])) + service[mgr.IndexToNode(a)])
    horizon = prob["depot"].get("tw", [0, 10 ** 6])[1]
    rt.AddDimension(time_cb, horizon, horizon, False, "time")
    tdim = rt.GetDimensionOrDie("time")
    for k, c in enumerate(prob["clients"], start=1):
        tw = c.get("tw", [0, horizon])
        tdim.CumulVar(mgr.NodeToIndex(k)).SetRange(tw[0], tw[1])
    p = pywrapcp.DefaultRoutingSearchParameters()
    p.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    p.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    p.time_limit.seconds = int(seconds)
    sol = rt.SolveWithParameters(p)
    if not sol:
        return {"solver": "ortools", "feasible": False}
    routes = []
    for k in range(v["count"]):
        idx, r = rt.Start(k), []
        while not rt.IsEnd(idx):
            node = mgr.IndexToNode(idx)
            if node:
                r.append(node)
            idx = sol.Value(rt.NextVar(idx))
        if r:
            routes.append(r)
    return {"solver": "ortools", "feasible": True, "routes": routes}


def evaluate(prob, routes, obj, dur, paths):
    """Recompute everything from the true (unshifted) matrices, so both solvers are judged alike,
    and check capacity and time windows independently of the solver."""
    out, total, violations = [], 0.0, []
    cap = prob["vehicles"]["capacity"]
    for r in routes:
        seq = [0] + r + [0]
        t, load = prob["depot"].get("tw", [0, 0])[0], 0
        cost, legs, stops = 0.0, [], []
        for a, b in zip(seq[:-1], seq[1:]):
            cost += obj[a][b]
            t += dur[a][b]
            legs.append(paths[(a, b)])
            if b:
                c = prob["clients"][b - 1]
                tw = c.get("tw", [0, 10 ** 9])
                t = max(t, tw[0])                         # wait if early
                if t > tw[1]:
                    violations.append("%s arrives at %.0fs after window end %ss" % (c.get("name", b), t, tw[1]))
                stops.append({"name": c.get("name", str(b)), "arrive_s": round(t, 1)})
                t += c.get("service_s", 0)
                load += c.get("demand", 0)
        if load > cap:
            violations.append("route load %s exceeds capacity %s" % (load, cap))
        total += cost
        out.append({"stops": stops, "load": load, "cost": round(cost, 4), "return_s": round(t, 1),
                    "node_path": [n for i, leg in enumerate(legs) for n in (leg if i == 0 else leg[1:])]})
    served = sorted(c for r in routes for c in r)
    if served != list(range(1, len(prob["clients"]) + 1)):
        violations.append("not every client served exactly once: %s" % served)
    return {"objective": prob.get("objective", "travel_time"), "total_cost": round(total, 4),
            "vehicles_used": len(routes), "routes": out, "violations": violations}


def solve(G, prob, solver="pyvrp", seconds=2.0):
    pts = [prob["depot"]] + prob["clients"]
    nodes = [on.nearest(G, p["lon"], p["lat"]) for p in pts]
    if len(set(nodes)) < len(nodes):
        raise ValueError("two stops snap to the same graph node; move them or densify the network")
    obj, dur, paths = cost_matrices(G, nodes, prob.get("objective", "travel_time"))
    runs = {"pyvrp": [solve_pyvrp], "ortools": [solve_ortools], "both": [solve_pyvrp, solve_ortools]}[solver]
    results = []
    for fn in runs:
        r = fn(prob, obj, dur, seconds)
        results.append({**r, **evaluate(prob, r["routes"], obj, dur, paths)} if r["feasible"] else r)
    return results


def main(argv=None):
    if (argv or sys.argv[1:])[:1] == ["--ortools-worker"]:
        d = json.load(sys.stdin)
        json.dump(_ortools_core(d["prob"], d["obj"], d["dur"], d["seconds"]), sys.stdout)
        return
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--dem")
    ap.add_argument("--problem", required=True)
    ap.add_argument("--solver", default="pyvrp", choices=["pyvrp", "ortools", "both"])
    ap.add_argument("--seconds", type=float, default=2.0)
    ap.add_argument("--paths", action="store_true", help="include node paths for baking to Rhino")
    a = ap.parse_args(argv)
    G = on.build(osm=a.osm, dem=a.dem)
    with open(a.problem) as fh:
        prob = json.load(fh)
    res = solve(G, prob, a.solver, a.seconds)
    if not a.paths:
        for r in res:
            for route in r.get("routes", []):
                route.pop("node_path", None) if isinstance(route, dict) else None
    json.dump(res, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
