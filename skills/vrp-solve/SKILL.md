---
name: vrp-solve
description: Solve vehicle routing problems (capacity, time windows, service times, multiple vans) on the real road network from osm-network, minimising time, distance or energy, with PyVRP and OR-Tools as an independent cross-check. Use for delivery planning, fleet sizing or comparing routing objectives.
---

# vrp-solve

`scripts/vrp_solve.py` plans delivery routes using road-network costs, not straight lines.

## Input (`examples/deliveries.json`)
```json
{"depot": {"lon": 7.1592, "lat": 62.7375, "tw": [0, 7200]},
 "clients": [{"name": "Clinic", "lon": ..., "lat": ..., "demand": 2, "service_s": 120, "tw": [0, 2400]}],
 "vehicles": {"count": 3, "capacity": 8},
 "objective": "travel_time"}
```
Times are seconds from the start of the shift. `objective` is `travel_time`, `length` or `energy_kwh`.

## Run
```
python scripts/vrp_solve.py --osm grid_molde.osm --problem examples/deliveries.json --solver both
python scripts/vrp_solve.py --osm molde.osm --dem dem.tif --problem day1.json --paths   # node paths for rhino baking
```

## How it works
1. Snap every stop to its nearest graph node; refuse if two stops share one.
2. All-pairs road costs between stops (osm-network `route`), plus durations for time windows.
3. Solve with **PyVRP** (hybrid genetic search) and/or **OR-Tools** (guided local search).
4. **Re-evaluate** every plan from the true matrices, independent of the solver: capacity, each client
   served once, arrival vs window (waiting if early). Violations are reported, never hidden.

## Rules
- Run `--solver both` for anything you will present: two different algorithms agreeing is evidence.
- Energy legs can be negative (downhill). Solvers need non-negative arcs, so a constant is added per
  leg. That keeps rankings for a fixed number of legs but slightly favours fewer vans; the reported
  energy is always the true, unshifted value.
- Solvers are heuristics with a time limit. Small cases are checked against brute force in the tests.

## Tested (`tests/test_vrp_solve.py`)
Both solvers feasible and within 2% on the example (they currently agree exactly: 1,120 s, 3 vans),
capacity and single visits, 5-stop single-van case equals brute-force TSP, window violations surface.
