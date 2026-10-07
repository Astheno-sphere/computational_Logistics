# Independent final 27B expansion audit

This directory prepares capture and offline verification of the **40,281**
expansion predictions. **No final-model audit has run, and no final 27B weight
package or prediction hashes are asserted here.** The CPU tests below use tiny
synthetic artifacts and existing preflight metadata; they do not load a model,
contact N1 or generate real predictions.

The contract is specific to the existing N1 final run:

| Identity | Fixed value |
| --- | --- |
| Model | `Qwen/Qwen3.8-27B`, revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0` |
| Evaluator commit | `0b6e4fcca3306b9fe98b96a08074e78b4674fd16` |
| Training commit | `99c5361d83edd5f9dbd11cb3f4bd9f9c54b5973e` |
| Run identity | `24c861e3a7937db09c8ba68b240600cb33c743d200e91375246b724a062b5bdb` |
| Dataset | `browser-drone-expansion-v1`; manifest `ba001b88787ce21576017897a0cbdedd5917ceb29ad3522b0e1fb7b4836d49df` |
| Full pass | 27,581 steps, 110,324 records, four CUDA/NCCL ranks |
| Evaluation | 14,902 test + 25,379 OOD; global concatenated index modulo four |
| Rank counts | 10,071 / 10,070 / 10,070 / 10,070 |

All five split hashes and the ordered 512 calibration-ID hash are fixed in
`expansion_contract.py`. `CALIBRATION_IDS_SHA` identifies selected IDs only;
actual calibration logits, training logs and checkpoint bytes are hashed from
completed artifacts. A different resumed source commit or run identity needs
explicit review; no CLI option weakens these pins.

## Future capture and verification

Use Python 3.12+ from the repository checkout. After the final run and complete
expansion evaluation have finished, explicitly invoke capture locally:

```bash
python3.12 reports/full-data-eval-expansion-n1-v1/capture.py \
  --output runs/full-data-eval-expansion-n1-v1/27b
```

Capture uses read-only SSH and tar against the fixed N1 paths. It requires an
existing trusted SSH host key, completed training/evaluation, four zero worker
exits and controller cleanup. Missing or unfinished completion artifacts return
`not_ready` with exit code 2 and create no destination. It never waits for a job,
allocates a GPU, changes a checkout or launches inference.

The copy contains all 16 evaluation files under `evaluation/`, six training
evidence files under `training/`, all checkpoint files (including PEFT's optional
README), two controller manifests and `capture.json`. Source hashes must agree
before and after copying. Existing destinations are preserved; failed copies
retain a separately named partial directory for inspection.

First create the actual final inference package through the standard
[offline checkpoint packaging workflow](../../docs/checkpoint-package.md), then
copy the complete package unchanged to
`runs/model-packages/browser-drone-expansion-v1/27b`. **That package does not yet
exist.** Packaging needs the complete finished run and frozen dataset; the
capture's reduced training evidence is not a substitute for those packager
inputs. With the unchanged local frozen dataset available:

```bash
python3.12 reports/full-data-eval-expansion-n1-v1/verify.py \
  --evidence runs/full-data-eval-expansion-n1-v1/27b \
  --data data/browser-drone-expansion-v1 \
  --package runs/model-packages/browser-drone-expansion-v1/27b \
  --output reports/full-data-eval-expansion-n1-v1/27b-audit.json
```

The verifier checks source commit bytes, all dataset/checkpoint/package hashes,
DDP completion logs, fixed calibration IDs and saved reload logits. It verifies
every original shard row and merged position, all 40,281 unique IDs and every
source/kind/group metric. Independent arithmetic recomputes saved-temperature
softmax, accuracy, expected accuracy, NLL, Brier, expected Brier, ECE and
confidence coverage. It reuses only the historical CPU verifier's hash-pinned
helpers; it never invokes producer metrics or merger code.

Inputs are rehashed before a passed report is written. Absent, inconsistent,
failed or incomplete evidence yields a failed report with no metrics. No final
checkpoint digest is guessed; the actual current checkpoint tree is tied to the
evaluation plan and the package's five inference payloads. Saved reload logits
do not retroactively prove the bytes loaded during historical inference.

This is a trained-checkpoint audit without a full-data baseline. It cannot
establish training gain, size-only effects across different training mixtures,
single-GPU latency, or end-to-end browser, game or flight success. Failed outputs
remain preserved and must not be replaced or omitted to claim completion.

## Local CPU verification

```bash
PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover \
  -s tests -p test_expansion_data_audit.py -v
PYTHONDONTWRITEBYTECODE=1 python3.12 reports/full-data-eval-expansion-n1-v1/capture.py --help
PYTHONDONTWRITEBYTECODE=1 python3.12 reports/full-data-eval-expansion-n1-v1/verify.py --help
```

The focused tests cover a five-row synthetic audit, global split-boundary
assignment, full-size counts from metadata, schemas/source hashes from pinned
producer commit `0b6e4fcc`, standard package compatibility, and rejection of
wrong identities, incomplete runs, calibration changes, missing/duplicate/failed
predictions, changed probabilities/metrics/weights, unstable captures, symlinks,
unsafe archives and output overwrites. No held-out dataset or JF100 rows are
read by these tests. The historical 2B/9B capture and verifier remain unchanged.

The [CPU preparation record](preparation-check.json) records **17 passing tests**
on Python 3.12.14 and both CLI help checks. A separate
[arithmetic review](arithmetic-review.json), reproduced by
[`review_arithmetic.py`](review_arithmetic.py), compared 1,155 synthetic rows
across seven batches and 847 numeric fields with the pinned producer. Maximum
absolute error was `4.62e-14`, within `1e-10` tolerance. These are tool-validation
results, not final-model scores.
