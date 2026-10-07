# Browser/drone mixture: input-length preflight

All three pinned tokenizers processed **all 163,050 records and 544,089 candidate
sequences per model**. The maximum is **1,756 tokens**. The existing expansion
training cap, `--max-length 4096`, accepts every sequence without truncation.
This is a tokenizer and configuration result; the candidate mixture remains
**untrained** and this audit establishes neither GPU memory fit nor task quality.

| Model | Frozen revision | Required 4,096 cap |
| --- | --- | --- |
| Qwen/Qwen3.5-2B | `15852e8c16360a2fea060d615a32b45270f8a8fc` | Pass |
| Qwen/Qwen3.5-9B | `c202236235762e1c871ad0ccb60c8ee5ba337b9a` | Pass |
| Qwen/Qwen3.8-27B | `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0` | Pass |

## Complete measurements

The three independently produced per-row length files are byte-identical. The
following counts therefore apply to **each** model, not to their combined work.
Percentiles use nearest rank over candidate sequences.

| Split | Records | Candidates | Nonpadding tokens | Maximum | p99 | Rows over 1,536 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Train | 110,324 | 365,257 | 188,212,841 | 1,445 | 1,255 | 0 |
| Calibration | 6,883 | 20,625 | 12,365,943 | 1,432 | 1,267 | 0 |
| Validation | 5,562 | 16,670 | 9,813,052 | 1,432 | 1,266 | 0 |
| Test | 14,902 | 50,181 | 27,906,286 | 1,441 | 1,267 | 0 |
| OOD | 25,379 | 91,356 | 65,828,973 | 1,756 | 1,567 | 449 |
| All | 163,050 | 544,089 | 304,127,095 | 1,756 | 1,490 | 449 |

The longest row is
`browser-control-v1:parent:76dfec94cd14bf434388f3a4:ambiguous_observed_target:operation`
in OOD, candidate index 6 (zero based).

| Explicit cap | Rows exceeding cap | Candidate sequences exceeding cap |
| --- | ---: | ---: |
| 512 | 63,259 | 222,099 |
| 1,536 | 449 | 1,833 |
| 2,048 | 0 | 0 |
| 4,096 | 0 | 0 |
| 8,192 | 0 | 0 |
| 16,384 | 0 | 0 |

The 512 and 2,048 results were independently derived from the complete saved
lengths by [verify.py](verify.py); the remaining caps were also counted by each
original tokenizer audit. The default `jev.train --max-length 512` is unsuitable:
40,926 train rows exceed it, including every browser and drone train row.
The older `scripts/preflight.py` default of 1,536 rejects part of OOD; explicitly
pass `--max-length 4096` for this mixture. No code default or source data was
changed to obtain a pass.

## Encoding and rejection behavior

The audit follows `DecisionModel.forward`: `candidate_prompts`, the model's
chat template with `tokenize=False`, `add_generation_prompt=True` and
`enable_thinking=False`, then tokenizer defaults with `truncation=False`.
Noul emits one candidate sequence; Choice and Score emit one per option.
Targets, metadata and row IDs are excluded from model inputs.

Bulk counting omits padding. For the first two rows of every populated
source/split pair (**144 sampled rows per model**), the audit checks lengths
against padded tokenization and compares token IDs with the older preflight's
`apply_chat_template(tokenize=True)` path. There were **zero mismatches**.
This sampled check does not prove every old-preflight token ID matches, and
identical length files do not prove token IDs are identical across models.

`DecisionModel.forward` sums attention masks and raises `ValueError` above the
configured cap, before transferring tensors to its device. It does not silently
truncate. [check_rejection.py](check_rejection.py) checks that actual method on
the longest OOD row using the real tokenizers and a CPU sentinel in place of the
neural backbone. Caps 512, 1,536 and 1,755 must reject; 1,756, 2,048 and 4,096
must reach the sentinel with all input tokens intact. See
[the observed rejection results](rejection-check.json). `DecisionModel.__init__`
is bypassed; no model weights, real backbone computation or CUDA initialization
is used.

## Workload implications

The trainer encodes all candidates of one row together. Gradient accumulation
does not reduce that row's candidate count. Serving batch/chunk settings do not
apply to this training loop.

| Train input dataset | Records | Candidates | Nonpadding tokens | Tokens after per-row padding |
| --- | ---: | ---: | ---: | ---: |
| release-v2 | 80,816 | 236,938 | 49,518,646 | 49,807,443 |
| browser-v1 | 13,814 | 80,661 | 86,614,407 | 87,020,151 |
| drone-control-v1 | 15,694 | 47,658 | 52,079,788 | 52,137,805 |
| Mixture | 110,324 | 365,257 | 188,212,841 | 188,965,399 |

Relative to release-v2, this mixture has **1.365× the train rows but 3.801× the
nonpadding input tokens** (3.794× after per-row padding). These are workload
counts, not a measured training-time multiplier. The largest train row has
8 candidates × 1,445 tokens = **11,560 padded tokens**; the largest OOD row has
8 × 1,756 = **14,048**. The maximum candidate count in any single row is 16.
No forward/backward memory or throughput measurement was performed.

Retain the current 4,096 training cap for the next experiment. A 2,048 cap also
covers these frozen records, but this flag is a rejection bound; padding is to
the current row's longest candidate, not to the configured cap. Raising the
cap to 8,192 or 16,384 is unnecessary for this dataset.

