# Fidelity note: fast zonal engine vs network model

**Status: static-network benchmark run; dynamic MATSim/eqasim cross-check not yet run.**

The static benchmark (zonal engine against NetworkX shortest-path assignment on the OSM-derived graphs of Molde
and Kristiansund, free flow, synthetic OD) is in [`../fidelity-benchmark/`](../fidelity-benchmark/README.md),
with scripts, measured errors and a plain statement of its limits.

**Remaining future work (not done): a dynamic network model.** The agent-based model
(`skills/abm-transport/scripts/abm.py`, driven by `examples/transplan_study.py`) still has no counterpart in a
dynamic simulator (MATSim, eqasim, SUMO). Running that comparison requires: (1) a MATSim or eqasim set-up for the
same Molde-Kristiansund study area (road graph from `skills/osm-network`, synthetic population and plans); (2) the
same scenarios and demand assumptions fed to both engines; (3) KPIs and an error definition fixed in advance, for
example percent difference in 2030 car km, car mode share and CO2 per commuter per scenario, plus rank agreement
across policy packages. This is proposed work for the PhD, not completed work, and no dynamic-fidelity number exists.
