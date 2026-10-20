# TRANSPLAN proposal — STATE v5.5 (2026-10-20)

Single source of truth for the written proposal. Pair with: `proposal_v5.4_content.md` (full text, carries the v5.5 re-weight), `proposal.html` (built v5.5 page), `visual_spec.md` (plate briefs), and `HANDOFF-visual-session.md` on branch `claude/lucid-galileo-3ss28v` (how plates get built).

## 0. Identity
- Position: PhD in Transport Modelling for Sustainability Transitions (TRANSPLAN), Faculty of Logistics, Molde University College. Sits in RA1 (scenarios & strategies).
- Candidate: Arshad Akhtar Abbasia. Deadline 1 Nov 2026. Eligibility CLEARED (invited to apply).
- Title: **From end states to pathways** — estimated acceptance, agents with memory, and robust road-pricing paths to a low-carbon Norway in 2050.
- Repo: github.com/Astheno-sphere/computational_Logistics.

## 1. The spine (v5.5 re-weight — the one real change from v5.4)
The empirical heart is prior to any pathway: **is public acceptance a quantity that can be estimated on real data and shown to persist (or not) over time?** The thesis answers that FIRST; the ensemble, MORDM search and robust front are what the answer is USED FOR, not the headline. This converts the proposal's central fallacy risk (elaborate machinery over a soft, assumed "acceptance") into the contribution itself. Tools, scope, claims, timeline UNCHANGED by the re-weight — only emphasis and order of framing (page 2 "empirical heart" para; claim 1 re-led; page 3 opens "everything rests on one measurement").

## 2. Honest research verdict
- Genuine, not hocus-pocus: nobody has estimated acceptance, carried it in agents over calendar time, and let it decide passenger+freight pathways; real live case; standard validated tools; two real evidence artifacts.
- The real vulnerability (named, not hidden): acceptance is latent and hard to measure; the dynamic persistence ρ is weakly identified off two waves. Mitigations: ICLV cross-section is the floor, ρ demoted to Level-3 stretch, falsification stated, robustness must be tested against the model's OWN parameters not just scenario dials.
- For a PhD specifically: clears the bar (sound, feasible, publishable, serves the centre). Weakness is competitive (vs a rival with a published choice paper) and candidate credibility (first-time estimator), both handled honestly.

## 3. Score (six-point requirement test) — ~70/100, lower-mid shortlist
- R1 Logistics/freight real — 7 (carrier SC estimated + NGM; signpost fires first)
- R2 DCM+ABM integration — 7 (coupling loop shown; ρ demoted)
- R3 deep uncertainty + backcasting — 8 (MORDM spine; backcasting now operationalised backward; Sobol decomposition; signposts scored twice)
- R4 finish in 3 years — ~6 (3 papers, one survey, ladder, data off critical path; still softest)
- R5 serve TRANSPLAN/NTM6/RTM — 8 (named; complement-not-replace; Tveter 2172 cited; RA1)
- R6 candidate credible — ~6 (Swissmetro real-data proof + honest skill path; no published paper)

## 4. The five-page content (body) + page 6
Spine: P2 states the empirical heart; P3 is its centre; P4 is where the measurement is taken; P5 is the consequence.
- **P1 Problem** — equilibria are silent on the route; path governed by fleet turnover, acceptance, debt; road-pricing erosion live. Main Q + RQ1/2/3 (RQ2 = the acceptance test). Numbers: 16.8 bn rev; 77.9 bn debt; 4-in-10 EV; 30% less/EV crossing; FNB 16.7%. Plate P1 (pathways/backcasting).
- **P2 Fit/gap/new** — NTM6/RTM/NGM named; TØI 1819/2021 mandate; RA1; complement-not-replace. Empirical-heart paragraph. Gap sentence. Three claims (led by the measurement claim; claim2 Sobol; claim3 lead-time+false-alarm). Plate P2 engine (DCM+ABM).
- **P3 Model** — "everything rests on one measurement." eq(1)(2)(3); DCM→ABM coupling loop; backcasting operationalised (2050 targets → admissible states backward); falsification; DMDU stance; targets table (Klimaloven 90-95%, finance, accessibility); tools + honest skill path + Swissmetro. Plate P3 "what memory does" (acceptance as admissibility).
- **P4 Case/design** — Bypakke Kristiansund live 1 Jun 2026; Molde comparison; three survey blocks (household acceptance + randomised info arms, passenger SC, carrier SC) + NGM freight fallback; H1/H2/H3; freight signpost fires first. Numbers: 34/27.20/19.04 kr; council 26-19, county 33-14; n=1,428/714; waves M6/M18. Plate P4 map (freight/acceptance live).
- **P5 Plan/robustness/receipts** — MORDM (min max-regret s.t. acceptance λ, finance, accessibility); ε-NSGA-II + PRIM; Shaabani-Hoff kin; ~10⁴×10³, 40-150 CPU-h; fidelity ~15% MAPE; 3 papers M14/26/34; thesis ladder; risks + freight floor; dissemination (Samferdsel + NORS); TRG + RA1; receipts (Swissmetro LL -5214.9, 87 tests). Plate P5 robust front.
- **P6 References** — all 25 keys; 9 Norwegian verified against primary sources 2026-10-17; 10 project-verified; 6 standard.

