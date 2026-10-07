# Asthenosphere

**An open framework and toolkit for computational transport and logistics planning: skills, agents,
models and protocols assembled into one tested system, from travel behaviour to scenario analysis to
design and visual storytelling.**

**Author:** Arshad Akhtar Abbasia · Research portfolio · Test region: Molde and Kristiansund, Norway

> The asthenosphere is the slowly flowing layer beneath the Earth's rigid crust. Cities have one too:
> the flows of people, vehicles and goods beneath their visible form. This framework models that layer
> and makes it visible.

---

## What this is

Asthenosphere assembles the pieces a transport and logistics planner needs into one coherent toolkit:

- **Skills**: tested, documented modules for discrete choice estimation, agent-based simulation,
  scenario analysis under deep uncertainty, road networks, vehicle routing, optimisation and
  Grasshopper data trees.
- **Agents and protocols**: the skills are a Claude Code plugin, an MCP server any agent host can use,
  and Grasshopper components through Hops, all over one shared core.
- **Design and storytelling**: connections to Rhino, Grasshopper and GIS, following the parametric and
  environmental toolkit used in computational design practice, so results become drawings, maps and
  narratives.
- **Knowledge bank**: about 290 license-checked open-source references (code, books, MCP servers)
  catalogued so new skills are built on real, current APIs.

It works for any city or region: networks are built from OpenStreetMap by place name or file, in the
local projected coordinate system. Molde and Kristiansund are the test case.

## The system and the thesis

<p align="center"><img src="docs/diagrams/abm-thesis-system.png" alt="ABM system and thesis flow: five lanes (evidence, behaviour, simulation, decision under deep uncertainty, story and interfaces) across four thesis articles, each component tagged in repo, in bank or proposed" width="900"></p>

