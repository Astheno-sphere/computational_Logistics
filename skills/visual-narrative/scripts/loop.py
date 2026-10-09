#!/usr/bin/env python3
"""Plate 04: the shortest loop.

Give one van, at plate 03's depot, a day's addresses (drawn at random from OSM buildings) and plan
the order with vrp-solve: PyVRP, cross-checked by OR-Tools, both re-evaluated on true road times.
Compare with driving them in the order the addresses came in.

    python skills/visual-narrative/scripts/loop.py              # needs docs/plates/03-depot.json (reach.py)
    python skills/visual-narrative/scripts/loop.py --stops 30 --seed 1
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pyproj
from shapely.geometry import LineString

import basemap as B
import plate as P

sys.path.insert(0, str(B.HERE.parents[1] / "vrp-solve" / "scripts"))
import osm_network as on  # noqa: E402
import vrp_solve as vrp  # noqa: E402

CALLOUT = (-900, 1500)
MARGIN = 400               # metres around the outermost stops
FRAME_SHIFT_N = 600


def addresses(town, depot_node, n, seed):
    """n building centroids at distinct junctions, reachable both ways from the depot."""
    import networkx as nx
    reach_out = nx.single_source_dijkstra_path_length(town.D, depot_node, weight="travel_time")
    reach_in = nx.single_source_dijkstra_path_length(town.D.reverse(copy=False), depot_node, weight="travel_time")
    b = B.buildings(town).centroid
    rng = np.random.default_rng(seed)
    picked, nodes = [], {depot_node}
    for i in rng.permutation(len(b)):
        node = on.ox.distance.nearest_nodes(town.G, b.iloc[i].x, b.iloc[i].y)
        if node in nodes or node not in reach_out or node not in reach_in:
            continue
        nodes.add(node)
        picked.append((b.iloc[i].x, b.iloc[i].y, node))
        if len(picked) == n:
            return picked
    raise ValueError("not enough distinct reachable addresses")


def path_lines(town, node_path):
    """Road geometry along a node path (cheapest parallel edge, oriented u -> v)."""
    G, out = town.G, []
    for u, v in zip(node_path[:-1], node_path[1:]):
        d = min(G[u][v].values(), key=lambda e: e["travel_time"])
        if "geometry" in d:
            xy = np.asarray(d["geometry"].coords)
            if np.hypot(*(xy[0] - (G.nodes[u]["x"], G.nodes[u]["y"]))) > np.hypot(*(xy[-1] - (G.nodes[u]["x"], G.nodes[u]["y"]))):
                xy = xy[::-1]
        else:
            xy = np.array([(G.nodes[u]["x"], G.nodes[u]["y"]), (G.nodes[v]["x"], G.nodes[v]["y"])])
        out.append(xy)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--osm", default=B.DEFAULT_OSM)
    ap.add_argument("--depot-json", default="docs/plates/03-depot.json")
    ap.add_argument("--stops", type=int, default=24)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--out", default="docs/plates/04-the-shortest-loop.png")
    a = ap.parse_args()

    town = B.load(a.osm)
    dep = json.loads(Path(a.depot_json).read_text())
    depot = dep["node"]
    stops = addresses(town, depot, a.stops, a.seed)
    to_ll = pyproj.Transformer.from_crs(town.crs, "EPSG:4326", always_xy=True)
    prob = {"depot": {"lon": dep["lon"], "lat": dep["lat"]},
            "clients": [dict(zip(("lon", "lat"), to_ll.transform(x, y)), name=f"{i + 1:02d}", demand=1)
                        for i, (x, y, _) in enumerate(stops)],
            "vehicles": {"count": 1, "capacity": a.stops}, "objective": "travel_time"}

    nodes = [depot] + [s[2] for s in stops]
    obj, dur, paths = vrp.cost_matrices(town.G, nodes, "travel_time")
    best = vrp.evaluate(prob, vrp.solve_pyvrp(prob, obj, dur, a.seconds)["routes"], obj, dur, paths)
    check = vrp.evaluate(prob, vrp.solve_ortools(prob, obj, dur, int(a.seconds))["routes"], obj, dur, paths)
    naive = vrp.evaluate(prob, [list(range(1, a.stops + 1))], obj, dur, paths)
    assert not best["violations"], best["violations"]
    t_best, t_naive, t_check = best["total_cost"], naive["total_cost"], check["total_cost"]
    saved = 1 - t_best / t_naive
    gap = t_check / t_best - 1

    fig, ax = P.figure(P.Plate(
        kicker="the same doors, a better order",
        label=f"MOLDE  —  ONE VAN  —  {a.stops} ADDRESSES  —  DRIVE TIME ON REAL ROADS",
        headline=[("THE", False), ("SHORTEST", False), ("LOOP", True)],
        sentence=(f"Give one van {a.stops} addresses and let a solver choose the order. Driven as they came in, "
                  f"the round takes {t_naive / 60:.0f} min at the wheel; in the solver's order, {t_best / 60:.0f} min: "
                  f"{saved:.0%} less driving for the same doors."),
        code="vrp_solve.solve_pyvrp(prob, obj, dur)   # cross-check: vrp_solve.solve_ortools",
        sources=(f"PyVRP (Wouda, Lan & Kool, INFORMS J. Computing 36, 2024); OR-Tools agrees within "
                 f"{max(abs(gap), 0.001):.1%}. "
                 f"Addresses: {a.stops} OSM buildings drawn at random (seed {a.seed}); driving time only, no "
                 "service time. " + B.OSM_CREDIT),
        number="04",
    ))
    G = town.G
    at = {i: (G.nodes[s[2]]["x"], G.nodes[s[2]]["y"]) for i, s in enumerate(stops, start=1)}   # where the van stops
    dx, dy = G.nodes[depot]["x"], G.nodes[depot]["y"]
    legs = path_lines(town, best["routes"][0]["node_path"])
    xs = np.concatenate([xy[:, 0] for xy in legs])
    B.frame(ax, town, focus=[LineString(xy) for xy in legs], width=xs.max() - xs.min() + 2 * MARGIN,
            shift_n=FRAME_SHIFT_N)
    B.context(ax, town, water_y=0.12)
    B.network(ax, town.segs, np.zeros(len(town.segs)), base=0.4, gain=0)
    for xy in legs:
        ax.plot(*xy.T, color=P.ACCENT, lw=5, alpha=0.15, solid_capstyle="round", zorder=4)
        ax.plot(*xy.T, color=P.ACCENT, lw=1.3, solid_capstyle="round", zorder=4.1)
    order = [int(s["name"]) for s in best["routes"][0]["stops"]]
    for k, i in enumerate(order, start=1):
        x, y = at[i]
        ax.scatter([x], [y], s=46, color=P.INK, edgecolors=P.PAPER, linewidths=0.8, zorder=5)
        ax.text(x, y, str(k), color=P.PAPER, size=4.6, ha="center", va="center", fontfamily=P.SANS, zorder=6,
                clip_on=True)
    B.mark(ax, (dx, dy), size=9)
    B.callout(ax, (dx, dy), "DEPOT  ·  STOPS NUMBERED IN DRIVING ORDER",
              f"{t_best / 60:.0f} min instead of {t_naive / 60:.0f}", CALLOUT)
    B.apparatus(ax)

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    P.save(fig, a.out)
    print(f"{a.out}: pyvrp {t_best:.0f} s, ortools {t_check:.0f} s ({gap:+.2%}), as received {t_naive:.0f} s "
          f"-> {saved:.1%} less")


if __name__ == "__main__":
    main()
