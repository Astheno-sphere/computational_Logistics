# Drone snapshot pilot: three-model evidence archive

**Complete three-head decisions match 5/120 (4.17%) for 2B, 14/120 (11.67%)
for 9B, and 21/120 (17.50%) for 27B.** The fixed `brake / risk=2 / loss=false`
baseline matches **7/120 (5.83%)**: 1/60 test and 6/60 OOD. The 2B complete
result is below that baseline. A post-hoc descriptive `brake / risk=1 /
loss=false` baseline matches **29/120 (24.17%)**, above all three pilots.
None of the models selects a gap maneuver, climb, or reacquire, despite those
being the reference actions in 49 cases.

These are the original [100-step engineering pilots](../pilot-results.md),
each trained on 400 rows. They were not trained on the separately generated
drone corpus or the browser/drone expansion. This is a transfer evaluation of
old checkpoints, not a result from the active release-v2 training run.

The inputs are independently authored **synthetic snapshots** with disclosed
geometry and evidence rules. No simulator, flight, closed-loop control, physical
target-loss ground truth, or flight competence is established by this test.
`target_truly_lost` measures whether the visible evidence meets the disclosed
loss rule. See [data scope](../../docs/drone-data.md) and the
[evaluation contract](../../docs/drone-eval.md).

## Results and failures

All three evaluations completed 120/120 requests, with zero pending cases,
zero HTTP/schema/identity errors, and evaluator exit code 0. The paired set has
40 parent scenes: 20 test and 20 OOD, three variants each, selected by
label-independent hashes with seed 42. The 360 calls reuse the same 120 cases;
parent variants are correlated.

| Model | Complete, overall | Complete, test | Complete, OOD | Maneuver, non-forced | Risk level | Loss evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2B | **5/120 (4.17%)** | 3/60 | 2/60 | 43/115 (37.39%) | 10/120 (8.33%) | 58/120 (48.33%) |
| 9B | **14/120 (11.67%)** | 5/60 | 9/60 | 41/115 (35.65%) | 23/120 (19.17%) | 107/120 (89.17%) |
| 27B | **21/120 (17.50%)** | 9/60 | 12/60 | 44/115 (38.26%) | 35/120 (29.17%) | 118/120 (98.33%) |

Forced one-candidate maneuvers are **5/5 for each model** and are excluded from
the non-forced maneuver denominator. Complete accuracy requires all three
heads to match. Risk is the modal Score level, breaking ties toward the lowest
level; it is not the rounded expected Score. Loss uses `Noul >= 0.5`. Every
selected case remains in accuracy denominators, including any errors or pending
cases; none occurred here. Full split/head counts are in [audit.json](audit.json).

Always selecting `brake` alone matches **43/115 (37.39%)** non-forced
maneuvers, compared with the models' 43, 41, and 44 matches. Thus even 27B has
only one additional matching maneuver on this sample.

The following constant-output combinations were counted **after inspecting
the frozen reference distribution**. They are descriptive post-hoc comparisons,
not preregistered baselines or a basis for model tuning. The 29/120 result does
not replace the fixed 7/120 baseline. Both are retained so comparison with the
weaker fixed baseline does not imply a useful decision policy.

| Constant maneuver / risk / loss | Complete matches |
| --- | ---: |
| brake / 0 / false | 1/120 |
| brake / 0 / true | 1/120 |
| brake / 1 / false | **29/120 (24.17%)** |
| brake / 1 / true | 7/120 |
| brake / 2 / false | **7/120 (5.83%), fixed before model requests** |
| brake / 2 / true | 3/120 |

- **2B:** chooses `brake` and risk level 2 for all 120 cases. It wrongly marks
  loss evidence true in 62/90 reference-false cases.
- **9B:** chooses only `brake` (98) or `hold_course` (22), and predicts risk 2
  in 92 cases although only 10 references have that level. There are 13/90
  false-positive loss-evidence decisions.
- **27B:** chooses `brake` 116 times and `hold_course` four times. It never
  predicts risk 0, missing all 31 risk-0 references. Two of 90 reference-false
  loss cases are false positives. Its 118/120 loss result still leaves 99/120
  incomplete decisions because of other heads.

| Model | Risk Brier, three-class | Expected-risk MAE | Expected-risk MSE | Loss Brier | Valid-response coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2B | 1.120036 | 0.805886 | 0.857758 | 0.238232 | 120/120 |
| 9B | 1.002840 | 0.723227 | 0.754547 | 0.094700 | 120/120 |
| 27B | 1.071135 | 0.808447 | 0.962971 | 0.010893 | 120/120 |

Probability errors use complete valid responses only. These are descriptive
measurements on the frozen sample, not a claim of calibrated flight risk.

## Provenance, archive, and offline audit

The suite ran on `kwade5342000001`, physical GPU 3 (H100), with code commit
`74ee5f8c9fd0b8af43edbc46f0359df3676a2a45`, `lora_decision_head`, context limit
16,384, and candidate batch size 1. Exact model revisions, checkpoint hashes,
calibration temperatures, commands, and GPU endpoint snapshots are in the
[final suite manifest](suite-manifest-final.json). It records `complete` /
`finished` at **2026-09-20 04:08:08.627617 UTC**. All three servers stopped;
the recorded post-shutdown GPU process lists are empty. These snapshots do not
prove continuous GPU exclusivity.

Each of [2B](2b/), [9B](9b/), and [27B](27b/) preserves eight original files:
`drone/{selection.json,source-manifest.json,requests.jsonl,references.jsonl,
outcomes.jsonl,report.json}`, `drone.log`, and `server.log`. Outcomes include
the exact original HTTP body bytes in base64, their SHA-256, and transport
status. Requests and references are byte-identical across the three models.

The [2B](2b/transfer.json), [9B](9b/transfer.json), and [27B](27b/transfer.json)
transfer records contain each original file's remote SHA-256 and byte count
before and after copying, plus its local hash and byte count. All match: eight
files and 1,258,277 / 1,259,818 / 1,266,489 bytes, respectively. Copies were
made after each model's measurement and server shutdown. The two running suite
snapshots and the final snapshot remain unchanged alongside the separate
`suite-manifest-final.json`.

| Binding | SHA-256 |
| --- | --- |
| Frozen source manifest | `6eefc11815640ad9ded3d6846fdc4483b8c867d270e8852835e8d0cb7cb7066a` |
| Frozen cases | `d4ca0d575186dca4f6f0e04e113c14aaa6dadde1fcdad2ae98746600409bb107` |
| Selection | `4d33a8347cf75fb329d2d3f0adf8c2238f62f0b1b78a97c3e5c281e7bc6a0845` |
| Final suite manifest | `ba65bc478cc514fe0eee359f44f1d57d6db0b8685e12bbecf64178a53a7b37c6` |

The standalone standard-library [audit.py](audit.py) imports no evaluator,
teacher, model, or training library. It recreates the selection, binds requests
and references to the frozen cases, checks raw HTTP bytes and scorer identity,
validates typed fields/probabilities/confidences, and independently recomputes
row correctness, all denominators, aggregate metrics, probability errors, and
the fixed baseline. [audit.json](audit.json) records **8,334 checks passed,
zero errors**. Frozen references are checked for identity, not independently
relabeled by this audit; file-transfer checks are recorded separately above.

From the repository root with the frozen source cases present:

```bash
python reports/pilot-drone-n1/audit.py \
  --archive reports/pilot-drone-n1 \
  --source data/drone-control-v1/cases.jsonl \
  --output reports/pilot-drone-n1/audit.json
```