Five lanes across the four thesis articles (A1 behaviour, A2 coupled DCM and ABM, A3 exploration,
A4 backcasting). Estimated choice models drive the agents. Decision models (Jev) and LLM agents
(AgentSociety, GATSim, LLM agents in GAMA) stress-test them on policies the surveys never covered.
Network ABMs (MATSim, eqasim, BEAM, SUMO, GAMA) train surrogates, so thousands of futures stay
affordable. Results reach agencies as dashboards and as Grasshopper data trees. The diagram is typed
JSON checked by [Archify](https://github.com/tt-a1i/archify); anyone can edit it and re-run the
checks ([how](docs/diagrams/README.md)). Download the
[interactive version](docs/diagrams/workflow-abm-thesis-system-20261007-0450/abm-thesis-system.html)
to pan, zoom and trace paths.

## Toolchain and protocols

<p align="center"><img src="docs/figures/toolchain.svg" alt="Toolchain: agents and harnesses, shared core, design, GIS and storytelling, with the protocols between them" width="900"></p>

| Protocol | Between | Status |
|---|---|---|
| Claude Code plugin (`.claude-plugin/`, `skills/`, `agents/`) | Claude Code ↔ skills | built |
| MCP over stdio (`servers/mcp_server.py`, `.mcp.json`) | any MCP host ↔ core | built, tested as a subprocess |
| Hops, HTTP/JSON (`servers/hops_app.py`) | Grasshopper ↔ core; routes as Rhino points, plans as data trees | built, tested with Grasshopper's payloads |
| Rhino MCP | agents ↔ live Rhino model (open servers in the bank) | used by the data-tree debugger |
| Files: GraphML, GeoJSON, GeoTIFF, CSV, LP/MPS/NL | core ↔ GIS, solvers, other tools | GraphML and solver formats built; GIS export planned |
| CI (GitHub Actions) | every push ↔ test suite | built |

## Toolkit

| Layer | Skill / component | What it gives you | Status |
|---|---|---|---|
| Behaviour | [`dcm-estimate`](skills/dcm-estimate/SKILL.md) | Multinomial logit with Biogeme, cross-checked by an independent estimator; value of time; parameter uncertainty | tested |
| Simulation | [`abm-transport`](skills/abm-transport/SKILL.md) | Agents to 2050: EV adoption with peer effects, mode choice from estimated utilities, congestion feedback, policy levers | tested |
| Decision | [`dmdu-explore`](skills/dmdu-explore/SKILL.md) | EMA Workbench ensembles, robustness, PRIM scenario discovery, backcasting to milestones | tested |
| Networks | [`osm-network`](skills/osm-network/SKILL.md) | Road graph for any place, terrain grades, travel time, EV energy, least-energy routing | tested |
| Operations | [`vrp-solve`](skills/vrp-solve/SKILL.md) · [`opt-model`](skills/opt-model/SKILL.md) | Vehicle routing (PyVRP, OR-Tools); AMPL-style LP/MIP with Gurobi, CPLEX or HiGHS | tested |
| Design | [`gh-datatree`](skills/gh-datatree/SKILL.md) · [agent](agents/gh-datatree-debugger.md) | Grasshopper data-tree model, live probe, diagnoser and debugging agent | model tested; live Rhino run pending |
| Routing | [`cl-foundations`](skills/cl-foundations/SKILL.md) | Router: sends each request to the right skill; shared conventions | built |
| Interfaces | [`servers/`](servers/) | MCP server and Hops app over a shared core | tested |
| Knowledge | [`knowledge-bank/`](knowledge-bank/README.md) | Vendored open-source code and books with licenses, searchable catalog, sync and harvest tools | curated |

## Design and storytelling toolkit

Computational design practice tells its stories through Rhino, Grasshopper and their plugins. The open
AEC skill collections by [Abhinav Bhardwaj](https://github.com/Abhinavbwj) rely on the tools below
(counted from mentions across his skill files in the knowledge bank). Asthenosphere connects its
results to the same tools so that a robust policy pathway becomes a map, a model and a narrative.

| Tool | Used for | Mentions in his skills | In our bank |
|---|---|---|---|
| Ladybug, Honeybee | climate, sun, daylight and energy analysis; environmental graphics | 29, 21 | yes (AGPL, isolated) |
| Dynamo | Revit automation | 31 | not yet |
| Karamba3D | structural analysis in Grasshopper | 22 | no (commercial) |
| Kangaroo | physics-based form finding | 20 | no (ships with Rhino) |
| Galapagos, Wallacei, Octopus, Opossum | single- and multi-objective optimisation in Grasshopper | 17, 9, 10, 11 | no (Galapagos is built in; others are free plugins) |
| Speckle | data exchange between design tools | 16 | yes |
| Rhino.Inside | Rhino and Grasshopper inside Revit and other hosts | 12 | yes (Revit) |
| Blender | rendering and animation for storytelling | 11 | Blender MCP server, yes |
| QGIS, Heron, Elk | GIS and OpenStreetMap into Rhino at true coordinates | 9, 8, 6 | QGIS and Heron yes |
| IfcOpenShell | BIM/IFC data | 9 | yes |
| Hops, Rhino Compute | Python and remote solvers as Grasshopper components | 8 | yes, and our Hops app uses it |
| COMPAS | computational design framework in Python | 7 | yes |
| Mapbox, kepler.gl, deck.gl | interactive maps for presentation | 7, 4 | yes |
| depthmapX | space syntax | 4 | link only (no license file) |

## Sample outputs

From the demonstration study (`python examples/transplan_study.py`; synthetic data, illustrative
parameters). These show what the toolkit produces, not findings about Molde.

<p align="center">
<img src="docs/figures/co2_pathways.png" alt="Sample: CO2 pathways under no policy and a robust policy package" width="430">
<img src="docs/figures/robustness_tradeoff.png" alt="Sample: robustness of policy packages against consumer surplus" width="430">
</p>
<p align="center"><img src="docs/figures/scenario_discovery.png" alt="Sample: PRIM scenario discovery" width="430"></p>

In the sample, no policy meets an 80% cut in commute CO₂ by 2050 in 7% of 60 futures; the most robust
package (pricing, public transport, cycling, EV support) meets it in 68%, and backcasting implies
milestones of about 58% of 2025 emissions by 2030, 36% by 2035 and 26% by 2040.

## Quick start

```bash
pip install -r requirements.txt
python -m pytest tests                      # 74 tests, also run in CI
claude --plugin-dir .                       # use the skills and agents in Claude Code
python servers/hops_app.py                  # then point a Grasshopper Hops component at localhost:5000/cl/vrp
python examples/transplan_study.py          # behaviour -> agents -> futures -> figures
python examples/routing_study.py            # terrain-aware routing and vehicle routing
```

## Research direction

The framework is built for scenario-based transport planning under deep uncertainty: estimated
behaviour driving agent-based models, explored across futures, with backcasting from 2050 targets.
**Framework proposal**: approaches, toolset, research flow and PhD alignment, with the landscape of
transport ABM platforms, LLM-driven agents, deep-uncertainty methods, surrogates and visualisation:
[`docs/FRAMEWORK.md`](docs/FRAMEWORK.md).
Research questions and a dissertation outline: [`docs/research-proposal-outline.md`](docs/research-proposal-outline.md).
What we absorb next and from where: [`docs/CHECKLIST.md`](docs/CHECKLIST.md).
How claims are sourced: [`docs/CLAIMS.md`](docs/CLAIMS.md).
Papers and repositories behind the agent, simulator, surrogate and visualisation choices, with
license status: [`docs/REFERENCES.md`](docs/REFERENCES.md).

## Limitations

- Demonstration data are synthetic; real data (national travel survey, SSB, NVDB, Entur, Kartverket)
  are the next step.
- The Rhino-side probe and Hops components follow McNeel's SDK and are tested with recorded payloads,
  but have not yet run in a live Rhino session.
- GIS export, environmental analysis and Grasshopper optimisation links are planned, not built.

## Repository map

```
skills/            Claude Code skills (SKILL.md + scripts/ each)
agents/            Claude Code agents
servers/           MCP server and Grasshopper Hops app over a shared core
examples/          end-to-end studies
data/synthetic/    synthetic test network and generator
docs/              system diagram (Archify), toolchain figure, sample results, proposal outline, checklist, claims policy
tests/             pytest suite (run in CI)
tools/             knowledge-bank tooling: sync, harvest, assemble
knowledge-bank/    third-party open-source references and books, with licenses
```

## License

MIT, © 2026 Arshad Akhtar Abbasia, for the original work in this repository. Third-party material
under `knowledge-bank/` keeps its own license.

## Credits

- Biogeme (Bierlaire), EMA Workbench (Kwakkel), OSMnx (Boeing), NetworkX, PyVRP, Google OR-Tools, Pyomo,
  HiGHS; Gurobi and IBM CPLEX free editions; MCP Python SDK; McNeel's ghhops-server and rhino3dm.
- Grasshopper data-tree rules checked against Rajaa Issa, *Essential Algorithms and Data Structures for
  Computational Design in Grasshopper*, 2nd ed., McNeel 2024 (CC BY-SA 3.0 US).
- Skill-plugin structure and the design toolkit above after Abhinav Bhardwaj's open AEC skill collections (MIT).
- Third-party code under `knowledge-bank/vendor/` keeps its own licenses: [`ATTRIBUTION.md`](knowledge-bank/ATTRIBUTION.md).
- Built with [Claude Code](https://claude.com/claude-code) as a coding assistant.
