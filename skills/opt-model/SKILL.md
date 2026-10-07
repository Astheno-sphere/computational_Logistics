---
name: opt-model
description: AMPL-style optimisation modelling for logistics in Pyomo, solver-agnostic (Gurobi, CPLEX, HiGHS; CBC/GLPK if installed). Ready models for transportation, capacitated facility location, minimum-cost flow and exact small CVRP, plus export to .lp/.mps/.nl/.gms. Use for depot siting, allocation, network flows, proving a heuristic route plan optimal, or any LP/MIP.
---

# opt-model

Write the model once (sets, parameters, variables, constraints, objective), keep data in JSON, choose
the solver at run time: the AMPL way of working, in open-source Python (Pyomo).

## Solvers (measured in this environment)
| Solver | License | Limit |
|---|---|---|
| Gurobi (`gurobipy`) | commercial; pip edition free but size-limited; free full academic license | 2,000 variables on the free edition |
| CPLEX (`cplex`) | commercial; Community Edition free; free full academic license (IBM Academic Initiative) | 1,000 variables on Community Edition |
| HiGHS (`highspy`) | open source (MIT) | none; always the fallback |

`--solver auto` picks the first available solver whose free edition fits the model and falls through on a
license error. Every report says which solver produced it. AMPL itself (`amplpy`) needs an AMPL license
(Community Edition on registration); `--export model.nl` writes AMPL's format for any AMPL solver.

## Models (`scripts/models.py`)
- `transportation(supply, demand, cost)`: LP.
- `facility_location(fixed, capacity, demand, cost)`: open depots, single-source assignment (MIP).
- `min_cost_flow(supply, arcs)`: LP on a network with arc capacities.
- `cvrp_exact(dist, demand, capacity, max_vehicles)`: exact CVRP, MTZ load constraints; small n only.
Costs between places should come from `osm-network` (road distance, time or energy), not straight lines.

## Run
```
python scripts/opt_cli.py facility_location examples/facility_location.json --solver all
python scripts/opt_cli.py transportation examples/transportation.json --solver gurobi --export t.lp
```
`--solver all` solves with every available solver and reports `solvers_agree`.

## Rules
- Present results only when `solvers_agree` is true (or say why one solver could not run).
- Use `cvrp_exact` to certify `vrp-solve` plans on small instances; use `vrp-solve` for real sizes.
- OR-Tools (in vrp-solve) and `highspy` cannot load in one process; vrp-solve runs OR-Tools in a
  subprocess for that reason. Do not import `ortools` directly next to Pyomo/HiGHS.

## Tested (`tests/test_opt_model.py`)
Transportation hand optimum; facility location vs brute force; min-cost flow vs NetworkX; exact CVRP vs
brute force; exact MIP certifies the PyVRP plan on the Molde grid; solver choice respects free-edition
limits; all four export formats. Every model is solved by every available solver, which must agree.
