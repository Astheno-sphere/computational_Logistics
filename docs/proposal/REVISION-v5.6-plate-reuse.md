# REVISION v5.6 — reuse the plates, declutter, cut back to five pages

The v5.5 build (the uploaded `proposal-v5.5.html`, generated in the Code session, not pushed) produced good art but three problems: it overflowed into eight sheets and buried the best plates in a supplement; it stamped build-notes on the artifact; and the prose ran ~5,000 words against a ~2,900 target. The art is NOT the problem — organisation and clutter are. **Reuse every strong plate.** Only one plate is dropped.

## 1. PLATE INVENTORY — verdict per plate (all 8 sheets reviewed)

**KEEP as-is (already proposal-grade):**
- **P4 Kristiansund toll map** (page 4) — the best plate. Real OSM graph, callouts, scale bar, data box, 48% stated correctly as connectivity, `[N1]` preserved. Keep exactly.
- **P3 three-agent acceptance trajectories** (page 3) — commuter/occasional/van with ρ labels and the λ crossing. Keep; strip only the long reduced-form footnote (see §3).
- **P5 Pareto robust front + signpost strip** (page 5) — scatter with chosen point, signpost stations below. Keep; strip the `PROTOTYPE · PARAMETERS ASSUMED` box text.
- **P2 five-layer engine stack** (page 2) — DATA→CHOICE→AGENTS→FUTURES→PATHWAYS isometric. Keep; lift the contrast on the right-hand scatter so it is not faint.

**PROMOTE from the supplement into the five-page body (these are your strongest; they must not sit in an appendix):**
- **Household street scene** (S1 — three time-steps, car turns electric 2029, acceptance gauges, people at true scale) → **page 1 hero.** It shows "a household lives a sequence" better than the isometric ever did. This becomes page 1's image.
- **Revenue-erosion fan + car waffle** (S1 — toll/crossing falling as the fleet electrifies, fan of futures against the debt line, "22% of futures fail to cover the debt") → **page 5**, beside the robust front (it answers "what replaces the lost revenue"). If page 5 is too full, put the fan as a slim strip at the foot of page 1.
- **Radial 904 "order matters" sunburst** (S2 — distance-then-package 67% vs package-then-distance 36%, leaf colour = futures on target) → **page 2** (next to "what is new") or **page 5**. Clearest "same instruments, different order, different fate" image in the set.
- **Data→wave→claim wiring timeline** (S2 — data sources wiring into A1/A2/A3 into the three claims) → **page 5** (the plan) or **page 2**. Shows the thesis ladder as a system.

**DROP (only these):**
- **Twin-city isometric** (page 1) — muddy red blobs, not line-work. Replaced by the street scene above.
- **The "HOW THIS WAS MADE" meta-plate framing** (S2 heading) and the **AI-tools-as-a-hero-block** — keep the AI disclosure as ONE small footer line on page 5, not a plate.

Net: the two supplement sheets disappear; their good plates move into the body; the book is five pages + references again.

## 2. FINAL FIVE-PAGE LAYOUT (plates mapped)
- **Page 1 (problem):** title block → body → RQ box → **household street scene** (promoted) as hero. Optional slim erosion-fan strip at the foot.
- **Page 2 (fit/gap):** body + "ask/answer" table + three claims → **engine stack** hero; **904 sunburst** as the secondary "order matters" plate if it fits.
- **Page 3 (model):** equations + targets table → **three-agent acceptance plate** hero. (No change.)
- **Page 4 (case):** body + survey/hypotheses → **Kristiansund map** hero. (No change.)
- **Page 5 (plan):** body + article/risk tables → **robust front** hero + **erosion fan** + **data→wave→claim wiring**; AI disclosure as one footer line.
- **Page 6:** references (unchanged).

## 3. STRIP THESE LEAKED NOTES / META (delete verbatim wherever they appear)
- The **hex colour-swatch legend strip** across the top of page 1 (`#9DB886 ROBUST`, `#D4A530 TODAY`, `#C45545 ERODES`, `#D4835C CHOSEN`, `#7CBAC4 FREE`) — delete entirely. A reviewer never sees the palette.
- `heights 3x` (page 1).
- `years from the prototype run, pathway E, page 5` (page 1 — also truncated at the frame; delete, do not just re-fit).
- `illustrative, not estimates` / `illustrative` stamped on plates (page 3 and others) — remove from the plates; one honesty line per page footer is enough.
- `prototype; fleet turnover assumed` · `Parameters assumed until A1 and A2 estimate them` · `PROTOTYPE · PARAMETERS ASSUMED` (pages 5, supp) — consolidate to a single footnote on page 5.
- `[to confirm: wording]` in the AI-tools box (supp).
- The long reduced-form footnote `reduced form of (2): δ·dose written as −κ·bill, info and z folded into a₀, scaled by (1−ρ); a₀ 0.55–0.87, κ 0.30–0.57` (page 3) — keep only the plain-words line `acceptance next year = memory of last year + what you pay + what you were told`.
- Fix truncated labels: `acceptance as admissibilit` (supp, cut off) and the page-1 cut-off.

## 4. SETTLE THE NUMBERS (one value, everywhere)
- **Test count is inconsistent across the build:** 87 (older text), 89 (repo `grep def test_`), **92** (printed on the uploaded page 5). Recount at the final tagged commit and use that single number on every sheet and in the README. Do not ship three different counts.
- Swissmetro reference already corrected to ≈ −5214.8 (ours −5214.9); keep.
- `[N1]` and the Führer `[to confirm]` stay as honest placeholders.

## 5. WORDS — cut ~40% back toward ~2,900
Each plate currently restates its point in a caption, a sub-caption, AND on-plate labels. Keep the on-plate labels + one short caption; delete the explanatory sub-caption paragraph under each plate where the body already carries the argument. The body paragraphs themselves are fine; the triple-stating is the bloat.

## 6. EXECUTION
The plates are self-contained `<svg>` blocks (plus the one embedded map JPEG), so promoting a supplement plate into a body page is a block move, not a redraw. Keep every plate's own art; change only placement, captions, and the stripped notes. Build on a branch off `lucid-galileo`, one PR, delete nothing.
