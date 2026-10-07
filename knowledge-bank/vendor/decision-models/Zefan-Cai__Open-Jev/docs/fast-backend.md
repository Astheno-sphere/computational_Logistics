# Experimental CUDA acceleration

The default Open-Jev PyTorch implementation is unchanged. Two inference-only
backends are explicit opt-ins. Neither changes training, checkpoint files,
temperature calibration or request formatting.

| Backend | Model profile | GPU | Implementation |
|---|---|---|---|
| `torch` | Existing supported releases | Existing supported devices | Released reference implementation |
| `triton-tail` | Explicit Qwen 2B, 9B and 27B profiles | CUDA sm80+ | Original Open-Jev final-row RMSNorm and FP32 scalar-head fusion |
| `fast-cuda` | Qwen3.8-27B only | CUDA sm90+ and a local CUDA toolkit | Attributed open-jev-fast backbone, low-memory ownership transfer and Open-Jev final-row fusion |

These are experimental architecture profiles, not guarantees that every model,
context length or GPU has been evaluated. Selecting an unsupported profile,
device, dtype, offloaded layout or input size raises an error. There is no silent
fallback or truncation. `--prefix-cache` selects a different HF inference path
and cannot be combined with either fast backend.

## Attribution and ownership

`third_party/open_jev_fast` vendors the necessary MIT source from
[Yiqi Lyu's open-jev-fast](https://github.com/lyuyiqi/open-jev-fast) at commit
`c52b8bb958c1f0d241d4eb7fce4ecd8d885bf1e4`. Its original author, license,
third-party notices and original file hashes are retained. No report webpage,
CC BY-SA assets, model weights or datasets are copied.

The Open-Jev integration adds:

- Layer-by-layer release of source gate/up and attention input projections
  after their merged copies are constructed. The retained backbone no longer
  keeps the original module tree alive.
- A low-memory split-K=1 mode, avoiding redundant down/output projection copies.
  This is a deliberate memory/performance tradeoff. It must be benchmarked
  against the reference; it does not reproduce upstream's B300 tuning choices.
- CUDA compilation for the visible target GPU instead of hardcoded sm103.
  Compiled artifacts live in PyTorch's external extension cache.
- An original Triton kernel that gathers candidate final rows, optionally adds
  a BF16 residual, computes RMSNorm, rounds to the backbone dtype, then applies
  the FP32 scalar head. The fast tree uses it at the last layer and avoids
  normalizing rows that will not be scored.

The source module tree is transferred to the fast scorer for inference. It must
not be reused for training or reference inference after transfer. The benchmark
loads and releases the reference and accelerated models sequentially.

## Run

Install the training runtime and fast dependencies, including a CUDA toolkit for
`fast-cuda`. Use a checkpoint directory containing `model.json`, `head.pt`, the
adapter and `temperature.json`.

```bash
pip install -e '.[train,fast]'
CUDA_VISIBLE_DEVICES=0 python -m jev.server \
  --checkpoint /path/to/package/checkpoint --device cuda:0 \
  --backend fast-cuda --batch-size 32 --port 8791
```

For a 2B or 9B checkpoint, choose `--backend triton-tail`. The fast tree is
limited to 4,096 packed rows and 65,536 replicated path tokens per scoring batch;
the limits are checked before allocating dense tree masks. Long shared contexts
can exceed the replicated-token limit even when the packed tree is small.

`fast-cuda --no-fused-final-head` isolates the attributed backbone from the
Open-Jev final-row fusion. CUDA Graph capture and cuBLASLt tuning are disabled in
this integration; cold/warm behavior must not be equated with upstream's graph
server results.

## Measure

GPU operator measurements use seeded BF16 activation fixtures. They demonstrate
the final operator's correctness and performance; they are not model quality or
whole-model latency measurements.

```bash
CUDA_VISIBLE_DEVICES=0 python -m scripts.benchmark_efficiency --kernel-only \
  --device cuda:0 --iterations 100 --warmup 10 --output kernel-results.json

CUDA_VISIBLE_DEVICES=0 python -m scripts.benchmark_efficiency \
  --checkpoint /path/to/package/checkpoint --request configs/example-request.json --fixture-suite \
  --backend all --device cuda:0 --iterations 20 --warmup 3 \
  --output model-results.json
```

`--fixture-suite` adds seven original deterministic short/medium/long mixed-type
and policy-boundary requests. Policy values straddle 0.2/0.8; the report measures
actual model probability margins without assuming the model is near those values.

`--backend all` requires the 27B profile. For other profiles, first measure
`--backend torch --output reference.json`, then measure
`--backend triton-tail --reference reference.json --output tail.json` with exactly
the same checkpoint, request and batch size. Repeat `--request` for short/long
contexts, small/large candidate sets and real application inputs.

Reports contain model/checkpoint, request, source and environment hashes; cold
load/checksum/compile time; first observed request latency; warm P50/P95;
requests/decisions/candidates per second; allocator resident/peak VRAM; input
sizes; maximum probability error; decision changes; threshold crossings including
official Noul thresholds 0.2/0.8; and boundary margins. In-process latency covers
the Predictor path including tokenization and response formatting. Loopback HTTP
latency is measured and labeled separately on an already warmed model, with a
fresh TCP connection per request and concurrency one. It includes local sockets
and JSON serialization; it is not comparable to a third-party WAN API latency.
Use `--no-http` to omit that measurement. Device-used
memory also includes the CUDA context and any other process on that GPU.

Parity requires matching question/candidate IDs and ordering, usage, finite
distributions, probability error within the specified bound, zero changed
decisions and zero threshold flips. Every measured accelerated response is
compared with the reference. A near-tied decision can fail this contract despite
a small probability error. Failed or missing-reference measurements are saved
and return a nonzero exit code; they are not evidence of a usable speedup.

Cold means the first observed call in this process. Disk, Hub and JIT caches may
already be warm. CPU tests establish correctness only. Actual GPU results and
their hardware/context scope must accompany any speed or memory claim.

## Measured H200 scope

On the recorded H200 run, nine seeded final-row operator cases passed parity
and showed 2.63–2.75× warm P50 ratios. The released 2B checkpoint then passed
eight original/example workloads, including 168 in-process and 168 loopback HTTP
comparisons, with maximum probability error about 1.00e-7 and no decision or
threshold flips. Whole-model P50 ratios were only 1.006–1.020× in this sequential
run; those small differences do not establish statistical significance.

See the [operator report](../reports/efficiency-20261002/h200-kernel-summary.md)
and [released 2B report](../reports/efficiency-20261002/h200-2b-summary.md) for
P50/P95, memory, exact source/runtime hashes and workload limits. Full 9B
checkpoint inference remains unmeasured in this experiment.

## Released 27B H100 smoke

The [released-27B smoke report](../reports/efficiency-20261002/ms-27b-smoke.md)
records real checkpoint inference and loopback HTTP for all three backends.
Triton-tail passed the single request with maximum probability error 2.82e-8.
Fast-CUDA failed the unchanged 1e-4 tolerance with error 0.00593, despite no
decision or threshold flips on that request. The complete three-backend run was
therefore skipped. Single sequential latency samples are diagnostic, and do not
establish a usable speedup.

The subsequent [safe full comparison](../reports/efficiency-20261002/ms-27b-safe-full-summary.md)
passed 168 in-process and 168 loopback HTTP checks across eight workloads, with
maximum probability error 1.89e-6 and no decision or audited threshold flips.
Warm P50 ratios were 1.004–1.020× in-process and 1.002–1.029× over loopback HTTP.
Both paths peaked at 54.124 GiB of request allocation. Sequential runs and a
short concurrent 2B pilot on another GPU prevent a significant speedup claim.

The adapter currently merges BF16 LoRA weights before constructing the fast
projection bundles; the reference loader retains PEFT's separate low-rank
forward path. Those operations have different rounding graphs. The smoke
cannot identify how much of the error comes from merging versus the custom
backbone kernels. A future diagnostic should compare an explicit merged-Torch
reference first, then isolate the same-version FLA and SDPA paths before changing
individual kernels. The probability gate stays unchanged throughout.
