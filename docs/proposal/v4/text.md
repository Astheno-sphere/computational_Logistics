# Proposal v4.3, Stage A: text only (typeset in src/a3v4.html with eight visuals)

Status: v4.2 plus the additions that earn their place (preliminary finding, model box, named
instruments, defined targets, one household through time, falsification, tools, open science, fit).
v4.2 kept in `snapshots/`. Figures reduced to four, each carrying one decisive sentence. Square
brackets are reference keys. `[N1]`, `[n]`, `[FID]`, `[SHA]`, `[TESTS]` are numbers still to compute;
`[CHECK: ...]` must be verified or removed before submission. Target length about 2,900 words.

## The story in one line per page

1. The path to 2050 is decided by things an equilibrium cannot carry, and road pricing shows it now:
   I have already measured how fast the toll base is eroding.
2. TRANSPLAN backcasts from 2050; this PhD adds the uncertainty, the people and the warning signals,
   in three claims that can each fail.
3. Here is the model, written down: what each agent remembers, which instruments a pathway is made
   of, and what "desirable" means in numbers.
4. Kristiansund is where acceptance is live: who pays, who can go around, and an experiment that
   separates persistence from information.
5. Three years, four articles, a thesis that survives a failed survey, and every number traceable.

---

**From end states to pathways**
*Estimated acceptance, agents with memory, and robust road-pricing paths to a low-carbon Norway in 2050*

Arshad Akhtar Abbasia. Research proposal for the PhD position in Transport Modelling for
Sustainability Transitions (TRANSPLAN), PhD programme in Logistics, Molde University College.

## Page 1. The problem, and what already exists

Norway plans its transport system with strategic models that compute an equilibrium for a chosen
year. Asked what 2050 looks like under a set of assumptions, they give a careful answer. Asked how
the country gets there, and which routes fail on the way, they are silent by construction. The path
is governed by things an equilibrium does not carry: a vehicle fleet that turns over slowly, public
acceptance that persists or erodes, and debt that must be repaid on a schedule.

Road pricing shows the problem in its sharpest form. It is the first lever proposed for the next
National Transport Plan, as a way to use existing capacity before building more [toi2172], yet the
national reform has stalled [wps]. Tolls raised NOK 16.8 billion in 2025, about 62% of it in city
packages, against toll-company debt of about NOK 78 billion [svv25, dok15]. Every revision of a toll
meets a public that has voted against tolls before: in 2019 a party with a single anti-toll demand won
16.7% in Bergen [snl19]. Whether a plan for 2050 is feasible depends on the order in which instruments
arrive and on whether people accept each step. That is a question about paths.

> **Main question.** Which sequences of road-pricing instruments reach a desirable 2050 on emissions,
> finance and accessibility while staying acceptable to the people who pay, across deep uncertainty;
> and which signals should tell planners when to switch?
>
> **RQ1, method (A1).** How can estimated choice models drive agents that carry state from year to
> year, so that strategic end states become pathways?
>
> **RQ2, behaviour (A2).** Does acceptance persist once a charge is permanent, and does information move
> it independently of experience?
>
> **RQ3, planning (A3).** Which pathways are robust, what margin of acceptance does each survive, and
> which signposts give lead time before a pathway fails?

**What already exists.** I have built a working prototype of the method, and it already gives a first
result. At the Kristiansund tariff, a zero-emission car with a tag pays NOK 19.04 against NOK 27.20,
so each electric crossing brings in NOK 8.16, or 30%, less [vegamot]. At today's national share of
four electric passings in ten [svvev], a crossing already earns 12% less than it would in a fossil
fleet; in an all-electric fleet it earns 30% less, while the debt stays the same. The prototype also
recovers known choice parameters from simulated survey data with relative bias below 3% and coverage
of 92 to 98% at two standard errors, and holds the road networks of both towns. The question is no
longer whether the toll base erodes, but which path through that erosion people will accept.

*Figure 1: one household, two answers. Left: the strategic model's 2050, one settled state. Right:
the same household year by year, its car turning electric, its toll bill and its acceptance
changing, and the branches that survive. People at true scale; those who pay drawn solid.*

## Page 2. Fit, gap and what is new

