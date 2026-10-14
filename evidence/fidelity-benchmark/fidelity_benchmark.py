#!/usr/bin/env python3
"""Two-engine fidelity benchmark: fast zonal engine (A) vs static network-assignment reference (B).

Towns: Molde and Kristiansund. Network: the repo's own OSM-derived road graph in docs/proposal/towns.json
(simplified street segments, UTM 32N metres, `major` flag). Demand: synthetic OD trips between the real OSM
building centroids stored in the same file. Both engines route the SAME trips. Free-flow, car only.

  Engine A (zonal):   trips aggregated to a square grid of zones; zone-to-zone time from centroid distance x
                      circuity / zone free speed (abm.py ZONES) + 3 min terminal time (abm.py car_time formula).
  Engine B (network): each trip is snapped to the graph and routed by NetworkX Dijkstra on travel time
                      (all-or-nothing static assignment, free flow).

Shared KPIs: (1) mean car travel time per OD cell (zone pair) and (2) total vehicle-minutes of the OD set.
Not a dynamic (MATSim/eqasim) benchmark. See README.md.
"""
import argparse
import json
import math
import platform
import sys
import time
from pathlib import Path

import networkx as nx
import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "skills/abm-transport/scripts"))
import abm  # noqa: E402  (zonal parameters: ZONES free speeds)

TOWNS = ROOT / "docs/proposal/towns.json"
# Assumptions (declared, not fitted): speeds by road class for the network engine (osm-network HWY_SPEEDS
# gives 50-60 km/h for primary-tertiary and 30 for residential), connector speed, circuity for the zonal engine.
V_MAJOR, V_MINOR, V_CONN = 50.0, 30.0, 30.0       # km/h
CIRCUITY = 1.30                                   # a-priori textbook detour factor, NOT fitted to B
TERMINAL_MIN = 3.0                                # same constant as abm._mode_choice car_time
ZONE_SPEED = {"molde": abm.ZONES["Molde"][3], "kristiansund": abm.ZONES["Kristiansund"][3]}  # km/h, abm.py
N_TRIPS, DECAY_M = 4000, 3000.0                   # synthetic gravity demand: P(dest) ~ exp(-d / DECAY_M)
MIN_CELL_TRIPS = 5


def build_graph(roads):
    """Undirected graph from segment endpoints (direction/one-way not stored in towns.json)."""
    G = nx.Graph()
    for maj, c, _share in roads:
        c = [tuple(p) for p in c]
        a, b = c[0], c[-1]
        if a == b:
            continue
        L = sum(math.dist(c[i], c[i + 1]) for i in range(len(c) - 1))
        v = V_MAJOR if maj else V_MINOR
        t = L / (v / 3.6)
        if not G.has_edge(a, b) or G[a][b]["t"] > t:
            G.add_edge(a, b, t=t, L=L)
    return G.subgraph(max(nx.connected_components(G), key=len)).copy()


def make_trips(pts, rng, n=N_TRIPS):
    o = rng.integers(0, len(pts), n)
    d = np.empty(n, int)
    for i, oi in enumerate(o):
        dist = np.hypot(*(pts - pts[oi]).T)
        dist[oi] = np.inf
        p = np.exp(-dist / DECAY_M)
        d[i] = rng.choice(len(pts), p=p / p.sum())
    return o, d


# ---------------------------------------------------------------- Engine B: network reference
def engine_b(G, pts, o, d):
    """Return per-trip car time in minutes (snapped OD, Dijkstra on travel time) and its runtime split."""
    t0 = time.perf_counter()
    nodes = list(G.nodes)
    xy = np.array(nodes, float)
    dist, idx = cKDTree(xy).query(pts)
    node_of = [nodes[i] for i in idx]
    conn_min = dist / (V_CONN / 3.6) / 60.0
    t_setup = time.perf_counter() - t0
    t0 = time.perf_counter()
    cache, out = {}, np.empty(len(o))
    for k, (oi, di) in enumerate(zip(o, d)):
        a, b = node_of[oi], node_of[di]
        if a not in cache:
            cache[a] = nx.single_source_dijkstra_path_length(G, a, weight="t")
        out[k] = cache[a][b] / 60.0 + conn_min[oi] + conn_min[di] + TERMINAL_MIN
    return out, t_setup, time.perf_counter() - t0


