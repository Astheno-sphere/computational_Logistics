# Asthenosphere framework: approaches, toolset and research flow

Author: Arshad Akhtar Abbasia. A proposal for how to tackle long-range, low-emission transport planning
under deep uncertainty with agent-based modelling, and how to make the results visible. It maps the
landscape, chooses a toolset, defines the flow from question to decision, and ties it to a PhD.

Status labels: **in repo** (built and tested here), **in bank** (cloned under `knowledge-bank/vendor/`
with its license), **link** (not copyable: no open license), **proposed** (not yet built).

---

## 1. The problem, stated as a modelling task

Find policy pathways that keep a 2050 low-emission target reachable across many plausible futures,
when behaviour, technology, prices and demography are deeply uncertain. That needs four things at once:

1. **Behaviour that is estimated, not assumed**: how people choose modes, vehicles, destinations.
2. **Dynamics and interaction**: fleets turning over, technology diffusing through neighbours,
   congestion feeding back, policies phasing in.
3. **Many futures, not one forecast**: thousands of runs, robustness, the conditions under which
   policies fail, and backcasting from the target.
4. **Communication**: results that planners, agencies and the public can see and argue about.

## 2. Landscape of approaches

### 2.1 Ways to represent travel behaviour

| Approach | Idea | Strength | Weakness | Tools |
|---|---|---|---|---|
| Discrete choice (MNL, nested, mixed logit) | utility maximisation, estimated from survey data | statistically grounded, interpretable, welfare measures | static, needs good data | Biogeme (in bank, used in repo), xlogit, pylogit (in bank), Apollo (R, link) |
| Activity-based models | full daily activity schedules per person | realistic tours and time use | heavy data and calibration | ActivitySim, PopulationSim (in bank) |
| Machine-learning choice models | flexible predictors of choice | capture non-linearities | weak behavioural interpretation and transferability | scikit-learn class; hybrid "theory-constrained" ML is an active research area |
| LLM-driven generative agents (frontier) | agents reason in language with memory, planning, reflection | rich, adaptive behaviour; can respond to novel policies | validity, cost, bias, reproducibility unresolved | AgentSociety, AgentTorch, Generative Agents, GATSim, LLM agents in GAMA (in bank); MobiVerse, LLMob (link) |
| Decision models (frontier, 2026) | a model trained to answer a typed decision question with a probability distribution over the options, not free text | fast (about 100 ms) and cheap enough for every agent at every step; output is already a choice distribution, like a logit | new, proprietary and hosted; behavioural validity for travel choice untested | Jev (TypeSafe AI); LLM2Jev paper on turning LLMs into such models |

### 2.2 Ways to simulate the system

| Approach | Platforms | Fits this project when |
|---|---|---|
| Compact research ABM (Python) | `abm-transport` (in repo), Mesa, Repast4Py (in bank) | thousands of runs for scenario exploration |
| Large-scale transport ABM with network simulation | MATSim (link), BEAM, eqasim (in bank), POLARIS, SimMobility | city-scale detail, validation against counts |
| Microscopic traffic | SUMO (in bank) | intersections, signals, emissions detail |
| Spatial ABM platforms | GAMA (in bank), NetLogo (in bank) | spatial behaviour, teaching, LLM-agent experiments |
| Static assignment and skims | AequilibraE (in bank), OSMnx/NetworkX (in repo) | travel times and costs for choice models |
| System dynamics | (e.g. PySD) | fast, aggregate stock-flow views of fleet transitions |

### 2.3 Ways to decide under deep uncertainty

| Method | Question it answers | Tools |
|---|---|---|
| Exploratory modelling | what happens across many futures and policies? | EMA Workbench (in bank, used in repo) |
| Robust Decision Making (RDM) | which strategy is robust, and where is it vulnerable? | EMA Workbench, Rhodium (in bank) |
| Scenario discovery (PRIM, CART) | which combinations of uncertainties make a policy fail? | EMA Workbench (in repo) |
| Many-objective robust optimisation (MORDM) | best trade-offs across objectives under uncertainty | EMA Workbench + Platypus, pymoo (in bank) |
| Dynamic adaptive policy pathways (DAPP) | sequences of actions, signposts and triggers over time | proposed, on top of the above |
| Backcasting | from a desirable 2050, what must be true by 2030, 2040? | `dmdu-explore.backcast` (in repo) |
| Global sensitivity analysis | which uncertainties matter most? | SALib (in bank) |

### 2.4 Making large ensembles affordable and credible

| Need | Method | Tools |
|---|---|---|
| Too slow for thousands of runs | surrogate models / emulators (Gaussian processes, neural nets, tree ensembles) trained on a designed set of ABM runs | SMT (in bank), scikit-learn |
| Calibrating ABM parameters to data | approximate Bayesian computation, history matching | pyABC (in bank) |
| Comparing policies fairly | common random numbers, fixed seeds | used in repo |

### 2.5 Ways to make it visible