TRANSPLAN starts from the premise that the 2050 goals are met and works backwards to the transport
system that meets them [transplan], and earlier work shows how existing models can serve backcasting
[toi2051]. This PhD adds what that backcasting does not yet carry: deep uncertainty, the acceptance of
the people who pay, and signals that tell planners a path is failing.

| The position asks for | This proposal answers with |
|---|---|
| Desirable futures under deep uncertainty | 10³ futures, satisficing targets, and uncertainty decomposed by source (claim 2) |
| DCM integrated with ABM | Choice models estimated on survey data drive agents whose acceptance and fleet carry over from year to year (claim 1, A1) |
| Behaviour under low-carbon scenarios to 2050 | Emissions as an explicit objective; cars, vans and heavy vehicles turn over by class, with load factors and empty running |
| Backcasting and pathways, not one forecast | Targets for 2050 defined on page 3; instrument orders enumerated and tested backwards from them |
| Methodological and practical contributions | Three testable claims, and a named decision: revising the zero-emission discount and tariff (A4) |

**The gap.** Strategic models give end states, and the national fleet model gives fleets [big]; neither
carries acceptance. Norwegian agent-based work assigns car traffic with MATSim in Oslo [tramodsim] and
has demonstrated flexible tolls beyond what the regional model can represent [toi2035], but takes
acceptance as given. Le Pira, Marcucci and Gatta integrated discrete choice and agent-based models to
evaluate acceptability of urban freight policy [lepira]; their agents are stakeholder groups
negotiating in rounds, not a population living through calendar time. Adaptive pathway methods
sequence actions against tipping points [dapp, edmondson] and design signals to adapt [haasnoot], but
treat acceptance as an external scenario. The road-pricing evidence is careful and mostly static.
Across 19 Norwegian toll projects, negative attitudes were strongly correlated with how little users
had been told before opening [odeck08]. Acceptance rose after Gothenburg's charge through status quo
bias [borjesson16]; concrete personal information moved support most in a national experiment while a
field trial changed little [toi2179]; positivity rose after Oslo's 2019 restructuring [toi2141].
**Nobody has estimated acceptance, carried it in agents over time, and let it decide which pathways
survive.**

**What is new.** Three claims and no others.

1. **Acceptance as an admissibility condition.** A pathway counts only if estimated acceptance stays
   above a threshold at every step; for each pathway the thesis reports the largest shift in that
   threshold it survives, its *acceptance margin*, as a result rather than an assumption.
2. **Uncertainty decomposed by source over a policy path.** The spread in 2050 outcomes is split, year
   by year, into behavioural parameters, external futures and the choice of path, so planners see
   which uncertainty more data can reduce and which only adaptation can.
3. **Signposts validated twice.** Signals that a pathway is failing are scored on held-out futures for
   lead time and false alarms, then against dated events that actually happened: the electric share
   of passings crossing thresholds, the 2019 anti-toll vote in Bergen, and Oslo's 2019 restructuring.

*Figure 2: the engine. Exploded layers: data (two waves, register, counts), estimated choice, agents
with memory, 10³ futures, pathways and signposts; each layer tagged with its article and claim, and
with the tool that runs it.*

## Page 3. The model, written down

**What each agent decides and remembers.** Each year *t*, household or firm *n* chooses a vehicle, how
often to cross and when, from an estimated choice model in which the instruments in force, *I(t)*, set
the cost:

  (1) U(n,j,t) = β · cost(j, I(t)) + θ' · x(n,j) + ε(n,j,t)

Its acceptance of the package follows a latent equation with memory:

  (2) A*(n,t) = ρ · A(n,t−1) + δ · dose(n,t) + η · info(n) + γ' · z(n) + u(n,t)

where *dose* is the toll the agent actually pays, *info* the information arm it was shown, and ρ the
memory term the two survey waves identify, from within-person change and the variation in exposure,
with the initial-conditions problem handled explicitly [wooldridge]. Estimation is mixed logit, then
hybrid choice with acceptance as the latent variable.

  (3) A pathway p is admissible if the share accepting stays at or above λ in every year; its
  acceptance margin is the largest rise in λ for which p stays admissible in the target share of
  futures.

