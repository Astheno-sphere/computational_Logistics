# Four-GPU evaluation of completed checkpoints

`scripts/evaluate_checkpoints_parallel.py` defaults to the completed 2B checkpoint
and then the completed 9B checkpoint on **every frozen release-v2 test and OOD
record**. The explicit `browser-drone-expansion-v1` profile evaluates the new
four-GPU DDP 27B checkpoint on **all 40,281 expansion test/OOD records**. Four
independent model replicas divide the data on N1-1 GPUs 0–3.
The entry point does not train, fit temperatures, select easier examples, change
the saved context limit, run JF100, or manage another job's process.

## Default release-v2 invocation

Run after both full-pass training jobs finish and the supervising scheduler
has released all four assigned GPUs:

```bash
HF_HUB_CACHE=/mnt/localssd/open-jev/hf-cache \
HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
/mnt/localssd/open-jev/runtime/venv/bin/python \
  scripts/evaluate_checkpoints_parallel.py \
  --data /mnt/localssd/open-jev/repo/data/release-v2 \
  --checkpoint-root /data/zefan/open-jev/runs/release-v2-fullpass-n1-v1 \
  --output-root /data/zefan/open-jev/evals/fullpass-2b-9b-four-gpu-data-v1
```

The output directory must not exist. `--checkpoint-root ROOT` resolves to
`ROOT/2b/checkpoint` and `ROOT/9b/checkpoint`. Use `--checkpoint-2b PATH` and
`--checkpoint-9b PATH` for explicit checkpoint directories; each explicit path
overrides its root-derived path. Without a common root, both explicit paths
are required by the default two-model run. `--dataset-profile release-v2` and
`--models 2b 9b` are the unchanged defaults; the existing supervisor command
needs no update. `--models` can select either or both of those models, always
in canonical 2B → 9B order. The default data directory is `data/release-v2` in
the checkout containing this script. There is no row-limit option.

Each checkpoint must have its training run's `run.json` and `summary.json` in
its parent directory. The entry point verifies:

- The pinned Qwen model/revision, final head and adapter files.
- Completed full-pass training: 20,204 optimizer steps, accumulation 4,
  80,816 consumed train rows, all rows selected in shuffled order.
- A finite checkpoint reload error at most 0.05, matching the trainer's limit.
- The original five release-v2 split hashes in the run metadata.
- The positive saved temperature's `split=calibration`, count and ordered ID
  hash, matching the saved run IDs and the frozen calibration split.

No temperature is fitted or selected using these test/OOD records. A training
resume snapshot, partially written final checkpoint, short pilot or different
dataset is rejected. Accuracy has no completion threshold: a low measured
accuracy is a valid result.

## Explicit expansion 27B invocation

The expansion adapter is code-ready and CPU-verified; GPU execution is
unverified and waits for the new 27B DDP run to finish. Follow the separate
pinned-checkout procedure in [final-checkpoint-evaluation.md](final-checkpoint-evaluation.md)
before running this future command. The older service-suite revision
`ceb1ea85d7905d18972afb39da0f5f0baef2097a` does not contain this profile.

```bash
HF_HUB_CACHE=/mnt/localssd/open-jev/hf-cache \
HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
/mnt/localssd/open-jev/runtime/venv/bin/python \
  -m scripts.evaluate_checkpoints_parallel \
  --dataset-profile browser-drone-expansion-v1 --models 27b \
  --data /data/zefan/open-jev/data/browser-drone-expansion-v1 \
  --checkpoint-27b /data/zefan/open-jev/runs/browser-drone-expansion-v1-27b-ddp-n1-v1/checkpoint \
  --output-root /data/zefan/open-jev/evals/expansion-27b-four-gpu-data-v1
```

This profile accepts only 27B and rejects release-v2 checkpoint/data inputs.
If `--data` is omitted, it resolves to `data/browser-drone-expansion-v1` in the
new checkout. `--checkpoint-root ROOT` still resolves to `ROOT/27b/checkpoint`;
the explicit path above selects the actual DDP run layout. The output directory
must not exist. In addition to final files and the reload check, it requires:

- `Qwen/Qwen3.8-27B` at revision
  `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`.
- Completed 27,581 optimizer steps consuming all 110,324 training rows,
  accumulation/global batch 4, shuffled training, seed 20260920,
  maximum length 4,096 and LoRA rank 8.
- Matching run/summary four-rank CUDA/NCCL DDP topology, one local row per
  step, a 64-hex run identity, and initialization from `fresh_pinned_upstream`
  or `strict_same_run_ddp_resume`.
- Every training-log step from 1 through 27,581 with finite loss, gradient
  norm and elapsed time; each step must record world size/global batch 4.
- The saved temperature from exactly 512 calibration records. The ordered
  IDs hash, computed as `sha256(json.dumps(ids).encode())`, must be
  `a1903776bafb4af05654c91ceaf3dc19a1135f82384186e7216001c76190ddad`.
  Saved calibration predictions must match those IDs in order and contain
  nonempty finite logits.
- The exact expansion manifest hash
  `ba001b88787ce21576017897a0cbdedd5917ceb29ad3522b0e1fb7b4836d49df`
  and all five split hashes pinned in the evaluator. The training and
  calibration log hashes also become part of checkpoint completion identity.

The DDP trainer's 512-row-per-split evaluation does not substitute for this
complete held-out evaluation. No expansion GPU evaluation result is asserted
by the CPU tests or data preflight.

## Resource ownership

