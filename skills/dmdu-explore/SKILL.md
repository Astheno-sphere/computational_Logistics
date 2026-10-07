---
name: dmdu-explore
description: Decision making under deep uncertainty for transport planning - run the agent-based model over an ensemble of futures and policy packages (EMA Workbench), measure robustness against a 2050 target, find the futures where policies fail (PRIM scenario discovery), and backcast from the target to required policy conditions and interim milestones. Use for scenario-based planning, robust policy design and backcasting.
---

# dmdu-explore

`scripts/dmdu.py` wraps `abm-transport` in EMA Workbench 3.0.

| Step | Function | Answers |
|---|---|---|
| Explore | `explore(n_scenarios, n_policies, beta=...)` | outcomes for every future x package (Latin hypercube; a no-policy reference) |
| Robustness | `robustness(exp, target)` | in what share of futures does each package reach the 2050 target? |
| Scenario discovery | `discover(exp, policy, target)` | which combinations of uncertainties make it fail? (PRIM box, coverage, density) |
| Backcasting | `backcast(exp, target)` | which lever settings success requires, the most robust package, and interim milestones |
| Figures | `figures(exp, target, outdir)` | robustness vs welfare, emission pathways fan chart, PRIM box |

```
python scripts/dmdu.py --scenarios 60 --policies 24 --target 0.2 --out results/
```

## Rules
- Uncertainties include the transferability of the estimated choice model (`cost_sens_scale`,
  `time_sens_scale`), so behavioural uncertainty is explored, not assumed away.
- EMA Workbench 3.0 API: policies are `Sample(name, **levers)` (formerly `Policy`); `prim.Prim(x, y,
  peel_alpha=..., mass_min=...)` (no `threshold` argument); EMA's LHS draws from numpy's global RNG, so
  `explore` seeds it.
- Report robustness with its target and ensemble size; a package robust in 60 futures is a hypothesis.

## Tested (`tests/test_dmdu.py`)
Reference and packages present; common futures across packages; robustness bounds; PRIM recovers a
planted region; backcast milestones fall over time.
