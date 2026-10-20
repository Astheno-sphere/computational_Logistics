# FINAL MASTER — TRANSPLAN proposal v5.5 (self-contained build pack)

This one file carries everything the build session needs: the title, the spine, every page's **title + kicker + body text verbatim**, the **storytelling angle and depth** for each page, and the **exact image positioning** (which plate sits where, its caption, its narration lines, its keyword, the Abhinav family to pull). It does not point you to other files for content — the content is here. The other repo files (`v5.5-content.md`, `visual_spec.md`, `STATE_v5.5.md`) remain the working sources, but this is the single feed.

Repo: **github.com/Astheno-sphere/computational_logistics** · build branch `claude/lucid-galileo-3ss28v`.
Format: HTML, five A3 pages + a sixth references page. No em dashes. Never invent a number — leave `[N1]` and `[to confirm]` exactly as written.

---

## 0. THE SPINE (one sentence; every page serves one clause of it)

> Norway's official models are static and macroscopic, and TØI itself calls for dynamic models built beside them; this PhD builds that layer: it estimates how people and freight accept and respond to road pricing (DCM), carries those responses in agents through calendar time (ABM), and searches for the instrument sequences that reach 2050 robustly (deep uncertainty and backcasting), reporting the signposts that warn when a path is failing, as a complement to NTM6, RTM and the national freight model, never a replacement.

**The storytelling arc across the five pages** (this is the angle — keep it intact):
1. **The problem is a path, not an end state** — and I already have a measured result proving the toll base is eroding. (hook: evidence in hand)
2. **TØI asked for exactly this dynamic layer; here is the gap nobody has filled.** (fit: I belong in this line of work)
3. **Here is the model, written down, and its empirical heart is a measurement that could fail.** (honesty: this is real research with a falsifiable core)
4. **Tested where acceptance is live and freight is real — Kristiansund, charging since June 2026.** (concreteness: a real town, real trips, real freight corridor)
5. **A three-year plan that survives a failed survey, with receipts for every number.** (deliverability + credibility: I will finish, and you can check me)

The ring closes: the signpost on page 5 that warns a path is failing is the same erosion page 1 showed *already happening* at the Kristiansund toll. Page 1 shows the disease; page 5 shows the instrument that detects it.

**Title block (top of page 1):**
- **Title:** From end states to pathways
- **Kicker / subtitle:** *Estimated acceptance, agents with memory, and robust road-pricing paths to a low-carbon Norway in 2050*
- **Byline:** Arshad Akhtar Abbasia. Research proposal for the PhD in Transport Modelling for Sustainability Transitions (TRANSPLAN), PhD programme in Logistics, Molde University College.

---

## VISUAL SYSTEM (all five plates, one hand — Abhinav poster style)

- Ground: charcoal `#16120F` (matches the existing sheets; lower risk than re-toning to oxblood `#2E151C` — pick charcoal and keep it across all five). Cream line-work `#E8DFD0`.
- Semantics fixed: sage `#9DB886` = good/robust/accepted · amber `#D4A530` = moderate/near · warm red `#C45545` = fails/erodes/danger · terracotta `#D4835C` = the chosen/focal thing · teal `#7CBAC4` = free alternative / directional.
- One accent per plate doing every accent job. Titles/labels: Inter (heavy) for titles OR a genuinely condensed face — pick one, apply to all; body stays the serif. Do not mix title faces.
- Honest encoding: bars from zero, axes carry units, no 3D, no fake smoothing. Every number is real (from the body text or the evidence folders).
- Caption leads with the diagram; keyword printed as a visible label on the plate.
- **The narration rule:** each plate's caption + annotations ADD depth the body text does not — a mechanism, a number, a consequence — never a repeat of the prose.

---

# PAGE 1 — The problem, and what already exists

