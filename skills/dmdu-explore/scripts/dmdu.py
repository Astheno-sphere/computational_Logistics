#!/usr/bin/env python3
"""Decision making under deep uncertainty (DMDU) around the agent-based transport model.

Instead of predicting one future, run the ABM over many plausible futures (deep uncertainties,
including the transferability of the estimated choice model) and many candidate policy packages:

  explore      Latin hypercube over uncertainties x policy packages, with a no-policy reference
               (EMA Workbench perform_experiments)
  robustness   share of futures in which each package meets a 2050 target (satisficing robustness)
  discover     PRIM scenario discovery: which combinations of uncertainties make a package fail
  backcast     start from the 2050 target: PRIM in lever space says which policy settings it requires;
               trajectories of successful runs give interim milestones (2030, 2035, 2040)

    python dmdu.py --scenarios 60 --policies 24 --target 0.3 --out results/

Targets and all model numbers are illustrative; the method is the point.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "abm-transport", "scripts"))
import abm  # noqa: E402

OUTCOMES = ["co2_2050_rel", "co2_cum_kt", "car_share_2050", "ev_fleet_2050", "cs_2050_nok"]


def model(n_agents=1000, beta=None):
    """EMA model around the ABM. `beta`: choice-model parameters (e.g. dcm-estimate output)."""
    from functools import partial

    from ema_workbench import Constant, Model, RealParameter, ScalarOutcome
    m = Model("transport_abm", function=partial(abm.ema_function, beta=beta))
    m.uncertainties = [RealParameter(k, lo, hi) for k, (lo, hi, _) in abm.UNCERTAINTIES.items()]
    m.levers = [RealParameter(k, lo, hi) for k, (lo, hi, _) in abm.LEVERS.items()]
    m.outcomes = [ScalarOutcome(o) for o in OUTCOMES]
    m.constants = [Constant("n_agents", n_agents), Constant("seed", 0)]
    return m


def policy_packages(n, seed=0):
    """No-policy reference plus n Latin-hypercube packages over the levers."""
    from ema_workbench import Sample
    from scipy.stats import qmc
    names = list(abm.LEVERS)
    lo = np.array([abm.LEVERS[k][0] for k in names])
    hi = np.array([abm.LEVERS[k][1] for k in names])
    pts = qmc.scale(qmc.LatinHypercube(d=len(names), seed=seed).random(n), lo, hi)
    pols = [Sample("no_policy", **{k: abm.LEVERS[k][2] for k in names})]
    pols += [Sample("P%02d" % i, **dict(zip(names, map(float, row)))) for i, row in enumerate(pts)]
    return pols


def explore(n_scenarios=60, n_policies=24, n_agents=1000, seed=0, beta=None):
    from ema_workbench import perform_experiments
    # EMA Workbench 3.0 samplers take an explicit rng; without it the futures differ run to run
    exp, out = perform_experiments(model(n_agents, beta), scenarios=n_scenarios,
                                   policies=policy_packages(n_policies, seed), log_progress=False,
                                   uncertainty_sampling_kwargs={"rng": seed})
    exp = exp.copy()
    for k, v in out.items():
        exp[k] = v
    exp["policy"] = exp["policy"].astype(str)
    return exp


def robustness(exp, target=0.3):
    """Per package: share of futures with co2_2050_rel <= target, plus median outcomes."""
    exp = exp.assign(meets=exp["co2_2050_rel"] <= target)
    g = exp.groupby("policy", observed=True)
    table = g.agg(robustness=("meets", "mean"), co2_2050_rel=("co2_2050_rel", "median"),
                  co2_cum_kt=("co2_cum_kt", "median"), car_share_2050=("car_share_2050", "median"),
                  cs_2050_nok=("cs_2050_nok", "median"))
    levers = g[list(abm.LEVERS)].first()
    return table.join(levers).sort_values(["robustness", "cs_2050_nok"], ascending=[False, False])


def _prim(x, y, mass_min=0.05, max_dims=None, min_coverage=0.5):
    """PRIM box. With max_dims, choose the densest box on the peeling trajectory that restricts at most
    max_dims inputs and keeps at least min_coverage of the cases of interest (interpretable boxes are the
    point of scenario discovery); otherwise the last box with coverage >= 0.6."""
    from ema_workbench.analysis import prim
    p = prim.Prim(x.reset_index(drop=True), np.asarray(y), peel_alpha=0.05, mass_min=mass_min)
    box = p.find_box()
    if box is None:
        return None
    traj = box.peeling_trajectory
    if max_dims:
        ok = traj[(traj["res_dim"] <= max_dims) & (traj["coverage"] >= min_coverage)]
        i = int(ok["density"].idxmax()) if len(ok) else int(traj.index[0])
    else:
        ok = traj[traj["coverage"] >= 0.6]
        i = int(ok.index[-1]) if len(ok) else int(traj.index[0])
    lims = box.box_lims[i]
    restricted = {}
    for c in x.columns:
        lo, hi = float(lims[c].iloc[0]), float(lims[c].iloc[1])
        if lo > float(x[c].min()) + 1e-9 or hi < float(x[c].max()) - 1e-9:
            restricted[c] = (lo, hi)
    base = float(np.mean(y))
    return {"coverage": float(traj.loc[i, "coverage"]), "density": float(traj.loc[i, "density"]),
            "mass": float(traj.loc[i, "mass"]), "base_rate": base,
            "lift": float(traj.loc[i, "density"]) / base if base else float("nan"), "box": restricted}


def discover(exp, policy, target=0.3):
    """Scenario discovery: which futures make `policy` miss the target."""
    sub = exp[exp["policy"] == policy]
    return _prim(sub[list(abm.UNCERTAINTIES)], (sub["co2_2050_rel"] > target).to_numpy(), max_dims=2)


def backcast(exp, target=0.3, milestones=(2030, 2035, 2040), n_agents=1000, n_traj=40, beta=None):
    """From the 2050 target back to today: lever conditions that make success likely (PRIM over levers
    on all runs), the most robust package that satisfies them, and median interim emission milestones
    on that package's successful trajectories."""
    cond = _prim(exp[list(abm.LEVERS)], (exp["co2_2050_rel"] <= target).to_numpy(), max_dims=3)
    rob = robustness(exp, target)
    best = rob.index[0]
    runs = exp[(exp["policy"] == best) & (exp["co2_2050_rel"] <= target)].head(n_traj)
    trajs = []
    for _, row in runs.iterrows():
        r = abm.run({k: row[k] for k in abm.LEVERS}, {k: row[k] for k in abm.UNCERTAINTIES}, beta=beta, n=n_agents)
        trajs.append(np.array(r["series"]["co2_t"]) / r["series"]["co2_t"][0])
    years = abm.YEARS
    ms = {}
    if trajs:
        T = np.vstack(trajs)
        ms = {int(y): float(np.median(T[:, list(years).index(y)])) for y in milestones}
    return {"target_2050": target, "lever_conditions": cond, "best_package": best,
            "best_robustness": float(rob.loc[best, "robustness"]),
            "best_levers": {k: float(rob.loc[best, k]) for k in abm.LEVERS}, "milestones": ms}