The hostname is fixed to `kwade5342000001` (N1-1). The checkout's
`state/auto_research/resource_policy.json` must explicitly contain
`parallel_data_evaluation_gpu_indices: [0, 1, 2, 3]`, permit those four indices,
and identify that hostname. This is a separate phase from the serial evaluation
suite; changing its old GPU-3 restriction is not part of this entry point.

The controller acquires `/tmp/open-jev-n1-gpu-0-3.lock` plus all four existing
`/tmp/open-jev-eval-gpu-{index}.lock` leases. A supervising wrapper should invoke
this command **without already holding those leases**. Later four-GPU training
must acquire the same leases after this process exits.

All four cards must have no compute process, less than 512 MiB allocated and
less than 10% utilization before launch. Discovered UUIDs bind the four workers
to physical indices 0–3; each worker sees its own card as `cuda:0`. Cards 4–7 are
outside this entry point's scope. The controller starts all four workers for
one model, reaps them, then starts the next model. It terminates only its own
`Popen` children after failures or SIGTERM/SIGINT, and waits up to 30 seconds for
driver cleanup before moving on or declaring completion. Occupancy by another
job causes a failure rather than a process termination.
Workers inherit the controller's process group. The handoff supervisor starts
that controller in its own session, so its final group-kill fallback also covers
workers if controller cleanup itself stalls.

## Fixed partition and recorded evidence

Each profile pins the actual bytes of all five split files. Only test and OOD
are evaluated. For release-v2, a row at zero-based position `i` within each
split belongs to worker `i % 4`. This unchanged `per_split` partition is reused
for both models; stable IDs and full record hashes bind every assignment.

| Split | Total records | Records per GPU |
| --- | ---: | ---: |
| Test | 10,532 | 2,633 |
| OOD | 15,920 | 3,980 |
| Both | 26,452 | 6,613 |

For expansion, concatenate test then OOD in original file order and assign
global position `i` to worker `i % 4` (`concatenated_test_ood`). The first OOD
record goes to rank 2 because test has 14,902 records. There is no padding,
dropping or sampling, and every held-out ID appears exactly once.

| Split | Total records | GPU 0 | GPU 1 | GPU 2 | GPU 3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Test | 14,902 | 3,726 | 3,726 | 3,725 | 3,725 |
| OOD | 25,379 | 6,345 | 6,344 | 6,345 | 6,345 |
| Both | 40,281 | 10,071 | 10,070 | 10,070 | 10,070 |

For each model the output directory contains:

- `plan.json`: dataset identity, checkpoint identity, policy/code hashes,
  UUIDs, partition rule and four ordered assignment hashes.
- `shard-{rank}.jsonl`: one raw result for each assigned row, including ID,
  split/index, source/group, target, row hash, checkpoint identity, saved
  temperature, logits/probabilities or explicit inference error.
- `shard-{rank}.json`: worker completion, assignment, output hash, counts,
  model-load/inference wall times and peak memory; `shard-{rank}.log` keeps
  diagnostic output.
- `merged-test.jsonl` and `merged-ood.jsonl`: validated results restored to
  original split-file order.
- `summary.json`: whole-split, source, kind and group statistics.

The root `manifest.json` records model order, owned process IDs, exit codes,
the current stage and final status. Profile, partition, per-split/total counts,
ordered IDs, all input hashes and rank assignments bind the plan, worker
reports and merged summary. Before any merge, all four workers must exit
successfully and produce matching checkpoint, data/plan, assignment and output
hashes. Missing, duplicate, reordered, cross-profile, wrong-split,
wrong-checkpoint or wrong-temperature rows cause failure. Raw probability
vectors are recomputed from saved logits and the frozen temperature for
verification.

## Failure denominators and performance interpretation

`jev.metrics.evaluate_probabilities` supplies the existing accuracy, expected
accuracy, NLL, Brier, ECE and confidence-threshold metrics. No oracle output or
uniform distribution substitutes for a failed inference. Every assigned error
row remains in the total and in per-source/per-group coverage:

- `count`, `successful`, `failed` and `inference_coverage` cover every row.
- `accuracy_all_rows_failures_incorrect` and
  `expected_accuracy_all_rows_failures_zero` include failures in the denominator.
- Top-level confidence-threshold `coverage` divides by all rows, including
  errors. The conditional probability metrics retain their explicitly stated
  successful-row scope.
- `probability_metrics_all_rows` is null if any prediction is missing;
  `probability_metrics_successful_rows_only` is labeled separately.

A worker crash makes the evaluation fail without producing a partial-data
success summary. Row-level inference errors preserve a complete error-aware
summary, mark it `completed_with_errors`, and give the controller a nonzero
exit status. The next model/training stage is not silently launched after an
evaluation failure.

`DecisionModel.load` and `TorchScorer` perform inference with the saved maximum
length. The existing forward method uses `truncation=False` and rejects long
inputs; these rejections become explicit error rows. Timing is four concurrent
replicas' wall time, including model loading in the controller measurement.
It is not a single-GPU latency benchmark and should not be mixed with earlier
serial latency reports.

CPU verification, without weights or GPUs:

```bash
python3 -m unittest tests.test_parallel_data_eval tests.test_four_gpu_handoff -v
```

The 36-test CPU run passed, including legacy supervisor behavior, expansion
checkpoint provenance, full-size partitioning and malformed shard rejection.
See `reports/runtime-checks/27b-expansion-eval-tests.json` and the independent
real-data audit `reports/runtime-checks/27b-expansion-eval-preflight.json`.
Neither performs model inference or establishes GPU evaluation completion.
