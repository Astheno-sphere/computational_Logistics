#!/usr/bin/env python3
"""Compare MATSim's dynamic car travel times with the zonal engine (and the static network benchmark).

    python compare_kpis.py scenario/molde/output            # a REAL MATSim output directory

Runs only against a real MATSim output directory (the one named by controller.outputDirectory, containing
output_trips.csv.gz and/or output_events.xml.gz). If it is absent the script says so and exits: it never invents or
estimates a number. The scenario directory (parent of the output dir, or --scenario) must hold scenario_meta.json
from make_plans.py.

KPIs are those of the static benchmark (evidence/fidelity-benchmark/fidelity_benchmark.py, `kpis`): mean car travel time
per OD cell = zone pair of the 1 km grid, cell MAPE and Pearson r over cells with >= 5 trips, per-trip MAPE, total
vehicle-minutes error. The reference ("truth") is now MATSim:

  zonal vs MATSim   engine A (abm.py skim)        against the MATSim car trips   <- the new dynamic number
  static vs MATSim  engine B (Dijkstra, free flow) against the MATSim car trips   <- how much congestion/dynamics add
  zonal vs static   the original benchmark, restricted to the same agents (no MATSim involved; for the 3-layer view)

MATSim door-to-door time of agent a<k> = in-vehicle trip time + the benchmark's building-to-node connector time at both
ends + the benchmark's 3 min terminal time, so the three layers share one definition.
Agents without a completed car trip (stuck / aborted) are excluded and counted; check the coverage line.
"""
import csv
import gzip
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MSG = "no MATSim output found; run run_matsim.sh first"


def find_output(d):
    trips, events = d / "output_trips.csv.gz", d / "output_events.xml.gz"
    return (trips if trips.exists() else None), (events if events.exists() else None)


def to_sec(v):
    v = str(v).strip()
    if ":" in v:
        h, m, s = v.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    return float(v)


