#!/usr/bin/env python3
"""Run a logistics optimisation model from a JSON data file, AMPL-style (model + data + solver).

  python opt_cli.py transportation ../examples/transportation.json --solver all
  python opt_cli.py facility_location ../examples/facility_location.json --solver gurobi --export fl.lp
Data keys per model: transportation {supply, demand, cost}; facility_location {fixed, capacity,
demand, cost}; min_cost_flow {supply, arcs}; cvrp_exact {dist, demand, capacity, max_vehicles}.
Pair costs are written "i|j": value. --solver all solves with every available solver and checks
that the objectives agree.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models  # noqa: E402
import solvers  # noqa: E402

BUILD = {
    "transportation": (lambda d: models.transportation(d["supply"], d["demand"], _pairs(d["cost"])),
                       models.extract_transportation),
    "facility_location": (lambda d: models.facility_location(d["fixed"], d["capacity"], d["demand"], _pairs(d["cost"])),
                          models.extract_facility_location),
    "min_cost_flow": (lambda d: models.min_cost_flow(d["supply"], [tuple(a) for a in d["arcs"]]),
                      models.extract_min_cost_flow),
    "cvrp_exact": (lambda d: models.cvrp_exact(d["dist"], d["demand"], d["capacity"], d.get("max_vehicles")),
                   models.extract_cvrp),
}


def _pairs(d):
    return {tuple(k.split("|")): v for k, v in d.items()}


def run(kind, data, solver="auto", export=None, time_limit=None):
    build, extract = BUILD[kind]
    names = solvers.available() if solver == "all" else [solver]
    runs = []
    for s in names:
        m = build(data)
        if export and not runs:
            solvers.export(m, export)
        try:
            rep = solvers.solve(m, prefer=s, time_limit=time_limit)
        except RuntimeError as e:
            runs.append({"solver": s, "error": str(e)})
            continue
        runs.append({**rep, "solution": extract(m)})
    objs = [r["objective"] for r in runs if "objective" in r]
    agree = bool(objs) and max(objs) - min(objs) <= 1e-6 * max(1.0, abs(objs[0]))
    return {"model": kind, "runs": runs, "solvers_agree": agree}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model", choices=sorted(BUILD))
    ap.add_argument("data")
    ap.add_argument("--solver", default="auto", help="auto | all | " + " | ".join(solvers.PREFERENCE))
    ap.add_argument("--export", help="also write the model as .lp / .mps / .nl / .gms")
    ap.add_argument("--time-limit", type=float)
    a = ap.parse_args(argv)
    with open(a.data) as fh:
        data = json.load(fh)
    print(json.dumps(run(a.model, data, a.solver, a.export, a.time_limit), indent=1, default=str))


if __name__ == "__main__":
    main()
