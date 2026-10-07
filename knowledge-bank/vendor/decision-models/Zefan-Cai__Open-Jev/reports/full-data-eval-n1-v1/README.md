# Full release-v2 held-out evaluation audit

This audit covers the completed, trained 2B and 9B checkpoints evaluated by
the original N1 four-GPU controller at source revision
`99c5361d83edd5f9dbd11cb3f4bd9f9c54b5973e`. Each model must cover all **10,532
test + 15,920 OOD = 26,452 records**, with 6,613 records per physical GPU 0–3.
It uses the historical per-split index-modulo-four partition.

## Verified results

The [2B audit](2b-audit.json) and [9B audit](9b-audit.json) each passed on all
26,452 rows, with no failed, missing or duplicate predictions. They independently
matched 275,339 and 281,315 numeric summary fields respectively, including all
918 test and 1,432 OOD groups. Maximum absolute metric differences were
`5.33e-15` and `1.74e-15`. Both complete 16-file source copies are retained locally.
At its capture, 2B was complete and the controller was still running 9B; that
historical status remains unchanged. The later 9B capture records the evaluation
controller complete with cleanup confirmed. That flag describes the evaluation
handoff at that time, not current GPU availability for another task.

Hard-label accuracy excludes soft-target rows. Expected accuracy uses target
mass at the first maximum-probability candidate over all rows. NLL, Brier and
ECE also cover every row in the named split and use the saved calibration.

| Model | Split | All rows | Hard correct / hard rows | Hard accuracy | Expected accuracy | NLL | Brier | ECE |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2B | Test | 10,532 | 9,515 / 10,046 | 94.71% | 91.95% | 0.195380 | 0.076117 | 0.011606 |
| 2B | OOD | 15,920 | 13,287 / 15,446 | 86.02% | 84.62% | 0.802990 | 0.246450 | 0.105594 |
| 9B | Test | 10,532 | 9,799 / 10,046 | 97.54% | 94.72% | 0.130947 | 0.039113 | 0.007707 |
| 9B | OOD | 15,920 | 14,205 / 15,446 | 91.97% | 90.40% | 0.299441 | 0.126647 | 0.037398 |

Customer-control decisions and the separate customer-service workflow source
are reported separately; neither is a live support-ticket completion test.

| Model | Source | Test hard correct / hard rows | OOD hard correct / hard rows | Test / OOD expected accuracy |
| --- | --- | ---: | ---: | ---: |
| 2B | `customer-control-v1` | 574 / 574 | 545 / 560 | 97.22% / 93.83% |
| 2B | `workflow-controls-v1/customer_service` | 452 / 456 | 568 / 600 | 99.12% / 94.67% |
| 9B | `customer-control-v1` | 574 / 574 | 560 / 560 | 97.22% / 96.33% |
| 9B | `workflow-controls-v1/customer_service` | 456 / 456 | 587 / 600 | 100.00% / 97.83% |

9B has more correct OOD customer-service workflow decisions, but that source's
NLL is `0.162840`, compared with `0.144101` for 2B. Higher hard-label accuracy
does not imply every probability-quality metric improved. The two models use
the same frozen evaluation IDs and definitions; this comparison is between
trained checkpoints and does not estimate training gain over a full-data baseline.

The three lowest sources by expected accuracy in each split expose limits
hidden by aggregate scores. Ranking is descriptive after evaluation and does
not change cases, calibration or inclusion in the denominator.

