# WORK ORDER — finish TRANSPLAN proposal v5.5 (for a delegated AI with repo write access)

Repo: Astheno-sphere/computational_Logistics. Read `docs/proposal/STATE_v5.5.md` first — it is the full state. This order lists the pending work and the rules. Owner: Arshad (Astheno-sphere). Deadline 1 Nov 2026.

## HARD RULES (do not break — these protect the submission)
1. **Work on ONE new branch off `main`** (`git checkout -b claude/v5.5-finish origin/main`). Never force-push. **Never merge to `main` or any shared branch.** Open a PR and stop; Arshad reviews.
2. **Never invent a number, citation, or result.** Every figure must trace to a repo file or a cited primary source. If a value is not computed, leave its placeholder (e.g. `[N1]`). A fabricated number is worse than a gap.
3. **No em dashes** in proposal prose. HTML first, never PDF unless asked.
4. **Tests in a venv only** (`python -m venv`; do not touch system packages; Debian PyYAML blocks pip). Report the pass count.
5. Report a `git diff --stat` and the commit hashes. Delete nothing. If unsure, leave it and note it.

## TASKS
### T1 — Fix the P4 "48%" error (integrity; highest priority)
Files: `docs/proposal/v5.5-content.md` and `docs/proposal/proposal-v5.5.html`.
The claim "48% of trips (can) avoid both stations" is WRONG. The repo's 48% is "48% of junction pairs lose every road connection when the Kristiansund graph splits at the bridge" — a connectivity figure, not a trip-avoidance share. Do ONE of:
 (a) replace with the honest connectivity statement, OR
 (b) keep the trip-avoidance share as the placeholder `[N1]` "to be counted in A1".
Do NOT present 48% as the share of trips avoiding the toll. Fix every occurrence (page-1 box and page-4 callout C).

### T2 — Soften the freight claim
"the heavy-vehicle signpost fires before the passenger one" is a PROPOSED/expected result, not computed. Reword as an expectation to be tested (e.g. "is expected to fire before"), in both files.

### T3 — Fill three bibliography fields (verify, do not invent)
In `v5.5-content.md` page 6: Führer et al. — add title + volume from DOI 10.1016/j.trip.2025.101683; NGM — add the specific report number/year (Hovi/TØI national freight model); Shaabani et al. — add year + venue. Verify each against the primary source; if you cannot confirm, mark `[to confirm]` and move on — never fabricate.

### T4 — Rebuild the proposal HTML from the corrected v5.5 content
`proposal-v5.5.html` is the current build. After T1–T3, ensure the HTML matches the corrected `v5.5-content.md` (five A3 pages + page-6 references, Abhinav system, dashed plate frames, no images). Keep numbers consistent across both files.

### T5 — MATSim dynamic cross-check (token/compute heavy; the delegated run)
Branch `matsim-bridge` has `skills/matsim-bridge/` (converters + runbook, verified to emit valid XML; MATSim NOT yet run). MATSim 2024.0 release ZIP downloads fine in the sandbox. Steps (see `skills/matsim-bridge/README.md`):
 - venv install `evidence/fidelity-benchmark/requirements.txt`; Java 17.
 - `bash skills/matsim-bridge/run_matsim.sh` with `TOWN=molde AGENTS=4000` → equil smoke test, build scenario, run MATSim at capacity factors 1.0 and 0.1, `compare_kpis.py`.
 - Capture the REAL dynamic numbers (zonal-vs-MATSim MAPE and r, both cap factors, coverage) from `dynamic_crosscheck.json`. If coverage <95% or many agents stuck, say so.
 - Commit ONLY the summary JSON + one figure + updated READMEs (not the raw multi-hundred-MB outputs; keep them gitignored). Update `evidence/fidelity/README.md` so the dynamic cross-check is DONE with the real number.
 - If MATSim fails, report exactly what failed. **Invent no number.**

### T6 — Prepare consolidation (DO NOT MERGE)
On the v5.5-finish branch, note in the PR description which branches hold what (main=evidence, clever-bell=v4.5, lucid-galileo=plates+notes). Propose the merge order. Leave the merge for Arshad.

## COMMIT / PUSH
Commit messages end with exactly:
```
Co-Authored-By: <delegate>
```
Push the branch, open a PR titled "v5.5 finish: 48% fix, freight wording, bib, MATSim dynamic". Do not merge.

## ACCEPTANCE CHECKS (Arshad / review AI runs these to verify the delegate)
- `git grep -n "48%" docs/proposal` → no occurrence claims trips avoid the toll; it is connectivity or `[N1]`.
- `git grep -n "fires before" docs/proposal` → reads as expectation, not fact.
- Bib: the three fields filled or clearly `[to confirm]`; no invented DOI/pages.
- Tests pass count reported; no system packages touched.
- MATSim: `dynamic_crosscheck.json` exists with real numbers, or an honest failure note; no raw outputs committed.
- Nothing merged to `main`; one branch, one PR; `git diff main...<branch> --stat` reviewable.