**What a pathway is made of.** Four instruments: revision of the package, the zero-emission rate, a
distance-based charge, and earmarking of revenue. A pathway opens with one instrument and adds
others in any order, each switch fired by a signpost at one of three thresholds: 4 + 36 + 216 + 648 =
904 pathways. At that size enumeration is a choice, not a shortcut: it gives the complete front with no
search bias; a larger set would call for multi-objective search [mordm].

**What desirable means.** A pathway is robust if it meets all three targets in at least a stated share
of the 10³ futures, with regret reported alongside, and scenario discovery finds where it fails [prim].

| Target in 2050 | Metric | Anchor |
|---|---|---|
| Emissions | Well-to-wheel CO₂e from road traffic crossing the case area | National climate targets [ntp] [CHECK: target figures] |
| Finance | Toll revenue at or above debt service; failure if below for three consecutive years | Package financing [innst337] |
| Accessibility | Generalised travel cost of the lowest income quintile no higher than in 2026 | Distributional floor, stated as a design choice |

**One household through time (illustrative).** A household on Nordlandet crosses Nordsundbrua twice a
day and opposes the package in 2026. In 2029 it replaces its car with an electric one and its toll bill
falls 30%; with ρ above zero, its acceptance carries forward. In 2035 a distance-based charge removes
the discount: its bill rises, its acceptance drops, and if enough households follow, that pathway
breaks the threshold and is inadmissible unless revenue is earmarked to what they use. The same model
runs this story for every agent in every future.

**What would falsify it.** If ρ is close to zero, agents need no memory and claim 1 reduces to a static
result; if η is close to zero, information does not move acceptance and H2 fails; if the fast engine
cannot reproduce the network model, the ensemble is cut to what the network model can run. Each is
reported, whichever way it falls.

**Tools.** Python throughout: estimation in Biogeme, the ensemble and scenario discovery in the EMA
Workbench, road networks with OSMnx and NetworkX, routing checks with OR-Tools; figures composed in
Rhino and Grasshopper with Heron and Blender, a visual language that carries into storytelling with
planners in A4 [story].

## Page 4. Case and design

**Why Kristiansund.** Bypakke Kristiansund began collection on 1 June 2026 at two stations on rv70,
Nordsundbrua and Omsundbrua, charging in both directions; about 70% of the package is toll-financed
over up to 15 years [bypakke, innst337]. A car pays NOK 34, NOK 27.20 with a tag, and NOK 19.04 if
zero-emission with a tag [vegamot]. The city council approved the basis 26 to 19 and the county 33 to
14: acceptance here is contested, and live. Exposure is not uniform. Computed on the town's road network, Nordsundbrua
splits Kristiansund in two: Nordlandet holds 32% of homes and 39% of workplaces, and inside the town
its only road to the other half is the bridge. Atlanterhavstunnelen has
been toll-free since 2020, so some trips have a free alternative; computed on the road network, [N1]%
of trips can avoid both stations. The study therefore has a measured dose rather than the assumption
that everyone pays. Molde, with no toll package, is the comparison town [CHECK: older stations near
Molde]. The case is a test bed; the question and the method are national.

**Survey.** Two blocks, in a Bayesian D-efficient design with priors from the pilot and the national
experiment's attribute ranges [toi2179].

