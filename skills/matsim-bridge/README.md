# matsim-bridge: export the Molde / Kristiansund assets to MATSim and cross-check the zonal engine dynamically

**Status: bridge code implemented and its XML output validated; MATSim has NOT been run on it. No dynamic result exists, and none is claimed.**

This is the future-work item named in [`../../evidence/fidelity/README.md`](../../evidence/fidelity/README.md), reduced to the part that can be built without running a simulator: converters from this repo's own data to a MATSim scenario, and a comparison script that reads a MATSim run and scores it with the static benchmark's KPIs. Run it locally (below) and it produces the number; until then the branch contains code, not evidence.

## What it adds, and what it does not

The static layer ([`../../evidence/fidelity-benchmark/`](../../evidence/fidelity-benchmark/README.md)) compares the zonal engine of `abm-transport` with free-flow shortest paths on the OSM-derived graph. This adds a **dynamic, congested** layer: MATSim's queue simulation of the same trips on the same graph, with route adaptation over iterations. Three layers, one KPI (car travel time per zone-pair cell): zonal (A), static network (B), MATSim (C).

**Honest scope.** Demand is still synthetic (the benchmark's gravity-style OD between OSM building centroids, not observed flows). One morning peak (07:00-09:00 departures), home-to-work trips, car only: no mode choice, no return trips, no time-of-day choice. The network is the simplified, undirected-then-doubled graph from `towns.json` with assumed speeds (major 50, minor 30 km/h) and **assumed** capacities and lanes (no lane or capacity data in the repo). The congestion level is set by the `--sample-share` assumption, not calibrated to counts. MATSim's reference is therefore another model, not observation. A close A-vs-C agreement would mean the zonal skim is consistent with a dynamic simulator on this stylised scenario; it would not validate the model against reality.

## Files

| File | Purpose |
|---|---|
| `common.py` | One definition of graph, speeds, capacities and demand, imported from / asserted against the static benchmark |
| `make_network.py` | `towns.json` -> `network.xml`: nodes in EPSG:32632, a link per direction, `freespeed` from `HWY_SPEEDS` by class, `capacity`/`permlanes` by class, `modes="car"` |
| `make_plans.py` | benchmark OD (seed 2026) -> `plans.xml` (`a<k>` = benchmark trip k) + `scenario_meta.json` |
| `make_config.py` | minimal standard `config.xml` (every non-default choice documented in its docstring) |
| `compare_kpis.py` | MATSim `output_trips.csv.gz` / `output_events.xml.gz` -> MAPE and Pearson r, A vs C, B vs C, A vs B on the same agents |
| `run_matsim.sh` | the end-to-end runbook below |

Conventions that keep the layers comparable: the same graph (largest connected component: Molde 2,753 nodes / 3,130 edges, identical to the benchmark), the first N of the benchmark's 4,000 trips (so N = 4000 reproduces the complete static OD set), MATSim door-to-door time = in-vehicle trip time + the benchmark's building-to-node connector time at both ends + its 3 min terminal time, zone pairs from the benchmark's 1 km grid, cells with at least 5 agents. With the default 1,000 agents there are far fewer qualifying cells than in the static benchmark; use `AGENTS=4000` for a like-for-like cell count.

## Requirements

Java 17 or newer for MATSim 2024.0 (the release is built with JDK 17). MATSim 2026.0 needs Java 21 and its config module names should be re-checked against that release's `examples/equil/config.xml`. Python 3.11+ with `pip install -r evidence/fidelity-benchmark/requirements.txt`. About 4 GB of heap for the town scenarios (`XMX=4g`, adjustable).

## Run it (local machine)

```bash
cd computational_logistics
git checkout matsim-bridge
pip install -r evidence/fidelity-benchmark/requirements.txt
bash skills/matsim-bridge/run_matsim.sh                      # Molde, 1000 agents, 20 iterations
# or: TOWN=kristiansund AGENTS=4000 bash skills/matsim-bridge/run_matsim.sh
```

What `run_matsim.sh` does, step by step (times are my estimates, not measurements, except the download size):

1. Java check (17+).
2. Download `matsim-2024.0-release.zip` from the GitHub release page (103 MB; I measured the size and SHA-256 when writing this, the script checks it) and unpack to `skills/matsim-bridge/work/`. Minutes, network-bound.
3. **Smoke test** on MATSim's bundled `examples/equil` scenario (`java -cp matsim-2024.0.jar org.matsim.run.RunMatsim config.xml`). Expect about a minute. Fix any Java problem here before going on.
4. For each capacity factor (default `1.0` and `0.1`): `make_network.py`, `make_plans.py`, `make_config.py` (seconds), then MATSim (20 iterations of 1,000 agents on a 6,260-link network: I expect a few minutes), then `compare_kpis.py`.
5. Results land in `skills/matsim-bridge/scenario/<town>_share<factor>/dynamic_crosscheck.json`, printed as A-vs-C, B-vs-C and A-vs-B rows. The `scenario/` and `work/` folders are git-ignored.

The two capacity factors are deliberate. Factor 1.0 puts 1,000 agents on a town network: nearly free-flow, so C-vs-B isolates what the MATSim representation changes (one-second time steps, link-by-link traversal rounding, nearest-link snapping of activities) and C-vs-A repeats the static comparison with a different engine. Factor 0.1 lets each agent stand for ten commuters (about 10,000 car commuters), so queues form and the ratio `mean MATSim / static in-vehicle time` shows what congestion adds. The 0.1 figure is an assumption about the size of the morning peak, not a calibrated value; report it as such, and consider a sweep (`SHARES="1.0 0.3 0.1 0.05"`).

Manual equivalent for one scenario:

```bash
cd skills/matsim-bridge
python3 make_network.py --town molde --out scenario/molde/network.xml
python3 make_plans.py   --town molde --agents 1000 --sample-share 0.1 --out scenario/molde/plans.xml
python3 make_config.py  --dir scenario/molde --iterations 20 --sample-share 0.1
(cd scenario/molde && java -Xmx4g -cp ../../work/matsim-2024.0/matsim-2024.0.jar org.matsim.run.RunMatsim config.xml)
python3 compare_kpis.py scenario/molde/output      # prints "no MATSim output found; run run_matsim.sh first" if absent
```

## Checks done without MATSim

Run on the sandbox that built this: `make_network.py --town molde` gives 2,753 nodes and 6,260 directed links (200.3 km; matches the benchmark's graph), `make_plans.py --town molde --agents 1000` gives 1,000 persons, both parse back with `xml.etree` and every link endpoint resolves to a node; the regenerated OD set reproduces the saved `per_trip_times.npz` zonal times exactly (`demand_reproduces_static_benchmark: true`); Kristiansund also builds. `compare_kpis.py` refuses to run without a MATSim output directory and was exercised on a synthetic stand-in file only to test the parsers (that file is not kept and produced no reported number). The `config.xml` module and parameter names (`controller`, `scoring`, `replanning`, `qsim.*`) follow the 2024.0 release's own `examples/equil/config.xml`, but the configuration itself has **not been loaded by MATSim**: if MATSim rejects a parameter, the error names it; fix it in `make_config.py`.

## Known limits to state when reporting

- MATSim has no intersection delay or turn restrictions here, and rounds link traversal to whole seconds, which can inflate times on this network of short links; the capacity-factor 1.0 run exposes that.
- Roads are bidirectional (towns.json has no one-way flag); capacities and lanes are class-level assumptions.
- Agents that get stuck are counted and excluded; `compare_kpis.py` warns below 95 % coverage.
- Single seed, single morning peak; no confidence interval is computed.
- MATSim 2024.0 download: the release zip downloaded and passed an integrity test in the build sandbox (103 MB, completed within the 90 s limit); MATSim itself was deliberately not executed there.
