# Request-local prefix caching

The HTTP model factory and `jev.server` / `jev.predict` inference commands now
support explicit prefix caching with `--prefix-cache`. It reuses actual transformer state for shared
token prefixes, then evaluates candidate suffixes against independent branches.
The existing training `DecisionModel.forward` still runs with `use_cache=False`;
the head, LoRA weights, candidate prompts, chat template, calibration and model
serialization are unchanged.

Caching remains **off by default**. The released 2B checkpoint has now been
measured on an H100: 9 of 11 workloads exceeded the predeclared `1e-4`
probability-error tolerance, with a maximum error of `0.005703`. Selected
decisions matched in all paired attempts, but the probabilities were not
equivalent under that test. The [full CUDA report](../reports/inference-latency/public/2b-h100-20260920/report.json)
retains timings and numerical differences. The 9B and 27B full-checkpoint CUDA
comparisons remain pending; strict FP32 CPU parity is a separate check.

This implementation targets the pinned `transformers==5.10.2` Qwen3.5 text
backbone used by Qwen3.5-2B, Qwen3.5-9B and Qwen3.8-27B. The last model's pinned
configuration also uses `model_type=qwen3_5_text`; it does not require a separate
Qwen3.8 cache class. Unsupported backbones or cache types raise an error when
caching is enabled. There is no silent fallback that could make a cache run
appear successful while recomputing every prefix.

## Usage and comparison

Enable caching explicitly:

```bash
python -m jev.server --model Qwen/Qwen3.5-2B \
  --revision 15852e8c16360a2fea060d615a32b45270f8a8fc \
  --max-length 4096 --batch-size 32 --prefix-cache

python -m jev.server --checkpoint /path/to/completed/checkpoint \
  --max-length 4096 --batch-size 32 --prefix-cache
```

Use `--no-prefix-cache` on the same checkpoint, temperature, context limit and
candidate batch size for an uncached comparison. The uncached mode is currently
the default. These commands start a real model service; CPU
verification of this change did not run them or start a GPU job.

The bounded A/B runner loads one checkpoint and alternates both paths on that
same model. Run it only after the assigned GPU is released by existing work:

```bash
python -m scripts.benchmark_prefix_cache \
  --checkpoint /path/to/completed/checkpoint \
  --request examples/workflows/customer_service.json \
  --device cuda:0 --batch-size 32 --repetitions 2 \
  --output /path/to/new-prefix-comparison.json
```

It checks answer identities, probability error and selected decisions before
reporting parity, and retains timing, independently counted processed tokens
and CUDA peak memory. Its default maximum probability error is `1e-4`; a failed
comparison exits with status 2 and retains the failure report.

Python inference exposes both paths:

```python
from jev.serving import load_predictor

cached = load_predictor(
    checkpoint="/path/to/completed/checkpoint", batch_size=32, prefix_cache=True
)
result = cached.predict({"state": state, "questions": questions})

# Select this mode when creating a separate comparison service/model.
uncached = load_predictor(
    checkpoint="/path/to/completed/checkpoint", batch_size=32, prefix_cache=False
)
```

At the model level, `model.score_cached(records, batch_size=32)` returns
`(logits, stats)`. `model(records)` remains the original uncached forward, used
by training and available for correctness comparisons. Cache scoring requires
evaluation mode and runs under `torch.inference_mode()`.

The generic `Predictor` constructor retains `prefix_cache=False` by default so
existing custom scorers implementing only `score(records)` keep working.
`load_predictor(..., prefix_cache=True)` enables the real `TorchScorer` cache path. A
custom scorer explicitly enabling this feature must provide
`score_request(records, batch_size=...)`; unsupported backends fail clearly.

## What is shared

1. Render every original candidate prompt through the same complete chat
   template and tokenize without truncation. Find the longest common prefix
   by exact token IDs, not by characters or separately tokenized strings.
   Tokenization may merge across text boundaries, so text-prefix reuse alone
   would be incorrect.
2. Prefill that common request prefix once. Within each multi-candidate
   question, prefill any additional shared token prefix once from a branch of
   the request cache. At least one final token remains for candidate scoring.
3. Group candidate suffixes by their actual token length and run each group in
   batches no larger than `batch_size`. Every suffix gets explicit absolute
   positions and an all-ones mask covering prefix plus suffix. Equal-length
   batches introduce no padding states.
4. Restore scores to the original question and option order. Noul retains its
   original `[0, score]` logits; Choice and Score retain all candidate logits.
   Temperature and normalization are applied after reassembly.

The `TorchScorer.score_request` path receives the whole compiled request before
candidate batching. A 255-way Choice therefore retains the same saved prefix
across all its suffix batches. A cache lives only until that request returns or
raises; it is never shared with a subsequent HTTP request, saved in a checkpoint
or reused after a model/adapter change.

## Hybrid-state correctness

Qwen3.5 combines full attention and gated delta-rule linear attention. Its
`DynamicCache` includes full-attention keys/values and linear-attention
convolution/recurrent states. The latter are updated in place, including during
single-token continuation. A KV-only copy, shallow cache copy or reused mutable
cache would contaminate later candidate branches.

`fork_cache` copies the cache and layer objects and allocates independent tensor
storage for **keys, values, conv states and recurrent states**. It preserves
the initialization flags, dtype and device and updates the branch batch size.
Only the pinned `DynamicLayer`, `LinearAttentionLayer`, and the local
recurrent-dtype-preserving layer forms are accepted;
offloaded, sliding or unfamiliar cache forms are rejected. Calling generic
`DynamicCache.batch_repeat_interleave` is insufficient in this version because
`LinearAttentionLayer` does not implement that method.

