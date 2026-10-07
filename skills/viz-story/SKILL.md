---
name: viz-story
description: Visual storytelling for the transport ABM and its ensembles - export a SimWrapper dashboard (CO2 pathway bands per policy package, robustness, mode shares, the futures table), a kepler.gl agent-flow map (every simulated commuter's home-to-work arc coloured by mode, 2025 vs 2050) and a Grasshopper pathway explorer (CO2 pathways as a data tree through Hops). Use to present results to planners, agencies, committees or the public.
---

# viz-story

`scripts/story.py` runs `abm-transport` for the study's policy packages across sampled futures and
writes three views of the same ensemble.

```bash
python skills/viz-story/scripts/story.py --out docs/story --futures 30 --agents 600   # about 10 s
```

| View | Output | How to open |
|---|---|---|
| SimWrapper dashboard | `docs/story/simwrapper/` (`dashboard-*.yaml` + CSVs) | `pip install simwrapper; simwrapper here` in that folder, or https://simwrapper.app/github/Astheno-sphere/computational_Logistics/docs/story/simwrapper |
| kepler.gl agent flows | `docs/story/kepler/agent-flows.html` (+ `.csv`, `.config.json` for kepler.gl/demo) | open in a browser; on the research atlas it is served by GitHub Pages |
| Grasshopper pathway explorer | Hops `/cl/pathways` + `grasshopper/pathway_explorer.py` | run `python servers/hops_app.py`; in Rhino 8 add a Hops component at `http://localhost:5000/cl/pathways` and a Python 3 Script component with the explorer code |

## Functions
| Function | Returns |
|---|---|
| `packages()` | no policy + the study's top packages with lever settings (`docs/results/transplan_study.json`) |
| `futures(n, seed)` | Latin-hypercube futures over the ABM's deep uncertainties |
| `run_pathways(packages, futures, n_agents)` | long table: package, future, year, CO2 relative to 2025, mode shares, EV share, success |
| `simwrapper(df, futures, outdir)` | dashboard YAML + CSVs; the most robust package |
| `agent_flows(levers, uncertainties, years)` | one row per agent and year: zone, mode, EV, home and work coordinates |
| `kepler_html(flows, path)` | self-contained kepler.gl 3.2 page (data inline; libraries from unpkg) |
| `pathway_tree(df, package)` | `{future}` -> CO2 per year, success flags: the Grasshopper tree |
| `pathway_polylines(...)` | the explorer's geometry in plain Python (tested twin of the Grasshopper script) |

## Notes
- Agents' per-year modes come from `abm.run(..., trace_years=...)`, drawn from each agent's choice
  probabilities with a separate random stream, so tracing never changes model results.
- Geography is illustrative: homes are placed around the zone's town centre at the agent's commute
  distance (Molde: north of the fjord), workplaces near the centre. Not a land-use model.
- Data are synthetic and parameters illustrative, as in `examples/transplan_study.py`.
