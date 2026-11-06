---
name: paper-extract
description: Turn an operations-research paper (offshore supply vessel routing, ferry scheduling, helicopter crew transport, worker routing, any VRP/PDP/scheduling variant) into a studio scenario.yaml that the solver, simulator and corrector can run - problem class, objective, constraints, instance data, fleet, and the paper's reported results with tolerances. Use when the user names or attaches a paper to reproduce, simulate or visualise.
---

# paper-extract

First stage of the sim studio (`docs/SIM_STUDIO.md`). Output: `studio/papers/<id>/scenario.yaml`,
copied from `studio/papers/_template/scenario.yaml`, plus `notes.md`.

## Procedure
1. Get the paper (attached PDF, DOI, or open-access link). Record licence: only open-access (CC BY etc.)
   figures and instance data may be redistributed; otherwise keep numbers, cite, and link.
2. Classify the problem in standard terms: CVRP, VRPTW, PDPTW, multi-depot, multi-trip, heterogeneous
   fleet, split delivery, periodic, synchronisation, weather windows. Map each to the solver that can
   express it (`studio/TOOLS.md`, Solver layer). If no solver can, say so; do not approximate silently.
3. Fill every field of the template. Each value carries `src:` (page/table/equation) or
   `assumption: true` with a one-line reason. **Never invent a parameter to make the model run.**
4. Copy the paper's headline results into `reported:` with a tolerance: 1% for exact methods on the
   paper's own instance, 2-5% for metaheuristics, wider only with a stated reason.
5. List in `notes.md` what the paper does not give (instance files, speeds, service times) and how
   the scenario fills it: published benchmark, public data (Sodir, Kystverket), or assumption.

## Rules
- Units as in `cl-foundations`: seconds, metres, kWh; coordinates WGS84 lon/lat.
- A scenario with any `assumption: true` on a parameter that drives a `reported:` KPI can still run,
  but the narrator must say the result is a re-run under assumptions, not a reproduction.
- Hand off to `sim-corrector`; never straight to rendering.