There is also a precision issue in the pinned HF cache: it initializes
recurrent-state storage with the convolution dtype. That casts the delta-rule
kernel's FP32 state to BF16 on a BF16 backbone at each split, although an
unsplit forward retains FP32 recurrent state. The small local
`RecurrentDtypeLayer` preserves the kernel output dtype for recurrent state
without changing convolution storage or any kernel. This removes that extra
cast; it does not promise bitwise BF16 equality across different forward
segmentations.

The pinned Qwen implementation supports multi-token cached continuation: it
prepends the saved convolution context and passes the saved recurrent state to
the chunk kernel. Its cached linear-attention path bypasses padding masks,
which is why this implementation uses equal-length suffix batches. Both
single-token and multi-token continuations are covered by the CPU checks.

The original PEFT wrapper remains the forward target, so active LoRA adapters
are applied during prefix prefill and every candidate continuation. Unwrapping
is used only to inspect the backbone configuration.

## Token accounting and limitations

`usage.input_tokens` retains its original meaning: the total tokens in all
complete candidate inputs. This makes usage comparable with uncached runs.
`metadata.prefix_cache` reports execution accounting separately:

| Field | Meaning |
| --- | --- |
| `enabled`, `mode` | Whether the request used the cache path; `request_local_token_prefix` or `independent_candidates` |
| `logical_input_tokens` | Sum of the complete, unpadded candidate token counts |
| `processed_input_tokens` | Token positions actually submitted to the backbone, including once-only prefills |
| `reused_input_tokens` | Logical minus processed token positions |
| `shared_prefix_tokens` | Length of the common request token prefix |
| `question_prefix_tokens` | Sum of additional question-prefix tokens processed once each |
| `prefill_calls` | Request and additional question-prefix backbone calls |
| `suffix_batches`, `max_suffix_batch` | Actual suffix call count and largest candidate batch |
| `suffix_tokens` | Total candidate suffix token positions submitted |
| `candidate_sequences` | Original number of candidate scoring sequences |
| `recurrent_state_dtype` | `preserve_kernel_output`; the recurrent cache keeps the dtype returned by the kernel |

The uncached path reports `enabled=false` and
`mode=independent_candidates`; it does not manufacture reuse statistics.

Reduced token processing does not guarantee reduced latency. Prefix prefill,
cache copying, suffix lengths and kernel/batch behavior all matter. The initial
implementation groups suffixes within each question, so many Noul questions
can produce single-sequence suffix batches and lose some cross-question
parallelism. All candidate token IDs are planned in host memory for the
request. Branches copy prefix KV rather than using a custom kernel that reads
one physical KV allocation across all candidates. No GPU speedup or memory
improvement is claimed from CPU verification.

## Verification scope

The independent `tests/test_prefix_cache.py` suite uses real, randomly
initialized tiny Qwen3.5 hybrid backbones with the three models' head-ratio
patterns and actual PEFT LoRA adapters. It compares cached and uncached raw
logits and probabilities, checks one- and multi-token continuation, verifies
KV/conv/recurrent branch isolation, and exercises zero/short/identical prefixes,
ragged suffixes, input permutations, request/exception cleanup, typed responses
and training gradients. The original serving tests also pass.

The local CPU runtime is Python 3.12 with torch 2.14.0,
transformers 5.10.2 and peft 0.19.1. This validates the real hybrid implementation
on CPU; it is not validation of full pretrained weights or CUDA kernels. Run
cached/uncached parity and latency checks on the intended completed checkpoint
before comparing GPU performance figures.

The [independent CPU report](../reports/runtime-checks/prefix-cache-cpu.json)
retains 24 tiny-model comparisons and the complete 12-test result. A separate
[255-candidate CPU probe](../reports/runtime-checks/prefix-cache-255-cpu.json)
confirms one prefix prefill across eight suffix batches at batch size 32:
116,790 logical input tokens require 23,064 processed tokens. Its selected
candidate matches and the maximum probability difference is `3.18e-9`.
These are synthetic tiny-model execution checks, not trained-model task scores
or measured GPU speedups.

The bounded comparison runner uses one loaded checkpoint and the same
Predictor, alternates cached/uncached order, synchronizes CUDA around timing,
and independently counts backbone token positions. Its output includes raw
timings, memory baselines/peaks, answer differences and the tolerance used.
For a future run on an available GPU with a completed checkpoint:

```bash
python -m scripts.benchmark_prefix_cache \
  --checkpoint /path/to/completed/checkpoint \
  --request examples/community/support_28.json \
  --device cuda:0 --batch-size 2 --warmup 1 --repetitions 2 \
  --output runs/prefix-cache-support-comparison.json
```

Choose a new output path. The default probability tolerance is `1e-4`, and a
parity failure exits nonzero. Noul decisions are compared at `p >= 0.5`;
Choice/Score candidate argmax is also checked. Score-value differences are
reported separately; acceptance does not claim a fixed absolute Score bound.
The runner excludes model loading and HTTP overhead. The command above has
not been run on a GPU as part of this change.

During investigation, a tiny 9B-ratio BF16 backbone with FP32 LoRA adapters had
maximum raw-logit/probability differences of about `0.00528` / `0.00150` with
the stock HF recurrent cache. Preserving recurrent-state dtype reduced those
differences to about `4.77e-7` / `5.96e-8` in that fixture. A tiny BF16 backbone
without LoRA still differed by about `0.00593` / `0.00100`, demonstrating that
removing this cast does not eliminate all BF16 segmentation effects. These are
random tiny CPU fixtures, not results on the trained 2B/9B/27B checkpoints.
