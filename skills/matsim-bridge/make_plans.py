#!/usr/bin/env python3
"""The static benchmark's synthetic OD demand -> MATSim plans.xml (+ scenario_meta.json for compare_kpis.py).

    python make_plans.py --town molde --agents 1000 --out scenario/molde/plans.xml

* Demand: fidelity_benchmark.make_trips (gravity-style, P(dest) ~ exp(-d/3 km) between the 2,500 real OSM building
  centroids in towns.json), numpy default_rng(2026). All 4,000 benchmark trips are generated and the FIRST --agents
  are used, so agent "a<k>" is exactly benchmark trip k (same origin, same destination) and --agents 4000 reproduces
  the complete static OD set.
* Each agent: home (end_time = departure) -> car leg -> work (open-ended). Home / work coordinates are the building
  centroids (EPSG:32632 metres); MATSim snaps them to the nearest network link.
* Departure times: uniform over the morning peak (default 07:00-09:00), drawn from default_rng(SEED + 1), independent
  of the OD draw.
* scenario_meta.json records, per agent, the benchmark trip index, o/d building indices, departure time and the
  building-to-node connector time (computed exactly as in the static engine B), so the comparison needs no guessing.
* Sanity check: the zonal engine is re-run on the regenerated trips and must reproduce the saved
  evidence/fidelity-benchmark/per_trip_times.npz, which proves the OD set is the benchmark's.
"""
import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

import common as C


def check_reproduces_benchmark(town, town_data, o_all, d_all, pts):
    """Return True/False/None: does the regenerated OD set reproduce the saved static-benchmark skims?"""
    npz = C.BENCH_DIR / "per_trip_times.npz"
    if not npz.exists():
        return None
    z = np.load(npz)
    zid = C.fb.zone_ids(pts, town_data["bbox"], 1000.0)
    tA, _, _ = C.fb.engine_a(pts, o_all, d_all, zid, C.fb.ZONE_SPEED[town])
    return bool(np.allclose(tA, z[f"{town}_tA"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--town", choices=C.TOWN_NAMES, default="molde")
    ap.add_argument("--agents", type=int, default=1000, help=f"number of agents, 1..{C.N_TRIPS_FULL} (default 1000)")
    ap.add_argument("--peak-start", default="07:00", help="peak start HH:MM")
    ap.add_argument("--peak-end", default="09:00", help="peak end HH:MM")
    ap.add_argument("--sample-share", type=float, default=1.0,
                    help="recorded in scenario_meta.json only; make_config.py applies it as flow/storage capacity factor")
    ap.add_argument("--out", type=Path, default=None, help="default: scenario/<town>/plans.xml next to this script")
    a = ap.parse_args()
    if not 1 <= a.agents <= C.N_TRIPS_FULL:
        raise SystemExit(f"--agents must be in 1..{C.N_TRIPS_FULL}")
    out = a.out or C.HERE / "scenario" / a.town / "plans.xml"

    town_data = C.load_town(a.town)
    pts, o, d, o_all, d_all = C.static_trips(town_data, a.agents)
    reproduces = check_reproduces_benchmark(a.town, town_data, o_all, d_all, pts)

    # building -> nearest network node connector time, exactly as fidelity_benchmark.engine_b
    G = C.build_graph(town_data)
    nodes = np.array(list(G.nodes), float)
    dist, _ = cKDTree(nodes).query(pts)
    conn_min = dist / (C.fb.V_CONN / 3.6) / 60.0

    h = lambda s: int(s[:2]) * 3600 + int(s[3:5]) * 60
    t0, t1 = h(a.peak_start), h(a.peak_end)
    dep = np.random.default_rng(C.SEED + 1).uniform(t0, t1, a.agents).round().astype(int)

    plans = ET.Element("plans")
    for k in range(a.agents):
        p = ET.SubElement(plans, "person", id=f"a{k}")
        pl = ET.SubElement(p, "plan", selected="yes")
        ET.SubElement(pl, "act", type="home", x=str(int(pts[o[k], 0])), y=str(int(pts[o[k], 1])), end_time=C.hhmmss(dep[k]))
        ET.SubElement(pl, "leg", mode="car")
        ET.SubElement(pl, "act", type="work", x=str(int(pts[d[k], 0])), y=str(int(pts[d[k], 1])))
    out.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(plans)
    out.write_text('<?xml version="1.0" encoding="utf-8"?>\n'
                   '<!DOCTYPE plans SYSTEM "http://www.matsim.org/files/dtd/plans_v4.dtd">\n'
                   + ET.tostring(plans, encoding="unicode") + "\n")

    meta = {"town": a.town, "crs": C.CRS, "seed": C.SEED, "agents": a.agents, "sample_share": a.sample_share,
            "peak": [a.peak_start, a.peak_end], "demand_reproduces_static_benchmark": reproduces,
            "agent_id_format": "a<k> = trip k of the static benchmark",
            "trip_index": list(range(a.agents)), "o": o.tolist(), "d": d.tolist(), "dep_s": dep.tolist(),
            "connector_min_o": conn_min[o].round(4).tolist(), "connector_min_d": conn_min[d].round(4).tolist(),
            "terminal_min": C.fb.TERMINAL_MIN}
    (out.parent / "scenario_meta.json").write_text(json.dumps(meta))
    print(f"{a.town}: {a.agents} agents, departures {a.peak_start}-{a.peak_end}, "
          f"OD reproduces static benchmark: {reproduces} -> {out}")


if __name__ == "__main__":
    main()
