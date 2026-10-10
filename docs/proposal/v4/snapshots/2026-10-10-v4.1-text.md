# Proposal v4.1, Stage A: text only

Status: draft for the adversary pass and for Arshad's rewrite. Words only; figures are named by number
and their callout letters, and are storyboarded separately. Square brackets are reference keys
(`refs.py`). Markers: `[N1]`, `[n]`, `[FID]`, `[SHA]`, `[TESTS]` are numbers still to compute;
`[CHECK: ...]` is a fact that must be verified or removed before submission. About 2,800 words.

---

**From end states to pathways**
*Estimated acceptance, agents with memory, and robust road-pricing paths to a low-carbon Norway in 2050*

Arshad Akhtar Abbasia. Research proposal for the PhD position in Transport Modelling for
Sustainability Transitions (TRANSPLAN), PhD programme in Logistics, Molde University College.

## 1. The problem

Norway plans its transport system with strategic models that compute an equilibrium for a chosen
year. Asked what 2050 looks like under a set of assumptions, they give a careful answer. Asked how
the country gets there, and which routes fail on the way, they are silent by construction. The path
is governed by things an equilibrium does not carry: a vehicle fleet that turns over slowly, public
acceptance that persists or erodes, and debt that must be repaid on a schedule.

Road pricing shows the problem in its sharpest form. Tolls raised NOK 16.8 billion in 2025, about 62%
of it in city packages, against toll-company debt of about NOK 78 billion [svv25, dok15]. Four in ten
passings are now electric [svvev], and zero-emission vehicles pay 30% below the agreement price
[vegamot]. As the fleet electrifies, the base that repays the debt narrows, the discount has to be
revised, and every revision meets a public that has voted against tolls before: in 2019 a party with a
single anti-toll demand won 16.7% in Bergen [snl19]. Whether a plan for 2050 is feasible depends on the
order in which instruments arrive and on whether people accept each step. That is a question about
paths, and it is the question this project is built to answer.

> **Main question.** Which sequences of road-pricing instruments and discount revisions reach a
> desirable 2050, judged on emissions, finance and accessibility, while remaining acceptable to the
> people who pay, across deep uncertainty; and which observable signals should tell planners when to
> switch?
>
> **RQ1, method (A1).** How can estimated choice models drive agents that carry state from year to
> year, so that strategic end states become pathways?
>
> **RQ2, behaviour (A2).** Does acceptance persist once a charge is permanent, and does information move
> it independently of experience?
>
> **RQ3, planning (A3).** Which pathways are robust, what margin of acceptance does each survive, and
> which signposts give lead time before a pathway fails?

*Figure 1: end state and paths, one street, two answers.*

## 2. Fit, gap and what is new

The advertisement asks for six things. The design answers each with a named part of the thesis.

| The position asks for | This proposal answers with |
|---|---|
| Analysis of desirable futures under deep uncertainty | An ensemble of 10³ futures, satisficing targets, and a decomposition of uncertainty by source (claim 2) |
| Integration of strategic models such as DCM with ABM | Choice models estimated on survey data drive agents whose acceptance and fleet carry over from year to year (claim 1, A1) |
| Behaviour under scenarios for a low-carbon 2050 | Emissions are an explicit objective; cars, vans and a minimal heavy fleet turn over by vehicle class |
| Backcasting and pathways rather than a single forecast | 2050 targets taken from national plans [ntp]; instrument orders enumerated and tested backwards from them |
| Methodological knowledge | Three claims, below, each testable and each able to fail |
| Practical decision support | A named decision: the revision of the zero-emission discount and tariff (A4) |

