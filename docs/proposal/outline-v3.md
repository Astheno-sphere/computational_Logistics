# Outline v3.1

**Question.** Which road-pricing instruments survive Norway's electric fleet and the people who must accept them, and in what order should a realistic plan introduce them?

**Candidate.** Arshad Akhtar Abbasia. PhD in Logistics, Molde University College, within TRANSPLAN (articles map to research areas 3, 2 and 1).

## Why it matters (Norway)
- Tolls raised a record NOK 16.8 bn in 2025 (preliminary), about three kroner in five from city packages, and toll companies carried about NOK 78 bn of debt (Vegvesen; Stortinget Dok. 15 answer).
- The fleet is turning electric and electric cars pay reduced rates (in the Kristiansund package NOK 19.04 against 27.20 with a tag, Vegamot), so the emissions rationale fades and the revenue base erodes. The national distance-based charge meant to replace fuel taxes has stalled.
- Every instrument needs acceptance: the 2019 toll protest won 16.7% in Bergen. Evidence on how acceptance moves is contested: experience in a randomised Oslo field trial changed attitudes little (TØI 2179/2026), yet the share positive to tolls rose after Oslo's 2019 restructuring (TØI 2141/2026), and Gothenburg's rise is attributed partly to status quo bias.
- National models (NTM6, RTM) compute equilibria, not the path between them, and do not carry acceptance.

## Design
- **Test bed: Kristiansund.** A city package with two toll stations on rv. 70, charging both ways, approved by the city council 26 to 19 (April 2024, technical basis) and the county council 33 to 14 (June 2024), and approved on an official traffic and revenue forecast. Start of collection in 2026 to be confirmed.
- **Control: Molde.** Similar town without the package; commuting between the towns checked for crossings of the new stations.
- **Reach.** The model is transferred to Molde with a stated transfer error. National implications are argued through the national question and TØI's national evidence, not modelled for every town.

## Three contributions, three articles
1. **What moves acceptance (A1).** Wave 1 in both towns: stated choice with randomised information treatments (personal cost, where the revenue goes, fairness framing). The treatments carry the causal claim. Inside Kristiansund, exposure is measured by how often a respondent crosses the stations, checked against toll passages by station, giving a dose-response estimate of experience. Wave 2: the same Kristiansund respondents twelve months later, a core part of the design, so the effect of living with the charge is estimated within persons. If collection has not yet started when wave 1 runs, Molde becomes a difference-in-differences control. The town contrast alone is reported as descriptive. Hybrid choice model for trust and fairness. A1 is submitted on wave 1; wave 2 feeds A2.
2. **An engine of households and vehicle classes (A2).** Households carry their car, trips and opinion. Opinions update each year by the rule estimated in A1 (information effects from wave 1, the within-person change from wave 2). Vans and lorries are agents that renew their fleets with the same turnover machinery, calibrated to the register's van and lorry fleet and to toll passages by class. Fleet turnover is calibrated to the vehicle register and checked against BIG; zones come from RTM. Each year: toll revenue against debt service, emissions well to wheel with vehicle production as a per-vehicle charge at purchase, who pays (residents, commuters from outside the town, firms) and support. Validation: the engine and the official forecast are both scored against observed counts after opening (Welde, Tveter and Odeck 2019; Tveter, Welde and Odeck 2025), acknowledging that a short window misses long-run drift; and a 2010 to 2025 history test of fleet turnover. Transfer to Molde without re-estimation.
3. **A robust order of instruments (A3).** A pathway orders up to three of four instruments (package revision, change of the electric-car rate, a distance-based charge, earmarking of revenue), each switch triggered by one signpost threshold, giving about 200 candidate pathways. Each is run in 10^3 futures with five repeated runs: 10^6 engine runs, about 28 CPU hours at the prototype's 0.1 s per run, before a many-objective search refines the best region. Institutional responses are deep uncertainties: the acceptance threshold θ is sampled within a range anchored on observed Norwegian toll decisions and protest votes; electric-car rate rules, state funding and reform timing are sampled too. A pathway fails politically when support falls below θ, and financially when revenue stays below debt service for three consecutive years. The search maximises the share of futures that reach the 2050 target without an unrecovered failure, reporting switches and public cost. Signposts are scored for lead time and false alarms on held-out futures.

## What is new and what is application
- **New.** (1) Acceptance as a formal constraint in the robust search for instrument sequences. (2) Experience and information effects on acceptance separated in a live toll case, within persons, against contested Norwegian evidence.
- **Application.** Agent-based fleet turnover, distribution reporting, robust-decision machinery, forecast-versus-reality evaluation, hindcasting, transfer between towns.
- **Nearest work.** BIG (Fridstrøm et al. 2016); Le Pira, Marcucci and Gatta 2017; Edmondson et al. 2025 (policy sequencing for durability); Haasnoot et al. (adaptive pathways); Ciccone et al. 2026 (TØI 2179); Welde, Tveter and Odeck 2019; Tveter, Welde and Odeck 2025.

## Data
Two survey waves (about 800 in wave 1 across both towns; Kristiansund panel in wave 2); vehicle register (cars, vans, lorries); national travel survey; Statistics Norway grid and commuting tables; NVDB; trafikkdata.no counts before and after opening; toll passages aggregated by station, hour and class (no personal data); the package's official forecast; Entur GTFS; NOBIL.

## Feasibility
Working prototype of the chain, to be retargeted to toll revenue, vehicle classes and support. Year 1: wave 1 and A1, engine retargeted. Year 2: wave 2, calibration, validation, transfer, A2. Year 3: pathways, A3, thesis.