| Audience | Medium | Tools |
|---|---|---|
| Transport modellers | dashboards of trips, flows, emissions | SimWrapper (in bank), kepler.gl, deck.gl (in bank) |
| Planners and designers | 3D models, street-level design, massing | Rhino + Grasshopper via Hops (in repo), Heron for GIS (in bank), Rhino MCP |
| Public and decision makers | maps, animations, narrative figures | kepler.gl stories, Blender (Blender MCP in bank), matplotlib figures (in repo) |
| Environmental context | climate, sun, daylight graphics | Ladybug Tools (in bank) |
| Agent motion in design space | flocking/agent visualisation in Grasshopper | Quelea, Culebra, Nursery/SlowRobotics (link: no open license file) |

## 3. Proposed framework: five layers, one loop

```
EVIDENCE   surveys (RVU, stated choice) · networks (OSM, NVDB, GTFS) · population and fleet (SSB) · terrain
   ↓
BEHAVIOUR  discrete choice estimation (Biogeme) · parameter uncertainty · optional LLM-agent experiments
   ↓
SIMULATION synthetic population → agent-based model (compact for exploration; MATSim/eqasim for detail)
           networks and travel times (OSMnx, AequilibraE) · operations (VRP, LP/MIP)
   ↓
DECISION   ensembles (EMA) → surrogate where needed → robustness, scenario discovery, MORDM → backcasting, pathways
   ↓
STORY      dashboards (SimWrapper, kepler.gl) · design models (Rhino/Grasshopper via Hops, data trees) · narrative figures
   ↺       workshops with agencies refine targets, levers and uncertainties → back to EVIDENCE
```

The full system, with every component tagged in repo / in bank / proposed and mapped to the four
articles, is the Archify diagram in [`diagrams/`](diagrams/README.md):

![ABM system and thesis flow](diagrams/abm-thesis-system.png)

### The frontier position (what would be new)

1. **Estimation uncertainty carried end to end.** Choice-model covariance and transferability ranges
   become explicit uncertainties in the ensemble, so behavioural uncertainty is explored alongside
   technology and prices instead of being fixed at point estimates.
2. **Hybrid agents in three tiers.** (a) Most agents follow estimated choice models: credible, cheap,
   with known uncertainty. (b) A decision-model tier (Jev-style) answers choice questions the survey
   never asked, such as a new mobility service, and returns a probability distribution that can be
   compared term by term with the logit probabilities. (c) A small panel of full LLM agents (AgentSociety,
   GATSim, LLM agents in GAMA) with memory and reflection probes adaptation over years. Tiers (b) and (c)
   are *stress tests* of structural uncertainty, benchmarked against tier (a), not the backbone.
3. **Backcasting with pathways.** Not only "which package is robust" but which milestones and trigger
   points along the way (2030, 2035, 2040) keep the target reachable: adaptive pathways.
4. **Design-native communication.** Results flow into Rhino/Grasshopper as data trees (one branch per
   scenario, agent or vehicle), so planners can see pathways in the tools they already design with.

## 4. Grasshopper data trees as the bridge to design

Data trees are how Grasshopper structures nested data. The framework uses a fixed path convention so
results arrive in Grasshopper already organised:

| Data | Path | Items |
|---|---|---|
| Vehicle routes | `{vehicle}` | route points |
| Agent trajectories | `{scenario; agent}` | points over time |
| Yearly indicators per scenario | `{scenario; indicator}` | values 2025-2050 |
| Pathway milestones | `{package; year}` | target share, lever settings |

The `gh-datatree` skill (in repo) models tree semantics, probes live trees and diagnoses mismatches;
the Hops app (in repo) already returns VRP plans as `{vehicle}` trees. Definitions to build next:
a pathway explorer (slider over futures, coloured by success), and an agent-flow viewer.

## 5. Agents and harnesses for doing the research

| Role | Tool | Use |
|---|---|---|
| Research assistant and code agent | Claude Code with this plugin | build, test and run skills; read the knowledge bank |
| Tool access for any agent | MCP server (in repo) | the same skills from Claude Desktop or other hosts |
| Open-model harness | Hermes Agent (in bank) | run the MCP tools with open-weight models, e.g. for reproducibility or offline work |
| Live model control | Rhino MCP servers (in bank) | agents drive Grasshopper/Rhino for visual outputs |
| Agents inside the model | AgentSociety, Concordia, OASIS, GATSim, LLM agents in GAMA, Mesa-LLM, AgentTorch; llm2jev, AnyJev, Open-Jev (in bank); Jev (hosted) | the hybrid-agent tiers above, kept separate from research assistance |
| Diagrams that stay current | Archify (in bank) | the system diagram is typed JSON checked by layout and browser gates; edit and re-run, see `diagrams/README.md` |

Keep the two uses of "agent" apart in writing: AI agents that help do the research, and simulated
agents that are part of the model.

## 6. Research flow (from question to decision)

