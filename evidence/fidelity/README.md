# Fidelity note: fast zonal engine vs network model

**Status: defined, not yet run. There is no fidelity number.**

The repository's agent-based model (`skills/abm-transport/scripts/abm.py`, driven by
`examples/transplan_study.py`) is the fast "zonal" engine: agents carry trip lengths, not routes, and
congestion is a BPR curve per zone solved by successive averages (see Limitations in the top-level README).
The repository contains no network-based model (MATSim, eqasim, SUMO or similar) and no script that runs
the same scenarios through both. A scalar percent error on key indicators (mode shares, car km, CO2)
therefore cannot be computed from code already present, and I have not produced or estimated one.

Running the benchmark requires: (1) a network model of the same Molde-Kristiansund study area (road graph
from `skills/osm-network`, synthetic population and plans, a MATSim or eqasim configuration); (2) the same
scenarios and demand assumptions fed to both engines; (3) agreed KPIs and an error definition fixed in
advance, for example percent difference in 2030 car km, car mode share and CO2 per commuter, per scenario,
plus rank agreement across policy packages. This is proposed work for the PhD, not completed work.
