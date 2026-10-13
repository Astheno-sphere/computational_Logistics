#!/usr/bin/env python3
"""Data for the proposal's motion plate -> docs/proposal/motion.json (about 2 s).

Re-runs the ABM for the median future of the most robust package and for no policy, tracing every
agent in every year, then keeps what the plate draws: per-agent state codes, home junctions on the
real OSM networks (towns.json), the 60-future CO2 fans (study.json) and compact road paths.

    python docs/proposal/make_motion.py

State code per agent and year: 0 petrol car, 1 electric car, 2 bus, 3 bike.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "skills" / "abm-transport" / "scripts"))
import abm  # noqa: E402

N_AGENTS = 1000


def road_paths(town, size=1000):
    """All roads as one SVG path string in a 0..size box (y up -> down), integer coordinates."""
    x0, y0, x1, y1 = town["bbox"]
    k = size / max(x1 - x0, y1 - y0)
    out = []
    for _maj, pts, _share in town["roads"]:
        out.append("M" + "L".join(f"{round((x - x0) * k)} {round((y1 - y) * k)}" for x, y in pts))
    return "".join(out), k


def main():
    study = json.loads((HERE / "study.json").read_text())
    towns = json.loads((HERE / "towns.json").read_text())
    beta = json.loads((ROOT / "docs" / "results" / "transplan_study.json").read_text())["dcm"]["beta"]
    best = study["best"]
    levers = next(p for p in study["packages_list"] if p["id"] == best)["levers"]
    unc = dict(zip(study["u_names"], study["futures_u"][study["trace"]["future"]]))
    years = [int(y) for y in abm.YEARS]
    states, zone = {}, None
    for name, lev in (("no_policy", {}), (best, levers)):
        r = abm.run(lev, unc, beta=beta, n=N_AGENTS, seed=0, trace_years=tuple(years))
        tr = r["trace"]
        zone = tr["zone"]
        cols = []
        for y in years:
            m, ev = np.array(tr["years"][y]["mode"]), np.array(tr["years"][y]["ev"], bool)
            cols.append(np.where(m == 0, np.where(ev, 1, 0), m + 1))   # mode 0 car, 1 bus, 2 bike
        states[name] = ["".join(str(int(c[i])) for c in cols) for i in range(N_AGENTS)]
    rng = np.random.default_rng(7)
    names = ["molde", "kristiansund"]
    home = []   # [town index, junction index] per agent; "Between" agents are split across the two towns
    for z in zone:
        t = names.index(z.lower()) if z.lower() in names else int(rng.integers(2))
        home.append([t, int(rng.integers(len(towns[names[t]]["points"])))])
    out = {"best": best, "years": years, "n": N_AGENTS, "target": study["target"], "home": home,
           "states": states, "fans": {k: study["traj"][k] for k in ("no_policy", best)}, "towns": []}
    for nm in names:
        t = towns[nm]
        path, k = road_paths(t)
        x0, y0, x1, y1 = t["bbox"]
        pts = [[round((x - x0) * k), round((y1 - y) * k)] for x, y in t["points"]]
        out["towns"].append({"name": nm, "w": round((x1 - x0) * k), "h": round((y1 - y0) * k), "span_m": round(1000 / k),
                             "path": path, "pts": pts})
    (HERE / "motion.json").write_text(json.dumps(out, separators=(",", ":")))
    print("motion.json", round((HERE / "motion.json").stat().st_size / 1e3), "kB;", best, "n =", N_AGENTS)


if __name__ == "__main__":
    main()