## 5. Evidence (real)
- `evidence/dcm-swissmetro/` on **main** — mixed logit reproduced, Biogeme 3.3.5, N=6,768, final LL -5214.875 (matches reference). R6.
- `evidence/fidelity-benchmark/` on **main** — zonal vs static-network, ~15-16% MAPE, r 0.73-0.84, thousands-fold speedup. R3/R6. Honest scope: static free-flow reference, not dynamic MATSim.
- `skills/matsim-bridge/` on branch **matsim-bridge** — export + cross-check code, NOT run (no dynamic number). Optional; static benchmark already closes the fidelity gap.

## 6. Git state (branches)
- `main` (14 Oct) — evidence merged (Swissmetro + fidelity); proposal on main is OLD generation.
- `clever-bell-tctxe3` (10 Oct) — Proposal **v4.5** text (pre-v5 improvements).
- `lucid-galileo-3ss28v` (≤19 Oct) — v4.5 + Plate A + visual-narrative reference + HANDOFF note. Most advanced VISUAL branch.
- `dcm-swissmetro-evidence`, `matsim-bridge` — evidence branches.
- `fervent-noether-nx38nl` — Pages config.

## 7. Visual build method (from the visual session handoff)
- `skills/visual-narrative/reference/motion-plate-spec.md` (motion grammar) + `cd-skills-map.md` (which CD skill per plate).
- Build data-driven plates (P3, P5) first — straight from model output; hand-drawn scenes (P1, P2, P4) after.
- Plate A exists: `make_motion.py` → `motion.json` → `src/motion.js`; `plate-a.html`; embedded as screen-only exhibit after sheet 5.
- House tokens already in v4.5: sage good / amber moderate / red fails / teal free / cream text.
- OPEN build choices: ground oxblood `#2E151C` (our proposal.html) vs v4.5 charcoal `#16120F`; titles Montserrat vs Inter.

## 8. Open items / what is NOT done (honest)
1. **v5.5 text + page-6 bib are NOT committed to the repo** — they live in `proposal_v5.4_content.md` (+re-weight) and `proposal.html` (scratchpad/local only). Committed repo proposal is still v4.5. Biggest gap to close at build.
2. **P4 "48%" is an error in proposal.html as written** — the repo's 48% is "48% of junction pairs lose every road connection at the bridge split", NOT share of trips avoiding both stations. Must revert to placeholder `[N1]` / connectivity wording before anything ships. (Flagged, not yet fixed per your steer.)
3. **"Freight signpost fires first"** is a PROPOSED finding, not computed — keep as aim.
4. **4 of 5 plates unbuilt** (P1, P2, P4 hand-drawn; P3, P5 data-driven). Only Plate A exists.
5. Branches scattered — v4.5, evidence, Plate A/visual-ref on different branches; consolidate onto one at final build.
6. Bib fields to fill: Führer title/volume from DOI; NGM report no./year; Shaabani year/venue.
7. `standalone.html` stale; some A3 sheets slightly over frame offline (web-font load).

## 9. Next steps (agreed order)
1. Correct the 48% line to honest `[N1]`/connectivity wording; soften freight claim. (on your go)
2. Commit v5.5 text (rebuild proposal HTML from the re-weighted content) onto ONE consolidated branch.
3. You send 5 reference images → build plates P3/P5 first (data), then P1/P2/P4 (scenes), to the chosen ground/type.
4. Consolidate branches; merge evidence; final receipts.

---

## 10. USP and draft scorecard

