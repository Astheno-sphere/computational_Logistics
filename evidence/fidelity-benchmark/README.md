# Fidelity benchmark: fast zonal engine vs static network assignment (Molde, Kristiansund)

*Prepared with AI assistance as part of proposal preparation. All numbers below were produced by the scripts in this folder (`run_log.txt`, `results.json`).*

## What this is, and what it is not

This benchmarks a **fast zonal engine** against a **static network-assignment reference** on the real OpenStreetMap-derived road graphs of Molde and Kristiansund, for the same synthetic OD demand. It is **not** a dynamic MATSim/eqasim benchmark: there is no time-of-day, no queueing, no agent plans, no mode choice and no congestion in either engine. A full dynamic cross-check remains future work; its preconditions are listed in `../fidelity/README.md`.

## Scenario

- **Network (engine B):** `docs/proposal/towns.json`, the repo's OSM-derived street segments in UTM 32N metres (simplified at 4 m and clipped to the town frame, with a `major` road flag). The raw OSM extracts are not committed (`data/osm/README.md`), so this simplified graph is the only OSM network in the repo. Largest connected component: Molde 2,753 nodes / 200 km; Kristiansund 2,954 nodes / 170 km. The file stores no one-way flags or speed limits, so the graph is undirected and speeds are assumed by road class: major 50 km/h, other 30 km/h, building-to-node connectors 30 km/h (`osm_network.py` urban defaults are 30-60 km/h).
- **Demand (same for both engines):** 4,000 synthetic car trips per town between the real OSM building centroids in `towns.json` (2,500 per town); destination probability proportional to exp(-d/3 km). Seed 2026. The demand is synthetic: the benchmark measures routing representation, not demand realism. There is no toll-station data in the repo, so no toll-crossing KPI.
- **Engine A (zonal):** trips aggregated to a square 1 km grid (Molde 29 zones, Kristiansund 21); building-weighted zone centroids; zone-to-zone car time = centroid distance x circuity 1.30 / zone free speed + 3 min terminal time. Free speeds (Molde 45, Kristiansund 40 km/h) and the +3 min constant are taken from `skills/abm-transport/scripts/abm.py` (`ZONES`, car-time formula). Intrazonal distance = half the distance to the nearest centroid. Circuity 1.30 is an a-priori textbook value, **not fitted to engine B**.
- **Engine B (network):** each trip snapped to the nearest graph node, routed by NetworkX Dijkstra on travel time (all-or-nothing, free flow), plus connector time and the same 3 min terminal time.

## KPIs

1. **Cell travel time:** mean car travel time per OD cell (zone pair), minutes. A gives one value per cell; B's value is the mean of the individual network trips in the cell. Errors computed over cells with at least 5 trips.
2. **Total vehicle-minutes** of the 4,000-trip OD set (signed relative error of A against B).

Per-trip MAPE (A's cell value against each trip's own network time) is also reported.

## Measured results (1 km zones, a-priori parameters)

| | Molde | Kristiansund |
|---|---|---|
| Cell MAPE | **16.4%** (95% CI 16.0-17.5) | **14.8%** (14.4-15.7) |
| Cell Pearson r / Spearman rho | **0.73** / 0.74 | **0.84** / 0.88 |
| Total vehicle-minutes error (A vs B) | -14.3% | -14.9% |
| Per-trip MAPE | 18.5% | 16.9% |
| Cells analysed (>=5 trips) | 223 | 199 |
| Mean car time A / B (min) | 6.25 / 7.30 | 6.08 / 7.15 |
| B routing runtime (4,000 trips) | 4.7 s | 5.1 s |
| A runtime (median of 20) | 0.59 ms | 0.52 ms |
| **Speed ratio B/A** | **~7,900x** | **~9,800x** |

Intervals are 300 bootstrap resamples over trips (they capture demand-sample noise only, not model-structure uncertainty). Speed ratio is routing/skim only: graph construction from `towns.json` is excluded from B and building the OD set is excluded from both; wall-clock on one CPU core, and A's sub-millisecond timing is noisy: three runs of the same code gave Molde 3,100-7,900x and Kristiansund 9,800-10,800x. Quote the order of magnitude (thousands of times faster), not the digit.

Further outputs in `results.json`:
- **Calibration on a held-out half:** one scalar fitted on a random half of trips (factor 1.31 Molde, 1.35 Kristiansund) removes the bias (total error -0.9% and +0.1% on the other half) but does **not** reduce cell MAPE (Molde 17.5% a-priori vs 20.6% calibrated; Kristiansund 15.3% vs 13.4%, same held-out half). The scatter is structural, not a scale problem.
- **Zone size (500 m / 1 / 2 / 3 km):** cell MAPE 15.8 / 16.4 / 17.2 / 13.6% in Molde and 12.5 / 14.8 / 14.1 / 13.5% in Kristiansund, while per-trip MAPE rises with zone size (Molde 17.3 / 18.5 / 21.4 / 23.8%). Cell-level MAPE is not monotone because coarse grids leave few cells with at least 5 trips (4-zone grids: 15 and 12 cells); the per-trip error is the cleaner indicator.

Figure: `fidelity_scatter.png` (zonal vs network cell time, y = x line). The largest misses are cells where the network detours around water (fjord inlets, bridge approaches) that centroid distance x a constant circuity cannot see.

## Reading

On this synthetic, free-flow, car-only OD set, a skim-based zonal engine reproduces the static-network travel time per zone pair to within roughly 15-16% mean absolute percentage error (correlation 0.73 in Molde, 0.84 in Kristiansund) and underestimates total vehicle-minutes by about 14-15%, at roughly three to four orders of magnitude less compute. Part of the bias reflects my assumed speeds (the zonal 45/40 km/h versus a 50/30 km/h road-class mix on the network), and a single fitted scalar removes the bias but not the scatter, which comes from geography (water, bridges) that the zonal abstraction ignores. These figures say nothing about congested conditions, mode choice, time-varying demand or one-way streets, and they compare two models I wrote with assumed speeds against each other, not against observed travel times or a dynamic simulator.

## Reviewer caveats

- Network is simplified and undirected, with assumed speeds; engine B's "truth" is itself a model.
- Demand is synthetic (gravity-style on building centroids); the 2,500 buildings per town are a random sample.
- Free-flow only; the BPR/MSA congestion of `abm.py` is not exercised here.
- One seed; the bootstrap does not cover re-drawing the demand.
- Both engines share the +3 min terminal time, which slightly compresses relative errors on short trips.

## Reproduce

```bash
pip install -r evidence/fidelity-benchmark/requirements.txt   # networkx 3.6.1, numpy 2.5.3, scipy 1.18.1, matplotlib 3.11.2 (Python 3.11+)
python evidence/fidelity-benchmark/fidelity_benchmark.py | tee evidence/fidelity-benchmark/run_log.txt   # ~12 s
python evidence/fidelity-benchmark/plot_results.py | tee -a evidence/fidelity-benchmark/run_log.txt
```

Files: `fidelity_benchmark.py`, `plot_results.py`, `results.json`, `results_summary.csv`, `per_trip_times.npz`, `fidelity_scatter.png`, `run_log.txt`, `requirements.txt`. Network geometry (c) OpenStreetMap contributors, ODbL.
