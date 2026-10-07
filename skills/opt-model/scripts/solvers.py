#!/usr/bin/env python3
"""Pick and run an optimisation solver through Pyomo, AMPL-style: the model is written once,
the solver is a choice.

Order of preference: Gurobi, CPLEX, HiGHS. Gurobi and CPLEX are commercial; their pip packages carry
free size-limited licenses (measured here: Gurobi up to 2,000 variables, CPLEX Community Edition up to
1,000 variables; above that they refuse the model). Full licenses are free for academic use through the
vendors' academic programmes. HiGHS is open source (MIT) with no size limit and is always the fallback.
"""
import time

import pyomo.environ as pyo

SOLVERS = {                     # our name -> Pyomo solver id
    "gurobi": "gurobi_direct",
    "cplex": "cplex_direct",
    "highs": "appsi_highs",
    "cbc": "cbc",
    "glpk": "glpk",
}
FREE_EDITION_VAR_LIMIT = {"gurobi": 2000, "cplex": 1000}
PREFERENCE = ["gurobi", "cplex", "highs", "cbc", "glpk"]


def available():
    out = []
    for name in PREFERENCE:
        try:
            if pyo.SolverFactory(SOLVERS[name]).available(exception_flag=False):
                out.append(name)
        except Exception:
            pass
    return out


def size(model):
    nv = sum(1 for _ in model.component_data_objects(pyo.Var, active=True))
    nc = sum(1 for _ in model.component_data_objects(pyo.Constraint, active=True))
    return nv, nc


def choose(model, prefer="auto"):
    """'auto' takes the first available solver whose free edition fits the model. Note that a full
    license lifts the limit, but we cannot see the license tier until a solve, so on a size failure
    `solve` retries with the next solver."""
    have = available()
    if prefer != "auto":
        if prefer not in have:
            raise RuntimeError("solver %r not available here; available: %s" % (prefer, have))
        return [prefer]
    nv, _ = size(model)
    fits = [s for s in have if nv <= FREE_EDITION_VAR_LIMIT.get(s, float("inf"))]
    return fits + [s for s in have if s not in fits]


def solve(model, prefer="auto", time_limit=None, mip_gap=None):
    """Solve and return a report. Tries solvers in order until one succeeds."""
    errors = {}
    for name in choose(model, prefer):
        opt = pyo.SolverFactory(SOLVERS[name])
        _options(opt, name, time_limit, mip_gap)
        t0 = time.time()
        try:
            res = opt.solve(model, load_solutions=False) if name != "highs" else opt.solve(model)
            tc = str(res.solver.termination_condition)
            if name != "highs":
                if tc not in ("optimal", "feasible", "maxTimeLimit"):
                    raise RuntimeError("termination: " + tc)
                model.solutions.load_from(res)
        except Exception as e:                       # size limit, license, infeasible, ...
            errors[name] = str(e).strip().splitlines()[-1][:200]
            continue
        nv, nc = size(model)
        obj = next(model.component_data_objects(pyo.Objective, active=True))
        return {"solver": name, "status": tc, "objective": pyo.value(obj), "seconds": round(time.time() - t0, 3),
                "variables": nv, "constraints": nc, "skipped": errors}
    raise RuntimeError("no solver succeeded: %s" % errors)


def _options(opt, name, time_limit, mip_gap):
    if time_limit:
        key = {"gurobi": "TimeLimit", "cplex": "timelimit", "highs": "time_limit"}.get(name)
        if key:
            opt.options[key] = time_limit
    if mip_gap is not None:
        key = {"gurobi": "MIPGap", "cplex": "mip_tolerances_mipgap", "highs": "mip_rel_gap"}.get(name)
        if key:
            opt.options[key] = mip_gap


def export(model, path):
    """Write the model in a standard file format, chosen by extension, so any solver can read it:
    .nl (AMPL solvers), .lp (CPLEX LP format, read by CPLEX, Gurobi, HiGHS), .mps, .gms (GAMS)."""
    if path.rsplit(".", 1)[-1] not in ("nl", "lp", "mps", "gms"):
        raise ValueError("export to .nl, .lp, .mps or .gms")
    model.write(path, io_options={"symbolic_solver_labels": True})   # format inferred from extension
    return path