- *Acceptance block,* with information randomised in three arms: personal cost, as numbers (what the
  respondent's own crossings cost per month); purpose, as a short narrative of what the package
  builds [story]; and control. The arms test the format of information as well as its content.
- *Stated choice block:* vehicle at next replacement, crossing frequency and time of day, under
  tariff and discount levels inside the national ranges, so estimates are comparable.

Kristiansund carries the full design; Molde carries the acceptance block. Wave 1 is fielded in month 6
and wave 2 in month 18 with the same respondents. A power analysis, reported with the minimum
detectable effect rather than a bare sample size [power], sets the sample at [n]: planning figure
1,200 to 1,500 in Kristiansund and about half in Molde, allowing for attrition.

**Hypotheses.** H1: acceptance persists once a charge is permanent (ρ > 0), tested as within-person
change between waves against dose. H2: information moves acceptance independently of experience
(η ≠ 0), tested by the randomised arms; this turns the Norwegian correlation between information and
attitude [odeck08] into a causal estimate. **The design separates persistence from information with an
experiment, not with a before-period nobody collected.**

**The public record.** Consultation submissions, council debate and local press from 2019 to 2026 are
coded into acceptance arguments with a language model, validated against a Norwegian-speaking human
coder, with agreement reported. This gives the period before collection an aggregate trajectory.

*Figure 3: who can avoid the toll. Kristiansund on lit terrain; buildings coloured by exposure (teal, a
free route exists; amber, partial; red, every trip pays); callouts A Nordsundbrua, B Omsundbrua, C the
free tunnel; beneath it, one choice card and the experiment strip (waves, arms, people icons sized
from the power analysis).*

## Page 5. Plan, risks and receipts

**The ensemble.** 904 pathways across 10³ futures and repeated draws: about 4.5 million runs, about 125
CPU hours on the fast zonal engine. A network model runs a stratified subset and the error between
them is reported: [FID]. Futures vary vehicle costs, incomes, energy prices, the timing of national
reform and the threshold λ within a range anchored on observed votes. Vans and heavy vehicles carry
class-specific load factors and empty running, which is what makes this a logistics question as well
as a passenger one.

*Figure 4: the robust front. 904 pathways, acceptance margin against the share of futures meeting all
targets; failures as ghosts, robust paths in sage, the chosen one in red; five paths A to E drop into a
strip of lines with their signposts as stations.*

| Article | Submit | Question | Data | Fieldwork |
|---|---|---|---|---|
| A1 Agents with estimated memory | Month 12 | RQ1 | National ranges, vehicle register; recovery tests; fidelity; fleet hindcast 2010 to 2025 [deuten]; the package's traffic forecast checked against station counts [welde19] | No |
| A2 Acceptance that persists | Month 24 | RQ2 | Both waves; public record | Yes |
| A3 Robust pathways and their signposts | Month 32 | RQ3 | The ensemble; dated events | Partly |
| A4 (optional) Revising the zero-emission discount | Month 34 | Practice | A3 with planners | No |

**Calendar.** Before the start, the survey instrument is designed. Months 1 to 3: the 30 ECTS of
coursework begins, including philosophy of science; the Sikt notification is filed through the
supervisor; the pilot runs with Norwegian-speaking co-authors. Month 6 wave 1 · month 12 A1 · month 18
wave 2 · month 24 A2 · month 32 A3 · months 33 to 36 the summary chapter. [CHECK: term and coursework
against the official advertisement.]

**A thesis that survives a failed survey.** Level 1, no new data: A1 and A3 on national ranges are a
thesis. Level 2, wave 1: adds H2 and a cross-sectional A2. Level 3, both waves: adds H1 and the
estimated memory term. Each level is a complete dissertation; the survey raises its ceiling.

| Risk | Trigger | Response |
|---|---|---|
| Low response | Wave 1 below planned power | Commercial panel top-up; Level 2 still holds |
| Attrition | Wave 2 retention below planning figure | Sample sized for it; H1 reported with its detectable effect |
| No microdata access | No agreement by month 6 | Published ranges and national evidence |
| Engine diverges from network model | Fidelity error above threshold | Larger network subset, fewer pathways |
| Language | Pilot comprehension issues | Instrument written in English, translated and piloted with Norwegian-speaking co-authors |

**Why here.** TRANSPLAN's backcasting, Molde's strength in stated choice and transport economics, and a
Logistics programme where freight vehicle classes belong. Partners, as possibilities to explore and
not agreements: TØI for the national experiment's ranges, CICERO for climate-policy acceptance, the
Norwegian Computing Center for surrogate methods.

**Receipts and open science.** Every number this proposal computes traces to commit [SHA], with
[TESTS] automated tests; the figures are generated from the same code. Code is released openly and
anonymised survey data are deposited under FAIR principles once Sikt conditions allow. The survey is
notified to Sikt with informed consent; traffic data are used as aggregate station counts only. The use
of AI tools in preparing this proposal is disclosed in the supplement.

**References.** Compact list.

---

## Moved to the portfolio (continuity, not cut)

Uncertainty-decomposition figure and calendar figure; full survey skeleton and power analysis; the DCM
notebook; toolchain chapter with commands; protocols (hindcast, forecast check, signpost validation,
LLM coding); pathway enumeration maths and run budget; data-access plan; full risk register; how the
design was stress-tested (one page, attack to fix); AI disclosure and register; extra plates; CV
evidence.