| Model | Split | Source | All rows | Hard correct / hard rows | Expected accuracy | NLL | Brier | ECE |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2B | Test | `trex_runner-v1` | 4 | 1 / 4 | 25.00% | 1.380182 | 0.819781 | 0.474135 |
| 2B | Test | `wikispeedia-v1` | 176 | 20 / 51 | 25.49% | 2.205727 | 0.328643 | 0.091963 |
| 2B | Test | `tic_tac_toe-v1` | 472 | 122 / 256 | 41.65% | 1.185687 | 0.398696 | 0.050996 |
| 2B | OOD | `wikispeedia-v1` | 219 | 33 / 57 | 29.28% | 2.159328 | 0.314261 | 0.124996 |
| 2B | OOD | `reasoning-control-v1` | 750 | 502 / 750 | 66.93% | 0.817463 | 0.449700 | 0.128141 |
| 2B | OOD | `painting-geometry-v1` | 6,912 | 5,565 / 6,912 | 80.51% | 1.432574 | 0.380853 | 0.184004 |
| 9B | Test | `wikispeedia-v1` | 176 | 23 / 51 | 27.09% | 2.168048 | 0.316286 | 0.096594 |
| 9B | Test | `tic_tac_toe-v1` | 472 | 165 / 256 | 52.06% | 1.098400 | 0.348093 | 0.066195 |
| 9B | Test | `trex_runner-v1` | 4 | 3 / 4 | 75.00% | 0.766888 | 0.405902 | 0.227246 |
| 9B | OOD | `wikispeedia-v1` | 219 | 38 / 57 | 32.74% | 2.111795 | 0.299055 | 0.143967 |
| 9B | OOD | `reasoning-control-v1` | 750 | 552 / 750 | 73.60% | 0.680170 | 0.360133 | 0.094176 |
| 9B | OOD | `painting-geometry-v1` | 6,912 | 5,965 / 6,912 | 86.30% | 0.460182 | 0.221294 | 0.079390 |

The T-Rex test source has only four rows. Wiki navigation and tic-tac-toe
include soft targets, so expected accuracy is not a game-win rate. Painting
OOD has 6,912 rows and, for 2B, much higher NLL/ECE than its 3,072-row test split
(NLL `0.012697`, ECE `0.003770`); 9B also shows a test/OOD gap there. Its weight
in the mixture matters when reading the overall OOD score.

## Capture and independent verification

`capture.py` makes read-only SSH queries and copies the 16 original per-model
evaluation files to ignored `runs/full-data-eval-n1-v1/<model>`. It waits for no
job: an unfinished model returns `not_ready` and exit code 2. Before copying it
requires the model summary and four worker reports to be complete, plus four
zero worker exits in the controller manifest. It preserves controller
manifests before/after copying, checks file hashes across the copy, and reads
the actual source-code, dataset and checkpoint hashes. It does not allocate a
GPU or alter a remote checkout, process, lease or file.

`verify.py` is a local CPU audit. It imports no project metric/model code and
recomputes accuracy, expected accuracy, NLL, Brier, expected Brier, 15-bin
top-label ECE and every confidence threshold directly from saved predictions.
It verifies every source/kind/group summary, every row identity and split
position, all four shard hashes, the original merged order and zero missing,
duplicate or failed predictions. The full five-split dataset, group separation,
saved calibration IDs, actual inference package files and source checkpoint
snapshots are bound into the result. The compact report retains all source/kind
metrics; group summaries are compared in full and recorded by counts/hashes.

Run only after root confirms that model completed:

```bash
python3 reports/full-data-eval-n1-v1/capture.py --model 2b
python3 reports/full-data-eval-n1-v1/verify.py \
  --model 2b --evidence runs/full-data-eval-n1-v1/2b \
  --checkpoint-evidence runs/fullpass-n1-v1/2b-evidence \
  --package reports/checkpoint-packages/2b-fullpass-v1 \
  --weight-package runs/model-packages/release-v2-fullpass-n1-v1/2b \
  --output reports/full-data-eval-n1-v1/2b-audit.json
```

For 9B, replace each `2b` in the commands with `9b`. Existing destinations
and audit outputs are never overwritten. An interrupted or changed-source
copy retains its partial directory. An audit failure writes an explicit
failure report with no metrics; preserve it before a separately named retry.
No continuous polling or automatic GPU evaluation is performed.

Completion belongs to the individual model. The 2B report can be valid while
the controller is still running 9B. The captured controller status and cleanup
flag remain separate from `model_evaluation_complete`.

These are trained-checkpoint full-data metrics. **No full-data baseline was
run**, so no full-data training gain is claimed. Historical baseline results
cover only 512 selected test and 512 selected OOD records. Synthetic held-out
decision metrics do not measure end-to-end browser, game or flight competence.
Four-replica wall time is not a single-GPU latency result. The current byte
identity binds the evaluated checkpoint to packaged inference files; it does
not retroactively bind the trainer's historical reload to a weight digest that
was not recorded at that time.
