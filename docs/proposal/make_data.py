#!/usr/bin/env python3
"""Numbers behind the proposal's figures 5-11 -> docs/proposal/study.json.

Re-runs the prototype ensemble of examples/transplan_study.py (same choice model, same 60 futures x
25 packages, 1,000 agents, seed 0) and keeps what the figures draw: every run's verdict, the CO2
trajectories of the no-policy reference and the most robust package, a self-interest acceptance proxy
per package, the public money each package moves, signposts, and one agent trace for the map.

    python docs/proposal/make_data.py            # ~3 min

Acceptance proxy (until A1 estimates acceptance from survey data): the share of commuters whose
commuting consumer surplus in 2030 is not lower than without the package in the same future.
It ignores purchase subsidies and how the package is financed, so it is a lower bound on support from
self-interest alone, not a forecast of a vote.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for p in ("abm-transport", "dmdu-explore"):
    sys.path.insert(0, str(ROOT / "skills" / p / "scripts"))
import abm  # noqa: E402
import dmdu  # noqa: E402

TARGET, N_AGENTS, ACCEPT_YEAR = 0.2, 1000, 2030


def two_threshold_box(X, y, min_coverage=0.7):
    """Exhaustive search for the densest box `a op1 t1 and b op2 t2` that holds >= min_coverage of the
    cases of interest. With 60 futures PRIM peels thin slices off many inputs; two thresholds read
    better and are re-tested on 10^4 futures in A3."""
    best = None
    cols = list(X.columns)
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            xa, xb = X[a].to_numpy(), X[b].to_numpy()
            for sa in (1, -1):
                for sb in (1, -1):
                    for ta in np.unique(xa):
                        ma = xa >= ta if sa > 0 else xa <= ta
                        for tb in np.unique(xb):
                            m = ma & (xb >= tb if sb > 0 else xb <= tb)
                            hit = int((m & y).sum())
                            if not m.any() or hit < min_coverage * y.sum():
                                continue
                            key = (hit / m.sum(), hit)
                            if best is None or key > best[0]:
                                best = (key, {a: (">=" if sa > 0 else "<=", float(ta)),
                                              b: (">=" if sb > 0 else "<=", float(tb))}, int(m.sum()), hit)
    (density, hit), box, inside, hit = best
    return {"box": box, "inside": inside, "hits": hit, "coverage": hit / int(y.sum()), "density": density,
            "base_rate": float(np.mean(y))}


def main():
    study = json.loads((ROOT / "docs/results/transplan_study.json").read_text())
    beta = study["dcm"]["beta"]
    exp = dmdu.explore(60, 24, N_AGENTS, seed=0, beta=beta)
    rob = dmdu.robustness(exp, TARGET)
    assert abs(rob["robustness"].max() - study["backcast"]["best_robustness"]) < 1e-9, "ensemble drifted"
    best = rob.index[0]

    U, L = list(abm.UNCERTAINTIES), list(abm.LEVERS)
    exp["future"] = exp.groupby("policy", observed=True).cumcount()
    runs, ref_cs = {}, {}
    for _, row in exp.sort_values("policy", key=lambda s: s != "no_policy").iterrows():
        r = abm.run({k: row[k] for k in L}, {k: row[k] for k in U}, beta=beta, n=N_AGENTS,
                    agent_cs_years=(ACCEPT_YEAR,))
        assert abs(r["co2_2050_rel"] - row["co2_2050_rel"]) < 1e-12
        f, cs = int(row["future"]), np.array(r["agent_cs"][ACCEPT_YEAR])
        if row["policy"] == "no_policy":
            ref_cs[f] = cs
        i30 = r["years"].index(2030)
        runs[(row["policy"], f)] = {
            "accept": float(np.mean(cs >= ref_cs[f] - 1e-9)),
            "co2": np.round(np.array(r["series"]["co2_t"]) / r["series"]["co2_t"][0], 3).tolist(),
            "ev30": r["series"]["ev_fleet_share"][i30], "car30": r["series"]["car_share"][i30],
            "co2_30": r["series"]["co2_t"][i30] / r["series"]["co2_t"][0],
            "meets": bool(r["co2_2050_rel"] <= TARGET),
            # public money per commuter per year, NOK, averaged 2025-2050: subsidies paid, tolls collected
            "sub": 1000 * float(np.mean(r["series"]["subsidy_knok_pc"])),
            "toll": 1000 * float(np.mean(r["series"]["toll_knok_pc"]))}

    pkgs = []
    for p, row in rob.iterrows():
        acc = [runs[(p, f)]["accept"] for f in range(60)]
        pkgs.append({"id": p, "robustness": round(float(row["robustness"]), 4),
                     "accept": round(float(np.median(acc)), 3),
                     "subsidy_nok": round(float(np.median([runs[(p, f)]["sub"] for f in range(60)]))),
                     "toll_nok_rev": round(float(np.median([runs[(p, f)]["toll"] for f in range(60)]))),
                     "co2_2050": round(float(row["co2_2050_rel"]), 3),
                     "levers": {k: round(float(row[k]), 3) for k in L},
                     "meets": [int(runs[(p, f)]["meets"]) for f in range(60)]})
    admissible = [q for q in pkgs if q["accept"] >= 0.5 and q["id"] != "no_policy"]
    best_adm = max(admissible, key=lambda q: q["robustness"])["id"] if admissible else None

    # signposts for the most robust package: which 2030 reading best separates futures that go on to
    # meet the 2050 target from those that do not (single threshold, maximum accuracy)
    sp = []
    ok = np.array([runs[(best, f)]["meets"] for f in range(60)])
    for key, label, below_bad in (("ev30", "EV share of the car fleet, 2030", True),
                                  ("car30", "car share of commutes, 2030", False),
                                  ("co2_30", "CO2 relative to 2025, in 2030", False)):
        x = np.array([runs[(best, f)][key] for f in range(60)])
        cands = np.unique(x)
        accs = [np.mean((x >= c) == ok) if below_bad else np.mean((x <= c) == ok) for c in cands]
        c = float(cands[int(np.argmax(accs))])
        flag = (x < c) if below_bad else (x > c)
        sp.append({"key": key, "label": label, "threshold": round(c, 3), "accuracy": round(float(max(accs)), 3),
                   "flags_failures": int((flag & ~ok).sum()), "failures": int((~ok).sum()),
                   "false_alarms": int((flag & ok).sum()), "values": np.round(x, 3).tolist(), "meets": ok.astype(int).tolist()})

    # one agent trace for the map: the best package in its median future
    co2b = np.array([runs[(best, f)]["co2"][-1] for f in range(60)])
    fmed = int(np.argsort(co2b)[len(co2b) // 2])
    row = exp[(exp["policy"] == best) & (exp["future"] == fmed)].iloc[0]
    tr = abm.run({k: row[k] for k in L}, {k: row[k] for k in U}, beta=beta, n=N_AGENTS, trace_years=(2025, 2050))["trace"]

    # hostile futures: no package in the set meets the target. What do they share? (PRIM, two inputs)
    M = np.array([q["meets"] for q in pkgs])
    hostile = M.sum(axis=0) == 0
    fut = exp[exp["policy"] == "no_policy"].sort_values("future")[U]
    hbox = two_threshold_box(fut, hostile)
    hpts = fut[list(hbox["box"])].round(5).values.tolist()

    d17 = exp[exp["policy"] == "P17"]
    out = {
        "note": "generated by docs/proposal/make_data.py; synthetic behaviour, illustrative parameters",
        "target": TARGET, "agents": N_AGENTS, "futures": 60, "packages": len(pkgs), "runs": len(exp),
        "best": best, "best_admissible": best_adm, "accept_year": ACCEPT_YEAR,
        "packages_list": pkgs,
        "traj": {"years": abm.YEARS.tolist(),
                 "no_policy": [runs[("no_policy", f)]["co2"] for f in range(60)],
                 best: [runs[(best, f)]["co2"] for f in range(60)],
                 **({best_adm: [runs[(best_adm, f)]["co2"] for f in range(60)]} if best_adm else {})},
        "milestones": study["backcast"]["milestones"],
        "signposts": sp,
        "discovery": {"policy": "P17", "box": study["scenario_discovery"]["P17"],
                      "points": [[round(float(a), 4), round(float(b), 5), int(c <= TARGET)]
                                 for a, b, c in zip(d17["fuel_price_growth"], d17["pop_growth"], d17["co2_2050_rel"])]},
        "u_names": U, "futures_u": fut.round(5).values.tolist(),
        "hostile": {"n": int(hostile.sum()), "box": hbox, "dims": list(hbox["box"]) if hbox else [],
                    "points": [r + [int(h)] for r, h in zip(hpts, hostile)]},
        "trace": {"future": fmed, "zone": tr["zone"], "mode25": tr["years"][2025]["mode"],
                  "mode50": tr["years"][2050]["mode"], "ev50": tr["years"][2050]["ev"]},
    }
    (ROOT / "docs/proposal/study.json").write_text(json.dumps(out, separators=(",", ":")))
    print("best", best, "best admissible", best_adm)
    for q in pkgs[:8]:
        print(q["id"], q["robustness"], q["accept"], q["subsidy_nok"], q["toll_nok_rev"], q["levers"])
    print("admissible", len(admissible), "of", len(pkgs) - 1)
    print("hostile futures", int(hostile.sum()), hbox)
    for s in sp:
        print({k: v for k, v in s.items() if k not in ("values", "meets")})


if __name__ == "__main__":
    main()