**USP (what makes this win, one line):** *the first proposal to estimate public acceptance on real data, carry it inside agents through calendar time, and let it decide which road-pricing pathways survive — tested on a live Norwegian toll (Bypakke Kristiansund) and delivered as a stress-testing layer TØI itself asked for.* Four differentiators, scored for strength:
- Estimated-acceptance-as-admissibility (novel combination) — **8/10**
- Live, contested, measurable case (EV toll erosion, 1 Jun 2026) — **9/10**
- Two runnable evidence artifacts + systems proof (built a fast engine AND a network reference, measured the gap) — **8/10**
- Complement-not-replace fit with TØI's own roadmap (1819/2021, RA1, Tveter 2172) — **9/10**
- Honest scoping + receipts (ladder, cuts, verified numbers) — **8/10**

**Draft readiness (each /10):** content depth 7 · flow/interconnection 8 (spine + hand-offs) · panel relevance 8 · naming 6 (evocative, needs scientific co-naming) · research novelty 6 (combination, not new method) · feasibility 6 · evidence 8 · visual readiness 2 (1 of 5 plates) · citations 9 (verified).
**Overall: ~70/100, lower-mid shortlist.** Vs an 80-rival with a published choice paper: TIES on fit/freight/OR spine, still trails on R6 (no prior estimate) and R4 (load) — competitive, not a guaranteed win.

## 11. Narration content (the lines that add depth beyond the body text)
- **P1** caption: "A model gives one 2050. A household lives a sequence. Only one of these is a plan." · annotations: fleet turns over slowly · acceptance carries year to year (ρ) · debt is due on a schedule · red ghost branch: "pathway breaks here — threshold crossed".
- **P2** caption: "Five layers. Each carries what the one below cannot." · per-layer: DCM A1 Biogeme estimated-not-assumed · ABM A2 acceptance in calendar time · FUTURES 10³ EMA Workbench · SEARCH A3 MORDM min-max-regret · SIGNPOSTS validated twice.
- **P3** footer (plain words): "acceptance next year = memory of last year + what you pay + what you were told." · caption: "Same instruments, different order, different fate. The order is the finding." · λ: "admissible only if acceptance stays above this every year."
- **P4** callout C: "48% …" → **MUST change** to the honest connectivity/[N1] wording (see §8.2) · callout D: "road-to-sea corridor — the heavy-vehicle signpost fires first" (aim, not computed) · tariff tag: "34 kr · 27.20 tag · 19.04 zero-emission = 30% less per electric crossing".
- **P5** caption: "Robust is not optimal. It is the path that still works when the future refuses to cooperate." · axis note: "acceptance margin = the largest rise in the threshold a path survives, reported as a result." · receipts strip: Swissmetro reproduced (LL −5214.9) · fast engine within ~15% · 87 tests, traceable to commit.

## 12. Visualisation content and status
- System: Abhinav oxblood (`#2E151C`) OR v4.5 charcoal (`#16120F`) — OPEN; cream line-work; one accent (terracotta) per sheet; Montserrat vs Inter — OPEN. Semantics fixed (sage/amber/red/terra/teal).
- Plate → Abhinav family: P1 split before/after + scene; P2 staged pipeline / context-tensor stack; P3 past/future chart + pattern fan; P4 metric street map + callouts; P5 Pareto scatter + selected point.
- Status: **Plate A built** (motion exhibit, lucid-galileo). **P1–P5 NOT built.** Build order: P3, P5 first (straight from model data), then P1, P2, P4 (hand-drawn scenes). Awaiting your 5 reference images.
- Build assets: `motion-plate-spec.md`, `cd-skills-map.md`, `make_motion.py`/`motion.json`/`src/motion.js`.

## 13. Claims and numbers audit (integrity)
| Claim / number | Status |
|---|---|
| Tariff 34 / 27.20 / 19.04 kr, "30% less" | VERIFIED (vegamot) + arithmetic checks (19.04/27.20=0.70) |
| Toll rev 16.8 bn; debt 77.9 bn; 4-in-10 EV | VERIFIED (svv25, dok15) |
| FNB 16.7% Bergen 2019 | VERIFIED (official result; SNL says 16.9 — we cite official) |
| Bypakke dates/votes (1 Jun 2026; 26-19; 33-14) | VERIFIED (bypakke, innst337) |
| Swissmetro LL −5214.875, N=6,768 | COMPUTED in repo (evidence/dcm-swissmetro, main) |
| Fidelity ~15–16% MAPE, r 0.73–0.84 | COMPUTED in repo (evidence/fidelity-benchmark, main) |
| 87 tests (89 on merged branch) | COMPUTED (tests/) — reconcile final count |
| Emissions anchor 90–95% by 2050 | VERIFIED (Klimaloven) |
| **P4 "48% of trips avoid both stations"** | **ERROR** — repo 48% = junction-pair disconnection at bridge split; trip-avoidance share is placeholder [N1] |
| "freight signpost fires first" | PROPOSED (aim), not computed |
| 904 pathways; 10³ futures; ~10⁴×10³ search; 40–150 CPU-h | PROPOSED design figures (prototype make_proto; full run is thesis-time) |
| ρ, λ symbols vs eq (2) | UNVERIFIED in current plate files — confirm at build |
| 25 citations | VERIFIED/standard (p6); 3 fields still to fill (Führer, NGM no., Shaabani yr) |