def read_trips_csv(path):
    """person -> in-vehicle seconds, car trips only (main_mode == car)."""
    out = {}
    with gzip.open(path, "rt", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if r.get("main_mode", "car") == "car" and re.fullmatch(r"a\d+", r["person"]):
                out[r["person"]] = to_sec(r["trav_time"])
    return out


def read_events(path):
    """person -> seconds between the car 'departure' and 'arrival' event (streamed; persons without arrival are dropped)."""
    dep, out = {}, {}
    with gzip.open(path, "rb") as f:
        for _, e in ET.iterparse(f, events=("end",)):
            if e.tag == "event":
                t, p = e.get("type"), e.get("person")
                if p and re.fullmatch(r"a\d+", p) and e.get("legMode") == "car":
                    if t == "departure":
                        dep[p] = float(e.get("time"))
                    elif t == "arrival" and p in dep:
                        out[p] = float(e.get("time")) - dep[p]
            e.clear()
    return out


def cell_kpis(fb, tA, tB, zo, zd, min_trips):
    """fidelity_benchmark.kpis, but returns None instead of crashing when too few cells exist."""
    import numpy as np
    key = zo.astype(np.int64) * 100000 + zd
    n = np.bincount(np.unique(key, return_inverse=True)[1])
    if (n >= min_trips).sum() < 3:
        return None
    k, _ = fb.kpis(tA, tB, zo, zd, min_trips=min_trips)
    return k


def fmt(k):
    if k is None:
        return "too few OD cells for the chosen --min-cell-trips"
    return (f"cell MAPE {k['cell_MAPE_pct']:.1f}%  r {k['cell_pearson_r']:.3f}  trip MAPE {k['trip_MAPE_pct']:.1f}%  "
            f"total-vehicle-min err {k['total_error_pct']:+.1f}%  cells {k['n_cells_ge_min']}  "
            f"mean {k['mean_time_A_min']:.2f} vs {k['mean_time_B_min']:.2f} min")


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("output_dir", type=Path, help="MATSim output directory (contains output_trips.csv.gz / output_events.xml.gz)")
    ap.add_argument("--scenario", type=Path, default=None, help="scenario dir with scenario_meta.json (default: parent of output_dir)")
    ap.add_argument("--min-cell-trips", type=int, default=5, help="minimum agents per zone-pair cell (benchmark: 5)")
    a = ap.parse_args()

    trips, events = find_output(a.output_dir) if a.output_dir.is_dir() else (None, None)
    if trips is None and events is None:
        print(MSG)
        sys.exit(2)
    scen = a.scenario or a.output_dir.resolve().parent
    if not (scen / "scenario_meta.json").exists():
        print(f"{scen / 'scenario_meta.json'} missing: run make_plans.py for this scenario")
        sys.exit(2)

    import numpy as np
    import common as C
    fb = C.fb
    meta = json.loads((scen / "scenario_meta.json").read_text())
    town, n = meta["town"], meta["agents"]
    if meta.get("demand_reproduces_static_benchmark") is not True:
        sys.exit("scenario OD set does not verifiably reproduce the static benchmark (per_trip_times.npz); refusing to compare")

    src = trips or events
    sec = read_trips_csv(trips) if trips else read_events(events)
    k_idx = np.array([k for k in range(n) if f"a{k}" in sec])
    tc_inveh = np.array([sec[f"a{k}"] for k in k_idx]) / 60.0
    cov = len(k_idx) / n
    print(f"{town}: read {src.name}; completed car trips {len(k_idx)}/{n} ({100 * cov:.1f}%), "
          f"capacity factor {meta.get('sample_share')}, iterations {meta.get('iterations')}")
    if cov < 0.95:
        print("WARNING: >5% of agents have no completed trip (stuck/aborted); results are biased toward uncongested trips")
    if len(k_idx) == 0:
        sys.exit("no completed trips in the MATSim output")

    z = np.load(C.BENCH_DIR / "per_trip_times.npz")
    tA, tB = z[f"{town}_tA"][k_idx], z[f"{town}_tB"][k_idx]
    zo, zd = z[f"{town}_zone_o"][k_idx], z[f"{town}_zone_d"][k_idx]
    conn = np.array(meta["connector_min_o"])[k_idx] + np.array(meta["connector_min_d"])[k_idx]
    tC = tc_inveh + conn + meta["terminal_min"]                       # door-to-door, same definition as A and B
    m = a.min_cell_trips
    res = {"town": town, "agents_planned": n, "agents_completed": int(len(k_idx)), "min_cell_trips": m,
           "capacity_factor": meta.get("sample_share"), "iterations": meta.get("iterations"), "source": src.name,
           "zonal_vs_matsim": cell_kpis(fb, tA, tC, zo, zd, m),
           "static_vs_matsim": cell_kpis(fb, tB, tC, zo, zd, m),
           "zonal_vs_static_same_agents": cell_kpis(fb, tA, tB, zo, zd, m),
           "mean_matsim_over_static_invehicle": float(tc_inveh.mean() / (tB - conn - meta["terminal_min"]).mean())}
    print(f"A = zonal engine, B = static Dijkstra, C = MATSim; >= {m} agents per zone-pair cell")
    for key, label in (("zonal_vs_matsim", "A vs C (dynamic cross-check)"), ("static_vs_matsim", "B vs C"),
                       ("zonal_vs_static_same_agents", "A vs B (original benchmark, same agents)")):
        print(f"  {label:44s} {fmt(res[key])}")
    print(f"  mean in-vehicle time, MATSim / static: {res['mean_matsim_over_static_invehicle']:.3f} "
          f"(>1 = congestion or MATSim 1 s link rounding; compare the capacity-factor 1.0 and 0.1 runs)")
    (scen / "dynamic_crosscheck.json").write_text(json.dumps(res, indent=1))
    print(f"wrote {scen / 'dynamic_crosscheck.json'}")


if __name__ == "__main__":
    main()
