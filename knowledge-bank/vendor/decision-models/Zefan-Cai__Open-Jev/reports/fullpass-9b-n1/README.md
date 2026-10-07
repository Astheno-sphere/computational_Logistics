# 9B full-pass training: independent saved-evidence audit

The `Qwen/Qwen3.5-9B` run completed **20,204 optimizer steps × 4 records =
80,816 training records**, one pass over frozen `release-v2`. Its independent
CPU audit passed on 2026-09-20 UTC, with no evidence-integrity or
metric-recomputation failures.

The results cover **512 selected test rows and 512 selected OOD rows**, using
source/kind-balanced selection with seed `20260919`. Calibration uses a separate
512 selected rows. This is **not** evaluation of all 26,452 held-out rows.
The audit did not load a model or inspect JF100. Game, browser, flight and other
closed-loop performance were not measured; game-named results below refer to
saved decision predictions.

## Overall results

NLL, Brier and ECE compare the baseline and trained model using each model's
**own calibration-only temperature**. Hard-label accuracy counts only exact
one-hot targets. Expected accuracy averages target mass at the predicted
candidate across every selected row. Calibration does not change the predicted
class.

| Split | Rows / hard-label rows | Hard-label correct, baseline → trained | Expected accuracy | NLL | Brier | ECE |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| Test | 512 / 470 | 304/470 (64.68%) → **447/470 (95.11%)** | 61.59% → 90.38% | 0.876303 → 0.254392 | 0.437570 → 0.074115 | 0.038033 → 0.029466 |
| OOD | 512 / 484 | 323/484 (66.74%) → **447/484 (92.36%)** | 63.79% → 88.64% | 0.864411 → 0.327474 | 0.427617 → 0.112074 | 0.069315 → 0.028300 |

Overall calibrated metrics improve on both selections. Calibration remains
material to that conclusion: raw OOD ECE worsened from the uncalibrated baseline
0.035787 to the uncalibrated trained model's 0.048558; the trained calibration
temperature brings it to 0.028300. Applying the baseline temperature itself
worsened baseline OOD ECE from 0.035787 to 0.069315. All eight raw/calibrated
metric sections are preserved in the audit, so this distinction is explicit.

## Customer-service results

The customer decision source reached **68/68 hard labels on test** (baseline
58/68) and **77/77 hard labels on OOD** (baseline 64/77). Including soft-target
rows, expected accuracy improved from 83.33% to 97.22% across 72 test rows and
from 81.07% to 97.12% across 81 OOD rows. These are decision labels, not measured
customer conversations or completed external actions.

| Customer decision subtask | Test hard-label correct, baseline → trained | OOD hard-label correct, baseline → trained |
| --- | ---: | ---: |
| Bug severity | 3/8 → 8/8 | 2/8 → 8/8 |
| Category | 23/23 → 23/23 | 24/25 → 25/25 |
| Churn likelihood | 7/7 → 7/7 | 7/7 → 7/7 |
| Frustration | 2/6 → 6/6 | 7/10 → 10/10 |
| Reproducible steps present | 13/14 → 14/14 | 12/15 → 15/15 |
| Refund requested | 10/10 → 10/10 | 12/12 → 12/12 |

The separate customer-service workflow source improved from 19/24 to **24/24**
on test. OOD remained **26/27**. Its `HAND OFF` subgroup remained **3/4**,
and calibrated NLL worsened from **0.601508 to 1.771294**, indicating worse
probability assignments despite unchanged hard-label accuracy. The other seven
customer-service workflow question groups were correct on their selected OOD
rows; group sizes range from one to five and should not be treated as broad
coverage.

## Other improvements and remaining weaknesses

- VizDoom decision accuracy improved from 26/73 to 71/73 on test and 40/81
  to 78/81 on OOD. Painting geometry improved from 61/74 to 74/74 on test
  and 46/81 to 74/81 on OOD. Snake hard-label accuracy improved from 24/43
  to 43/43 on test and 27/48 to 48/48 on OOD. These do not establish live
  game-playing or image-generation competence.
