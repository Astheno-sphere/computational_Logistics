# Outline v3

**Question.** Which road-pricing instruments survive Norway's electric fleet and the people who must accept them, and in what order should a realistic plan introduce them?

**Candidate.** Arshad Akhtar Abbasia. PhD in Logistics, Molde University College, within TRANSPLAN.

## Why it matters (Norway)
- Tolls raise a record NOK 16.8 bn (2025), about three kroner in five from city packages, and finance roads and public transport. Toll companies carry NOK 78 bn of debt.
- The fleet is turning electric. Electric cars pay less (30% below the agreement price in the newest package), so the emissions rationale fades and the revenue base erodes. The national distance-based charge meant to replace fuel taxes has stalled.
- Every instrument needs acceptance to survive: the 2019 toll protest won 16.7% in Bergen. The newest evidence on how acceptance moves is mixed: experience in a randomised Oslo field trial changed attitudes little (TØI 2179/2026), yet the share positive to tolls rose after Oslo's 2019 restructuring (TØI 2141/2026), and Gothenburg's rise is attributed partly to status quo bias.
- National models (NTM6, RTM) compute equilibria, not the path between them, and do not carry acceptance.

## Design
- **Test bed: Kristiansund.** A toll package on two bridges, tolling since 2026, approved by the city council 26 to 19 and approved on an official traffic and revenue forecast.
- **Control: Molde.** Similar town without the package.
- **National reach.** Results scaled to Norway's other towns of the same centrality class; national comparability through TØI's national acceptance attribute ranges.

## Three contributions, three articles
1. **What moves acceptance (A1, TRANSPLAN RA3).** A stated-choice survey in both towns with randomised information treatments (personal cost, where the revenue goes, fairness framing). In Kristiansund people are living with the charge; in Molde they are not. This separates experience from information and revenue visibility. Hybrid choice model for trust and fairness. A follow-up wave only if funding allows.
2. **An engine of households and vehicle classes (A2, RA2).** Agents carry their car, trips and opinion; vans and lorries enter from toll passages by class. Fleet turnover calibrated to the vehicle register and checked against BIG; zones from RTM. Outputs per year: toll revenue, emissions (well to wheel and vehicle production), who pays (residents, commuters from outside who cannot vote, firms) and support. Validated by reproducing traffic after opening against the approved forecast, and by a 2010 to 2025 history test. Transferred to Molde without re-estimation, then scaled by centrality class.
3. **Robust order of instruments (A3, RA1).** Which sequences of instruments (package revisions, discount changes, a distance-based charge, earmarking of revenue) stay effective, financially viable and acceptable across about 10^3 futures. Institutional responses (acceptance threshold, discount rules, state funding, reform timing) are sampled as deep uncertainties, not modelled. Decision problem: a pathway is an ordered set of instruments with switching rules; it fails politically when support falls below θ, a sampled threshold, or financially when revenue falls below debt service; the search maximises the share of futures reaching the 2050 target without unrecovered failure, reporting switches and public cost. Early-warning signposts scored for lead time and false alarms. Optional workshop with county and Vegvesen planners, tested for whether the pathways help them agree.

## What is new and what is application
- **New.** (1) Acceptance as a formal constraint in the robust search for instrument sequences. (2) A mechanism test of acceptance in a live toll case with a control town, against contested Norwegian evidence. (3) Scaling a validated household engine across Norway by centrality class.
- **Application.** Agent-based fleet turnover, distribution reporting, robust-decision machinery, forecast-versus-reality evaluation, hindcasting.
- **Nearest work.** BIG (Fridstrøm et al. 2016); Le Pira, Marcucci and Gatta 2017; Edmondson et al. 2025 (policy sequencing for durability); Haasnoot et al. (adaptive pathways); Ciccone et al. 2026 (TØI 2179); Welde, Tveter and Odeck (forecast accuracy).

## Data
Survey (about 800, both towns); vehicle register; national travel survey; Statistics Norway grid, centrality and commuting tables; NVDB; trafikkdata.no counts before and after opening; toll passages aggregated by station, hour and class (no personal data); the package's official forecast; Entur GTFS; NOBIL.

## Feasibility
Working prototype of the chain (choice model, household agents with fleet turnover, futures ensemble), to be retargeted to toll revenue and support. Year 1 survey and A1, engine retargeted in parallel. Year 2 calibration, validation, transfer, A2. Year 3 pathways, A3, thesis. Research stay at a deep-uncertainty group (to confirm).
