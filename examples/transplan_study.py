#!/usr/bin/env python3
"""End-to-end demonstration of the research method proposed for TRANSPLAN-type questions:

  1. Discrete choice: simulate a stated-choice survey, estimate an MNL (Biogeme, cross-checked by an
     independent MLE).
  2. Agent-based model: commuters choose modes with the *estimated* utilities, buy EVs with peer effects,
     and face congestion, 2025-2050; mode constants calibrated to base-year shares.
  3. Deep uncertainty: an ensemble of futures x policy packages (EMA Workbench); robustness against a
     2050 target; PRIM scenario discovery; backcasting from the target to lever conditions and milestones.

Synthetic, illustrative data throughout. Output: docs/figures/*.png and docs/results/transplan_study.json.
Usage: python examples/transplan_study.py [--scenarios 60 --policies 24]
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ("skills/dcm-estimate/scripts", "skills/abm-transport/scripts", "skills/dmdu-explore/scripts"):
    sys.path.insert(0, os.path.join(ROOT, p))
import dcm  # noqa: E402
import dmdu  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=int, default=60)
    ap.add_argument("--policies", type=int, default=24)
    ap.add_argument("--agents", type=int, default=1000)
    ap.add_argument("--target", type=float, default=0.2)
    a = ap.parse_args()
    figdir, resdir = os.path.join(ROOT, "docs", "figures"), os.path.join(ROOT, "docs", "results")
    os.makedirs(resdir, exist_ok=True)

    sp = dcm.simulate(800, 8, seed=1)
    bio, mle = dcm.estimate_biogeme(sp), dcm.estimate_mle(sp)
    beta = bio["beta"]

    exp = dmdu.explore(a.scenarios, a.policies, a.agents, seed=0, beta=beta)
    rob = dmdu.robustness(exp, a.target)
    rob.round(4).to_csv(os.path.join(resdir, "robustness.csv"))
    bc = dmdu.backcast(exp, a.target, n_agents=a.agents, beta=beta)
    figs = dmdu.figures(exp, a.target, figdir, a.agents, beta=beta)
    summary = {
        "dcm": {k: {kk: bio[k][kk] for kk in dcm.PARAMS} for k in ("beta", "std_err")} | {
            "true": dcm.TRUE, "rho2": bio["rho2"], "value_of_time_nok_per_hour": bio["value_of_time_nok_per_hour"],
            "max_abs_diff_vs_independent_mle": max(abs(bio["beta"][p] - mle["beta"][p]) for p in dcm.PARAMS)},
        "ensemble": {"futures": a.scenarios, "packages": a.policies + 1, "runs": len(exp), "target_2050": a.target},
        "no_policy_robustness": float(rob.loc["no_policy", "robustness"]),
        "no_policy_median_co2_2050_rel": float(rob.loc["no_policy", "co2_2050_rel"]),
        "top_packages": rob.head(5).round(3).reset_index().to_dict("records"),
        "scenario_discovery": {p: dmdu.discover(exp, p, a.target)
                               for p in ["no_policy"] + ([figs["discovery_package"]] if "discovery_package" in figs else [])},
        "backcast": bc,
        "figures": {k: os.path.relpath(v, ROOT) for k, v in figs.items() if k != "discovery_package"},
    }
    with open(os.path.join(resdir, "transplan_study.json"), "w") as fh:
        json.dump(summary, fh, indent=1, default=float)
    print(json.dumps(summary, indent=1, default=float))


if __name__ == "__main__":
    main()
