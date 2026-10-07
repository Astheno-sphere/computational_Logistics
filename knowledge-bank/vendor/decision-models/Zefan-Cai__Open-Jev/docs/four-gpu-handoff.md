# N1-1 four-card schedule

The user requested this order on physical GPUs **0–3 only**:

1. Finish the current 2B and 9B runs, including calibration, checkpoint writing
   and reload verification. A last-step training log alone is insufficient.
2. Retire the precisely identified old single-GPU 27B process. Its original
   directory, logs and immutable 500-step snapshots remain in place.
3. Evaluate 2B, then 9B, splitting every release-v2 test/OOD record across all
   four cards. Each model has 26,452 rows: 6,613 per card.
4. Train a **fresh** Qwen3.8-27B on four cards using the independently frozen
   browser/drone expansion. This replaces the proposed extra 2B pilot.

The user explicitly permitted restarting 27B. The new run starts from pinned
upstream revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`, rather than importing
old single-process optimizer state. It does not claim to preserve unsaved
in-memory progress from the retired run.

## Training and evaluation contracts

The expansion has **110,324 train rows**. Four ranks each process one row per
optimizer step; DDP averages their gradients, then gradient clipping and AdamW
run once. The global batch remains four, so **27,581 steps consume one complete
shuffled pass**. Rank `r` at zero-based step `s` uses row `4*s+r`. Training uses
the existing LoRA/scalar head, the 4,096 input limit, and separate calibration.
JF100 remains an external evaluation set and is not part of this training data.

The new [DDP entry point](../jev/train_distributed.py) records its own code and
topology identity. Its atomic snapshots save all four RNG streams, trainable
parameters, optimizer state, the global cursor and original baseline evidence.
Only a matching DDP snapshot can resume this run; legacy single-process
snapshots cannot be relabeled as DDP snapshots.

[Parallel data evaluation](parallel-data-eval.md) uses the final saved
temperatures and immutable release-v2 test/OOD rows. Missing/duplicate shards,
wrong checkpoint identity, malformed predictions or infrastructure failures
prevent the handoff to training. Low measured accuracy is a valid completed
evaluation. Four-card throughput is separate from single-card latency evidence.

DDP replicates the full 27B backbone on every card; it does not divide backbone
memory by four. Complete tokenizer checks establish that input lengths fit.
The [first CUDA training observations](../reports/27b-ddp-n1/README.md) now
record finite optimizer steps, memory and throughput, plus an independently
checked step-500 snapshot. They do not establish memory fit for all remaining
rows, training completion, a fourfold speedup or a model quality gain.

## Supervisor and ownership

[The frozen plan](../configs/n1-four-gpu-handoff.json) records original process
IDs, Linux start ticks, user, command lines, CUDA UUIDs and run identities. It
also pins both datasets' ten split files and the exact phase commands.

`scripts/run_four_gpu_handoff.py` checks source/data identities before waiting,
again before stopping the old 27B, and again before fresh training. Retirement
uses a Linux pidfd after verifying the old process identity and the latest
complete snapshot. It never signals a discovered unrelated job. The original
training checkout stays at `99e881108c6cacadafd364088505e84975ca43fc`.

The supervisor uses a separate checkout at `/mnt/localssd/open-jev/four-gpu-repo`.
Keep it at the recorded launch commit while the supervisor or DDP run is active.
The existing hourly task should observe this supervisor, not start competing
jobs or the superseded 2B expansion pilot.
On N1-1 the supervisor uses `/usr/bin/python3 -S`, whose Linux `os.pidfd_open` and
`signal.pidfd_send_signal` interfaces were verified. The model runtime's Python
build lacks `os.pidfd_open` and is correctly rejected by the supervisor's
preflight; evaluation and training still use the established model runtime.
The supervisor itself needs only the standard library. `-S` and
`PYTHONNOUSERSITE=1` exclude unrelated site packages from its controller/tests.

Phase transitions share a four-card lease and the existing per-card evaluation
leases. GPU occupancy must clear before evaluation and again before training.
Other work on GPU 4–7 and N4-4 is outside this schedule.

The supervisor writes `status.json`, `events.jsonl`, the exact plan, and child
logs under `/data/zefan/open-jev/queues/n1-four-gpu-handoff-v1`. It keeps failures
visible and does not automatically relaunch failed phases. Recovery must
inspect these records and preserve the original outputs first.

To check the deployed plan without starting or stopping any job:

```bash
cd /mnt/localssd/open-jev/four-gpu-repo
CUDA_VISIBLE_DEVICES='' PYTHONNOUSERSITE=1 /usr/bin/python3 -S \
  -m scripts.run_four_gpu_handoff \
  --plan configs/n1-four-gpu-handoff.json \
  --output-root /data/zefan/open-jev/queues/n1-four-gpu-handoff-v1 \
  --expected-commit "$(git rev-parse HEAD)" --prepare-only
```

The actual queued process uses the same command without `--prepare-only`,
detached with retained stdout/stderr. SIGTERM/SIGINT trigger cleanup of its
owned child controller; that controller cleans up its own workers.
