---
name: panel-review
description: Read the TRANSPLAN PhD proposal and portfolio as the Molde panel would, score them on a fixed rubric, and run a drift inspection before anything is shared. Use after every substantive edit to docs/proposal/src/*.html.
---

# Panel review and drift inspector

Two passes, run every time the proposal or portfolio changes. Scores are only comparable across
rounds because the rubric, the readers and the rules below stay fixed. Change them only on purpose,
and record the change in the log at the bottom.

## Pass 1: the panel

Each reader is scored 1 to 10 on five axes. Overall is the mean.

| Axis | Question the reader asks |
|---|---|
| Gets it fast | Do I know the question, the method and the payoff after the first page? |
| Hits my agenda | Does this serve what I and TRANSPLAN need? |
| Novelty I believe | Is each claim placed against the nearest work, and does it survive? |
| Feasible in 3 years | Data, survey, engine, ensemble: can one PhD do it? |
| Trust in the candidate | Do the honesty, the numbers and the prototype make me trust the person? |

### Readers (from their published work and role; never invent views)

- **Valerio Gatta**, potential supervisor. Stated choice, DCM feeding ABM (Le Pira et al. 2017;
  Gatta et al. 2020), acceptability, storytelling for consensus (Lozzi, Marcucci and Gatta 2025).
  Probes: identification of acceptance dynamics, survey design and recruitment, hypothetical bias,
  the candidate's own stated-choice experience.
- **Eivind Tveter**, TRANSPLAN coordinator at Molde. Forecast accuracy of fixed links, uncertainty in
  cost-benefit analysis, co-author of TØI 2172/2026. Probes: link to Norwegian appraisal and the
  national models (RTM, NTM6), scope versus national targets, numbers read as forecasts.
- **Harald M. Hjelle**, PhD committee chair. Comparative CO2 of transport chains, freight. Probes:
  why this is a Logistics PhD, emissions accounting, workload of each year.
- **Arild Hoff**, operations research and logistics (Shaabani, Hvattum, Laporte and Hoff 2024,
  stability). Role as dean unverified; read as the OR examiner. Probes: a well-posed decision
  problem, the choice of robustness metric and threshold, run counts and surrogates.

### Markers to report

Psychological: primacy (first two sentences), processing fluency, in-group signals (cited, not
flattered), honesty markers, concreteness, cognitive load, peak-end. Academic: one research question
per article, bounded novelty, currency of literature (2024 to 2026), feasibility evidence, ownership
(would the candidate defend every sentence aloud).

For every reader list where we impress and where we raise doubt, and for every doubt either the fix
already in the text or the exact sentence that would fix it.

## Pass 2: the drift inspector

Fail the round if any item fails. Report each with the offending text.

1. **Format.** The ranked proposal prints to at most five A4 pages including references
   (`docs/proposal/build_pdf.py`, then count pages). HTML first; the PDF is built from the HTML.
2. **Voice.** No em dashes. No filler ("delve", "crucial", "landscape", "leverage", "robust" used as
   praise, "not only... but also", triads for rhythm). First person where the candidate acts.
3. **Spine.** Five contributions (C1 path, C2 acceptance that moves, C3 three uncertainty sources,
   C4 signposts with a hit rate, C5 tested on history), three articles mapped RA3 to A1, RA2 to A2,
   RA1 to A3, A4 optional. The 2010 to 2025 historical test is one validation step, never a fourth
   article. Molde main case, Kristiansund transfer case, both "case studies, not a national sample".
4. **Numbers.** Every number in text and plates traces to `docs/proposal/study.json`,
   `docs/proposal/towns.json`, `docs/results/transplan_study.json` or a cited source. Prototype numbers
   carry "synthetic behaviour" or "prototype" nearby. Current anchors: P12 robust in 41 of 60 futures;
   19 hostile futures; 2030 gate at 63% flags 17 of 19 failures with 4 false alarms among 41;
   EV fleet share 32, 51, 75, 86% in 2025, 2030, 2040, 2050; Øvre veg 17.5%; Gomabrua 24.9%; 1,500 runs;
   87 tests. Survivors of the illustrative filter (R ≥ 0.55, median acceptance ≥ ½): P12, P21, P04, P10, P09.
   Money is NOK per commuter per year. The prototype target (20% of 2025) is looser than the Climate Change Act
   implies (about 5 to 10%); say so wherever it matters.
5. **Sources.** Do not cite Lee and Brown 2021 or "Natterer 2025" (not found). Wangsness, Proost and
   Steinsland 2026 is in *Transportation Research Interdisciplinary Perspectives* 38, 102064.
   Measured signpost detection is "mainly in water management", never "only".
6. **Plates.** Each plate shows something only this work produced, and its title names the finding
   with one accent word. Families: charcoal for places and people, oxblood for methods.
7. **Not watered down.** Each contribution still states what is new against the nearest work.

## Output

A table of scores with the previous round beside it, the impress and doubt lists, the inspector
verdict, and at most five next fixes ranked by score gain per word.

## Log

| Round | Date | Gatta | Tveter | Hjelle | Hoff | Inspector | Note |
|---|---|---|---|---|---|---|---|
| 1 | 2026-10-09 | 7.6 | 7.6 | 6.6 | 7.4 | length fail (about 8 pages) | long page, before the cut; scored by the author |
| 2 | 2026-10-09 | 7.2 | 7.2 | 6.6 | 7.4 | fail: package count 24 vs 25, plate titles, refs 22 to 24 | five-page cut; first round by independent reader agents |
| 3 | 2026-10-09 | 8.0 | 8.0 | 7.2 | 8.2 | pass | counts, τ against the Climate Change Act, held-out signposts, survey blocks, freight sentence, refs renumbered |
