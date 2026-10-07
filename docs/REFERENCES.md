# References: agents, simulators, surrogates and visualisation

The sources behind the ABM and thesis layer ([diagram](diagrams/abm-thesis-system.png)). Papers are
linked, not copied. Code is cloned into `knowledge-bank/vendor/` only when its license allows it.

Status: **bank** = cloned with its license · **link** = no open license, so we link and do not copy ·
**paper** = article only.

## Overviews

| Source | What it gives the thesis | Status |
|---|---|---|
| [An Overview of Agent-based Traffic Simulators (arXiv 2102.07505)](https://arxiv.org/pdf/2102.07505) | Comparison of MATSim, SUMO, POLARIS, BEAM and others: scale, behaviour, network loading. Basis for choosing the A2 platform | paper |
| [Awesome Urban LLM Agents](https://github.com/usail-hkust/Awesome-Urban-LLM-Agents) | Curated list of LLM agents for urban mobility, planning and simulation | link (no license file) |

## Transport ABM platforms

| Source | Role | Status |
|---|---|---|
| [BEAM (arXiv 2308.02073)](https://arxiv.org/pdf/2308.02073), [code](https://github.com/LBNL-UCB-STI/beam) | MATSim-based mesoscopic ABM with ride-hail, EV charging and freight; full source | bank (GPL, isolated) |
| MATSim, [eqasim](https://github.com/eqasim-org/ile-de-france) | Network ABM and a reproducible synthetic-population pipeline | eqasim in bank (GPL); MATSim link |
| [SUMO](https://github.com/eclipse-sumo/sumo) | Microscopic traffic and emissions; source, tools and docs | bank (EPL/GPL); regression fixtures (`tests/`) left out |
| [GAMA](https://github.com/gama-platform/gama), [NetLogo](https://github.com/NetLogo/NetLogo) | Spatial ABM platforms | bank (GPL) |
| [ActivitySim](https://github.com/ActivitySim/activitysim) | Activity-based demand | bank (BSD-3) |

## LLM-driven and decision-model agents

| Source | Role | Status |
|---|---|---|
| [AgentSociety](https://github.com/tsinghua-fib-lab/AgentSociety) (Tsinghua FIB lab; papers [v1 arXiv 2502.08691](https://arxiv.org/abs/2502.08691), [v2 arXiv 2607.11895](https://arxiv.org/abs/2607.11895)) | LLM agents in an urban environment at society scale. The repository holds `agentsociety` (v1), `agentsociety2` (agents, environment routers, skills, storage, tracing; Ray-based scaling), a benchmark package, the web frontend, docs and examples | bank (Apache-2.0), full depth; one frontend file containing a public Mapbox token is left out because GitHub push protection blocks it |
| [LLM agents in GAMA](https://github.com/dungzvu/llm-agents-gama) ([arXiv 2510.19497](https://arxiv.org/pdf/2510.19497)) | LLM-driven travellers inside GAMA, Toulouse case | bank (Apache-2.0) |
| [GTA: Generative Traffic Agents (arXiv 2601.16778)](https://arxiv.org/pdf/2601.16778) | Generative agents for traffic simulation | paper |
| [GATSim](https://github.com/qiliuchn/gatsim) | Generative-agent transport simulation with hierarchical memory and learning | bank (Apache-2.0); experiment logs (`gatsim/storage/`) left out |
| [Generative Agents](https://github.com/joonspk-research/generative_agents) (Park et al.) | Memory, reflection and planning architecture | bank (Apache-2.0); replay storage left out |
| [AgentTorch](https://github.com/AgentTorch/AgentTorch) | Differentiable large-population models with LLM-guided archetypes | bank (AGPL, isolated) |
| [MobiVerse](https://github.com/ucla-mobility/MobiVerse) (UCLA) | LLM agents for urban mobility with SUMO | link (license not recognised) |
| [LLMob](https://github.com/Wangjw6/LLMob/) | LLM agents generating personal activity trajectories from real data | link (no license file) |
| Jev (TypeSafe AI, Sept 2026) | "System One" decision model: answers typed decision questions with a probability distribution over the options in about 100 ms, instead of generating text. Coverage: [Towards Data Science](https://towardsdatascience.com/jev-vs-llms-when-ai-moves-from-generation-to-decision-making/), [Eden AI](https://www.edenai.co/post/jev-a-new-kind-of-ai-model-built-for-decisions-not-conversation) | hosted model (proposed use) |
| [LLM2Jev (arXiv 2610.02076)](https://arxiv.org/html/2610.02076v1) | When and how LLMs can be fine-tuned into Jev-style decision models | paper |

## Surrogates, emulation and explanation

| Source | Role | Status |
|---|---|---|
| [Surrogate modelling and XAI for simulation exploration (arXiv 2510.16742)](https://arxiv.org/pdf/2510.16742) | Surrogates plus explainable AI to read large simulation ensembles | paper |
| [Machine learning to emulate agent-based models (arXiv 2005.02077)](https://arxiv.org/pdf/2005.02077) | Which ML emulators reproduce ABM outputs, and at what cost | paper |
| [SMT](https://github.com/SMTorg/smt), [pyABC](https://github.com/ICB-DCM/pyABC), [SALib](https://github.com/SALib/SALib) | Surrogates, ABC calibration, sensitivity | bank |

## Visualisation and storytelling

| Source | Role | Status |
|---|---|---|
| [SimWrapper](https://github.com/simwrapper/simwrapper) ([paper](https://svn.vsp.tu-berlin.de/repos/public-svn/publications/vspwp/2022/22-21/CharltonSana2022SimWrapper.pdf)) | Browser dashboards for MATSim and ABM outputs | bank (GPL), full depth |
| [Archify](https://github.com/tt-a1i/archify) | Typed-JSON interactive diagrams with layout and browser gates; used for this repo's system diagram | bank (MIT) |
| [Quelea](https://github.com/lxfschr/Quelea) | Agent and flocking library for Grasshopper | link (no license file) |
| [SlowRobotics / Nursery](https://github.com/daneisinger/SlowRobotics), [Culebra](https://grasshopper3d.com/group/parametrichouse/forum/topics/culebra-agents) | Agent behaviours in Rhino/Grasshopper | link |
| kepler.gl, deck.gl, Ladybug Tools | Maps and environmental graphics | bank |
