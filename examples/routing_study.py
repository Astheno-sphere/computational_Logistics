#!/usr/bin/env python3
"""Reproduce the numbers in README.md: terrain effect on routing, and a VRP plan from two solvers.
Synthetic data: a 7 x 7 street grid at Molde harbour with a 60 m Gaussian hill (not real terrain).
Usage: python examples/routing_study.py
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ("skills/osm-network/scripts", "skills/vrp-solve/scripts"):
    sys.path.insert(0, os.path.join(ROOT, p))
import osm_network as on  # noqa: E402
import vrp_solve as vs  # noqa: E402

GRID = os.path.join(ROOT, "data", "synthetic", "grid_molde.osm")


def hill(G, height=60.0, sigma=350.0):
    xs = [d["x"] for _, d in G.nodes(data=True)]
    ys = [d["y"] for _, d in G.nodes(data=True)]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    return lambda x, y: height * math.exp(-(((x - cx) / sigma) ** 2 + ((y - cy) / sigma) ** 2))


def main():
    flat = on.build(osm=GRID)
    H = on.add_costs(on.add_terrain(on.load(osm=GRID), elevation_fn=hill(flat)))
    o, d = on.nearest(H, 7.1592, 62.7375), on.nearest(H, 7.1826, 62.7483)
    rows = []
    for w in ("length", "travel_time", "energy_kwh"):
        r = on.route(H, o, d, w)
        rows.append({"objective": w, **{k: r[k] for k in ("length_m", "travel_time_s", "energy_kwh", "climb_m")}})
    prob = json.load(open(os.path.join(ROOT, "skills/vrp-solve/examples/deliveries.json")))
    plans = vs.solve(H, prob, "both", seconds=2)
    out = {"network": on.summary(H), "routes_over_hill": rows,
           "vrp": [{"solver": p["solver"], "total_travel_time_s": p["total_cost"], "vehicles": p["vehicles_used"],
                    "violations": p["violations"]} for p in plans]}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
