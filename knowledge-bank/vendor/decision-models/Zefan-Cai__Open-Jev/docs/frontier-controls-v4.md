# Frontier controls v4

This is an original synthetic development mixture for six failure conditions:
deadline boundaries, latest-account state, direct authorization and revocation,
negation, numeric candidate selection, and irrelevant department policies.
All labels are recomputed by executable Python oracles. These are synthetic
controls, not real customer conversations.

The previously published 27B public JevBench result informed the priorities:
`temporal_numeric` had 13 errors among 15 decisions, and `long_policy` had eight
among 19. The analysis preserves the checkpoint and aggregate checksum in
[development-error-families.json](../reports/frontier-controls-v4/development-error-families.json).
Individual original responses were not available in the local saved aggregate;
the analyzer does not invent per-example explanations. JevBench's 231 public
decisions are now development feedback, not an untouched test. No public
benchmark question, scenario or answer text, and no sealed material, enters the
generator.

## Build and audit

```bash
python -m scripts.build_frontier_controls_v4 \
  --output data/frontier-controls-v4-20261002 --groups-per-family 100
python -m scripts.analyze_jevbench_errors \
  --report reports/new27b-jevbench-20260922/report.json \
  --output reports/frontier-controls-v4/development-error-families.json
python -m unittest tests.test_frontier_controls_v4
```

Both commands refuse to overwrite their outputs. The generator needs only the
standard library. The default produces 3,360 records: 2,400 train and 240 each
for calibration, validation, test and OOD. Every four counterfactual variants
of a scenario remain in the same split; the split is never placed in the model
state. Every record follows the existing training schema and includes original
CC0-1.0 provenance, its generator revision, and a group identifier. The manifest
pins each split and the generator by SHA-256.

Three variants use dynamic Choice candidates, and one asks whether a proposed
outcome holds as a Noul. Option order is shuffled independently of the label.
The independent `audit` recomputes the answer from state facts and rejects even
a valid one-hot target if it differs from the oracle.

The OOD split uses separately named template versions, rewritten question
prefixes, new entity identities and, where applicable, new time windows and
departments. It tests controlled variations within these six workflows. It
does not establish transfer to wholly new domains or human-written requests.

## Evaluate before claiming improvement

Use the untouched synthetic test/OOD files once after choosing training and
calibration settings on their respective files. Preserve the unmodified
checkpoint baseline on the same records. The continued-training runner selects
256 train, 64 calibration and 128 each test/OOD rows by whole counterfactual
group, balancing families without looking at labels:

```bash
python -m scripts.train_frontier_controls_v4 \
  --checkpoint /path/to/released-2b-checkpoint \
  --data data/frontier-controls-v4-20261002 \
  --output runs/frontier-controls-v4-2b-20261002 \
  --steps 64 --train-rows 256 --calibration-rows 64 --eval-rows 128
python -m unittest tests.test_train_frontier_controls_v4
```

It starts from `DecisionModel.load`, explicitly enables the existing LoRA A/B
and decision-head parameters, and keeps the backbone frozen. It uses the
released temperature for the original baseline, fits the new temperature only
on independent calibration rows, and locks it before trained test/OOD inference.
Checkpoint selection is the fixed final step; test and validation do not choose
training settings or checkpoints. Split hashes, selected IDs, checkpoint files,
runner hash, code commit and trainable parameter names are recorded. A fresh
load must reproduce probabilities within 0.005 on saved Choice/Noul/OOD probes.

Report the selected IDs and input hashes, per-family accuracy, Noul Brier/ECE,
and the original-checkpoint versus adapted-checkpoint difference. Improvement
on this mixture does not imply improvement on JevBench or BANKING77.

## Completed 2B continued-training pilot, October 2, 2026

One fixed 64-step run consumed 256 training rows, with four rows per optimizer
step. It used 64 separate calibration rows and 128 rows each from test and OOD.
The released Open-Jev-2B checkpoint and the adapted checkpoint used the same
selected records, pinned Qwen base revision and 4,096-token limit on one H200.
The original checkpoint remained unchanged. This is an experimental adapted
checkpoint, not a replacement for the released model.

