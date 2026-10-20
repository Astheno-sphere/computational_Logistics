# FINAL BUILD BRIEF — feed this to the Claude Code (Abhinav-diagram) session

Goal: build the final five-page TRANSPLAN proposal, with its GitHub link, and leave the repo arranged so a selection panel exploring it has a guided experience. **Delete nothing** — every branch, narration file, OSM/model run and plate stays. This brief is the single entry point; it names the other files to read.

Repo: **github.com/Astheno-sphere/computational_Logistics**. Build branch for the proposal work: `claude/lucid-galileo-3ss28v` (commit 57e4446 at time of writing).

## 0. Read these first (all in the repo, on lucid-galileo)
- `docs/proposal/v5.5-content.md` — THE FINAL TEXT (five A3 pages + page-6 references). Authoritative wording. Spine: acceptance-estimation is the empirical heart; the ensemble/robust front is its consequence.
- `docs/proposal/proposal-v5.5.html` — current built page (no plates yet; dashed frames mark the five slots).
- `docs/proposal/visual_spec.md` — the five plate briefs: for each, the Abhinav family to pull, composition, and the narration that adds depth.
- `docs/proposal/STATE_v5.5.md` — full state, six-point scores, USP, claims audit, git map.
- `docs/proposal/HANDOFF-visual-session.md` — how plates are built (motion-plate-spec, cd-skills-map, data-driven P3/P5 first).
- `skills/visual-narrative/` + `skills/visual-narrative/reference/motion-plate-spec.md` + `reference/cd-skills-map.md` — the house style and which CD skill loads per plate.

## 1. Hard rules (unchanged, non-negotiable)
- HTML first. No em dashes. Never invent a number or citation — leave `[N1]` and `[to confirm]` as-is.
- Every figure Abhinav-style only (oxblood/charcoal ground, cream line-work, one accent, honest encoding, title/caption carries the finding).
- Work on a branch; do NOT merge to `main` without Arshad's approval. Delete nothing.

## 2. The five plates — build order and slots
Build data-driven first (straight from model output), then the hand-drawn scenes. Each carries its keyword label + the narration lines in `visual_spec.md`.
1. **P5 robust front** (Pareto scatter + selected point) — from the prototype ensemble. keyword: robustness/regret/receipts.
2. **P3 "what memory does"** (acceptance trajectories + instrument fan) — from eq (2) reduced form. keyword: acceptance as admissibility.
3. **P2 "the engine"** (exploded DCM→ABM→futures→MORDM→signposts) — isometric. keyword: DCM+ABM.
4. **P1 "one place, two answers"** (equilibrium vs household-over-time) — scene. keyword: pathways/backcasting.
5. **P4 "who pays depends on where you live"** (Kristiansund toll-exposure map, three trips, freight corridor) — map register, built from the real OSM graph. keyword: freight/acceptance live.
Plate A (motion exhibit) already exists; keep it as the screen-only exhibit after sheet 5.

## 3. Settle two build choices (recommendation)
- **Ground:** use charcoal `#16120F` to match the existing v4.5 sheets (lower risk than re-toning everything to oxblood). Accent terracotta `#D4835C`; semantics sage/amber/red/teal fixed.
- **Title font:** the Abhinav skill calls for heavy condensed caps; Montserrat is not condensed. Use **Inter** (already on the v4.5 page) for titles OR a genuinely condensed face — pick one and apply across all sheets. Do not mix.

## 4. Toolchain to show on the page (honest "tools" strip)
Name the real toolchain, with the honesty condition noted:
- **Computation (all real, in repo):** Python — Biogeme (choice estimation), EMA Workbench (ensemble, ε-NSGA-II/MORDM, PRIM), OSMnx + NetworkX (OSM road graphs), OR-Tools (routing checks), MATSim 2024.0 (dynamic cross-check), NGM elasticities (freight).
- **Visual composition:** plates computed in Python (the `visual-narrative` skill), then composed in **Rhino + Grasshopper** (Heron for geo-referencing, Blender for render) for the scene plates. **CONDITION:** keep the Rhino/Grasshopper line only if Arshad does that composition himself (he has the skills; `make_rhino.py` exports Kristiansund to `.3dm`). If he does not, change the line to "drawn in Python/SVG" — never claim a tool that was not used.
- **Evidence:** the Swissmetro estimation and the two-engine + MATSim fidelity benchmarks are runnable in the repo.

## 5. GitHub link + "exploration as an experience" (the repo tour)
Put the repo link in the proposal footer/tools strip: `github.com/Astheno-sphere/computational_Logistics`.
Then make `main`'s top-level `README.md` a GUIDED LANDING (not a raw file list) so a panel that clicks through has a story, not a headache. Structure:
1. One-paragraph pitch + the proposal link (the built HTML/PDF).
2. **"Start here"** table: Proposal → `docs/proposal/` · Evidence → `evidence/` · Skills/tools → `skills/` · Case data & plates → `docs/proposal/plates/`, OSM graphs.
3. **Evidence you can run** — three bullets with the headline number each and the exact reproduce command: Swissmetro (`evidence/dcm-swissmetro`, LL −5214.9), static fidelity (`evidence/fidelity-benchmark`, ~15%), MATSim dynamic (`evidence/fidelity-benchmark/matsim`, ~19% free-flow, breaks under congestion).
4. **The skills** — one line each (abm-transport, osm-network, dcm-estimate, dmdu-explore, opt-model, vrp-solve, visual-narrative…), so the breadth reads as a system.
5. A short "how to read this repo" note + the test badge (87 tests).
Keep it honest and skimmable; the goal is that clicking any link rewards the reviewer.

## 6. Git assembly plan (NOTHING deleted)
- Keep ALL branches as the record: `clever-bell-tctxe3` (v4.5), `lucid-galileo-3ss28v` (v5.5 + plates + notes), `dcm-swissmetro-evidence`, `matsim-bridge`, `fervent-noether` (Pages), `main`.
- Build the final plates on `lucid-galileo` (or a fresh `v5.5-final` off `main`), then open ONE PR into `main`. `main` becomes the clean "front door": v5.5 proposal + plates + evidence + the guided README.
- Tag the submission commit (e.g. `v5.5-submission`). The branch tag-push was refused by the proxy before, so point the receipt at the commit hash if tagging fails.
- Arshad reviews and merges; the AI does not merge to `main` itself.

## 7. Acceptance checks before "done"
- Five plates in their frames, Abhinav-consistent, each with keyword + caption; Plate A exhibit intact.
- `[N1]` and `[to confirm]` still present (not fabricated); every number traces to a repo file or verified source.
- Tests pass (report count); nothing deleted; all branches still on the remote.
- README landing renders as a guided tour; GitHub link in the proposal; toolchain line honest about Rhino/Grasshopper.
- One PR into `main`, reviewable by diff; submission commit tagged or hash-pinned.
