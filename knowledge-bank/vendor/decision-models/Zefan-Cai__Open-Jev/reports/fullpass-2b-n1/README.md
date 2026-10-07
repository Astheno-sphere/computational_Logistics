# 2B full-pass training: independent saved-evidence audit

The `Qwen/Qwen3.5-2B` run completed **20,204 optimizer steps × 4 records =
80,816 training records**, one pass over frozen `release-v2`. The independent
CPU audit passed on 2026-09-20 UTC. There were no evidence-integrity or
metric-recomputation failures.

These are the run's **512 selected test rows and 512 selected OOD rows**, using
source/kind-balanced selection with seed `20260919`. This is **not** evaluation
of all 26,452 held-out rows. The calibration set has a separate 512 selected
rows. The audit does not run JF100, models, games, browsers, flight simulators,
or any closed-loop task. Game-named source rows below are saved decision
predictions, not measured game performance.

## Overall results

Each NLL/Brier/ECE comparison below uses the baseline and trained model with
its **own calibration-only temperature**. Hard-label accuracy uses only exact
one-hot targets; expected accuracy averages target mass assigned to the chosen
candidate across all rows. Calibration does not change the predicted class.

| Split | Rows / hard-label rows | Hard-label correct, baseline → trained | Expected accuracy | NLL | Brier | ECE |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| Test | 512 / 470 | 257/470 (54.68%) → **431/470 (91.70%)** | 52.19% → 87.06% | 1.024574 → 0.323670 | 0.511116 → 0.113106 | 0.068390 → 0.020282 |
| OOD | 512 / 484 | 287/484 (59.30%) → **425/484 (87.81%)** | 57.20% → 84.38% | 0.967353 → 0.535945 | 0.485897 → 0.197706 | **0.051152 → 0.078488** |

OOD calibration remains a weakness: ECE worsened despite better accuracy,
NLL and Brier. Applying the trained temperature helps relative to its own
uncalibrated OOD ECE (0.094325 → 0.078488), but does not beat the calibrated
baseline. The uncalibrated baseline ECE was 0.061707.

## Task improvements and regressions

These comparisons use the same saved, paired examples before and after
training. Small groups are reported with their denominators.

- Customer decision rows: expected accuracy improved from 62.50% to 97.22%
  on 72 test rows and from 71.19% to 89.71% on 81 OOD rows. The separate
  customer-service workflow source reached 24/24 on test; OOD remained
  25/27 before and after training. Within customer decisions, the OOD
  `has_reproducible_steps` question regressed from **14/15 to 12/15**.
- VizDoom decision rows improved from 29/73 to 71/73 on test and 30/81 to
  74/81 on OOD. Painting geometry improved from 36/74 to 73/74 on test and
  45/81 to 71/81 on OOD. These do not establish game-playing or image-generation
  competence. Several single-example OOD painting questions still have large
  confident-error losses; all per-question results are retained in the audit.
- T-Rex decision accuracy regressed from **2/4 to 1/4** on test, with NLL
  increasing from 1.161442 to 1.380182. There were no T-Rex rows in this OOD
  selection; four examples cannot support a broad conclusion.
- Wiki decisions have multiple acceptable actions and mostly soft targets.
  Test expected accuracy changed from 22.48% to 23.32% across 24 rows, while
  optimal-action hit improved from 15/24 to 17/24. Its **hard-label subset
  regressed from 2/8 to 1/8**. OOD expected accuracy improved from 8.23% to
  27.34% across 27 rows; optimal-action hit improved from 8/27 to 18/27,
  with the hard-label subset improving from 1/9 to 5/9. Expected accuracy and
  optimal-action hit must not be relabeled as ordinary classification accuracy.
  Wiki OOD ECE also worsened, from 0.102847 to 0.151345.

## What was independently checked

[The audit JSON](independent-audit.json) records all eight baseline/trained,
raw/calibrated test/OOD metric sections, including every source, kind and
question group, coverage, ordinal MAE and Wiki optimal-action metrics.
[The standalone verifier](verify.py) uses only the Python standard library;
it does not import the training or packaging metric implementation.

- **43,263 numeric metric leaves matched**, with maximum absolute difference
  `1.4502288259166107e-15`.
- Independent convex optimization in inverse temperature reproduced the
  calibration optima: baseline recorded `1.5195101659228476` versus independently
  fitted `1.519510321456353`; trained recorded `1.518796342858676` versus
  `1.5187970797741903`. Maximum calibration NLL regret was `2.55e-14`.
- All five frozen split hashes matched the run and manifest; all data IDs were
  unique and groups did not cross splits. Selected row IDs, order, targets,
  `question_id` and `target_basis` matched the frozen data. All 20,204 training
  log steps were contiguous, with finite nonnegative loss and gradient norms.
- The one saved reload row matched its trained-test reference exactly
  (maximum logit difference **0.0**). Current checkpoint files were hashed on
  the remote host, but weights were not loaded in this audit. Training did
  not record a contemporaneous output-weight digest, so the historical reload
  is **not cryptographically bound to the current weight bytes**.

Training coverage is established from the saved configuration, full input
selection and step log; gradients were not independently replayed. Raw evidence
was copied without changing remote files or jobs. It remains under ignored
`runs/fullpass-n1-v1/2b-evidence`; the report exposes hashes and aggregate metrics.

Pinned upstream revision: `15852e8c16360a2fea060d615a32b45270f8a8fc`.
Training code commit: `99e881108c6cacadafd364088505e84975ca43fc`.
Frozen data manifest SHA-256:
`56105dc9fc89ef74919f5beb60bb6ae8c6e17bb95699dab59205f67d8b338d97`.
Current adapter SHA-256:
`2d23935b1a7380db444abac572c04646918ba794e59002d1588236182a3ca18f`.
Current head SHA-256:
`3532cd576c58d5ad5bf17c3e9f2df4be8c70e08c07fa6bb7fa673dcd7b401f2a`.

To reproduce from the separately retained raw evidence and frozen data, choose
a new output path; the verifier refuses to replace an existing audit file:

```bash
python reports/fullpass-2b-n1/verify.py \
  --evidence runs/fullpass-n1-v1/2b-evidence \
  --data data/release-v2 \
  --output /tmp/open-jev-2b-independent-audit.json
```
