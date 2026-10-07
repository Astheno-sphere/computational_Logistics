#!/usr/bin/env python3
"""Logistics optimisation models in Pyomo, written AMPL-style: sets, parameters, variables,
constraints, objective, kept separate from the data (plain dicts / JSON) and from the solver.

  transportation(supply, demand, cost)                    LP: ship from sources to sinks at least cost
  facility_location(fixed, capacity, demand, cost)         MIP: which depots to open, who serves whom
  min_cost_flow(supply, arcs)                              LP: flows on a network with capacities
  cvrp_exact(dist, demand, capacity, max_vehicles)         MIP: exact vehicle routing (small n, MTZ)

Each model has an `extract(model)` partner that returns a plain dict. All solve with any solver via
solvers.solve(model, prefer="auto" | "highs" | "gurobi" | "cplex").
"""
import pyomo.environ as pyo


# ---- transportation -----------------------------------------------------------------------------
def transportation(supply, demand, cost):
    """supply: {source: units}, demand: {sink: units}, cost: {(source, sink): cost per unit}."""
    m = pyo.ConcreteModel("transportation")
    m.I, m.J = pyo.Set(initialize=list(supply)), pyo.Set(initialize=list(demand))
    m.s = pyo.Param(m.I, initialize=supply)
    m.d = pyo.Param(m.J, initialize=demand)
    m.c = pyo.Param(m.I, m.J, initialize=cost)
    m.x = pyo.Var(m.I, m.J, within=pyo.NonNegativeReals)
    m.supply = pyo.Constraint(m.I, rule=lambda m, i: sum(m.x[i, j] for j in m.J) <= m.s[i])
    m.demand = pyo.Constraint(m.J, rule=lambda m, j: sum(m.x[i, j] for i in m.I) >= m.d[j])
    m.cost = pyo.Objective(expr=sum(m.c[i, j] * m.x[i, j] for i in m.I for j in m.J))
    return m


def extract_transportation(m):
    return {"flows": {"%s->%s" % (i, j): round(pyo.value(m.x[i, j]), 6)
                      for i in m.I for j in m.J if pyo.value(m.x[i, j]) > 1e-9},
            "cost": pyo.value(m.cost)}


# ---- capacitated facility location, single sourcing ----------------------------------------------
def facility_location(fixed, capacity, demand, cost):
    """fixed: {site: opening cost}, capacity: {site: units}, demand: {client: units},
    cost: {(site, client): cost of serving the whole demand of client from site}."""
    m = pyo.ConcreteModel("facility_location")
    m.F, m.C = pyo.Set(initialize=list(fixed)), pyo.Set(initialize=list(demand))
    m.f = pyo.Param(m.F, initialize=fixed)
    m.cap = pyo.Param(m.F, initialize=capacity)
    m.d = pyo.Param(m.C, initialize=demand)
    m.c = pyo.Param(m.F, m.C, initialize=cost)
    m.open = pyo.Var(m.F, within=pyo.Binary)
    m.assign = pyo.Var(m.F, m.C, within=pyo.Binary)
    m.served = pyo.Constraint(m.C, rule=lambda m, j: sum(m.assign[i, j] for i in m.F) == 1)
    m.capacity = pyo.Constraint(m.F, rule=lambda m, i: sum(m.d[j] * m.assign[i, j] for j in m.C) <= m.cap[i] * m.open[i])
    # strengthening: never assign to a closed site (tightens the LP relaxation, same integer optimum)
    m.link = pyo.Constraint(m.F, m.C, rule=lambda m, i, j: m.assign[i, j] <= m.open[i])
    m.cost = pyo.Objective(expr=sum(m.f[i] * m.open[i] for i in m.F) +
                           sum(m.c[i, j] * m.assign[i, j] for i in m.F for j in m.C))
    return m


def extract_facility_location(m):
    opened = [i for i in m.F if pyo.value(m.open[i]) > 0.5]
    return {"open": opened, "assign": {j: next(i for i in m.F if pyo.value(m.assign[i, j]) > 0.5) for j in m.C},
            "cost": pyo.value(m.cost)}


# ---- minimum-cost flow ----------------------------------------------------------------------------
def min_cost_flow(supply, arcs):
    """supply: {node: net supply (>0 source, <0 sink, 0 transit)}, must sum to 0.
    arcs: [(u, v, cost per unit, capacity or None)]."""
    if abs(sum(supply.values())) > 1e-9:
        raise ValueError("supplies must balance (sum to zero)")
    m = pyo.ConcreteModel("min_cost_flow")
    m.N = pyo.Set(initialize=list(supply))
    m.A = pyo.Set(initialize=[(u, v) for u, v, _, _ in arcs], dimen=2)
    cost = {(u, v): c for u, v, c, _ in arcs}
    cap = {(u, v): k for u, v, _, k in arcs}
    m.x = pyo.Var(m.A, within=pyo.NonNegativeReals,
                  bounds=lambda m, u, v: (0, cap[(u, v)]))
    m.balance = pyo.Constraint(m.N, rule=lambda m, n: sum(m.x[a] for a in m.A if a[0] == n) -
                               sum(m.x[a] for a in m.A if a[1] == n) == supply[n])
    m.cost = pyo.Objective(expr=sum(cost[a] * m.x[a] for a in m.A))
    return m


def extract_min_cost_flow(m):
    return {"flows": {"%s->%s" % a: round(pyo.value(m.x[a]), 6) for a in m.A if pyo.value(m.x[a]) > 1e-9},
            "cost": pyo.value(m.cost)}


# ---- exact CVRP (two-index, Miller-Tucker-Zemlin load variables) ------------------------------------
def cvrp_exact(dist, demand, capacity, max_vehicles=None):
    """dist: square matrix, node 0 = depot. demand[0] = 0. Exact, so only for small instances
    (roughly n <= 15 on free editions; use vrp-solve beyond). Its value is as a proof of optimality
    for heuristic plans on small cases."""
    n = len(dist)
    N, C = range(n), range(1, n)
    m = pyo.ConcreteModel("cvrp_exact")
    m.A = pyo.Set(initialize=[(i, j) for i in N for j in N if i != j], dimen=2)
    m.x = pyo.Var(m.A, within=pyo.Binary)
    m.u = pyo.Var(C, bounds=lambda m, i: (demand[i], capacity))          # load after visiting i
    m.into = pyo.Constraint(C, rule=lambda m, j: sum(m.x[i, j] for i in N if i != j) == 1)
    m.out = pyo.Constraint(C, rule=lambda m, i: sum(m.x[i, j] for j in N if j != i) == 1)
    m.depot = pyo.Constraint(expr=sum(m.x[0, j] for j in C) == sum(m.x[j, 0] for j in C))
    if max_vehicles:
        m.fleet = pyo.Constraint(expr=sum(m.x[0, j] for j in C) <= max_vehicles)
    m.mtz = pyo.Constraint([(i, j) for i in C for j in C if i != j],
                           rule=lambda m, i, j: m.u[j] >= m.u[i] + demand[j] - capacity * (1 - m.x[i, j]))
    m.cost = pyo.Objective(expr=sum(dist[i][j] * m.x[i, j] for (i, j) in m.A))
    return m


def extract_cvrp(m):
    succ = {i: j for (i, j) in m.A if pyo.value(m.x[i, j]) > 0.5}
    routes = []
    for start in sorted(j for (i, j) in m.A if i == 0 and pyo.value(m.x[i, j]) > 0.5):
        r, k = [], start
        while k != 0:
            r.append(k)
            k = succ[k]
        routes.append(r)
    return {"routes": routes, "cost": pyo.value(m.cost)}