**The gap.** Strategic models give end states, and the national fleet model gives fleets [big], but
neither carries acceptance. Agent-based models have been placed inside uncertainty studies, but they
are slow and take acceptance as given [CHECK: MATSim and eqasim references]. Le Pira, Marcucci and
Gatta integrated discrete choice and agent-based models to evaluate how stakeholders accept urban
freight policy [lepira]; their agents are few, their acceptance is evaluated rather than estimated
from a population, and it does not decide whether a long-run pathway is admissible. Adaptive pathway
methods sequence actions against tipping points [dapp, edmondson] and design signals to adapt
[haasnoot], but treat social acceptance as an external scenario. The road-pricing evidence is
careful and static: acceptance rose after Gothenburg's charge through status quo bias [borjesson16],
personal cost information moved support most in a national experiment while a field trial changed
little [toi2179], and positivity rose after Oslo's 2019 restructuring [toi2141]. Nobody has estimated
acceptance, carried it in agents over time, and let it decide which pathways survive.

**What is new.** The thesis makes three claims and no others.

1. **Acceptance as an admissibility condition.** A pathway counts only if estimated acceptance stays
   above a threshold at every step; for each pathway the thesis reports the largest shift in that
   threshold it survives, its *acceptance margin*, as a result rather than an assumption.
2. **Uncertainty decomposed by source over a policy path.** The spread in 2050 outcomes is split, year
   by year, into what comes from behavioural parameters, from external futures, and from the choice
   of path, so planners see which uncertainty more data can reduce and which only adaptation can.
3. **Signposts validated twice.** Signals that a pathway is failing are scored on held-out futures for
   lead time and false alarms, then against dated events that actually happened.

The choice models mirror the published structure of the national and regional models and are
calibrated to their elasticities, so results can be handed to the tools planners already use.

## 3. Case and design

**Why Kristiansund.** Bypakke Kristiansund began collection on 1 June 2026 at two stations on rv70,
Nordsundbrua and Omsundbrua, charging in both directions; about 70% of the package is financed by
tolls over up to 15 years [bypakke, innst337]. A car pays NOK 34, NOK 27.20 with a tag, and NOK 19.04
if zero-emission with a tag [vegamot]. The city council approved the basis 26 to 19 and the county
33 to 14: acceptance here is contested, and it is live. Exposure is not uniform. The Atlantic Ocean
Tunnel has been toll-free since 2020, so some trips have a free alternative; computed on the road
network, [N1]% of trips can avoid both stations. That gives the study a measured dose rather than the
assumption that everyone pays. Molde serves as the comparison town [CHECK: no comparable tolling in
Molde]. The case is a test bed; the question and the method are national.

*Figure 2: who can avoid the toll. Callouts A (Nordsundbrua), B (Omsundbrua), C (the free tunnel).*

**Survey.** Two blocks.

