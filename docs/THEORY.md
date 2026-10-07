# Theory funnel

The literature that feeds the thesis, arranged as a funnel: broad paradigms at the top narrow down to
the theories each article tests, and then to the research questions. Each level states what it gives
the thesis. Full entries are in [`references.bib`](references.bib); the diagram is in
[`diagrams/`](diagrams/README.md).

How to use it: read down the funnel when writing the introduction and literature review; cite up the
funnel when defending a modelling choice. A new paper goes in the level whose question it answers,
and into `references.bib` with a `keywords` tag for that level.

```
L1  Paradigm          sustainable mobility, backcasting                       why 2050 targets, not forecasts
L2  Decision theory   deep uncertainty, robustness, scenario discovery, DAPP  how to decide without one future
L3  Behaviour         random utility, crowding, new mobility (Tirachini)      what travellers value and how it shifts
L4  Simulation        agent-based transport models, calibration, emulation    how micro-choices become system outcomes
L5  Frontier          LLM agents, decision models                             what is new and still unproven
        ↓
    Thesis            A1 behaviour · A2 DCM + ABM · A3 exploration · A4 backcasting
```

## L1 Paradigm: sustainable mobility and backcasting

| Reference | What it gives the thesis |
|---|---|
| Robinson (1982), *Energy backcasting*, Energy Policy 10(4) | Origin of backcasting: start from a desirable future and work back to the policies that reach it |
| Banister (2008), *The sustainable mobility paradigm*, Transport Policy 15(2) | Why transport planning should manage demand and accessibility, not only supply speed |
| Banister and Hickman (2013), *Transport futures: thinking the unthinkable*, Transport Policy 29 | Transport backcasting in practice; scenario images for low-carbon futures |
| Hickman and Banister (2014), *Transport, Climate Change and the City*, Routledge | Backcasting studies for London, Delhi, Jinan and others; the template for A4 |
| Norwegian National Transport Plan 2025-2036 (Meld. St. 14 (2023-2024)) | Policy targets and context for the Norwegian case |

## L2 Decision theory under deep uncertainty

| Reference | What it gives the thesis |
|---|---|
| Lempert, Popper and Bankes (2003), *Shaping the Next One Hundred Years*, RAND MR-1626 | Robust decision making: compare strategies across many futures |
| Bryant and Lempert (2010), *Thinking inside the box*, Technological Forecasting and Social Change 77(1) | Scenario discovery (PRIM): the futures in which a policy fails |
| Haasnoot, Kwakkel, Walker and ter Maat (2013), *Dynamic adaptive policy pathways*, Global Environmental Change 23(2) | Pathways, signposts and triggers; extends backcasting over time |
| Kwakkel (2017), *The Exploratory Modeling Workbench*, Environmental Modelling and Software 96 | The software used in `dmdu-explore`; XLRM framing |
| Marchau, Walker, Bloemen and Popper (eds.) (2019), *Decision Making under Deep Uncertainty: From Theory to Practice*, Springer (open access) | Textbook covering RDM, DAPP, exploratory modelling; the methods chapter of the thesis |

## L3 Behaviour: random utility and new mobility

| Reference | What it gives the thesis |
|---|---|
| McFadden (1974), *Conditional logit analysis of qualitative choice behavior*, in Zarembka (ed.), *Frontiers in Econometrics* | The multinomial logit model |
| Ben-Akiva and Lerman (1985), *Discrete Choice Analysis*, MIT Press | Random utility theory for travel demand |
| Train (2009), *Discrete Choice Methods with Simulation*, 2nd ed., Cambridge University Press | Mixed logit and simulation-based estimation (A1) |
| Bierlaire (2003), *BIOGEME: a free package for the estimation of discrete choice models*, Swiss Transport Research Conference | The estimator used in `dcm-estimate` |
| Tirachini, Hensher and Rose (2013), *Crowding in public transport systems*, Transportation Research Part A 53 | How crowding enters user costs and demand estimation |
| Tirachini, Hurtubia, Dekker and Daziano (2017), *Estimation of crowding discomfort in public transport: results from Santiago de Chile*, Transportation Research Part A 103 | Estimated crowding multipliers; a model for stated-choice attributes in A1 |
| Tirachini (2020), *Ride-hailing, travel behaviour and sustainable mobility: an international review*, Transportation 47 | Evidence on substitution from public transport and added vehicle km; a new-mobility uncertainty for A3 |
| Tirachini and Antoniou (2020), *The economics of automated public transport*, Economics of Transportation 21 | Automation effects on cost, frequency, fare and subsidy; levers for scenarios |
| Tirachini and Cats (2020), *COVID-19 and public transportation*, Journal of Public Transportation 22(1) | Shocks and lasting behaviour change; a deep-uncertainty driver |
| Fielbaum, Tirachini and Alonso-Mora (2024), *Improving public transportation via line-based integration of on-demand ridepooling*, Transportation Research Part A 190 | Public transport plus on-demand pooling as a policy lever |

## L4 Simulation: agent-based transport models

| Reference | What it gives the thesis |
|---|---|
| Bonabeau (2002), *Agent-based modeling*, PNAS 99(suppl. 3) | Why ABM: emergence, heterogeneity, interaction |
| Horni, Nagel and Axhausen (eds.) (2016), *The Multi-Agent Transport Simulation MATSim*, Ubiquity Press (open access) | The reference large-scale transport ABM (A2) |
| Kagho, Balac and Axhausen (2020), *Agent-based models in transport planning*, Procedia Computer Science 170 | Current state and open issues of transport ABMs |
| Grimm et al. (2020), *The ODD protocol ... second update*, JASSS 23(2) | Standard for documenting the ABM (A2 methods) |
| [Overview of agent-based traffic simulators (arXiv 2102.07505)](https://arxiv.org/pdf/2102.07505) | Platform comparison |
| [Machine learning to emulate ABMs (arXiv 2005.02077)](https://arxiv.org/pdf/2005.02077), [surrogates and XAI (arXiv 2510.16742)](https://arxiv.org/pdf/2510.16742) | Emulators that make large ensembles affordable (A3) |

## L5 Frontier: LLM agents and decision models

| Reference | What it gives the thesis |
|---|---|
| Park et al. (2023), *Generative agents: interactive simulacra of human behavior*, UIST '23 | Memory, reflection and planning architecture |
| Piao et al. (2025), *AgentSociety* ([arXiv 2502.08691](https://arxiv.org/abs/2502.08691)) | LLM agents at city scale |
| [Prompt-learning LLMs for travel choice (arXiv 2406.13558)](https://arxiv.org/pdf/2406.13558) | LLMs predicting mode choice against logit benchmarks |
| [LLM2Jev (arXiv 2610.02076)](https://arxiv.org/abs/2610.02076) | Decision models that return choice probabilities; tier 2 agents |

## Funnel to thesis

| Article | Draws on | Question it answers |
|---|---|---|
| A1 Behaviour | L3 (random utility, crowding, new mobility), L5 (LLM choice as benchmark) | How do travellers trade off time, cost, crowding and technology, and how transferable is that? |
| A2 DCM + ABM | L4, L3 | How do estimated choices drive agents consistently, and how is the coupled model validated? |
| A3 Exploration | L2, L4 (emulation) | Which futures make 2050 targets unreachable, and which packages are robust? |
| A4 Backcasting | L1, L2 (pathways) | Which sequences of decisions keep the target reachable, and when must they be taken? |
