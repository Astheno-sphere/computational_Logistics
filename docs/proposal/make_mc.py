#!/usr/bin/env python3
"""Monte Carlo check of the choice-model estimator -> docs/proposal/mc.json.

One synthetic survey recovering its parameters proves little; this repeats the survey R times with
fresh seeds (800 respondents x 8 tasks, the prototype design) and reports, per parameter, the mean
bias and how often the true value falls inside one and two estimated standard errors (expected about
68% and 95% if the estimator and its standard errors are right).

    python docs/proposal/make_mc.py --reps 50     # ~6 min
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "dcm-estimate" / "scripts"))
import dcm  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=50)
    a = ap.parse_args()
    est, se = {p: [] for p in dcm.PARAMS}, {p: [] for p in dcm.PARAMS}
    for r in range(a.reps):
        fit = dcm.estimate_mle(dcm.simulate(800, 8, seed=1000 + r))
        for p in dcm.PARAMS:
            est[p].append(fit["beta"][p])
            se[p].append(fit["std_err"][p])
    out = {"reps": a.reps, "design": "800 respondents x 8 tasks, MNL, synthetic", "params": {}}
    for p in dcm.PARAMS:
        b, s, t = np.array(est[p]), np.array(se[p]), dcm.TRUE[p]
        out["params"][p] = {"true": t, "mean_est": float(b.mean()), "rel_bias": float((b.mean() - t) / abs(t)),
                            "cover_1se": float(np.mean(np.abs(b - t) <= s)), "cover_2se": float(np.mean(np.abs(b - t) <= 2 * s)),
                            "sd_est": float(b.std(ddof=1)), "mean_se": float(s.mean())}
    (ROOT / "docs" / "proposal" / "mc.json").write_text(json.dumps(out, indent=1))
    for p, v in out["params"].items():
        print(p, {k: round(x, 4) for k, x in v.items()})


if __name__ == "__main__":
    main()
