#!/usr/bin/env python3
"""Discrete choice models for travel behaviour: simulate a stated-choice experiment, estimate a
multinomial logit (MNL) with Biogeme, cross-check with an independent maximum-likelihood estimator,
and hand the estimated utilities (with their covariance) to the agent-based model.

Modes: car (ICE), ev, bus, bike. Attributes per alternative: in-vehicle/travel time [min], cost [NOK],
plus wait time [min] for bus. Utility, for person n and mode j:

    V_nj = ASC_j + b_time * time_nj + b_cost * cost_nj + b_wait * wait_nj      (ASC_car = 0)

Value of time (NOK/hour) = 60 * b_time / b_cost.

CLI:
    python dcm.py --simulate 800 --tasks 8 --out sp.csv      # synthetic stated-choice data
    python dcm.py --estimate sp.csv                          # Biogeme + scipy, side by side
"""
import argparse
import contextlib
import json
import os
import tempfile

import numpy as np
import pandas as pd

MODES = ["car", "ev", "bus", "bike"]
# Illustrative "true" parameters for simulation. Not estimates for any real population.
TRUE = {"ASC_ev": -0.8, "ASC_bus": 0.6, "ASC_bike": -0.4,
        "B_TIME": -0.06, "B_COST": -0.025, "B_WAIT": -0.09}
PARAMS = list(TRUE)


def simulate(n_resp=800, n_tasks=8, true=None, seed=0):
    """Stated-choice data in wide format: one row per choice task, with an attribute-level design
    drawn around a realistic Molde/Kristiansund commute (5-25 km)."""
    true = true or TRUE
    rng = np.random.default_rng(seed)
    n = n_resp * n_tasks
    dist = np.repeat(rng.uniform(5, 25, n_resp), n_tasks)                 # km, per respondent
    car_t = dist / rng.uniform(40, 60, n) * 60 + rng.uniform(2, 8, n)       # min incl. parking
    d = {
        "RESP": np.repeat(np.arange(n_resp), n_tasks),
        "DIST": dist,
        "TIME_car": car_t, "COST_car": dist * rng.uniform(2.0, 4.0, n) + rng.choice([0, 20, 40], n),  # fuel + toll
        "TIME_ev": car_t, "COST_ev": dist * rng.uniform(0.6, 1.4, n) + rng.choice([0, 10, 20], n),
        "TIME_bus": dist / rng.uniform(20, 35, n) * 60 + 5, "COST_bus": rng.choice([30, 40, 50], n),
        "WAIT_bus": rng.choice([5, 10, 15, 30], n),
        "TIME_bike": dist / rng.uniform(14, 22, n) * 60, "COST_bike": np.zeros(n),
    }
    df = pd.DataFrame(d)
    V = utilities(df, true)
    eps = rng.gumbel(size=V.shape)
    df["CHOICE"] = np.argmax(V + eps, axis=1) + 1          # 1..4, Biogeme convention
    return df


def utilities(df, b):
    """n x 4 matrix of systematic utilities for the four modes."""
    cols = []
    for m in MODES:
        v = b.get("ASC_" + m, 0.0) + b["B_TIME"] * df["TIME_" + m].to_numpy() + b["B_COST"] * df["COST_" + m].to_numpy()
        if m == "bus":
            v = v + b["B_WAIT"] * df["WAIT_bus"].to_numpy()
        cols.append(v)
    return np.column_stack(cols)


def probabilities(V):
    V = V - V.max(axis=1, keepdims=True)
    e = np.exp(V)
    return e / e.sum(axis=1, keepdims=True)


def logsum(V):
    """Expected maximum utility per row (for consumer surplus = logsum / -b_cost)."""
    m = V.max(axis=1)
    return m + np.log(np.exp(V - m[:, None]).sum(axis=1))


