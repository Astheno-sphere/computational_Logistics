# Offline checkpoint release packaging

`scripts.package_checkpoint` prepares a local inference-weight package from a
**completed, verifiable run**. It uses Python's standard library and the
repository's standard-library-only `jev.metrics`. It does not import Torch,
load tensors, run a model, access the network, upload files, or change repository
visibility. The source run and frozen data are read-only inputs.

This tooling does not establish that the current GPU queue or release pipeline
has finished. Tests use synthetic artifact files, not real model weights.
Run it on a real artifact only after that run has produced its final summary,
calibration, trained predictions, and reload check.

## Command

From a checkout containing the packager, `jev/metrics.py`, `jev/__init__.py`,
`LICENSE`, and `third_party/qwen/{LICENSE,README.md}`:

```bash
python -m scripts.package_checkpoint \
  --run /path/to/completed-run \
  --output /path/to/new-package
```

If the run was copied from another machine, relocate its **unchanged frozen
data** explicitly:

```bash
python -m scripts.package_checkpoint \
  --run /path/to/copied-completed-run \
  --data /path/to/frozen-data \
  --output /path/to/new-package
```

Without `--data`, the script uses the data path recorded in `run.json`. A new
location does not relax checksum, selection, or provenance checks. The output
must not exist, must be outside the source run and data, and must have a single
publisher. Work is assembled in a temporary sibling directory, checked, then
renamed atomically. Validation/copy failures remove the temporary package.
The final JSON stdout reports the package path and manifest SHA-256; it always
reports `uploaded: false`.

## Required evidence

The completed run must retain:

| Input | Verification |
| --- | --- |
| `run.json` | Exact supported Qwen model/revision, training parameters, code commit, run identity hash, frozen-data hashes, and ordered selected IDs |
| `summary.json` | `status: complete`, matching model/steps/consumed rows, finite reload result, two temperatures, and eight metric sections |
| `training.jsonl` | Consecutive optimizer steps from 1 through the planned last step; finite loss, gradient norm, and elapsed time |
| `baseline_test.jsonl`, `baseline_ood.jsonl`, `baseline_calibration.jsonl` | Original baseline predictions bound to the selected rows; DDP also binds their original recorded hashes |
| `calibration.jsonl`, `trained_test.jsonl`, `trained_ood.jsonl` | IDs, groups, source, kind, targets, question IDs, target basis, finite logits, probabilities, and latency |
| `reload_check.jsonl` | First test row with matching identity and finite, equal-length logits; independently recomputed maximum error must match the summary and be at most 0.05 |
| Frozen data manifest and all five split JSONLs | Byte hashes and row counts must match the run and manifest; training/evaluation selections are rebuilt with the original seed and sampling policy |
| Final `checkpoint/` | Complete inference-file whitelist and consistent model, adapter and calibration metadata |

Both `jev.train` single-process runs and `jev.train_distributed` four-rank runs
are supported. DDP metadata is checked against the summary and step logs;
`identity_sha256` is its combined identity field, whereas the single-process
entrypoint records `run_identity_sha256`. Missing identities are rejected,
including older pilots that did not record one. No identity is invented to
make a legacy artifact pass.

A `training_resume_only` or distributed resume snapshot is not a final
inference checkpoint. Optimizer state is never loaded or copied. Model size,
training completion, and full-pass status are determined from verified fields
and row counts, not from a directory name. A bounded pilot is not labeled a
full pass.

Duplicate JSON keys, nonfinite JSON constants, inconsistent calibration,
changed source bytes, unknown checkpoint files, symlinks, and adapter metadata
containing credential fields are rejected. The native PEFT config's empty
`base_model_name_or_path` and null `revision` are accepted; `model.json` supplies
the authoritative pinned upstream identity. A nonempty conflicting identity or
local base-model path is rejected.

## Metrics and calibration