| Step | Output | Tools |
|---|---|---|
| 1. Frame | targets, levers, uncertainties, outcomes (XLRM table) with agencies | workshop; EMA naming |
| 2. Data | survey, network, population, fleet datasets | RVU, SSB, NVDB, Entur, OSM, Kartverket |
| 3. Behaviour | estimated choice models with uncertainty | Biogeme, xlogit |
| 4. Population | synthetic agents with attributes | PopulationSim, synthpop |
| 5. Model | calibrated ABM; validated on held-out indicators | `abm-transport` → MATSim/eqasim for detail; pyABC |
| 6. Explore | ensemble of futures × packages | EMA Workbench; surrogate (SMT) if slow |
| 7. Analyse | robustness, scenario discovery, sensitivity, trade-offs | PRIM, SALib, pymoo/Platypus |
| 8. Backcast | milestones, triggers, pathways | `dmdu-explore.backcast`, DAPP |
| 9. Communicate | dashboards, design models, figures | SimWrapper, kepler.gl, Grasshopper via Hops |
| 10. Iterate | revised levers and uncertainties | back to step 1 |

## 7. PhD alignment (3-4 articles)

| Article | Steps | Main tools | Frontier element |
|---|---|---|---|
| A1 Behaviour and transferability | 2-3 | Biogeme, xlogit, RVU + stated choice | estimation uncertainty as an explicit input to scenario analysis |
| A2 Coupled DCM-ABM | 4-5 | PopulationSim, ABM, MATSim/eqasim, pyABC | calibration and validation of estimated behaviour inside an ABM; hybrid LLM agents as stress test |
| A3 Exploration and discovery | 6-7 | EMA Workbench, SMT, SALib | surrogate-assisted ensembles at scale |
| A4 Backcasting and pathways | 8-9 | EMA, pathways, Grasshopper and SimWrapper | adaptive pathways communicated in design tools |

## 8. Open questions to settle with supervisors

- Case scope: commuting only, or all trips and freight? One region or comparison of two?
- Data access: RVU microdata, SSB registers, agency model outputs.
- Platform for the detailed model: MATSim/eqasim versus extending the compact ABM.
- How far to take LLM agents, given validity and reproducibility concerns.

## 9. What more agents to pull, and what is still missing

**Agents worth pulling next** (license checked before cloning):

| Candidate | Why | Status |
|---|---|---|
| POLARIS (Argonne), SimMobility (MIT/SMART) | large-scale activity-based ABMs named in the simulator overview | to check licenses |
| MATSim core (`matsim-libs`) in full | the platform eqasim and BEAM build on | link now; GPL, can be cloned |
| Mesa-LLM, Concordia (Google DeepMind), OASIS | LLM agents in Python ABM frameworks | cloned |
| Open-weight decision models | a reproducible alternative to hosted Jev for tier (b) | cloned: llm2jev, LLM2Jev, AnyJev, Open-Jev |
| CityBehavEx and similar urban-behaviour benchmarks | validation sets for LLM travel behaviour | to find |

**Missing pieces in the framework itself:**

1. A real-data bridge: RVU, SSB, NVDB and Entur loaders (Evidence lane).
2. A synthetic-population step (PopulationSim or eqasim pipeline) feeding both ABMs.
3. A MATSim/eqasim run for the case region, so the surrogate has training runs.
4. The Jev / LLM benchmarking harness: the same choice situations asked to logit, Jev and LLM agents.
5. A SimWrapper dashboard spec for ensemble outputs, and a Grasshopper pathway explorer.
6. Adaptive pathways (DAPP) on top of backcasting.

## Sources for the landscape

- [An Overview of Agent-based Traffic Simulators (arXiv 2102.07505)](https://arxiv.org/pdf/2102.07505)
- [BEAM framework (arXiv 2308.02073)](https://arxiv.org/pdf/2308.02073)
- [AgentSociety](https://github.com/tsinghua-fib-lab/agentsociety/) · [LLM agents in GAMA, Toulouse](https://github.com/dungzvu/llm-agents-gama) · [Awesome Urban LLM Agents](https://github.com/usail-hkust/Awesome-Urban-LLM-Agents) · [GTA: Generative Traffic Agents (arXiv 2601.16778)](https://arxiv.org/pdf/2601.16778)
- [SimWrapper (TU Berlin)](https://svn.vsp.tu-berlin.de/repos/public-svn/publications/vspwp/2022/22-21/CharltonSana2022SimWrapper.pdf)
- [Quelea for Grasshopper](https://www2.food4rhino.com/en/node/1900) · [SlowRobotics / Nursery](https://github.com/daneisinger/SlowRobotics)
- [Surrogate modelling and XAI for simulation exploration (arXiv 2510.16742)](https://arxiv.org/pdf/2510.16742) · [ML to emulate ABMs (arXiv 2005.02077)](https://arxiv.org/pdf/2005.02077)
- Full list with license status: [`REFERENCES.md`](REFERENCES.md)