## Proposed next training run — not launched

[proposed-training.json](proposed-training.json) records a **fresh 2B pilot**:
400 optimizer steps, accumulation 4, all train rows eligible in a deterministic
shuffled order. It consumes **1,600 records**, not a full pass. Wait until its
designated training GPU is free; do not use the evaluation GPU or interrupt any
current training process. This audit did not launch this command:

```bash
cd /mnt/localssd/open-jev/repo
CUDA_VISIBLE_DEVICES=GPU-fc42ba52-5802-1120-aef6-87fb880ddb8e \
HF_HUB_CACHE=/mnt/localssd/open-jev/hf-cache \
HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=4 \
/mnt/localssd/open-jev/runtime/venv/bin/python -u -m jev.train \
  --model Qwen/Qwen3.5-2B \
  --revision 15852e8c16360a2fea060d615a32b45270f8a8fc \
  --data /data/zefan/open-jev/data/browser-drone-expansion-v1 \
  --output /data/zefan/open-jev/runs/browser-drone-expansion-v1-2b-pilot-n1-v1 \
  --steps 400 --train-rows 0 --max-length 4096 \
  --training-sampling shuffled --accumulation 4 \
  --eval-rows 512 --calibration-rows 512 \
  --lora-rank 8 --lr 5e-5 --head-lr 1e-4 --brier-weight 0.1 \
  --seed 20260920 --checkpoint-every 100
```

A one-pass run would instead require **27,581 optimizer steps** because
110,324 / 4 = 27,581, with a new output directory and, for example, checkpoint
interval 500. Neither release-v2 snapshots nor a completed 400-step pilot can
be resumed under this different dataset/schedule: the current strict resume
identity binds dataset hashes, selected records and total steps. The supported
path is a fresh run from the pinned base model. Do not bypass resume validation.

`scripts/launch_expansion.py` already specifies 4,096, but requires exactly three
simultaneously free GPUs; it cannot fill only one newly freed training slot.
The proposed direct command handles one model and must be scheduled with the
same resource policy. Length passing alone is not a GPU launch readiness check.

## Provenance and reproduction

The immutable input manifest SHA-256 is
`ba001b88787ce21576017897a0cbdedd5917ceb29ad3522b0e1fb7b4836d49df`.
The training checkout stayed at
`99e881108c6cacadafd364088505e84975ca43fc`; inspected implementation file hashes
and all five input split hashes remained unchanged. Each audit ran CPU-only,
offline, with a weight-file read guard and one tokenizer/OMP worker. Runtime:
Transformers 5.10.2 and tokenizers 0.22.2. Torch was imported by the runtime;
CUDA was not initialized. No model weights were loaded.

The runs completed on 2026-09-20 UTC in approximately 434–438 seconds each,
with exit code 0. All three observed training PIDs (409482, 409485, 409498)
retained their original start ticks before and after the audits. The later
[remote state capture](remote-state-after.json) confirms the pinned checkout
and active PIDs; its only untracked checkout file was `_vizdoom.ini`.

The exact audit source is [scripts/audit_candidate_lengths.py](../../../scripts/audit_candidate_lengths.py),
SHA-256 `3bb6eb7ab72a90743f64b1fa225bccadad76ffd2c6c4da071deeb534a7f6db8c`.
The individual model reports contain all source, tokenizer-asset and data hashes:
[2B](2b/report.json), [9B](9b/report.json), [27B](27b/report.json).
Each model directory also contains its own `row-lengths.jsonl.gz` (7,865,816 bytes),
SHA-256 `f1d48a59f9c6ba25318fb2b30b2d50fab9b15c7bd708a80d3bc9d636ca7bc2e8`.

To repeat the tokenizer measurement on N1-1, place the frozen audit script outside
the checkout, retain `CUDA_VISIBLE_DEVICES=''`, and choose an absent output
directory. Substitute the model and revision from the table for the other runs:

```bash
CUDA_VISIBLE_DEVICES='' HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
nice -n 15 /mnt/localssd/open-jev/runtime/venv/bin/python \
  /data/zefan/open-jev/preflights/browser-drone-expansion-v1-input-lengths-20260920/audit_candidate_lengths.py \
  --repo /mnt/localssd/open-jev/repo \
  --data /data/zefan/open-jev/data/browser-drone-expansion-v1 \
  --cache-dir /mnt/localssd/open-jev/hf-cache \
  --model Qwen/Qwen3.5-2B --revision 15852e8c16360a2fea060d615a32b45270f8a8fc \
  --expected-encoder-sha256 b8f135ef2da1f1205ba715b02f3dcf3c25962a2bec7e92a335198f59b6083c83 \
  --output-dir /data/zefan/open-jev/preflights/browser-drone-expansion-v1-input-lengths-recheck/2b \
  --max-length 4096
```

To verify the archived evidence locally without tokenizers, weights or network:

```bash
python3 reports/preflight/browser-drone-expansion-v1/verify.py \
  --data data/browser-drone-expansion-v1 > /tmp/browser-drone-length-verification.json
```

The saved [verification.json](verification.json) checks every row's ID, split,
source, kind, canonical model-input SHA and candidate count against the frozen
dataset, compares the three files, recomputes reported totals and cap failures,
and records the copied artifact hashes. Those hashes and sizes match the remote
state capture. Source-group and split-group totals are available there as well.
