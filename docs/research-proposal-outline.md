# Research proposal outline (for the applicant to write in their own words)

Target: PhD position at Molde University College, Faculty of Logistics, linked to TRANSPLAN (Norwegian
Centre for Sustainable Transport Planning). The call asks for a 3-5 page proposal for a dissertation of
3-4 publishable articles on *modelling future desirable transport scenarios under deep uncertainty*,
integrating strategic transport models such as discrete choice modelling (DCM) with agent-based
modelling (ABM), supporting scenario-based planning and backcasting towards a low-carbon society in 2050.

This outline maps the call to a research design and to what this repository already demonstrates.
Everything in the repository runs on synthetic data; the proposal should say so and describe the
real data it would use. **Write the proposal yourself**: committees assess your thinking, and most
programmes expect disclosure of AI assistance.

## 1. Working title
For example: *Robust pathways to low-emission mobility: coupling discrete choice and agent-based models
for exploratory scenario analysis and backcasting*.

## 2. Problem and gap (about 1 page)
- Long-range transport planning to 2050 faces deep uncertainty: technology costs, behaviour, telework,
  demography, policy acceptance. A single forecast is not a sound basis for decisions.
- Strategic models (DCM-based) represent choices well at a point in time but are rarely run across
  thousands of futures; ABMs capture dynamics and interaction (diffusion, congestion feedback) but often
  rest on weakly estimated behaviour.
- Gap to argue (support with literature you have read; the theory funnel in `docs/THEORY.md` maps it): few frameworks combine *estimated* behaviour,
  agent dynamics and exploratory modelling in one reproducible loop that also supports backcasting.

## 3. Aim and research questions
Aim: a modelling framework that identifies policy pathways robust across plausible futures for a
low-emission transport system in 2050.
- RQ1 (behaviour): how do travellers trade off time, cost, reliability and vehicle technology, and how
  heterogeneous and transferable are these preferences?
- RQ2 (coupling): how can estimated choice models drive an ABM so that micro-behaviour, diffusion and
  network feedback stay consistent, and how should the coupled model be calibrated and validated?
- RQ3 (exploration): which combinations of uncertainties make low-emission targets unreachable, and
  how robust are policy packages across them?
- RQ4 (backcasting): starting from desirable 2050 outcomes, which policy sequences and milestones keep
  the target reachable, and when must decisions be taken?

## 4. Articles (3-4)
| # | Article | Methods | Repository starting point |
|---|---|---|---|
| A1 | Mode and vehicle-technology choice with taste heterogeneity | MNL, nested and mixed logit on revealed and stated data; value of time; transferability tests | `skills/dcm-estimate` (MNL, Biogeme + independent MLE, parameter covariance) |
| A2 | Coupling estimated choice models into an agent-based model | DCM-driven ABM, EV diffusion with peer effects, congestion feedback, calibration to base-year shares, validation | `skills/abm-transport` (calibration, policy ramps, tested responses) |
| A3 | Exploratory modelling and scenario discovery for 2050 targets | ensembles over deep uncertainties incl. behavioural parameter uncertainty; robustness metrics; PRIM; global sensitivity (Sobol) | `skills/dmdu-explore` (EMA Workbench, PRIM, robustness) |
| A4 | Backcasting and adaptive policy pathways | backcasting from targets; lever conditions; milestones; adaptive pathways with signposts and triggers; engagement with transport agencies | `dmdu-explore.backcast` (lever conditions, milestones) |

## 5. Data (to be confirmed with supervisors and TRANSPLAN partners)
- Revealed travel behaviour: Norwegian national travel survey (RVU).
- Stated-choice survey designed in A1 (efficient design; vehicle technology, pricing, telework).
- Networks and supply: OpenStreetMap, NVDB (Statens vegvesen road database), Entur GTFS, Kartverket
  elevation data.
- Population and fleet: Statistics Norway (SSB) population and vehicle registers.
- Existing strategic models used by Norwegian transport agencies, for comparison and calibration targets.

## 6. Methods and validation principles
- Two independent estimators for every choice model; synthetic-data recovery tests before real data.
- ABM calibrated to observed base-year shares, validated on held-out indicators (e.g. trend in EV
  fleet share), with common random numbers when comparing policies.
- Uncertainty ensembles reported with target, ensemble size and seeds; every figure reproducible from
  a script (as in `examples/transplan_study.py`).

## 7. Work plan (3 years)
| Period | Work |
|---|---|
| Months 1-6 | Literature review; data access; stated-choice design; extend estimation to nested/mixed logit |
| 6-15 | A1 data collection and estimation; ABM extension to the case region; A1 submitted |
| 15-24 | Coupled model calibration and validation; A2 submitted |
| 24-32 | Exploratory modelling at scale (cluster), scenario discovery; A3 submitted |
| 32-36 | Backcasting and pathways with stakeholders; A4; thesis synthesis |

## 8. Contribution
Methodological: a reproducible DCM-ABM-DMDU loop with estimation uncertainty carried into scenario
analysis. Practical: decision support that identifies robust policy packages and milestones rather than
a single forecast.

## 9. Evidence of readiness (what to point the committee to)
- Working, tested prototypes of each step (`python -m pytest tests`, 74 tests).
- System, agent-tier and theory-funnel diagrams on the research atlas (`docs/index.html`).
- `examples/transplan_study.py`: estimation → ABM → 1,500-run ensemble → robustness, PRIM, backcasting.
- Clear statement of limits: synthetic data, illustrative parameters, compact ABM.
