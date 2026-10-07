# Fresh 27B: early four-GPU training evidence

The browser/drone expansion run has entered CUDA/NCCL optimization on N1-1
physical GPUs 0–3. The 08:07 UTC observation (`../monitoring/handoff-20260920T080741.json`, operational record retained in the development archive)
records **779 / 27,581 optimizer steps**, no nonfinite logged values, the same
four worker identities and unchanged active checkout. The full run is still
in progress; no final 27B checkpoint or task-quality result exists yet.

The later 11:05 UTC observation (`../monitoring/handoff-20260920T110540.json`, operational record retained in the development archive)
records 4,457 completed steps with unchanged process and active-code identities.
The step-4,000 manifest check (`../runtime-checks/27b-ddp-step4000-manifest.json`, operational record retained in the development archive)
passes hashes, metadata binding, finite logs and file stability checks. The
tensor and scheduled-row audits below retain their original early-run scope.

The run starts from pinned Qwen3.8-27B revision
`1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`, uses code
`99c5361d83edd5f9dbd11cb3f4bd9f9c54b5973e`, and has combined training/distribution
identity `24c861e3a7937db09c8ba68b240600cb33c743d200e91375246b724a062b5bdb`.
Its plan is one shuffled pass over **110,324 rows**, with one row per rank,
global batch four and maximum input length 4,096. The `training_rows_consumed`
field in `run.json` records that planned total; it is not a live progress counter.

## Completed-step and data audit

A separate CPU audit (`../runtime-checks/27b-ddp-early-training.json`, operational record retained in the development archive) captured
an earlier stable log prefix at **08:05 UTC: steps 1–728**. All steps were
contiguous, finite and marked world size/global batch four. The pinned
training schedule associates those steps with **2,912 unique training rows**,
728 per rank. It includes all 15 sources and all three task forms: 1,021 Choice,
1,434 Noul and 457 Score rows. In particular, the prefix includes **378 browser**
and **417 drone** rows.

The audit independently rebuilt the shuffle from the frozen training file and
seed 20260920, then matched its ordered-ID hash against the separately audited
step-500 snapshot. Rank-specific row IDs are not written in the optimizer log:
these coverage counts follow from saved inputs, the pinned schedule and the
completed-step cursor, not an independent replay of gradients or observation
of every rank's row presentations. Source coverage does not establish task
mastery; the entire training mixture has only 28 T-Rex rows, for example.

The three original baseline files each contain their planned 512 rows and are
bound to the frozen test, OOD and calibration selections. They are not final
trained predictions, and JF100 was not accessed during either audit.

## First immutable snapshot

The step-500 audit (`../runtime-checks/27b-ddp-step500-audit.json`, operational record retained in the development archive) passed all
**47 checks**. Its six files match before/after hashes and a retained local
copy. It is a schema-2 training-resume artifact with `inference_ready=false`.
The saved cursor and every AdamW state are at step 500, corresponding to 2,000
scheduled training rows.

CPU loading with `weights_only=True` succeeded without initializing CUDA.
The 322 trainable parameter tensors and 644 optimizer moment tensors are
finite; parameter/state shapes agree, second moments are nonnegative, and the
four rank-specific RNG records are distinct. Python and CPU RNG states passed
local round trips. Exact loading into a newly constructed Qwen model, CUDA RNG
restoration and an actual four-rank resumed optimizer step were not exercised.
The active training process was not interrupted.

Snapshot resume SHA-256:
`76844b4f52ba77155d847f4d136f54e5c521231290ccf7d7def8cd62e8050298`.
Training-state SHA-256:
`32c5faad98d90db0b31445de6b3942122a128ee844a81c886dc2b543e46e72bb`.
The 195,286,366-byte original snapshot remains on N1-1 and in ignored local
`runs/browser-drone-expansion-v1-27b-ddp-n1-v1-evidence/step-00000500`.

## Timing and memory scope

A later 09:07 UTC observation (`../monitoring/handoff-20260920T090730.json`, operational record retained in the development archive)
records 1,997 completed steps with no nonfinite log values and unchanged
supervisor, controller and four worker identities. A separate
step-1,500 manifest check (`../runtime-checks/27b-ddp-step1500-manifest.json`, operational record retained in the development archive)
verified all five listed file hashes, contiguous finite logs, a byte-identical
parent log prefix and unchanged baseline files. It did not load tensor payloads
or exercise a resume. The detailed first-snapshot and schedule audits above retain their
original step-500 and step-728 scopes.

The step-3,000 manifest audit (`../runtime-checks/27b-ddp-step3000-manifest-stability.json`, operational record retained in the development archive)
also passes the combined run identity, five file hashes, finite contiguous
log, parent prefix and baseline checks. It rechecks all payload hashes after
reading, binds the saved run metadata, and requires regular files within the
snapshot directory. Its file hashes also match the initial capture (`../runtime-checks/27b-ddp-step3000-manifest.json`, operational record retained in the development archive).
The 10:04 UTC observation (`../monitoring/handoff-20260920T100441.json`, operational record retained in the development archive)
records 3,199 completed steps and unchanged process/code identities. Use the
standalone read-only capture to check a later **already complete** snapshot;
give each observation a new output file:

```bash
python reports/runtime-checks/capture_27b_snapshot_manifest.py \
  --step 3000 --output /tmp/open-jev-step3000-check.json
```

This reads files over SSH with system Python, without importing Torch or
changing the job. Hash verification does not validate tensor semantics or
perform a resumed optimizer step.

These measurements use the fixed 728-step audited prefix above:

| Window | Mean seconds per optimizer step | Projected remaining optimizer hours |
| --- | ---: | ---: |
| Steps 1–728 | 3.079 | 22.96 |
| Last 500 steps | 3.043 | 22.70 |
| Last 100 steps | 2.680 | 19.99 |

The first two windows include the interval following the step-500 snapshot;
the last does not. Save time is included in the following logged interval and
is not measured separately. The clock starts after model loading and baseline
evaluation. These are early extrapolations, not completion commitments; final
snapshot saving, calibration, evaluation, reload, packaging, future downtime
and throughput changes are excluded.

The observed maximum allocated Torch memory was **59.64 GiB** across ranks.
At 08:07 UTC, `nvidia-smi` reported 72,015 / 69,555 / 66,595 / 73,479 MiB for
physical cards 0/1/2/3. Device usage includes allocator reservations and other
runtime overhead, so it differs from the logged allocated-memory peak. Early
successful steps do not establish memory fit for every remaining row or a
fourfold speedup over single-card training on a different mixture.

After the run completes calibration, final reload and cleanup, follow the
[pinned full-data and task evaluations](../../docs/final-checkpoint-evaluation.md).
Until then, keep the active checkout fixed and do not start competing GPU work.