- Reasoning/control accuracy remains lower: 62/72 on test and **56/80 on
  OOD**, versus baseline 44/72 and 45/80. Five single-example OOD painting
  question groups changed from correct to incorrect, even while the source
  average improved. Another OOD painting example remained incorrect with NLL
  increasing from 0.991381 to 8.404114. Full per-question metrics are retained.
- Wiki decisions mostly have soft targets and multiple acceptable actions.
  On 24 test rows, expected accuracy improved from 19.59% to 27.48%,
  optimal-action hit from 13/24 to 18/24, and hard-label accuracy stayed 2/8.
  On 27 OOD rows, expected accuracy improved from 10.82% to 33.94%,
  optimal-action hit from 9/27 to 19/27, and the hard-label subset from 2/9
  to 7/9. **Wiki OOD ECE worsened from 0.153023 to 0.230491**. Expected
  accuracy and optimal-action hit are not ordinary classification accuracy.
- T-Rex test decisions improved from 2/4 to 3/4, but NLL increased slightly
  from 0.747129 to 0.766888. There are no T-Rex rows in this OOD selection.
  Tic-tac-toe test expected accuracy improved from 35.32% to 45.73% on 24
  mostly soft-target rows, while ECE worsened from 0.084931 to 0.121094.
  These small groups do not establish generalization across games.

## Independent verification and provenance

[The audit JSON](independent-audit.json) contains all eight baseline/trained,
raw/calibrated test/OOD sections, including every kind, source and question
group, coverage, ordinal MAE and Wiki optimal-action metrics.
[The verifier](verify.py) adapts the already-audited 2B script without changing
the 2B files. It uses only the Python standard library and does not import the
training or packaging metric implementation.

- **44,277 numeric leaves matched**, with maximum absolute difference
  `1.7763568394002505e-15`.
- Independent convex optimization in inverse temperature reproduced the
  calibration optima: baseline recorded `1.182255567450606` versus independent
  `1.1822554543702075`; trained recorded `1.8969118766347646` versus independent
  `1.8969112498624878`. Maximum calibration NLL regret was `7.61e-15`.
- All five frozen split hashes matched the manifest and run. All data IDs were
  unique and groups did not cross splits. Selected IDs, ordering, targets,
  `question_id` and `target_basis` bound to the frozen data. The 20,204 training
  log steps were contiguous with finite nonnegative loss and gradient norms.
- At collection time, the original training checkout's `train.py`, `model.py`,
  `api.py`, `data.py` and `metrics.py` hashes matched their Git objects at the
  recorded training commit. Both sets of hashes are recorded. This confirms
  their current agreement, not an independent history of runtime file changes.
- The one saved reload row matched its trained-test reference exactly:
  maximum logit difference **0.0**, with matching row identity and valid saved
  probabilities. Current checkpoint files were hashed but not loaded.
  Training recorded no contemporaneous output-weight digest, so the historical
  reload is **not cryptographically bound to the current weight bytes**.

Training coverage is derived from saved configuration, full input selection and
step logs; gradients were not independently replayed. Collection at
`2026-09-20T07:01:49.633148+00:00` changed no remote file or job. Raw evidence
remains under ignored `runs/fullpass-n1-v1/9b-evidence`; this report publishes
hashes and aggregate metrics.

Pinned upstream revision: `c202236235762e1c871ad0ccb60c8ee5ba337b9a`.
Training code commit: `99e881108c6cacadafd364088505e84975ca43fc`.
Frozen data manifest SHA-256:
`56105dc9fc89ef74919f5beb60bb6ae8c6e17bb95699dab59205f67d8b338d97`.
Current adapter SHA-256:
`f85650a8fb97c6d0ac3e948cdca2f30a0ca6ace8b8a43aebca1c152fe38aeb75`.
Current head SHA-256:
`229fe9800384e824135e59d1af59bda7346da031aea61640be5f456b9be6ce70`.

To reproduce from the separately retained raw evidence and frozen data, choose
a new output path; existing audit files are not overwritten:

```bash
python reports/fullpass-9b-n1/verify.py \
  --evidence runs/fullpass-n1-v1/9b-evidence \
  --data data/release-v2 \
  --output /tmp/open-jev-9b-independent-audit.json
```
