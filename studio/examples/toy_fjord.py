"""End-to-end pipeline check on a SYNTHETIC fjord (no internet, no real data):

    solve (PyVRP) -> replay (SimPy) -> validate (contract) -> KPIs -> scene.json -> render

    python -m studio.examples.toy_fjord --out studio/out/toy            # scene + report
    python studio/render_deck/render.py --scene studio/out/toy/scene.json --out studio/out/toy/toy.mp4

Two supply vessels serve nine installations from one base. The baseline serves them in the order
received; the optimised plan is PyVRP's. Geometry is invented and labelled as such on screen.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from pyvrp import Model
from pyvrp.stop import MaxRuntime
from shapely.geometry import Polygon
from shapely.ops import unary_union

from studio.contract import compare_to_paper, haversine_m, kpis, validate
from studio.scene import build_scene, write
from studio.sim.replay import replay

KN = 0.514444  # m/s per knot
# synthetic fjord: a straight channel between two land strips, so straight legs stay at sea
LAND = unary_union([Polygon([(10.30, 59.00), (10.52, 59.00), (10.52, 59.60), (10.30, 59.60)]),
                    Polygon([(10.78, 59.00), (11.00, 59.00), (11.00, 59.60), (10.78, 59.60)])])
BASE = (10.53, 59.56)


def instance(seed=7, n=9):
    rng = np.random.default_rng(seed)
    pts = np.column_stack([rng.uniform(10.56, 10.74, n), rng.uniform(59.05, 59.50, n)])
    nodes = [BASE] + [tuple(map(float, p)) for p in pts]
    demand = {i: int(rng.integers(1, 4)) for i in range(1, n + 1)}
    tw = {i: (int(rng.integers(0, 4)) * 3600, None) for i in range(1, n + 1)}  # earliest crane slot
    return nodes, demand, tw


def matrix(nodes):
    lon, lat = np.array(nodes).T
    return haversine_m(lon[:, None], lat[:, None], lon[None, :], lat[None, :])


def solve(nodes, demand, n_veh, cap, speed, seconds=2):
    D = matrix(nodes)
    m = Model()
    m.add_vehicle_type(num_available=n_veh, capacity=cap)
    locs = [m.add_location(x=int(x * 1e5), y=int(y * 1e5)) for x, y in nodes]
    m.add_depot(locs[0])
    for i, l in enumerate(locs[1:], 1):
        m.add_client(l, delivery=demand[i])
    for i, a in enumerate(locs):
        for j, b in enumerate(locs):
            m.add_edge(a, b, distance=int(D[i, j]), duration=int(D[i, j] / speed))
    res = m.solve(stop=MaxRuntime(seconds), display=False)
    assert res.is_feasible(), "PyVRP returned an infeasible plan"
    # PyVRP 0.14: is_client is a method, and a client's idx counts clients only (node = idx + depots)
    return [[a.idx + 1 for a in r if a.is_client()] for r in res.best.routes()], float(res.cost())


def run(out):
    nodes, demand, tw = instance()
    speed, cap, n_veh = 12 * KN, 10, 2
    agents = pd.DataFrame({"agent_id": ["PSV-A", "PSV-B"], "cls": "psv", "speed_mps": speed,
                           "vmax_mps": speed, "capacity": cap, "domain": "sea"})
    service = {i: 1800 for i in demand}
    routes, cost = solve(nodes, demand, n_veh, cap, speed)
    opt = dict(zip(agents["agent_id"], routes + [[]] * (n_veh - len(routes))))
    # baseline: orders in the order received, each vessel filled to capacity before the next one
    base_routes, fill, ids = {a: [] for a in agents["agent_id"]}, 0, list(agents["agent_id"])
    for c in demand:
        if fill + demand[c] > cap:
            ids, fill = ids[1:], 0
        base_routes[ids[0]].append(c)
        fill += demand[c]
    results = {}
    for name, rts in (("baseline", base_routes), ("optimised", opt)):
        traj, ev = replay(nodes, rts, agents, service_s=service, tw=tw, demand=demand)
        rep = validate(traj, agents, land=LAND)
        results[name] = (traj, ev, rep, kpis(traj))
        print(f"{name:9s} {rep}  distance {results[name][3]['distance_km']:.1f} km  makespan {results[name][3]['makespan_s'] / 3600:.2f} h")
    k0, k1 = results["baseline"][3], results["optimised"][3]
    saving = 1 - k1["distance_km"] / k0["distance_km"]
    # the toy has no paper: check the replay against the solver's own objective instead
    check = compare_to_paper({"distance_km": k1["distance_km"]}, {"distance_km": {"value": cost / 1000, "rel_tol": 0.01}})
    print(check.to_string(index=False))
    traj, ev, rep, k = results["optimised"]
    sites = [{"pos": list(BASE), "label": "supply base", "height_m": 1200}] + \
            [{"pos": list(nodes[i]), "label": f"I{i}"} for i in demand]
    hours = lambda s: f"{s / 3600:.1f} h"
    scene = build_scene(
        traj, agents, rep, land=LAND, sites=sites, accent=("PSV-A", "PSV-B"), seconds=12,
        camera={"fit": [[10.50, 59.03], [10.80, 59.58]], "pitch": 45, "bearing": -12},
        overlay={"kicker": "how far do two supply vessels sail to serve nine installations?",
                 "title": "Toy fjord — routed vs order received",
                 "legend": [["#FF5B3A", "optimised route (PyVRP)"], ["#E8E1CF", "installation"]],
                 "source": "SYNTHETIC geometry and demand · pipeline test · studio/examples/toy_fjord.py",
                 "watermark": "COMPUTATIONAL LOGISTICS"},
        kpi_track=[["km sailed vs order received", [[0, f"−{saving:.0%}"]]],
                   ["fleet makespan", [[0, hours(k["makespan_s"])]]]])
    out = Path(out)
    write(scene, out / "scene.json")
    traj.to_csv(out / "trajectory.csv", index=False)
    (out / "report.json").write_text(json.dumps({"contract": str(rep), "kpis": {n: r[3] for n, r in results.items()},
                                                 "saving_distance": saving, "self_check": check.to_dict("records")}, indent=1, default=float))
    return results, saving, check


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="studio/out/toy")
    run(ap.parse_args().out)
