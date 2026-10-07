# Browser snapshot service evaluation

`scripts.evaluate_browser_service` sends the exact saved browser requests to an
Open-Jev HTTP service. It measures decisions on synthetic held-out snapshots.
There is no browser executor, page transition, or real web-task success metric.
The visible-state teacher supplies evaluation references only; it never fills
in a failed model response.

## Run

Use the frozen [browser dataset](browser-data.md), including `cases.jsonl` and
its sibling `manifest.json`. Start a real model service separately, then run:

```bash
python -m scripts.evaluate_browser_service \
  --cases data/browser-v1/cases.jsonl \
  --endpoint http://127.0.0.1:8791/v1/systemone \
  --split test ood --parents-per-split 20 --variants-per-parent 3 --seed 42 \
  --expected-model Qwen/Qwen3.5-2B --expected-method lora_decision_head \
  --output-dir runs/browser-2b-pilot-v1
```

`--expected-revision` and `--expected-checkpoint-sha256` optionally pin the
reported model artifacts. A checkpoint service must report its checkpoint hash;
all services must report their model, base revision, accepted scoring method,
positive calibration temperature, and exact candidate-sequence count. The
evaluator also records code commit and context limit when exposed. An identity
change during the run invalidates the affected response and sets an error exit
code; raw responses remain available for inspection.

The managed N1-1 suite can run this same fixed sample with its own server,
checkpoint identity checks and physical-GPU-3 guard:

```bash
python -m scripts.run_service_suite \
  --expected-hostname kwade5342000001 --gpu 3 --models 2b 9b 27b \
  --checkpoint-root /mnt/localssd/open-jev/runs \
  --checkpoint-template '{tag}-pilot-v1/checkpoint' \
  --browser-cases /data/zefan/open-jev/data/browser-v1/cases.jsonl \
  --measurements browser --max-length 16384 --batch-size 1 \
  --output-root /data/zefan/open-jev/evals/pilot-browser-snapshots-n1-v1
```

`browser` is opt-in; it does not change the suite's original default workloads.
For a completed full-pass checkpoint, change its root/template and use a new
output directory. `--models` can select one model as its final checkpoint
becomes ready. Run from the separate evaluation checkout, preserving the
training checkout and frozen datasets.

Use `--max-cases 8` for a bounded integration check. The default protocol selects
20 parents from each split and up to three variants per parent: at most 120
requests. Parents and variants are ranked by SHA-256 of their IDs and seed,
without consulting references. Case limits are applied in round-robin order
across splits and parents before adding a second variant. The report records
actual parent/case/variant counts; a capped run is a different configuration.

Every source case is checked for duplicate IDs, cross-split parent groups and
identical cross-split requests before selection. The cases-file hash and count
must match its manifest. Selected requests must exactly reproduce the current
runtime builder, including mapping order, and their saved active references
must match the disclosed teacher. This does not revalidate unrelated training
split files or establish semantic decontamination.

## Metrics and denominators

`report.json` contains `overall` and `by_split`, each with `cases`, `parents`,
`variants`, `teacher_operations`, and these `metrics` objects:

| Key | Denominator and interpretation |
| --- | --- |
| `operation` | All selected snapshots; the operation Choice matches the reference |
| `active_conditional` | Reference-active target/value heads with at least two candidates, even when the model predicts the wrong operation |
| `forced_active_conditional` | Reference-active heads with exactly one candidate, reported separately from the main conditional metric |
| `proposal_exact` | All selected snapshots; the complete proposal for the predicted operation exactly matches the reference operation, target and applicable value |

Every metric contains `{correct, total, accuracy}`. A zero head denominator has
`accuracy: null`. Inactive heads have no gold and contribute no head denominator.
However, the complete response must pass the existing browser adapter's typed
answer/probability validation, including inactive questions. Every Choice also
requires a finite confidence in [0, 1] consistent with its probabilities under
Open-Jev's confidence formula. Missing questions or confidence, invalid
probabilities, HTTP failures, malformed JSON or identity errors make
the whole case score zero across its applicable metrics. One HTTP attempt is
made per case; no retries or fallback predictions are used.

The three variants of one parent are correlated. These are descriptive sample
accuracies, without an independent-sample confidence interval or a browser-task
completion claim. Reports from the original pilots must still be identified as
100-step pilot results, separately from later trained checkpoints.

## Artifacts and exit codes

The output directory must be empty or absent; prior or partial runs cannot be
overwritten. Each run retains:

- `selection.json`: source/manifest/evaluator hashes, configuration, expectations,
  selected case identities and a selection hash.
- `requests.jsonl`: exact posted JSON text and SHA-256, written before each call.
  The body contains only `model`, `state` and `questions`.
- `references.jsonl`: only active reference answers and their complete proposal.
- `outcomes.jsonl`: HTTP status, timing, exact response-body bytes as base64 and
  SHA-256, parsed response when possible, service identity, errors and scores.
- `report.json`: progress and final aggregate results. Pending cases retain
  their denominators and score zero if a run is interrupted. `complete` and
  `pending_cases` must be checked before interpreting a partial report.

Exit **0** means all selected cases were attempted without transport, identity
or schema errors; incorrect model decisions still produce exit 0. Exit **1**
means all were attempted but at least one such error occurred. Exit **2** means
configuration, source integrity or artifact I/O failed. A keyboard interruption
propagates normally, after attempting to save an `interrupted` report.

CPU-only tests use an explicitly synthetic local HTTP test server; those tests
verify evaluation accounting and are not model results:

```bash
python -m unittest tests.test_browser_service_eval -v
```