# ---- estimator 1: Biogeme ------------------------------------------------------------------------------
def estimate_biogeme(df):
    import biogeme.biogeme as bio
    from biogeme.database import Database
    from biogeme.expressions import Beta, Variable
    from biogeme.models import loglogit

    data = df[[c for c in df.columns if c != "RESP"]].copy()
    db = Database("stated_choice", data)
    b = {p: Beta(p, 0, None, None, 0) for p in PARAMS}
    V = {}
    for k, m in enumerate(MODES, start=1):
        v = b["B_TIME"] * Variable("TIME_" + m) + b["B_COST"] * Variable("COST_" + m)
        if m != "car":
            v = b["ASC_" + m] + v
        if m == "bus":
            v = v + b["B_WAIT"] * Variable("WAIT_bus")
        V[k] = v
    with tempfile.TemporaryDirectory() as tmp, contextlib.chdir(tmp):   # Biogeme writes files to cwd
        model = bio.BIOGEME(db, loglogit(V, None, Variable("CHOICE")), generate_html=False, generate_yaml=False)
        model.model_name = "mnl_mode_choice"
        r = model.estimate()
    beta = r.get_beta_values()
    # Biogeme 3.3: get_default_variance_covariance_matrix() returns the *type* (robust when the Hessian is
    # available), which get_variance_covariance_matrix() then computes; the same one behind std errors.
    cov = np.asarray(r.get_variance_covariance_matrix(r.get_default_variance_covariance_matrix()))
    idx = [r.get_parameter_index(p) for p in PARAMS]
    return _report("biogeme", {p: beta[p] for p in PARAMS}, {p: r.get_parameter_std_err(p) for p in PARAMS},
                   r.final_loglikelihood, len(df), cov[np.ix_(idx, idx)])


# ---- estimator 2: independent maximum likelihood (scipy) -------------------------------------------------
def estimate_mle(df):
    from scipy.optimize import minimize
    y = df["CHOICE"].to_numpy() - 1
    rows = np.arange(len(df))

    def nll(x):
        V = utilities(df, dict(zip(PARAMS, x)))
        V = V - V.max(axis=1, keepdims=True)
        return -(V[rows, y] - np.log(np.exp(V).sum(axis=1))).sum()

    res = minimize(nll, np.zeros(len(PARAMS)), method="BFGS", options={"gtol": 1e-7, "maxiter": 2000})
    hess = _numeric_hessian(nll, res.x)
    cov = np.linalg.inv(hess)
    se = np.sqrt(np.diag(cov))
    return _report("scipy-mle", dict(zip(PARAMS, res.x)), dict(zip(PARAMS, se)), -res.fun, len(df), cov)


def _numeric_hessian(f, x, h=1e-4):
    n = len(x)
    H = np.zeros((n, n))
    for i in range(n):
        for j in range(i, n):
            e_i, e_j = np.eye(n)[i] * h, np.eye(n)[j] * h
            H[i, j] = H[j, i] = (f(x + e_i + e_j) - f(x + e_i - e_j) - f(x - e_i + e_j) + f(x - e_i - e_j)) / (4 * h * h)
    return H


def _report(name, beta, se, ll, n, cov):
    ll0 = n * np.log(1 / len(MODES))
    return {"estimator": name, "beta": {k: float(v) for k, v in beta.items()},
            "std_err": {k: float(v) for k, v in se.items()},
            "t_stat": {k: float(beta[k] / se[k]) for k in beta},
            "loglik": float(ll), "rho2": float(1 - ll / ll0), "n_obs": int(n),
            "value_of_time_nok_per_hour": float(60 * beta["B_TIME"] / beta["B_COST"]),
            "cov": np.asarray(cov).tolist(), "param_order": PARAMS}


def draw_parameters(est, n, seed=0):
    """Sample parameter vectors from the estimates' asymptotic normal distribution, so behavioural
    (estimation) uncertainty can be carried into the ABM and the scenario analysis."""
    rng = np.random.default_rng(seed)
    mu = np.array([est["beta"][p] for p in PARAMS])
    return [dict(zip(PARAMS, x)) for x in rng.multivariate_normal(mu, np.array(est["cov"]), size=n)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--simulate", type=int, metavar="N_RESP")
    ap.add_argument("--tasks", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out")
    ap.add_argument("--estimate", metavar="CSV")
    a = ap.parse_args(argv)
    if a.simulate:
        df = simulate(a.simulate, a.tasks, seed=a.seed)
        df.to_csv(a.out or "stated_choice.csv", index=False)
        print("wrote", a.out or "stated_choice.csv", len(df), "choices")
    if a.estimate:
        df = pd.read_csv(a.estimate)
        out = [estimate_biogeme(df), estimate_mle(df)]
        for o in out:
            o.pop("cov")
        print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
