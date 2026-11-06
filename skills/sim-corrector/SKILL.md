---
name: sim-corrector
description: Gatekeeper of the sim studio - checks every simulation before anything is drawn or posted. Validates the trajectory contract (time order, speed limits, teleports, moving while loading, capacity, sea legs crossing land), re-checks the solver plan independently, and compares measured KPIs with the paper's reported values within tolerance. Use after any solve or replay, when results look wrong, or before a scene, video or post is built.
---

# sim-corrector

Code: `studio/contract.py` (`validate`, `kpis`, `compare_to_paper`). Tests: `tests/test_studio.py`.

## Gates, in order: stop at the first failure and report it
1. **Plan**: the solver's plan, re-evaluated outside the solver: every client served once, capacity,
   time windows, route length. Use `vrp-solve`'s independent re-evaluation pattern.
2. **Replay = plan**: replayed distance/duration equals the solver objective (`compare_to_paper` with
   the objective as the "reported" value, 1%). A gap means an index or unit bug, never "noise".
3. **Contract**: `validate(traj, agents, land=...)` returns `ok`. Land geometry from the world
   (`studio/worlds/`); aircraft are exempt from the land check.
4. **Reproduction**: `compare_to_paper(kpis(...), scenario.reported)`. All pass = "reproduction";
   any fail = say which KPI, by how much, and the likely cause (missing instance data, assumption, model
   difference). Do not tune parameters until the numbers match; that is fitting, not reproducing.

## Known traps (each has burnt us once)
- PyVRP 0.14: `ScheduledActivity.is_client` is a **method**: call it. A client's `idx` counts clients
  only: node = `idx + number_of_depots`. Getting either wrong produced a plan that looked plausible
  but overloaded a vessel and was 35% longer than the solver's objective.
- A baseline must be feasible too. "Order received" that ignores capacity flatters the optimiser.
- Distances: haversine in metres for checks; solver matrices must be built from the same geometry the
  replay sails (straight line vs sea lane), or gate 2 fails.

## Output
`report.json` beside the scenario: contract text, KPI table, gate results. `studio.scene.build_scene`
refuses an invalid report, so a failed gate cannot reach a video.
