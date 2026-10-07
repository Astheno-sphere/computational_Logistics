# Fixed released-2B temporal-window pilot, October 2, 2026

The fixed adaptation improved aggregate synthetic temporal accuracy but
regressed on requests outside the valid window. It is a diagnostic checkpoint,
with no release promotion or official JevBench improvement claim.

## Frozen execution and verification

The [plan](../pilot-plan.json) was committed before evaluation. Source
`6db40fe18d354450984654020bbb1d05cb771ce9` ran once, from released package
`3076462e6356412082e79af909227b39b2863b90def79155ca0821aa506b7ded`, with
dataset manifest `615a79fff7bb8ba9b3774efacab81f051d8ff16b92abeb6003ab6472d03d278c`.
The final checkpoint was fixed at 64 optimizer steps and accumulation 4:
256 examples consumed, 128 distinct training rows. Calibration used 32
independent rows; test and controlled OOD each used 32 rows in eight complete
counterfactual groups. These correlated rows are small descriptive samples.

MS N1-1 GPU5 was released by the queue controller after two empty readings.
The actual pilot self-registered its Linux session birth identity before any
Torch/model call. The external [watchdog receipt](operations/temporal-v5-2b-fixed64-20261002.watchdog-receipt.json)
records exit 0, no timeout or error, 185.1475 seconds and confirmed session
cleanup. The queue controller independently observed zero live members of
that session, zero GPU5 memory and no compute process. No further model run
was requested. Released files remained unchanged, and saved/reloaded
probabilities agreed exactly on three fixed checks.

The [preflight](preflight.json) records all 11 source tests and five watchdog
fault checks passing in the actual runtime. The [raw artifact manifest](artifact-manifest.json)
pins 24 downloaded nonweight files. No adapted weights are included here.
The standard-library-only [replay](operations/replay.py) verified all file
hashes, 675 saved probability rows, all 64 finite-loss/gradient steps, all
16 whole-split temperature combinations, family/type/boundary/offset metrics
and paired decisions to `1e-12`; it imports neither the training runner nor
the Jev metric implementation. Its [receipt](independent-replay.json) preserves
the checks and the earlier-runtime baseline differences.

```bash
python reports/temporal-windows-v5-20261002/ms-2b-fixed-pilot/operations/replay.py \
  --dataset data/temporal-windows-v5-20261002-r1 \
  --previous-v4 reports/frontier-controls-v4/continued-2b-20261002
```

## Decision accuracy and paired regressions

Argmax accuracy is unchanged by either positive temperature. Both checkpoint
states were rerun in this same runtime; v4 rows are the original frozen
selection, rather than a new test.

| Split | Released | Fixed adapted | Incorrect→correct | Correct→incorrect |
|---|---:|---:|---:|---:|
| V5 test | 15/32 (46.9%) | 24/32 (75.0%) | 11 | 2 |
| V5 controlled OOD | 17/32 (53.1%) | 25/32 (78.1%) | 12 | 4 |
| V4 regression test | 86/128 (67.2%) | 83/128 (64.8%) | 4 | 7 |
| V4 regression OOD | 83/128 (64.8%) | 81/128 (63.3%) | 4 | 6 |

V5 Choice improved from 11/24 to 18/24 on test and 12/24 to 18/24 on OOD.
Noul argmax improved from 4/8 to 6/8 and 5/8 to 7/8. That argmax measure
does not include the abstention policy below.

| V5 boundary | Test released→adapted | OOD released→adapted |
|---|---:|---:|
| Before delivery | 1/4→0/4 | 2/4→1/4 |
| Exactly at delivery | 3/4→4/4 | 1/4→4/4 |
| Inside the window | 4/8→8/8 | 2/8→8/8 |
| Exactly at deadline | 3/4→4/4 | 1/4→4/4 |
| After deadline | 1/4→0/4 | 3/4→0/4 |
| Approved exception | 3/8→8/8 | 8/8→8/8 |

The outside-window rows together fell from 2/8 to 0/8 on test and from 5/8
to 1/8 on OOD. In the replayed [action-level diagnostic](exclusion-action-diagnostic.json),
the adapted model selected `accept` for all 12 outside-window Choice cases
(six in each split), despite shuffled option positions; every gold action was
`reject`. Before adaptation it selected `reject` for one of these test cases
and four OOD cases. This is an observed default-approval pattern. The aggregate
increase does not demonstrate learned interval comparison; this one run does
not establish the pattern's causal mechanism.

The v4 regression retained numeric accuracy at 6/20 on test and 7/20 on OOD.
State tracking fell from 15/24 to 13/24 and 15/24 to 14/24. Timeline test
fell from 16/24 to 15/24; timeline OOD remained 14/24. Authorization and
negation were unchanged; policy distractors lost one OOD row.

The released v4 test baseline here is 86/128, whereas the earlier v4 report
was 84/128. Exactly two timeline Choice decisions changed to correct; OOD
remained 83/128. The package files and base content identities were verified.
The earlier runtime used Torch 2.9.0+cu128; this run used 2.8.0+cu128. This
observed difference is preserved without attributing it to a particular
kernel/version. Adaptation comparisons use the current same-runtime baseline.

## Temperature and Noul abstention

Released temperature was `1.518796342858676`; the one newly fitted temperature
was `1.2960827517392262`, using only 32 calibration rows. All four combinations
are in the [raw summary](pilot/summary.json).

| V5 split | Released logits + released T: Brier / NLL | Adapted logits + released T | Adapted logits + fitted T |
|---|---:|---:|---:|
| Test | 0.5804 / 0.8563 | 0.3099 / 0.4681 | 0.3122 / 0.4611 |
| OOD | 0.5655 / 0.8061 | 0.3137 / 0.4813 | 0.3167 / 0.4829 |

Weights changed argmax decisions. The newly fitted temperature did not improve
all probability metrics: it slightly worsened adapted Brier on both splits
and NLL/ECE on OOD relative to those same adapted logits at the released
temperature. This is a descriptive ablation, not selection of a replacement
temperature from test/OOD results.

At inclusive `P(yes) <= 0.2` / `>= 0.8`, everything between those thresholds
abstains. Comparing released logits/T against adapted logits/fitted T:

| V5 split | Correct / all | Accepted / all | Errors / accepted | Abstentions |
|---|---:|---:|---:|---:|
| Test released | 1/8 | 2/8 | 1/2 | 6 |
| Test adapted | 3/8 | 3/8 | 0/3 | 5 |
| OOD released | 3/8 | 5/8 | 2/5 | 3 |
| OOD adapted | 4/8 | 4/8 | 0/4 | 4 |

Zero accepted errors in three or four examples is not a reliability estimate.
The v4 test accepted errors rose from 6/23 to 8/27; v4 OOD went from 9/23
to 8/25. Coverage changes must accompany any threshold-accuracy claim.

## Consequence for the next experiment

Keep this checkpoint separate from releases. Investigate the observed approval
pattern and the v4 state-tracking regressions, then freeze another original
training/evaluation design before any new model use. V5 test/OOD and the
previously inspected public64 sample are now development evidence. Exact
date/amount rules in an application should still use deterministic computation.
V5 did not address negative/zero balances or ledger-order variation. This one
synthetic pilot does not measure natural user requests, unseen workflow
domains, daylight-saving/business calendars or official JevBench progress.
