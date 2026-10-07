---
name: abm-transport
description: Agent-based transport model to 2050 driven by an estimated discrete choice model - car fleet turnover with EV adoption and peer effects, daily mode choice, congestion feedback, CO2 and consumer surplus, with policy levers (tolls, EV exemptions, transit, cycling, subsidies) and deep uncertainties. Use to simulate transport behaviour under policy scenarios and as the model inside scenario discovery and backcasting.
---

# abm-transport

`scripts/abm.py`: agents (commuters) in a synthetic two-town region inspired by Molde-Kristiansund.

## Mechanics, each year 2025-2050
1. **Fleet**: owners replace cars (1/lifetime); EV vs ICE by binary logit on purchase-price gap (parity
   year uncertain), subsidy, yearly running-cost saving (energy, toll exemption), peer effect, range concern.
2. **Mode choice**: own car, bus, bike with the MNL utilities from `dcm-estimate` (pass `beta=`), income
   heterogeneity in cost sensitivity, sample enumeration.
3. **Congestion**: BPR travel times per zone, car demand by the method of successive averages.
4. **Calibration**: mode constants adjusted so 2025 shares match `TARGET_SHARES_2025` (placeholders until
   replaced by RVU shares). Levers phase in 2026-2030.

Outcomes: mode shares, EV fleet share, car km, CO2, consumer surplus per year; scalars for exploration.

## Use
```python
from abm import run
r = run(levers={"toll_nok": 40, "ev_toll_share": 0.0}, uncertainties={"ev_parity_year": 2030}, beta=estimates)
```
`LEVERS` and `UNCERTAINTIES` hold names, ranges and defaults; `ema_function` is the EMA Workbench interface.

## Rules
- Every number in the model is illustrative and uncalibrated beyond base-year shares. Say so with results.
- Same seed, same answer: compare policies with common random numbers (the default).
- This is a compact research ABM for exploration (thousands of runs). For network-level detail the
  bank holds MATSim (link), ActivitySim, SUMO and Mesa.

## Tested (`tests/test_abm.py`)
Shares sum to one and match calibration targets; reproducible; no policy effect before policies start;
toll monotonically lowers car share; earlier EV parity lowers cumulative CO2; EV toll exemption raises EV
adoption; bike infrastructure raises cycling; EMA interface.
