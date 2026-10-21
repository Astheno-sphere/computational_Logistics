# AUDIT v5.6 — content thinker + visual inspector findings (2026-10-21)

Two agents audited the assembled proposal before the next build. Summary + the plan. No build started yet — awaiting Arshad's decisions (bottom).

## KEY DISCOVERY: finished oxblood plates already exist, unused
`docs/proposal/plates/*.svg` (all in-palette, panel-grade, BETTER than what shipped):
- **front.svg** — robust front WITH an instrument-sequence rail (A–E drawn as Z/D/E tokens at the electric-share each switches on). Fixes the "A–E don't match narration" complaint.
- **engine.svg** — exploded 5-stage pipeline (DATA → ESTIMATED CHOICE → AGENTS → 10³ FUTURES → PATHWAYS) with a between-layer bracket ladder. Replaces the six map re-tints (p2).
- **memory.svg** — richer 3-agent acceptance plate (replaces the plain chart, p3).
- **erosion.svg** — full revenue-vs-debt fan (replaces the illegible thumbnail, p5).
- **answers.svg** — equilibrium-2050 vs same-place-as-path iso cities (fills p1 empty upper-right).
- **household.svg** — acceptance gauge + toll bill, 2026/2029/2035 (fills p3 right column).
- **thesismap.svg** — data sources → 4 articles on 36-mo axis → 3 claims (fills p6 lower half).
- **tree.svg** — radial 904 "order matters".

Plus `docs/plates/01–05` = REAL Molde OSM network diagrams (navy palette; 05 already oxblood). Re-tone = ~6 color constants in `skills/visual-narrative/scripts/plate.py` + re-run scripts.

## VISUAL FIXES (reassembly, not redraw)
1. Swap shelved oxblood plates in (front, engine, memory, erosion, answers, household, thesismap).
2. Robust-front A–E → adopt front.svg's instrument rail; drop generic iso blocks.
3. Kristiansund printed twice (p1+p4) → either differentiate crops, or put a re-toned Molde `01-freight-pinch-points` on p1 and keep the Kristiansund map once, on p4.
4. References (p6) → shrink keys to inline mono-gold; group (Norwegian models/policy · acceptance & DCM · ABM/pathways/robustness · data & tariff); add DOIs/URLs; a ruled **Evidence ledger** (commit hash · what it proves · result); fill lower half with thesismap.svg.
5. Genuine new builds: the broken p4 freight chart (labels clipped), and the p6 relayout.

## CONTENT GAPS (need Arshad's input)
1. **Why me / why here** (highest): name the DCM mentorship resident at Molde (Marcucci & Gatta, authors of [lepira]); surface the 4 yrs cross-border freight procurement (DACH/India/UAE) as carrier-survey + freight credibility; frame OR/logistics MSc as fit. Converts the "I haven't estimated choice models" line from weakness to fit.
2. **Named supervisor / constellation** — currently only "the group."
3. **Ethics/DMP** — two-wave re-links same households a year apart (GDPR/pseudonymisation/key custody/retention); add a short DMP block.
4. **Norwegian PhD structure** — state 3-yr vs 4-yr+25% pliktarbeid; 30-ECTS coursework (DCM-heavy); midway evaluation.
5. **Survey funding** — fieldwork (1,428+714 households) never costed/funded; is it in the TRANSPLAN budget, or is the Level-1 free-data ladder the funding answer?
6. Latest DCM-in-ABM / Norwegian pricing lit slightly thin (add 2–3).
7. Be explicit that Level-1 protects completion, not the headline novelty.

## INTERCONNECTION (real spine, fixable breaks)
- Handoffs P1→P5 all fire; empirical heart threads P2→P5; Claims 1 & 3 delivered. ✓
- **Claim 2 orphaned** — "uncertainty decomposed by source" promised (p2), never delivered. Add a variance-decomposition panel/line on p5, or it's an overclaim.
- **Ring asserted, not paid** — p1 revenue erosion ↔ p5 revenue fan are the same thread; make them cross-reference explicitly (both directions).
- p1 should seed the empirical heart (currently only financial).
- "Named decision: ZE discount/tariff" promised (p2), never surfaced as an output — state it in A3/p5.
- p3 eqs ↔ p4 hypotheses: cross-reference ρ/η by equation number.
- Equity axis mismatch: p3 income-quintile vs p4 geography — link them.

## MOLDE — elevate as network-methods + no-toll CONTROL (not a 2nd toll case)
- Kristiansund = policy town (toll, acceptance, pathways, signposts). Spine stays singular.
- Molde = network/methods proving ground + control arm (information without experience → sharpens H2). Carries real freight-fragility evidence (Øvre veg 18% of routes; closure strands 0.9%) and OR rigor (VRP 48 vs 137 min, OR-Tools vs PyVRP within 0.1%).
- Put it: p5 fidelity as a two-graph (Molde+Kristiansund) validation; p2/p4 one freight-fragility plate + one sentence.
- Guardrails: Molde has NO toll — no pathways/signposts there; plate 05 (stock-turns) and plate 04's 24 addresses are synthetic → keep ILLUSTRATIVE; Molde is mechanism/fidelity, not an A3 input.

## DECISIONS PENDING (before build)
1. Supervision: named supervisor / agreed, or write as proposed constellation?
2. Duration: 3-yr, or 4-yr + 25% pliktarbeid?
3. Funding: fieldwork in TRANSPLAN budget, or Level-1 is the funding answer?
4. Add the "why me/why here" paragraph (Molde DCM mentorship + freight-procurement background)?
5. Elevate Molde as network-control town?
6. Re-tone Molde plates to oxblood, or keep one navy "computational evidence" section?