# ---------------------------------------------------------------- Engine A: zonal
def zone_ids(pts, bbox, size):
    gx = ((pts[:, 0] - bbox[0]) // size).astype(int)
    gy = ((pts[:, 1] - bbox[1]) // size).astype(int)
    return gx * 10000 + gy


def engine_a(pts, o, d, zid, speed_kmh, circuity=CIRCUITY):
    """Per-trip car time in minutes from the zone-to-zone skim (centroid distance based). Returns (times, runtime)."""
    t0 = time.perf_counter()
    zs, inv = np.unique(zid, return_inverse=True)
    cen = np.array([pts[inv == z].mean(axis=0) for z in range(len(zs))])        # building-weighted centroids
    dz = np.hypot(cen[:, None, 0] - cen[None, :, 0], cen[:, None, 1] - cen[None, :, 1])
    near = np.where(np.eye(len(zs), dtype=bool), np.inf, dz).min(axis=1)
    near = np.where(np.isfinite(near), near, 0.0)
    dz[np.diag_indices(len(zs))] = 0.5 * near                                   # intrazonal: half nearest-centroid distance
    skim = dz * circuity / 1000.0 / speed_kmh * 60.0 + TERMINAL_MIN             # minutes
    res = skim[inv[o], inv[d]]
    return res, time.perf_counter() - t0, inv


def kpis(tA, tB, zo, zd, min_trips=MIN_CELL_TRIPS):
    """Cell-level (zone pair) and total errors. Cell truth = mean of individual network trips in the cell."""
    key = zo.astype(np.int64) * 100000 + zd
    cells, inv = np.unique(key, return_inverse=True)
    n = np.bincount(inv)
    mB = np.bincount(inv, weights=tB) / n
    mA = np.bincount(inv, weights=tA) / n                                       # A is constant within a cell
    m = n >= min_trips
    w = n[m]
    ape = np.abs(mA[m] - mB[m]) / mB[m]
    r = float(np.corrcoef(mA[m], mB[m])[0, 1])
    # Spearman via ranks
    ra, rb = mA[m].argsort().argsort(), mB[m].argsort().argsort()
    rho = float(np.corrcoef(ra, rb)[0, 1])
    return {
        "n_cells_ge_min": int(m.sum()), "n_cells_all": int(len(cells)),
        "cell_MAPE_pct": float(100 * ape.mean()), "cell_MAPE_tripweighted_pct": float(100 * (ape * w).sum() / w.sum()),
        "cell_pearson_r": r, "cell_spearman_rho": rho,
        "cell_mean_bias_pct": float(100 * ((mA[m] - mB[m]) / mB[m]).mean()),
        "trip_MAPE_pct": float(100 * (np.abs(tA - tB) / tB).mean()),
        "total_vehicle_min_A": float(tA.sum()), "total_vehicle_min_B": float(tB.sum()),
        "total_error_pct": float(100 * (tA.sum() - tB.sum()) / tB.sum()),
        "mean_time_A_min": float(tA.mean()), "mean_time_B_min": float(tB.mean()),
    }, (mA[m], mB[m], n[m])


def calibrate_scale(tA, tB, idx):
    """Single scalar on the zonal travel part (excluding terminal time) fitted on trips `idx` (ratio of sums)."""
    return float(((tB[idx] - TERMINAL_MIN).sum()) / ((tA[idx] - TERMINAL_MIN).sum()))


def run_town(name, town, seed, zone_size, repeats):
    rng = np.random.default_rng(seed)
    pts = np.array(town["points"], float)
    G = build_graph(town["roads"])
    o, d = make_trips(pts, rng)
    tB, t_setup, t_route = engine_b(G, pts, o, d)
    out = {"town": name, "graph_nodes": G.number_of_nodes(), "graph_edges": G.number_of_edges(),
           "graph_km": float(sum(e["L"] for *_, e in G.edges(data=True)) / 1000), "n_trips": len(o),
           "n_origins_unique_buildings": int(len(np.unique(o))), "zonal_speed_kmh": ZONE_SPEED[name]}
    # primary: a-priori parameters (circuity 1.30, abm.py zone speed), zone size zone_size
    zid = zone_ids(pts, town["bbox"], zone_size)
    ts = []
    for _ in range(repeats):
        tA, t_a, inv = engine_a(pts, o, d, zid, ZONE_SPEED[name])
        ts.append(t_a)
    t_a = float(np.median(ts))
    k, cells = kpis(tA, tB, inv[o], inv[d])
    out["n_zones"] = int(inv.max() + 1)
    out["primary_apriori"] = k
    out["runtime_s"] = {"A_zonal_median": t_a, "A_repeats": repeats, "B_network_setup": t_setup, "B_network_routing": t_route,
                        "speed_ratio_routing_only": t_route / t_a, "speed_ratio_with_setup": (t_route + t_setup) / t_a}
    # calibrated variant: scalar fitted on a random half of trips, evaluated on the held-out half
    perm = rng.permutation(len(o)); tr, te = perm[: len(o) // 2], perm[len(o) // 2:]
    s = calibrate_scale(tA, tB, tr)
    tAc = (tA - TERMINAL_MIN) * s + TERMINAL_MIN
    kc, _ = kpis(tAc[te], tB[te], inv[o][te], inv[d][te], min_trips=2)
    ka, _ = kpis(tA[te], tB[te], inv[o][te], inv[d][te], min_trips=2)   # a-priori A on the SAME held-out half
    out["calibrated_heldout"] = {"scale_factor_fitted_on_train_half": s, "min_trips_per_cell": 2, **kc}
    out["apriori_on_same_heldout_half"] = {"min_trips_per_cell": 2, **ka}
    # sensitivity to zone size (a-priori parameters)
    sens = {}
    for size in (500, 1000, 2000, 3000):
        z = zone_ids(pts, town["bbox"], size)
        tAs, _, inv_s = engine_a(pts, o, d, z, ZONE_SPEED[name])
        ks, _ = kpis(tAs, tB, inv_s[o], inv_s[d])
        sens[str(size)] = {"n_zones": int(inv_s.max() + 1), **{x: ks[x] for x in ("cell_MAPE_pct", "cell_pearson_r", "trip_MAPE_pct", "total_error_pct", "n_cells_ge_min")}}
    out["zone_size_sensitivity_m"] = sens
    # bootstrap (over trips) of cell-level MAPE and r, primary configuration
    B = []
    for _ in range(300):
        i = rng.integers(0, len(o), len(o))
        try:
            kb, _ = kpis(tA[i], tB[i], inv[o][i], inv[d][i])
            B.append((kb["cell_MAPE_pct"], kb["cell_pearson_r"], kb["total_error_pct"]))
        except Exception:
            pass
    B = np.array(B)
    out["bootstrap_300_trip_resamples_95ci"] = {n: [float(np.percentile(B[:, j], 2.5)), float(np.percentile(B[:, j], 97.5))]
                                                 for j, n in enumerate(("cell_MAPE_pct", "cell_pearson_r", "total_error_pct"))}
    return out, (cells, tA, tB, inv[o], inv[d])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--zone-size", type=float, default=1000.0)
    ap.add_argument("--repeats", type=int, default=20)
    ap.add_argument("--out", default=str(HERE))
    a = ap.parse_args()
    towns = json.loads(TOWNS.read_text())
    res = {"meta": {"seed": a.seed, "primary_zone_size_m": a.zone_size, "circuity_apriori": CIRCUITY,
                    "speeds_kmh": {"major": V_MAJOR, "minor": V_MINOR, "connector": V_CONN}, "terminal_min": TERMINAL_MIN,
                    "demand": f"{N_TRIPS} synthetic OD trips between OSM building centroids, P(dest)~exp(-d/{DECAY_M:.0f} m)",
                    "min_cell_trips": MIN_CELL_TRIPS,
                    "versions": {"python": platform.python_version(), "networkx": nx.__version__, "numpy": np.__version__,
                                 "scipy": __import__("scipy").__version__}}, "towns": {}}
    raw = {}
    for name in ("molde", "kristiansund"):
        r, rawdata = run_town(name, towns[name], a.seed, a.zone_size, a.repeats)
        res["towns"][name] = r
        raw[name] = rawdata
        p = r["primary_apriori"]
        print(f"{name}: nodes={r['graph_nodes']} zones={r['n_zones']} cells>={MIN_CELL_TRIPS}:{p['n_cells_ge_min']} "
              f"cellMAPE={p['cell_MAPE_pct']:.1f}% r={p['cell_pearson_r']:.3f} tripMAPE={p['trip_MAPE_pct']:.1f}% "
              f"total_err={p['total_error_pct']:+.1f}% | calibrated held-out cellMAPE={r['calibrated_heldout']['cell_MAPE_pct']:.1f}% "
              f"r={r['calibrated_heldout']['cell_pearson_r']:.3f} (a-priori same half {r['apriori_on_same_heldout_half']['cell_MAPE_pct']:.1f}%) | speed x{r['runtime_s']['speed_ratio_routing_only']:.0f} "
              f"(A {r['runtime_s']['A_zonal_median']*1000:.2f} ms, B {r['runtime_s']['B_network_routing']:.1f} s)")
    out = Path(a.out)
    (out / "results.json").write_text(json.dumps(res, indent=1))
    import csv
    with open(out / "results_summary.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["town", "config", "cell_MAPE_pct", "cell_pearson_r", "cell_spearman_rho", "trip_MAPE_pct", "total_error_pct", "n_cells", "speed_ratio_routing_only"])
        for n, r in res["towns"].items():
            for cfg, k in (("apriori_1km", r["primary_apriori"]), ("apriori_heldout_half", r["apriori_on_same_heldout_half"]), ("calibrated_heldout_half", r["calibrated_heldout"])):
                w.writerow([n, cfg, f"{k['cell_MAPE_pct']:.2f}", f"{k['cell_pearson_r']:.4f}", f"{k['cell_spearman_rho']:.4f}",
                            f"{k['trip_MAPE_pct']:.2f}", f"{k['total_error_pct']:.2f}", k["n_cells_ge_min"], f"{r['runtime_s']['speed_ratio_routing_only']:.0f}"])
    np.savez(out / "per_trip_times.npz", **{f"{n}_{k}": v for n, (c, tA, tB, zo, zd) in raw.items() for k, v in (("tA", tA), ("tB", tB), ("zone_o", zo), ("zone_d", zd))})


if __name__ == "__main__":
    main()