**Angle:** open on the structural blind spot (equilibrium models can't answer "how do we get there"), then immediately land a measured result I already hold. The reader should finish page 1 thinking *this person has a real finding, not just an idea.*
**Serves the spine clause:** the problem is a path under erosion.

**Body text (verbatim):**

Norway appraises transport with a national model system that computes an equilibrium for a chosen year. Asked what 2050 looks like under a set of assumptions, it answers carefully. Asked how the country gets there, and which routes fail on the way, it is silent by construction. TØI's own review of the model system says as much: the current models are static and macroscopic, and less suited to dynamic questions [toi1819]. The path to 2050 is governed by what an equilibrium does not carry: a vehicle fleet that turns over slowly, public acceptance that persists or erodes, and debt repaid on a schedule.

Road pricing shows the problem in its sharpest form. It is named among the levers for the next National Transport Plan, where TRANSPLAN's first deliverable argues the plan must be realistic and goal-directed rather than a wish list [toi2172]; yet the national reform has stalled. Tolls raised NOK 16.8 billion in 2025, about 62% in city packages, against toll-company debt near NOK 78 billion [svv25, dok15]. Every revision meets a public that has voted against tolls before: a single-issue anti-toll party won 16.7% in Bergen in 2019 [snl19]. Whether a 2050 plan is feasible depends on the order in which instruments arrive and whether people accept each step. That is a question about paths.

> **Main question.** Which sequences of road-pricing instruments reach a desirable 2050 on emissions, finance and accessibility while staying acceptable to the people and firms who pay, across deep uncertainty; and which signals tell planners when to switch?
> **RQ1, method (A1).** How can choice models estimated on real data drive agents that carry state year to year, so that strategic end states become pathways?
> **RQ2, behaviour (A2).** Does acceptance persist once a charge is permanent, and does information move it independently of experience?
> **RQ3, planning (A3).** Which pathways, for passengers and for freight, are robust; what acceptance margin does each survive; and which signposts give lead time before one fails?

**What already exists.** I have a working prototype and a first measured result. At the Kristiansund tariff a zero-emission car with a tag pays NOK 19.04 against NOK 27.20, so each electric crossing earns NOK 8.16, or 30%, less [vegamot]. At today's national share of four electric passings in ten, a crossing already earns about 12% less than in a fossil fleet; in an all-electric fleet it earns 30% less while the debt is unchanged. On the road network, the toll-free Atlantic Ocean Tunnel lets some crossings avoid both stations; Article 1 counts that share ([N1]), so exposure is measured on the network rather than assumed uniform. The question is no longer whether the toll base erodes; it is which path through that erosion people will accept.

**Handoff line to page 2 (print it):** → So Norway needs the dynamic layer TØI calls for. What should it be, and who has built the pieces?

### IMAGE — Plate P1, positioned as the page-1 hero (lower-right, spanning ~55% width, below the RQ block)
- **Keyword label on plate:** PATHWAYS
- **Abhinav family to pull:** split before/after panel (framed, vertical cream rule, two labelled halves) + a scene-register household for the right half.
- **Composition:** one frame, split by a thin cream rule. LEFT = a single settled 2050 block (one flat isometric mass, date "2050", static, grey-cream). RIGHT = the SAME household drawn four times down a year axis (2026 → 2050): its car flips cream → teal (electric), a small toll-bill bar shrinks, an acceptance line rises then dips, and the path splits into surviving (sage) and broken (red ghost) branches. A true-scale stick figure at the door on the right.
- **Caption (leads, bottom of plate):** *"A model gives one 2050. A household lives a sequence. Only one of these is a plan."*
- **Narration that adds depth (letter these on — each is a mechanism the body only names):**
  - Left label: `EQUILIBRIUM — one state, no route`
  - Right annotations: `fleet turns over slowly` · `acceptance carries year to year (ρ)` · `debt is due on a schedule` — the three things an equilibrium cannot hold.
  - One red ghost branch tagged: `pathway breaks here — threshold crossed`.
- **Leave out:** any second figure, any map. One household, one axis.

---

# PAGE 2 — Fit, gap and what is new

**Angle:** prove I know the Norwegian system by name (NTM6/RTM/NGM/tramodsim), place this work *inside* TØI's own stated programme, then name the precise gap nobody has filled — and declare the empirical heart honestly. The reader (Tveter, Hjelle) should feel *this candidate is realistic and already fluent in our models.*
**Serves the spine clause:** a complement built beside the official models, filling a named gap.

**Body text (verbatim):**

The national system has three parts a candidate must name: NTM6, the national passenger model for trips over 70 km; RTM, the regional passenger model; and the national freight model, Nasjonal godsmodell (NGM), with its commodity-flow matrices and transport-chain costs [toi1819, ngm]. These anchor the National Transport Plan and are trusted for point appraisal. TØI's forward-looking review recommends not replacing them but building dynamic models alongside them [toi1819]; the institute has started, with a MATSim-based agent assignment for Greater Oslo, tramodsim, and an activity-based model for Trondheim [tramodsim]. This PhD joins that line rather than importing a method from outside it. It supplies the exploratory, stress-testing layer that sequences instruments across thousands of futures and reports where each sequence fails, so the national models keep producing the appraisal the agencies rely on while this layer supplies the robustness and failure conditions they are not built to give.

| The position asks for | This proposal answers with |
|---|---|
| Desirable futures under deep uncertainty | 10³ futures, satisficing targets, uncertainty decomposed by source |
| DCM integrated with ABM | Choice models estimated on real survey data drive agents whose acceptance and fleet carry over year to year |
| Behaviour under low-carbon scenarios to 2050 | Emissions an explicit objective; passenger acceptance and carrier mode choice both estimated; freight vehicles turn over by class, with load factors and empty running from NGM |
| Backcasting and pathways, not one forecast | 2050 targets defined on page 3; instrument orders searched backward from them |
| Methodological and practical contributions | Three testable claims and a named decision: revising the zero-emission discount and tariff |

**The gap.** Strategic models give end states and NGM gives freight chains; neither carries acceptance. Norwegian agent work assigns traffic with MATSim but takes acceptance as given [tramodsim]. Le Pira, Marcucci and Gatta integrated discrete choice and agent-based models to evaluate the acceptability of urban freight policy [lepira]; their agents are stakeholder groups negotiating in rounds, not a population living through calendar time. Adaptive pathway methods sequence actions against tipping points [dapp, haasnoot] but treat acceptance as an external scenario. The deep-uncertainty frontier runs ensembles over transport agent models, most recently on a fictional city with acceptance left out [fuhrer]. The road-pricing acceptance evidence is careful and mostly static, and hybrid choice with a latent acceptance variable is now an established way to read it [hybridaccept, odeck08, borjesson16, toi2179]. **Nobody has estimated acceptance on real data, carried it in agents over calendar time, and let it decide which passenger and freight pathways survive.**

**The empirical heart.** The question beneath the whole proposal is prior to any pathway: *is public acceptance a measurable quantity that can be estimated on real data and carried forward in time, or not?* The thesis answers that first; the ensemble and the robust front are what the answer is then used for, not the other way round.

**What is new. Three claims and no others.**
1. **Acceptance, estimated and carried, as an admissibility condition.** First that acceptance is a quantity that can be estimated on real survey data and shown to persist (or not) between waves; then that a pathway counts only if that estimated acceptance stays above a threshold at every step, with the largest shift it survives reported as its acceptance margin, a result not an assumption.
2. **Uncertainty decomposed by source over a policy path.** The spread in 2050 outcomes is split, year by year, into behavioural parameters, external futures and the choice of path, so planners see which uncertainty more data can reduce and which only adaptation can.
3. **Signposts validated twice, and ordered across modes.** Signals that a pathway is failing are scored on held-out futures for lead time and false alarms, then against dated events that happened; and the passenger and freight signposts are compared, because the slower fleet decides which fires first.

**Handoff line to page 3 (print it):** → Here is that layer, written down.

### IMAGE — Plate P2, positioned centre-right of page 2, beside "What is new" (vertical, spanning the three-claim block)
- **Keyword label on plate:** DCM + ABM
- **Abhinav family to pull:** staged pipeline (panels left→right with arrows) OR context-tensor isometric stack.
- **Composition:** five isometric layers stacked / chained, each a thin-cream plane on charcoal, one terracotta thread running up through all five showing data becoming decision. Layers bottom→top: `REAL DATA` (survey + register) → `ESTIMATED CHOICE (DCM)` → `AGENTS WITH MEMORY (ABM)` → `10³ FUTURES` → `ROBUST SEARCH → SIGNPOSTS`. Each layer tagged on its right edge with its **article · claim · tool**.
- **Caption (leads):** *"Five layers. Each carries what the one below cannot."*
- **Narration that adds depth (per-layer micro-labels):** `DCM: A1 · Biogeme · estimated, not assumed` · `ABM: A2 · acceptance carried in calendar time` · `FUTURES: 10³ · EMA Workbench` · `SEARCH: A3 · MORDM, min max-regret` · `SIGNPOSTS: validated twice`. Side note by the tool column: `every layer = one named tool, one article`.
- **Leave out:** decorative gears/cogs. It is strata, not machinery.

---

# PAGE 3 — The model, written down

**Angle:** this is the technical spine and the honesty page. Write the model as equations, state plainly what would falsify it, and disclose the skill path and AI assistance without flinching — then back it with the Swissmetro receipt. The reader (Hoff, Arild) should feel *the maths is real and the candidate is not overclaiming.*
**Serves the spine clause:** the DCM→ABM estimation layer, whose heart is a measurement that can fail.

**Body text (verbatim):**

**What each agent decides and remembers.** Each year t, a household or firm n chooses a vehicle, how often to cross and when, from a choice model where the instruments in force I(t) set the cost:
(1) U(n,j,t) = β·cost(j, I(t)) + θ'·x(n,j) + ε(n,j,t)
Everything rests on one measurement, so the model begins there. Acceptance is estimated in its core, cross-sectional form in A1, as an integrated choice and latent-variable model on real wave-1 data, the same hybrid-choice approach used to read acceptance surveys elsewhere [hybridaccept], extending Le Pira, Marcucci and Gatta from negotiating stakeholder groups to a population of individually estimated agents [lepira]. There acceptance depends on the dose actually paid, the information arm and covariates. Whether that latent construct is cleanly identified, and whether it persists, is the thesis's first empirical test; the pathway machinery below is built on its answer. The dynamic form adds one first-order persistence term:
(2) A*(n,t) = ρ·A(n,t−1) + δ·dose(n,t) + η·info(n) + γ'·z(n) + u(n,t)
identified between the two waves with the initial-conditions problem handled [wooldridge]. This persistence term ρ is a Level-3 extension, pursued only if both waves land; the core contribution does not rest on it. I claim only what the data identify: a cross-sectional acceptance model as the floor, one persistence term as the stretch, never a full dynamic panel.

**What a pathway is, and how it is chosen.** Five instruments: revision of the package, the zero-emission rate, a passenger distance charge, a heavy-vehicle distance charge, and earmarking of revenue. A3 is a search, not a catalogue: choose the switch-on year and level of each instrument to maximise the share of futures meeting all three 2050 targets and minimise maximum regret, subject to acceptance holding above threshold every year, revenue covering debt service, and an accessibility floor. The search runs with a many-objective robust algorithm over the ensemble, then scenario discovery names the futures where the robust set still breaks [prim, mordm]. Treating robustness as the quantity to optimise under uncertainty follows the stability-metrics line of Shaabani, Hvattum, Hoff and Laporte [shaabani]. Full enumeration of a reduced instrument set is kept only to check the search: that core is the 904 ordered instrument sequences (orders of one to four instruments at three switching thresholds, 4 + 36 + 216 + 648 = 904), while the full search ranges over switch-years and levels, on the order of 10⁴ candidate pathways.

(3) A pathway p is admissible if the share accepting stays at or above λ every year; its acceptance margin is the largest rise in λ for which p stays admissible in the target share of futures.

| Target in 2050 | Metric | Anchor |
|---|---|---|
| Emissions | Well-to-wheel CO₂e from road traffic crossing the case area | Climate Change Act: 55% by 2030, 90–95% by 2050 [klimalov] |
| Finance | Toll revenue at or above debt service; failure if below three years running | Package financing [innst337] |
| Accessibility | Generalised cost of the lowest income quintile no higher than 2026 | Distributional floor, stated as a design choice |

**What would falsify it.** If ρ is near zero, agents need no memory and claim 1 reduces to a static result; if η is near zero, information does not move acceptance and H2 fails; if the fast engine cannot reproduce the network model within tolerance, the ensemble is cut to what the network model can run. Each is reported whichever way it falls.

**Tools, and the honest skill path.** Python throughout: Biogeme for estimation, the EMA Workbench for the ensemble, search and scenario discovery, OSMnx and NetworkX for networks, OR-Tools for routing checks, and NGM elasticities for the freight chains. My foundation is a logistics master from this faculty and an operations-research and programming background; I have not estimated choice models professionally, and I do not claim to. What exists is a prototype pipeline, built in preparation and with disclosed AI assistance, that runs the whole chain end to end, from estimation through the agent model to the ensemble. As a reproducibility check I estimated a standard mixed logit on the public Swissmetro stated-preference data in Biogeme (N = 6,768, 1,000 Halton draws), reproducing the published reference results (final log-likelihood −5214.9 against the reference −5215.7, rho-bar-squared 0.25); the commented code and outputs are in the project repository [evdcm]. That shows the pipeline runs on real choice data and not only on synthetic recovery, which is the honest claim; it is not a claim of prior estimation expertise. Choice-model estimation is the first named skill I deepen, in Year-1 coursework and under supervision in the Transport Research Group (TRG) at Molde University College, where the DCM and ABM tradition sits; each article names the one skill it requires and where it is learned.

**Handoff line to page 4 (print it):** → Tested where acceptance is live and freight is real.

### IMAGE — Plate P3, positioned as the page-3 hero (upper band, full width above the equations, OR right column beside eqs 1–2)
- **Keyword label on plate:** ACCEPTANCE AS ADMISSIBILITY
- **Abhinav family to pull:** past/future line chart with uncertainty band (for the three agents) + pattern-fan / convergence motif (for the instrument order).
- **Composition:** top two-thirds — three acceptance trajectories over 2026→2050 (three agents: a commuter, a firm, a low-income household), each a cream line; the band where acceptance drops below threshold λ is a red zone; the line that stays above is sage. Bottom third — an **instrument fan**: the same four instruments in two different orders, ending in two different fates (one sage "admissible", one red "inadmissible").
- **Caption (leads):** *"Same instruments, different order, different fate. The order is the finding."*
- **Narration that adds depth:**
  - Footer equation in plain words (not symbols): `acceptance next year = memory of last year + what you pay + what you were told`. (reduced form of eq. 2 — this is the depth: it decodes the equation the body prints in symbols.)
  - Threshold label: `λ — a pathway is admissible only if acceptance stays above this every year`.
  - One fan branch tagged: `charge road freight too late → window shuts`.
- **Leave out:** the full latent-variable maths. One plain sentence carries it.
- **Build note:** this is a data-driven plate — generate the trajectories from the reduced form of eq (2); build it first (with P5).

---

# PAGE 4 — Case and design

**Angle:** make it concrete and make freight unmissable. A real town charging since June 2026, a contested vote, three traceable trips (one pays, one escapes free through the tunnel, one is freight to the sea corridor), and a survey that separates persistence from information with an actual experiment. The reader (Hjelle, "where's the freight?") should feel *freight is load-bearing here, not decoration.*
**Serves the spine clause:** estimation of both passenger acceptance and carrier mode choice, on a live case.

**Body text (verbatim):**

**Why Kristiansund, and where freight enters.** Bypakke Kristiansund began collection on 1 June 2026 at two rv70 stations, Nordsundbrua and Omsundbrua, in both directions; about 70% of the package is toll-financed over up to 15 years [bypakke, innst337]. A car pays NOK 34, 27.20 with a tag, 19.04 if zero-emission with a tag [vegamot]. The council approved the basis 26 to 19 and the county 33 to 14: acceptance here is contested and live. The town sits on the Møre og Romsdal west-coast corridor, where the Ferjefri E39 programme and NGM both treat coastal short-sea shipping as the competing mode for freight bound to Oslo and the continent [ngm]. Freight is estimated here, not borrowed: a short carrier stated-choice instrument (below) gives the mode-and-timing response of hauliers to a distance charge, which the NGM chains then carry to the network. Because the heavy fleet turns over slowly and the sea alternative needs volume to stay viable, a pathway that reaches road freight with a distance charge too late closes the modal-shift window and locks the emissions in. The thesis reports the year the freight signpost must fire, estimated from carrier behaviour rather than assumed, and it is expected to fire before the passenger one, an expectation the design tests rather than a result it assumes. Delete freight and that finding, and the earliest switch in the robust pathways, disappears. Molde, with no package, is the passenger comparison town.

**Survey.** Three blocks in a Bayesian D-efficient design, priors from the pilot and the national experiment's ranges [toi2179].
- *Acceptance block* (households), information randomised in three arms: personal cost as numbers, purpose as a short narrative of what the package builds, and control. The arms test the format of information as well as its content.
- *Passenger stated-choice block:* vehicle at next replacement, crossing frequency and time, under tariff and discount levels inside national ranges, so estimates are comparable.
- *Carrier stated-choice block* (firms and hauliers on the corridor): mode (road vs coastal short-sea), route and timing under a distance charge, single wave, small targeted sample. This is the estimated freight element; it feeds A3's freight pathways and is NGM-anchored for the network.
Kristiansund carries the household and carrier design; Molde the acceptance block. Passenger wave 1 and the single-wave carrier block are fielded in month 6; passenger wave 2 in month 18 with the same households. A power analysis, reported as the minimum detectable effect rather than a bare sample size, sets the planning sample at 1,428 households in Kristiansund and 714 in Molde, with a small carrier sample sized for the main mode-choice effect, allowing for attrition.

**Hypotheses.** H1: acceptance persists once a charge is permanent (ρ > 0), tested as within-person change between waves against dose. H2: information moves acceptance independently of experience (η ≠ 0), tested by the randomised arms, turning the Norwegian correlation between information and attitude [odeck08] into a causal estimate. H3 (freight): a distance charge shifts carrier mode choice toward short-sea above a threshold rate, estimated from the carrier block. The design separates persistence from information with an experiment, not with a before-period nobody collected.

**Freight fallback.** If the carrier sample under-powers, the freight arm reverts to NGM mode-split elasticities with a reported sensitivity on the key elasticity; the freight signpost is then a modelled consequence rather than an estimate, and the thesis ladder absorbs it without loss of a complete dissertation.

**Handoff line to page 5 (print it):** → And here is the three-year plan to deliver it.

### IMAGE — Plate P4, positioned as the page-4 hero (large, centre, map register; choice card + experiment strip tucked beneath it)
- **Keyword label on plate:** FREIGHT / ACCEPTANCE LIVE
- **Abhinav family to pull:** metric map register (footprints only, callout boxes with leader lines, scale bar + N arrow) — the betweenness "MOST SHARED STREET" / "PINCH POINT" family. No windows, no trees.
- **Composition:** Kristiansund footprints on charcoal, buildings tinted by toll exposure — teal (a free route exists via the tunnel), amber (partial), red (every trip pays). Three traceable trips drawn solid and offset: trip 1 pays at Nordsundbrua, trip 2 runs free through the Atlantic Tunnel, trip 3 to the freight corridor. Callout boxes (dark fill, cream border, leader to a point): A Nordsundbrua, B Omsundbrua, C the free tunnel, D the road-to-sea corridor. Built from the real OSM graph.
- **Caption (leads):** *"The toll is not one price. It is a map of who can avoid it."*
- **Narration that adds depth:**
  - Callout C: `Article 1 counts the share of trips avoiding both stations ([N1]) — exposure measured, not assumed`.
  - Callout D (freight): `road-to-sea corridor — the heavy-vehicle signpost is expected to fire before the passenger one`.
  - Tariff tag near A: `34 kr · 27.20 tag · 19.04 zero-emission = 30% less per electric crossing`.
  - Scale bar `0 / 500 / 1000 m`, N arrow top-right.
- **Leave out:** terrain prettiness, 3D buildings. Flat footprints, honest.
- **Build note:** built from the real Kristiansund OSM graph (OSMnx) — this is a run, not a drawing.

---

# PAGE 5 — Plan, robustness and receipts

**Angle:** close the loop and prove deliverability. Price the compute honestly, show the fidelity benchmark (and where the fast engine *breaks*, which is why robust paths are re-checked), lay out the article timeline, and show the thesis survives even if the survey fails. End on receipts: every number traces to a tagged commit. The reader should feel *this will finish in three years and I can audit every claim.*
**Serves the spine clause:** robust search + signposts, delivered and reproducible.

**Body text (verbatim):**

**The ensemble and the search, priced.** The robust search explores on the order of 10⁴ candidate pathways, each scored against a Latin-hypercube sample of futures, with the surviving robust set re-checked on the full 10³ futures: a few million fast-engine evaluations in total. Each evaluation advances a zonal state to 2050, about 25 ms, so the budget is roughly 40 to 150 CPU-hours, embarrassingly parallel and well inside a desktop over a weekend. The fast engine's fidelity to the network model is measured, not assumed: a prototype benchmark on the real OpenStreetMap graphs of Molde and Kristiansund reproduces static-network car travel times per zone pair within about 15% mean absolute error (r 0.73 to 0.84), underestimating total vehicle-minutes by roughly 14%, at three to four orders of magnitude less compute [evfid]. That is the regime the design relies on: the fast engine ranks pathways across the ensemble, the robust set is re-checked on the network model, and above a stated tolerance the future sample is widened and the pathway set reduced. A dynamic cross-check against MATSim (Molde, 4,000 agents, 20 iterations) now confirms this regime: at free flow the fast engine matches MATSim car travel times to about 19% per zone pair (r 0.74) and the static assignment matches MATSim to 6% (r 0.999); under a tenfold capacity squeeze the free-flow engine breaks down, as such engines must, which is exactly why robust pathways are re-checked on the network model [evfid]. Futures vary vehicle costs, incomes, energy prices, the timing of national reform and the threshold λ within ranges anchored on observed votes. Passenger and freight vehicles carry class-specific load factors and empty running from NGM, which is what makes this a logistics question as well as a passenger one.

| Article | Submit | Question | Data | Fieldwork |
|---|---|---|---|---|
| A1 Choice estimated: household acceptance and carrier mode choice | Month 14 | RQ1 | Wave-1 households and the carrier block; recovery and fidelity tests; fleet hindcast 2010–2025 | Yes (wave 1 + carrier) |
| A2 Acceptance that persists | Month 26 | RQ2 | Both household waves | Yes (wave 2) |
| A3 Robust passenger and freight pathways | Month 34 | RQ3 | The ensemble; estimated carrier choice (NGM fallback); dated events | Partly |

**Calendar.** Before the start, the survey instruments are designed and the SSB and RVU microdata applications are filed in week 1, since they run for months and must not sit on the critical path. Months 1 to 3: coursework begins, including philosophy of science; the Sikt notification is filed through the supervisor; the pilot runs with Norwegian-speaking co-authors. Month 6 household wave 1 and the single-wave carrier block · month 14 A1 · month 18 wave 2 · month 26 A2 · month 34 A3 · months 34 to 36 the summary chapter. Articles are pipelined, not serial: A1 is under review while A2 runs.

**A thesis that survives a failed survey.** Level 1, no new data: A1 on national ranges and A3 on NGM elasticities, freight included, are a thesis. Level 2, wave 1 plus the carrier block: adds H2, a cross-sectional A2, and estimated freight (H3). Level 3, both household waves: adds H1 and the dynamic persistence term, the stretch. Each level is a complete dissertation; the survey raises its ceiling. The guaranteed spine is my own collected survey, under my control; the national microdata and model runs are complements, not dependencies. The language-model coding of the public record is moved to the portfolio as supporting continuity, not a thesis dependency.

| Risk | Trigger | Response |
|---|---|---|
| Low response | Wave 1 below planned power | Commercial panel top-up; Level 2 holds |
| Attrition | Wave 2 retention below plan | Sample sized for it; H1 reported with its detectable effect |
| No microdata by month 6 | No agreement | Published ranges and NGM elasticities; the spine is the own survey |
| Carrier sample under-powers | Freight block below its detectable effect | Revert the freight arm to NGM elasticities with a reported sensitivity; thesis ladder holds |
| Engine diverges from network model | Fidelity error above tolerance | Larger network subset, fewer pathways |
| Language | Pilot comprehension issues | Instrument in English, translated and piloted with Norwegian-speaking co-authors |

**Why here.** TRANSPLAN's backcasting and its call for realistic, goal-directed plans [toi2172]; Molde's strength in stated choice and transport economics and the DCM and ABM tradition already in the Transport Research Group (TRG) at Molde University College, where I would be supervised; and a Logistics programme where freight vehicle classes belong. Partners as possibilities, not agreements: TØI for the national experiment's ranges and NGM, CICERO for climate-policy acceptance, the Norwegian Computing Center for surrogate methods.

**Receipts and open science.** Every number this proposal computes traces to a tagged commit, with 87 automated tests, and the figures are generated from the same code. Code is released openly and anonymised survey data deposited under FAIR principles once Sikt allows. The survey is notified to Sikt with informed consent; traffic data are used as aggregate station counts only. The use of AI tools in preparing this proposal is disclosed in the supplement.

**Dissemination.** Three journal articles (A1 to A3), one Norwegian-language popular piece in *Samferdsel* in year 3, and presentation at the annual NORS (Norwegian Operational Research Society) conference, where I have presented before (my MSc work, VERA-SNARK, and OR papers). The aim is a Norwegian research presence and a direct line to TRANSPLAN's agency partners.

**Handoff line / ring close (print it):** → The signpost that warns a path is failing is the same mechanism page 1 showed already happening. The ring closes.

### IMAGE — Plate P5, positioned as the page-5 hero (upper-right, with the signpost strip and receipts strip running beneath)
- **Keyword label on plate:** ROBUSTNESS / REGRET / RECEIPTS
- **Abhinav family to pull:** Pareto scatter with selected point (dotted ghost = dominated, solid = front, circled "selected" + dashed crosshairs, curved trade-off arrow). This is the canonical Abhinav diagram.
- **Composition:** x = share of 10³ futures meeting all three 2050 targets; y = acceptance margin. Failing pathways as red ghost dots, robust set in sage, the chosen pathway circled in terracotta with dashed crosshairs to both axes. A curved arrow: `more ambition = less margin`. Below, five chosen paths A–E drop into a thin strip where their passenger and freight **signposts** sit as stations on a line. A small **receipts strip** along the bottom edge.
- **Caption (leads):** *"Robust is not optimal. It is the path that still works when the future refuses to cooperate."*
- **Narration that adds depth:**
  - Selected-point label: `chosen: survives the widest shift in λ`.
  - Axis depth note: `y = acceptance margin — the largest rise in the threshold a path survives, reported as a result`.
  - Receipts strip (the systems-thinking proof, lettered small): `choice pipeline reproduced on real Swissmetro data (LL −5214.9)` · `fast engine within ~15% of the network model` · `87 tests, traceable to commit`.
- **Leave out:** a second chart. One scatter, one strip.
- **Build note:** data-driven — from the prototype ensemble output. Build first (with P3).

---

## PLATE BUILD ORDER & SLOTS (summary for the builder)
Build data-driven first, then the hand-drawn scenes:
1. **P5** robust front (Pareto scatter + selected point) — page 5 hero.
2. **P3** what memory does (acceptance trajectories + instrument fan) — page 3 hero.
3. **P2** the engine (exploded DCM→ABM→futures→MORDM→signposts) — page 2 centre-right.
4. **P1** one place, two answers (equilibrium vs household-over-time) — page 1 hero.
5. **P4** who pays depends on where you live (Kristiansund toll-exposure map) — page 4 hero.
Plate A (the motion exhibit) already exists; keep it as the screen-only exhibit after sheet 5.

| Plate | Page / slot | Abhinav family to search your set for |
|---|---|---|
| P1 | p1 hero, lower-right | split before/after panel + scene-register household/street |
| P2 | p2 centre-right | staged pipeline OR context-tensor isometric stack |
| P3 | p3 hero, upper band | past/future line chart w/ uncertainty band + pattern fan |
| P4 | p4 hero, centre map | metric/Space-Syntax street map, footprints + callouts + scale bar |
| P5 | p5 hero, upper-right | Pareto scatter with selected point + crosshairs |

---

## TOOLCHAIN STRIP (print on the page — honest)
- **Computation (all real, in repo):** Python — Biogeme (choice estimation), EMA Workbench (ensemble, ε-NSGA-II/MORDM, PRIM), OSMnx + NetworkX (OSM road graphs), OR-Tools (routing checks), MATSim 2024.0 (dynamic cross-check), NGM elasticities (freight).
- **Visual composition:** plates computed in Python (the `visual-narrative` skill), then composed in **Rhino + Grasshopper** (Heron for geo-referencing, Blender for render) for the scene plates. **CONDITION:** keep the Rhino/Grasshopper line only if Arshad does that composition himself (`make_rhino.py` exports Kristiansund to `.3dm`). If not, change the line to "drawn in Python/SVG" — never claim a tool that was not used.
- **Evidence:** Swissmetro estimation and the two-engine + MATSim fidelity benchmarks are runnable in the repo.
- **Repo link (footer):** github.com/Astheno-sphere/computational_logistics

---

## REPO AS AN EXPERIENCE (the `main` README landing — for the panel)
Make `main`'s top-level `README.md` a guided landing, not a raw file list:
1. One-paragraph pitch + the proposal link (the built HTML/PDF).
2. **"Start here"** table: Proposal → `docs/proposal/` · Evidence → `evidence/` · Skills/tools → `skills/` · Case data & plates → `docs/proposal/plates/`, OSM graphs.
3. **Evidence you can run** — three bullets, headline number + exact reproduce command: Swissmetro (`evidence/dcm-swissmetro`, LL −5214.9), static fidelity (`evidence/fidelity-benchmark`, ~15%), MATSim dynamic (`evidence/fidelity-benchmark/matsim`, ~19% free-flow, breaks under congestion).
4. **The skills** — one line each (abm-transport, osm-network, dcm-estimate, dmdu-explore, opt-model, vrp-solve, visual-narrative…), so breadth reads as a system.
5. A short "how to read this repo" note + the test badge (87 tests).

---

## GIT ASSEMBLY (delete NOTHING)
- Keep ALL branches as the record: `clever-bell-tctxe3` (v4.5), `lucid-galileo-3ss28v` (v5.5 + plates + notes), `dcm-swissmetro-evidence`, `matsim-bridge`, `fervent-noether` (Pages), `main`.
- Build final plates on `lucid-galileo` (or a fresh `v5.5-final` off `main`), then open ONE PR into `main`. `main` becomes the clean front door: v5.5 proposal + plates + evidence + guided README.
- Tag the submission commit (e.g. `v5.5-submission`); if branch/tag push is refused by the proxy, pin the receipt to the commit hash.
- Arshad reviews and merges; the AI does not merge to `main` itself.

## ACCEPTANCE CHECKS before "done"
- Five plates in their frames, Abhinav-consistent, each with keyword + caption; Plate A exhibit intact.
- `[N1]` and `[to confirm]` still present (not fabricated); every number traces to a repo file or verified source.
- Tests pass (report count); nothing deleted; all branches still on the remote.
- README landing renders as a guided tour; GitHub link in the proposal; toolchain line honest about Rhino/Grasshopper.
- One PR into `main`, reviewable by diff; submission commit tagged or hash-pinned.

---

# PAGE 6 — References (verbatim; separate sheet from the five-page body)

Status: all cited sources verified against primary sources as of 2026-10-17. [VERIFIED] confirmed; [STANDARD] well-known method reference. A few verified entries still need a field completed before submission (noted inline).

**Verified**
- [toi1819] Flügel, S., Madslien, A., Hulleberg, N., Steinsland, C., Johansen, B. G. (2021). *A forward-looking perspective on Norwegian transport models*. TØI report 1819/2021. Institute of Transport Economics, Oslo. [VERIFIED]
- [toi2172] Tveter, E. et al. (2026). *Veivalg for en realistisk og målrettet transportplan*. TØI report 2172/2026. Institute of Transport Economics, Oslo. [VERIFIED]
- [lepira] Le Pira, M., Marcucci, E., Gatta, V., Inturri, G., Ignaccolo, M. (2017). Integrating discrete choice models and agent-based models for ex-ante evaluation of stakeholder policy acceptability in urban freight transport. *Research in Transportation Economics* 64, 13-25. [VERIFIED]
- [fuhrer] Führer, d'Hont, Rouwette, Kwakkel (2025). *Transportation Research Interdisciplinary Perspectives*, vol. 34, 101683 [volume to confirm]. DOI 10.1016/j.trip.2025.101683. [VERIFIED — DOI]
- [tramodsim] Flügel, S., Flötteröd, G., Ringdal, M., Weber, C. (2023). *TraModSim*. TØI report 1993/2023. Institute of Transport Economics, Oslo. [VERIFIED]
- [ngm] Madslien, A., Hovi, I. B., et al. *Nasjonal godstransportmodell* — the national freight transport model, documented in TØI report 1247/2012 (model introduction), with the logistics cost-model update *Kostnadsmodeller for transport og logistikk, basisår 2021* (2022). Commodity-flow matrices, transport-chain costs, port-efficiency classes. [VERIFIED]
- [shaabani] Shaabani, H., Hvattum, L. M., Laporte, G., Hoff, A. (2024). Stability metrics for a maritime inventory routing problem under sailing time uncertainty. *EURO Journal on Transportation and Logistics* 13, 100146. DOI 10.1016/j.ejtl.2024.100146. [VERIFIED]
- [evdcm] Abbasia, A. A. (2026). Swissmetro mixed-logit reproduction, Biogeme 3.3.5, N = 6,768. Project repository, `evidence/dcm-swissmetro`. [VERIFIED]
- [evfid] Abbasia, A. A. (2026). Zonal-versus-network fidelity benchmark, Molde and Kristiansund OSM graphs, about 15% MAPE. Project repository, `evidence/fidelity-benchmark` (commit 879c37a). [VERIFIED]
- [klimalov] Lov om klimamål (klimaloven), LOV-2017-06-16-60. Norwegian Climate Change Act; 2050 target of 90-95% emission reduction versus 1990. [VERIFIED]

**Standard methods**
- [wooldridge] Wooldridge, J. M. (2005). Simple solutions to the initial conditions problem in dynamic, nonlinear panel data models with unobserved heterogeneity. *Journal of Applied Econometrics* 20(1), 39-54. [STANDARD]
- [mordm] Kasprzyk, J. R., Nataraj, S., Reed, P. M., Lempert, R. J. (2013). Many objective robust decision making for complex environmental systems undergoing change. *Environmental Modelling & Software* 42, 55-71. [STANDARD]
- [prim] Friedman, J. H., Fisher, N. I. (1999). Bump hunting in high-dimensional data. *Statistics and Computing* 9(2), 123-143. [STANDARD]
- [haasnoot] Haasnoot, M., Kwakkel, J. H., Walker, W. E., ter Maat, J. (2013). Dynamic adaptive policy pathways: a method for crafting robust decisions for a deeply uncertain world. *Global Environmental Change* 23(2), 485-498. [STANDARD]
- [dapp] Same work as [haasnoot] (Dynamic Adaptive Policy Pathways). Merge into one key, or cite Walker, Haasnoot, Kwakkel (2013), *Sustainability* 5(3), 955-979, for adaptive policymaking. [STANDARD]
- [hybridaccept] Method anchor: Ben-Akiva, M. et al. (2002). Hybrid choice models: progress and challenges. *Marketing Letters* 13(3), 163-175. The text implies a road-pricing application of latent-variable choice; one such application paper should be chosen (candidate lead: Hess and Börjesson, CTS Working Paper 2016:24, not checked). [STANDARD]

**Norwegian and empirical sources (verified 2026-10-17 against primary sources)**
- [svv25] Statens vegvesen (2026). *Bompengerapport 2025*. Toll revenue about NOK 16.8 billion in 2025, roughly 62% in city packages. [VERIFIED]
- [dok15] Statens vegvesen, *Bompengerapport 2025*, Tabell 38: toll-company debt NOK 77.9 billion at end-2025 ("about NOK 78 billion" is a fair rounding). [VERIFIED]
- [snl19] Official result, Bergen municipal election 2019 (valg.no / SSB): Folkeaksjonen nei til mer bompenger (FNB) 16.7%, 11 seats. [VERIFIED] (SNL states 16.9%; the body cites the official 16.7%, the harder source.)
- [vegamot] Vegamot AS, Bypakke Kristiansund tariff: NOK 34 standard, 27.20 with tag, 19.04 zero-emission with tag; rv70 stations at Nordsundbrua and Omsundbrua; collection from 1 June 2026. (Base 32/64 kr in 2023-prices per Prop. 87 S.) [VERIFIED]
- [bypakke] Bypakke Kristiansund: adopted by Kristiansund city council 18 April 2024 (26-19), approved by the Storting 3 June 2025; about NOK 2.2 billion (2025-prices), 21 measures, tolling up to 15 years. [VERIFIED]
- [innst337] Innst. 337 S (2024-2025), Innstilling fra transport- og kommunikasjonskomiteen om Prop. 87 S (2024-2025), Utbygging og finansiering av Bypakke Kristiansund i Møre og Romsdal. Storting, 3 June 2025. [VERIFIED]
- [toi2179] *Acceptance of distance-based road pricing: evidence from a national choice experiment and a field trial in the Oslo region*. TØI report 2179/2026. Institute of Transport Economics, Oslo. [VERIFIED] (add author list from the toi.no record)
- [odeck08] Odeck, J., Bråthen, S. (2008). Travel demand elasticities and users' attitudes: a case study of Norwegian toll projects. *Transportation Research Part A* 42(1), 77-94. [VERIFIED]
- [borjesson16] Börjesson, M., Eliasson, J., Hamilton, C. (2016). Why experience changes attitudes to congestion pricing: the case of Gothenburg. *Transportation Research Part A* 85, 1-16. [VERIFIED]

**New citations, one line each on why each earns its place:** [toi1819] mandate for dynamic models beside NTM6/RTM · [toi2172] TRANSPLAN's "realistic" frame · [ngm] the national freight model · [tramodsim] Norwegian MATSim agent assignment · [hybridaccept] latent-variable acceptability method · [fuhrer] the nearest neighbour, out-positioned · [klimalov] the 2050 target · [shaabani] robustness-as-metric (Hoff lineage) · [evdcm]/[evfid] the in-repo evidence.