## 14. Codes and tests
- `evidence/dcm-swissmetro/` — Biogeme mixed logit, runs, reproduces reference. ✓
- `evidence/fidelity-benchmark/` — zonal vs network, runs, real numbers. ✓
- `skills/` — abm-transport, osm-network, vrp-solve, dmdu-explore, dcm-estimate, opt-model, visual-narrative, viz-story, gh-datatree, cl-foundations. Repo plugin + MCP server.
- `skills/matsim-bridge/` — converters + runbook, VERIFIED to emit well-formed XML; MATSim itself NOT run.
- `tests/` — 87 project tests pass (89 on lucid-galileo incl. motion); reconcile the headline count at final commit.

## 15. Pending runs (none are proposal-blocking; all thesis-time unless a cited number needs it)
- **MATSim dynamic cross-check** — bridge built, NOT run (no dynamic MAPE). Optional; static benchmark already closes the fidelity gap. Runnable here if you approve (token/compute spend — ASK FIRST).
- **A1 trip-avoidance share [N1]** — the real P4 number; computed in the PhD, placeholder until then.
- **Full ensemble / MORDM run** — real pathway numbers are prototype-level now; the full 10⁴×10³ run is a thesis deliverable, not needed to submit.

## 16. Gitwork (tips as of 2026-10-20)
- `main` 879c37ac — evidence merged (Swissmetro + fidelity); proposal on main is OLD.
- `clever-bell-tctxe3` a0f702f3 — Proposal v4.5 text (pre-v5).
- `lucid-galileo-3ss28v` 8fb997c3 — v4.5 + Plate A + visual-narrative reference + HANDOFF.
- `dcm-swissmetro-evidence` 5495dc46 · `matsim-bridge` 67bcaa26 (not run) · `fervent-noether-nx38nl` 6c95ed79 (Pages).
- **Uncommitted / local only:** the v5.5 text (`proposal_v5.4_content.md` + re-weight) and `proposal.html`. NOT in any branch yet.
- Consolidation plan at final build: branch off main (has evidence) → add v5.5 text + plates → carry v4.5's still-wanted assets → one clean branch → PR.

## 17. Delegate audit (2026-10-20) — MATSim run + v5.5 finish
- Delegate reported T1–T5 done on its LOCAL branch `claude/v5.5-finish`, but it could NOT push (third-party GitHub App returned 403). Nothing reached our remote; `main` untouched (confirmed by ls-remote). Its code is therefore UNVERIFIED — audited its report, not its diff.
- Corrected here and pushed (lucid-galileo): the **48% error removed** in content/html/spec → trip-avoidance share is `[N1]`, exposure "measured not assumed"; **freight "fires before" → "expected to fire before"** (both occurrences); **citation specifics flagged TO CONFIRM** — NGM "TØI 1918/2022" and Shaabani "EURO JTL 13/100146/2024, Laporte-before-Hoff" were NOT confirmed by independent search → do not ship; Führer DOI kept as the anchor, vol. 34 to confirm.
- MATSim numbers the delegate claims (free-flow zonal-vs-MATSim ~19% MAPE r0.735; static-vs-MATSim 6.2% r0.999; 0.1 congested gridlock ~78%) are plausible and honestly caveated, but live ONLY in its environment — NOT verified, NOT in our git. NOT added to the proposal.
- SECURITY: do NOT grant the third-party GitHub App `meta-muse-ai` Contents:write. To bring the MATSim result in safely: have the delegate run `git bundle create v5.5.bundle main..claude/v5.5-finish` (or upload the two `dynamic_crosscheck.json` + the scatter figure); verify against this audit, then push from a trusted session.