def figures(exp, target, outdir, n_agents=1000, beta=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(outdir, exist_ok=True)
    rob = robustness(exp, target)
    paths = {}
    # 1. robustness vs welfare per package
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ref = rob.loc["no_policy"]
    other = rob.drop("no_policy")
    sc = ax.scatter(other["cs_2050_nok"] - ref["cs_2050_nok"], other["robustness"], c=other["toll_nok"],
                    cmap="viridis", s=36, edgecolor="k", linewidth=0.3)
    ax.scatter([0], [ref["robustness"]], marker="x", color="crimson", s=60, label="no policy")
    ax.set_xlabel("Change in consumer surplus vs no policy, 2050 (NOK per commuter-trip)")
    ax.set_ylabel("Robustness: share of futures meeting target")
    ax.set_title("Policy packages under deep uncertainty (target: 2050 CO$_2$ <= %d%% of 2025)" % round(100 * target), fontsize=9)
    fig.colorbar(sc, label="Road toll (NOK/trip)")
    ax.legend(fontsize=8, loc="lower left")
    fig.tight_layout()
    paths["robustness"] = os.path.join(outdir, "robustness_tradeoff.png")
    fig.savefig(paths["robustness"], dpi=160)
    plt.close(fig)
    # 2. fan chart: CO2 trajectories, no policy vs most robust package
    best = rob.index[0]
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    for pol, colour in (("no_policy", "0.45"), (best, "tab:green")):
        rows = exp[exp["policy"] == pol].head(40)
        T = np.vstack([np.array(abm.run({k: r[k] for k in abm.LEVERS}, {k: r[k] for k in abm.UNCERTAINTIES},
                                         beta=beta, n=n_agents)["series"]["co2_t"]) for _, r in rows.iterrows()])
        T = T / T[:, :1]
        q = np.percentile(T, [10, 50, 90], axis=0)
        ax.fill_between(abm.YEARS, q[0], q[2], color=colour, alpha=0.25, linewidth=0)
        ax.plot(abm.YEARS, q[1], color=colour, label="%s (median, 10-90%%)" % ("no policy" if pol == "no_policy" else "package " + pol))
    ax.axhline(target, color="crimson", linestyle="--", linewidth=1, label="2050 target")
    ax.set_ylabel("Commute CO$_2$ relative to 2025")
    ax.set_xlim(2025, 2050)
    ax.legend(fontsize=8)
    ax.set_title("Emission pathways across futures", fontsize=9)
    fig.tight_layout()
    paths["pathways"] = os.path.join(outdir, "co2_pathways.png")
    fig.savefig(paths["pathways"], dpi=160)
    plt.close(fig)
    # 3. scenario discovery: the package whose failures are best explained by at most two uncertainties
    cands = [p for p in rob.index if 0.25 <= rob.loc[p, "robustness"] <= 0.75]
    found = [(p, discover(exp, p, target)) for p in cands]
    found = [(p, d) for p, d in found if d and d["box"]]
    if found:
        pol, d = max(found, key=lambda pd_: pd_[1]["lift"])
        dims = (list(d["box"]) + [c for c in ("ev_parity_year", "fuel_price_growth") if c not in d["box"]])[:2]
        sub = exp[exp["policy"] == pol]
        bad = sub["co2_2050_rel"] > target
        fig, ax = plt.subplots(figsize=(5.8, 4.3))
        ax.scatter(sub.loc[~bad, dims[0]], sub.loc[~bad, dims[1]], s=16, color="tab:blue", label="meets target")
        ax.scatter(sub.loc[bad, dims[0]], sub.loc[bad, dims[1]], s=16, color="tab:red", label="misses target")
        b0 = d["box"].get(dims[0], (sub[dims[0]].min(), sub[dims[0]].max()))
        b1 = d["box"].get(dims[1], (sub[dims[1]].min(), sub[dims[1]].max()))
        ax.add_patch(plt.Rectangle((b0[0], b1[0]), b0[1] - b0[0], b1[1] - b1[0], fill=False, lw=1.5, ec="k"))
        ax.set_xlabel(dims[0])
        ax.set_ylabel(dims[1])
        ax.set_title("Scenario discovery (PRIM), package %s\ncoverage %.2f, density %.2f, lift %.1f over base rate %.2f"
                     % (pol, d["coverage"], d["density"], d["lift"], d["base_rate"]), fontsize=9)
        ax.legend(fontsize=8)
        fig.tight_layout()
        paths["discovery"] = os.path.join(outdir, "scenario_discovery.png")
        fig.savefig(paths["discovery"], dpi=160)
        plt.close(fig)
        paths["discovery_package"] = pol
    return paths


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenarios", type=int, default=60)
    ap.add_argument("--policies", type=int, default=24)
    ap.add_argument("--agents", type=int, default=1000)
    ap.add_argument("--target", type=float, default=0.3, help="2050 CO2 as a share of 2025")
    ap.add_argument("--out", default="results")
    a = ap.parse_args(argv)
    exp = explore(a.scenarios, a.policies, a.agents)
    os.makedirs(a.out, exist_ok=True)
    exp.to_csv(os.path.join(a.out, "experiments.csv"), index=False)
    rob = robustness(exp, a.target)
    rob.to_csv(os.path.join(a.out, "robustness.csv"))
    summary = {"runs": len(exp), "robustness_top5": rob.head(5).reset_index().to_dict("records"),
               "no_policy_robustness": float(rob.loc["no_policy", "robustness"]),
               "backcast": backcast(exp, a.target, n_agents=a.agents),
               "figures": figures(exp, a.target, a.out, a.agents)}
    with open(os.path.join(a.out, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=1, default=float)
    print(json.dumps(summary, indent=1, default=float))


if __name__ == "__main__":
    main()
