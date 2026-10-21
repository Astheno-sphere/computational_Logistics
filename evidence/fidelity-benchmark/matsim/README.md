# Dynamic (MATSim) fidelity cross-check — Molde

Provenance: produced by a delegated run (MATSim 2024.0, Molde, 4,000 agents, 20 iterations, capacity factors 1.0 and 0.1), supplied as the two JSON summaries here. Verified by Arshad's main session for INTERNAL CONSISTENCY and agreement with the static benchmark (zonal-vs-static recomputed here = 16.39% MAPE, matches the independent evidence/fidelity-benchmark ~15%); NOT independently re-run. Raw MATSim outputs are not committed.

Headline (free flow, cf 1.0): zonal-vs-MATSim 19.0% MAPE, r 0.735; static-vs-MATSim 6.2% MAPE, r 0.999.
Congested (cf 0.1): free-flow engines break down (zonal-vs-MATSim 78% MAPE, r 0.16; MATSim ~21.9x static travel time) — the stated limit of a free-flow screening engine, hence pathways are re-checked on the network model.