- *Acceptance block,* with a randomised information treatment in three arms: personal cost (what the
  respondent's own trips cost per month), system purpose (what the package builds), and control.
- *Stated choice block:* vehicle at next replacement, crossing frequency and time of day, under tariff
  and discount levels inside the ranges used in the national experiment [toi2179], so estimates are
  comparable.

Kristiansund carries the full design; Molde carries the acceptance block only. Wave 1 is fielded in
month 6 and wave 2 in month 18 with the same respondents. A power analysis sizes the sample at [n],
planning figure 1,200 to 1,500 in Kristiansund and about half that in Molde, allowing for attrition
between waves.

**Hypotheses.** H1: acceptance persists once a charge is permanent, tested as within-person change
between waves against exposure. H2: information moves acceptance independently of experience, tested
by the randomised arms. The design separates persistence from information with an experiment, not
with a before-period nobody collected.

**The public record.** Consultation submissions, council debate and local press from 2019 to 2026 are
coded into acceptance arguments with a language model, validated against a Norwegian-speaking human
coder, with agreement reported. This gives the period before collection an aggregate trajectory.

**Estimation.** Mixed logit first, then a hybrid choice model with acceptance as a latent variable. The
two waves identify a state-dependence term: how much last year's acceptance and exposure shape this
year's. That term is what lets agents remember.

## 4. Articles, models and calendar

**The model.** Households and firms are agents. Each year from 2026 to 2050 they choose vehicles,
crossings and timing from the estimated models, update their acceptance through the state term, and
renew their fleets by vehicle class. Toll revenue is set against debt service each year. A fast zonal
engine runs the ensemble; a network model runs a stratified subset, and the error between the two is
reported: [FID]. If the error is too large, the network subset grows and the pathway set shrinks.

**The ensemble.** 904 pathways (orders of one to four instruments, three switching thresholds each)
across 10³ futures and repeated draws: about 4.5 million runs, about 125 CPU hours on the zonal
engine. Futures vary vehicle costs, incomes, energy prices, the timing of national pricing reform, and
the acceptance threshold within a range anchored on observed votes. A pathway is robust if it meets
all three 2050 targets (emissions, debt service, accessibility for low-income households) in a high
share of futures [mordm]; scenario discovery finds the conditions under which it fails [prim].

*Figure 3: the robust front. 904 pathways; failures as ghosts; five chosen paths A to E drop into a
strip of lines with their signposts.*

| Article | Submit | Question | Data | Fieldwork needed |
|---|---|---|---|---|
| A1 Agents with estimated memory | Month 12 | RQ1 | Published attribute ranges, vehicle register; recovery tests, fidelity, fleet hindcast 2010 to 2025 as validation [deuten] | No |
| A2 Acceptance that persists | Month 24 | RQ2 | Both waves; public record | Yes |
| A3 Robust pathways and their signposts | Month 32 | RQ3 | The ensemble; dated events for signpost validation | Partly |
| A4 (optional) Revising the zero-emission discount | Month 34 | Practice | A3 results with planners | No |

**Calendar.** Before the start: the survey instrument is designed. Months 1 to 3: coursework begins,
the Sikt notification is filed through the supervisor, and the pilot runs with Norwegian-speaking
co-authors. Month 6: wave 1. Month 12: A1 submitted. Month 18: wave 2. Month 24: A2. Month 32: A3.
Months 33 to 36: the summary chapter. [CHECK: appointment length and coursework credits against the
official advertisement.]

**A thesis that survives a failed survey.** Level 1, no new data: A1 and A3 on published ranges are a
thesis. Level 2, wave 1: adds H2 and a cross-sectional A2. Level 3, both waves: adds H1 and the
estimated state term. Each level is a complete dissertation; the survey raises its ceiling.

**Partners.** TRANSPLAN brings the people this needs. Possibilities to explore, not agreements: TØI
for the national experiment's ranges and acceptance evidence, CICERO for climate-policy acceptance,
and the Norwegian Computing Center for surrogate and statistical methods.

*Figure 4: the calendar band, with the three levels.*

## 5. Contributions, risks and receipts

**Contributions.** For method: agents whose acceptance is estimated and remembered, turning strategic
end states into tested paths. For behaviour: persistence separated from information in a live,
contested case. For planning: pathways that come with an acceptance margin and with signposts whose
lead time has been measured.

| Risk | Response |
|---|---|
| Low response | Commercial panel recruitment and oversampling |
| Attrition between waves | Sample sized for it; Level 2 remains a thesis |
| No access to microdata | Published attribute ranges and national evidence |
| Fast engine diverges from the network model | Larger network subset, fewer pathways |
| Language | Instrument written in English, translated and piloted with Norwegian-speaking co-authors |

**Receipts.** A working prototype exists and every number this proposal computes traces to commit
[SHA]: [TESTS] automated tests; Monte Carlo recovery of choice parameters with relative bias below 3%
and coverage of 92 to 98% at two standard errors; a network pipeline built from OpenStreetMap for
both towns. The figures are generated from the same code.

**Ethics.** The survey is notified to Sikt with informed consent. Traffic data are used as aggregate
station counts only; no individual passages are processed. The use of AI tools in preparing this
proposal is disclosed in the supplement.

*Figure 5: what we do not know, by source. Input strip, composite to 2050, one what-if line.*

**References.** Compact list, page 5.