| Measure | Test, released → adapted | Controlled OOD, released → adapted |
| --- | ---: | ---: |
| Accuracy | 84/128 → 99/128, 65.6% → 77.3% | 83/128 → 95/128, 64.8% → 74.2% |
| NLL | 0.8900 → 0.6046 | 0.9080 → 0.6998 |
| Brier | 0.4903 → 0.3266 | 0.5028 → 0.3733 |
| ECE, 15 bins | 0.1353 → 0.1088 | 0.1736 → 0.1261 |
| Noul accuracy, 32 rows | 24/32 → 26/32, 75.0% → 81.3% | 22/32 → 26/32, 68.8% → 81.3% |
| Noul Brier | 0.4748 → 0.3288 | 0.5703 → 0.3096 |
| Noul ECE, 15 bins | 0.2240 → 0.1844 | 0.3033 → 0.1467 |

These synthetic metrics use argmax decisions and sum squared probability error
over the complete class vector. The Noul Brier values therefore include both
No and Yes components. Noul ECE uses selected-class confidence; these are not
JevBench's selective 0.2/0.8 scoring or a Yes-only calibration metric.

| Family | Rows per split | Test accuracy, released → adapted | OOD accuracy, released → adapted |
| --- | ---: | ---: | ---: |
| Authorization | 20 | 75.0% → 100.0% | 75.0% → 100.0% |
| Negation | 20 | 95.0% → 100.0% | 85.0% → 100.0% |
| Numeric candidates | 20 | 30.0% → 30.0% | 35.0% → 30.0% |
| Irrelevant policies | 20 | 75.0% → 100.0% | 75.0% → 100.0% |
| Account state | 24 | 62.5% → 75.0% | 62.5% → 66.7% |
| Timeline | 24 | 58.3% → 62.5% | 58.3% → 54.2% |

Numeric candidate accuracy did not improve on test and fell on OOD; timeline
accuracy also fell on OOD. Aggregate gains therefore do not establish reliable
arithmetic or deadline handling. Production workflows should compute exact
amounts and dates in code and retain the model for semantic decisions.

The original temperature was 1.518796342858676; the new calibration-only
temperature was 1.5446931834967927. NLL, Brier and ECE differences include both
weight updates and fresh temperature fitting. Accuracy uses the probability
argmax, which temperature scaling does not change. This is one synthetic
pilot seed with controlled variations within the same workflows; it does not
establish JevBench, BANKING77, new-domain or real-customer improvement.

The [full summary](../reports/frontier-controls-v4/continued-2b-20261002/summary.json)
and [run lock](../reports/frontier-controls-v4/continued-2b-20261002/run.lock.json)
preserve selected IDs, split and checkpoint hashes, exact settings and source
commit `80ca8e81d08992cb2a4cbb6a0caa1355ad3e5aee`.
The [training log](../reports/frontier-controls-v4/continued-2b-20261002/training.jsonl),
[calibration lock](../reports/frontier-controls-v4/continued-2b-20261002/calibration.lock.json)
and [reload probes](../reports/frontier-controls-v4/continued-2b-20261002/reload-check.jsonl)
are saved without checkpoint tensors. Fresh checkpoint reload reproduced the
saved probabilities exactly on the three Choice/Noul/OOD probes: maximum error
0.0. The [completion receipt](../reports/frontier-controls-v4/continued-2b-20261002/completion-receipt.json)
records 185.99 seconds for the full runner, including evaluation, training,
calibration and reload. Its serving checkpoint fingerprint is
`61e22c91bfbcdcba02ea1c62d039d8169cdf4f73f79cfe2c170322da2bb7c037`;
the runner also records a separate hash of the essential checkpoint-file
hashes, so the two identity algorithms should not be compared as equal values.