The packager checks raw probabilities against their logits, then reproduces
the trainer's exact Python rounding path: `softmax([x / temperature for x in
logits])`. It refits the trained and original-baseline temperatures separately
using **only their respective calibration rows**. Calibration split, count,
ordered-ID SHA, saved temperature and summary temperature must agree.

It recomputes all eight baseline/baseline-calibrated/trained/calibrated test
and OOD sections, including core metrics, ECE, coverage, kind/source/question
groups, Score ordinal error, and applicable Wiki action metrics. A same-sized
summary copied from another model is rejected when it disagrees with the raw
predictions. Only normalized, verified metric fields enter the package.

The generated model card shows actual sample counts and full source-split
sizes. In the current single-process full-pass configuration, test and OOD
metrics normally use **512 rows each**; they do not represent the separate
**26,452-row** release-v2 full-data evaluation. The expansion dataset has
different split sizes. No later evaluation, JF100 score, browser/drone pilot,
flight, or closed-loop result is automatically attached.

Dataset names and source composition are assigned only after all split hashes
match and the manifest has one of these exact hashes:

| Dataset | Manifest SHA-256 | Source composition |
| --- | --- | --- |
| `release-v2` | `56105dc9fc89ef74919f5beb60bb6ae8c6e17bb95699dab59205f67d8b338d97` | release-v1 + reasoning-control-v1 |
| `browser-drone-expansion-v1` | `ba001b88787ce21576017897a0cbdedd5917ceb29ad3522b0e1fb7b4836d49df` | release-v2 + browser-v1 + drone-control-v1 |

Other verified inputs are labeled **custom frozen dataset**, including fixture
datasets. A directory named `release-v2` is insufficient evidence.

## Package contents and licenses

The inference whitelist is:

```text
checkpoint/head.pt
checkpoint/model.json
checkpoint/temperature.json
checkpoint/adapter/adapter_config.json
checkpoint/adapter/adapter_model.safetensors   # or adapter_model.bin, exactly one
```

A standard `checkpoint/adapter/README.md` may exist in the source; it is
explicitly ignored so an older generated adapter card cannot substitute for the
new verified card. Extra checkpoint files and directories are rejected.

The package adds:

- `LICENSE`: the complete pinned upstream Apache 2.0 text, including Alibaba
  Cloud's copyright notice. Its required SHA-256 is
  `bbedc3fda3305820b977265f01b8619d87570a6739de3a5582c3464840f1e57a`.
- `LICENSE-CODE`: the repository's separate MIT source-code license.
- `UPSTREAM.md`: Qwen attribution and Open-Jev modification notices.
- `README.md`: a model card filled from this artifact's verified training and
  metrics, plus a minimal Open-Jev server command.
- `provenance.json`: normalized provenance, calibration binding, verification
  scope, and full hashes of the original source evidence files.
- `metrics.json`: the verified actual metrics.
- `manifest.json`: SHA-256 and byte count for every other package file. The
  manifest's own SHA-256 is returned separately to avoid self-reference.

Training weights in this package use **Apache-2.0**. Source code remains
**MIT**. Dataset licenses do not automatically license model weights. Original
`run.json` paths, PIDs, arbitrary environment fields, source datasets, baseline
rows, optimizer state, and training snapshots are not included.

The generated card directs users to install Open-Jev's `.[train]` dependencies
and serve `/path/to/package/checkpoint` with `python -m jev.server`. Inference
requires a suitable GPU and the exact upstream weights/tokenizer. Open-Jev's
scalar head and typed decisions require its loader; a regular AutoPeftModel
generation call does not implement the decision interface.

## Verification limits and tests

The packager hashes the **current** adapter/head bytes without deserializing
Torch, pickle or safetensors. It does not establish tensor validity or repeat
GPU inference. The current trainers did not record output-weight hashes at the
time of their reload check. Consequently, comparing saved reload logits verifies
the historical evidence, not an independent historical-to-current weight match.
These limits appear in every generated model card and provenance file.

```bash
python -m unittest discover -s tests -p test_checkpoint_package.py -v
```

The 11 tests cover single-process 2B/9B and DDP 27B metadata forms; private-field
omission; nonfinite, shape-mismatched or inconsistent reloads; calibration,
metrics and grouping tampering; duplicate JSON keys; data relocation and
mutation; unwanted optimizer/credential files; symlinks; pinned license bytes;
source changes during copying; and output preservation/temporary cleanup.
The fixture weight bytes are deliberately opaque test data and are never
presented as trained models or public release artifacts.
