# Open-Jev on consumer GPUs

Contributor report by [Turkidev](https://github.com/Turkidev) in [PR #2](https://github.com/Zefan-Cai/Open-Jev/pull/2). The hardware measurements below are author-reported; the PR does not include raw per-request measurement records. They do not replace the project's independently audited release results. Hardware, kernels, caching and warmup protocols differ across rows, so the table does not establish a matched-hardware speedup. CPU fixture tests validate loading guards and cache mechanics, not these GPU measurements.

I wanted Open-Jev 9B answering questions about Saudi court judgments on hardware I already own: a Windows desktop with an RTX 4060 Ti 16 GB and an RTX 5060 Ti 16 GB, and a Linux box with one RTX 5060 Ti 16 GB. The released setup assumes a single large GPU. Qwen3.5-9B is 17.98 GiB in bf16, so on my first attempt I loaded it in 8-bit and split it across both desktop cards. One request took 83 seconds.

It now runs in bf16 on one 16 GB card, returns the same JevBench score as the published numbers, and a full request on my workload takes 4.4 seconds. This page covers what was slow, what I changed, and the numbers on each card, including an H100 for comparison.

The changes were contributed in PR #2. Every option is opt-in; with none set, the code behaves exactly like upstream and the upstream test suite passes unchanged.

## Results on JevBench

The 231 public JevBench tasks at commit `f8ce713`, scored with this repo's own harness (`scripts/jevbench_openjev.py`). The request file hash is `2e20ff5f…`, the same one in the published report, so the inputs are byte-identical. Weights are the pinned upstream revisions. Latency is one request at a time, full HTTP round trip.

| GPU | Model | Correct | Accuracy | P50 | P95 |
|---|---|---:|---:|---:|---:|
| RTX 4060 Ti 16 GB (Windows) | 2B | 150 / 231 | 64.94% | 0.108 s | 0.518 s |
| RTX 4060 Ti 16 GB (Windows) | 9B | 179 / 231 | 77.49% | 0.346 s | 1.569 s |
| RTX 5060 Ti 16 GB (Linux) | 2B | 150 / 231 | 64.94% | 0.058 s | 0.306 s |
| RTX 5060 Ti 16 GB (Linux) | 9B | 180 / 231 | 77.92% | 0.315 s | 1.277 s |
| H100 80 GB | 2B | 151 / 231 | 65.37% | 0.156 s | 0.278 s |
| H100 80 GB | 9B | 179 / 231 | 77.49% | 0.311 s | 0.543 s |
| Published, H100, cache off | 2B | 150 / 231 | 64.94% | 0.138 s | 0.206 s |
| Published, H100, cache off | 9B | 179 / 231 | 77.49% | 0.189 s | 0.839 s |

The 9B fits on a single 16 GB card with no quantization. At the median, the 2B on a 5060 Ti answers faster than the published H100 figure (0.058 s against 0.138 s), though its P95 is slower.

Before trusting any of this I checked that my changes don't move answers. With prefix caching off (the published protocol), the 5060 Ti scored 179/231 on the 9B (Brier 0.3212 against the published 0.3219) and 150/231 on the 2B (0.4754 against 0.4751). Same correct count; the fourth-decimal Brier difference comes from running on a different GPU.

The two scores that differ from the published ones differ by one task each. The 9B at 180 on the 5060 Ti comes from prefix caching, which reorders floating-point work; the upstream docs already warn about this. The 2B at 151 on the H100 comes from running the torch reference kernels there instead of flash-linear-attention (explained below).

The H100 was a rented card on Modal, with two settings changed for reasons covered under Hopper. Its numbers are the second of two passes over the same tasks in one container. The first pass, run cold, had a median of 1.3 s (2B) and 1.7 s (9B), and I didn't track down that remaining cold cost. The published H100 numbers come from a single pass, so the two protocols differ.

## What was slow

I measured before changing anything. My workload asks 21 multiple-choice questions about one judgment. Open-Jev scores every option as its own sequence, so one request is 97 candidate sequences of about 1,900 tokens each: 187,071 tokens.

Prefix caching was already in the code, switched off by default. Turning it on reuses the shared judgment text, and the model then processes only 5,813 of those 187,071 tokens. That alone took a request from 83 s to 10.4 s. It needs `transformers==5.10.2`, the version this repo pins. On 5.17 it fails with `'Qwen3_5TextConfig' object cannot be interpreted as an integer`.

With the cache on, a request still made 95 forward calls, most of them tiny. When I later timed each phase, the 21 question prefills took 2.07 s for 656 tokens, about 100 ms of fixed cost per call, while copying the cache for each branch took 1%. Most of the calls came from how suffixes were batched: candidates are grouped by exact suffix length, and option texts rarely share a length, so 97 candidates became 73 separate calls. One question had eight options of eight different lengths and so made eight calls.

Batch size made no difference (4, 16 and 32 all gave about 10 s), because the batches it could fill were one or two rows long.

## What I changed

**Ragged suffix batches** (`JEV_RAGGED_SUFFIX=1`). All of a question's options go into one right-padded call, and each row is scored at its own last real token. That is what the uncached path already does. Attention is causal, so padding after a row's last token can't change it, and the forked cache is thrown away afterwards. Calls drop from 95 to 43. This is off by default because upstream deliberately never pads the cached path and has a test asserting it. `tests/test_prefix_cache_ragged.py` checks the ragged logits against uncached scoring for every model profile, with and without LoRA, at batch sizes 1, 2, 4 and 8, and checks that padding actually happened.

**One 16 GB card for the 9B.** After construction only `model.language_model` is kept. The vision tower, `mtp` and `lm_head` are dropped, so the resident model is 14.78 GiB. That fits a 16 GB card if loading doesn't briefly need all 17.98 GiB, which took four fixes:

- `JEV_DEVICE_MAP` accepts an explicit JSON map, so the dropped modules can load on CPU.
- The offload guard now ignores modules that are discarded after init. Anything else offloaded still refuses to serve.
- With `lm_head` on CPU its weight is a meta tensor, so the two rows that seed the decision head are read straight from the checkpoint file.
- The embedding (1.89 GiB) goes on CPU too. accelerate copies an offloaded module to the GPU on every call, which I found from an OOM that tried to allocate exactly 1.89 GiB. Now the lookup happens on CPU and the model gets `inputs_embeds`. An embedding lookup is a gather, so the values are identical.

`JEV_PREFILL_CHUNK=256` feeds the shared prefix through the cache 256 tokens at a time, so its activations fit beside the weights.

Quantization turned out to be the wrong direction. 8-bit on one 4060 Ti took 18.2 s per request; bf16 on the same card takes 6.2 s, because LLM.int8 matrix multiplies are slow. It also changes the weights the decision head was trained on, so its answers aren't comparable to the released ones.

## Running it on one 16 GB card

```bash
export JEV_DEVICE_MAP='{"model.visual":"cpu","lm_head":"cpu","model.language_model.embed_tokens":"cpu","model.language_model.rotary_emb":0,"model.language_model":0}'
export JEV_PREFILL_CHUNK=256
export JEV_RAGGED_SUFFIX=1
python -m jev.server --checkpoint path/to/Open-Jev-9B/package/checkpoint \
  --device cuda:0 --batch-size 2 --max-length 16384 --prefix-cache
```

The 2B needs none of the placement variables. Use `--batch-size 8` or more.

Keep the 9B at batch size 2 on 16 GB. At 4, the Linux card ran out of memory 171 tasks into JevBench, and the Windows card, which also drives a display, crashed under my judgment workload. The Linux card has 2.2 GiB free after loading the 9B.

Reproducing the table:

```bash
python scripts/jevbench_openjev.py prepare --upstream path/to/jevbench --output jb_en
python scripts/jevbench_openjev.py collect --prefix-cache --requests jb_en/requests.json \
  --input-sha256 2e20ff5f94dd04d015b3a7b9abd955757b6c5be25b55b97fcd141cb52f88b4aa \
  --endpoint http://127.0.0.1:8791/v1/inference --identity identity.json --output run
python scripts/jevbench_openjev.py summarize --upstream path/to/jevbench --run-dir run --output summary.json
```

`identity.json` holds the seven identity fields the server returns in its response metadata. `--prefix-cache` is new. Without it the harness refuses a cached server on the first request, as before, and the setting is written into the run report so `summarize` replays with it.

## Things that cost me time

The `The fast path is not available` warning doesn't mean flash-linear-attention is off. `modeling_qwen3_5.py` falls back one kernel at a time, and the warning fires whenever `causal_conv1d` is missing, even if the delta-rule kernels are active. Check the kernel directly:

```bash
python -c "import transformers.models.qwen3_5.modeling_qwen3_5 as m; print(m.chunk_gated_delta_rule is not None)"
```

It also appears only on the first inference, not at startup, so grepping the log right after `ready` shows nothing either way.

On Windows, `triton-windows` and `flash-linear-attention==0.5.2` install from wheels without a CUDA toolkit. `causal_conv1d` needs `nvcc` and won't build, but it's only the small depthwise convolution, which falls back to `F.conv1d`. Set `PYTHONUTF8=1` when the data has Arabic in it. `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` isn't supported there.

If the embedding and the transformer blocks are mapped to different GPUs, pin `model.language_model.rotary_emb` to the blocks' card. Otherwise `inv_freq` and `position_ids` end up on different devices and every forward fails.

### Hopper

The H100 first measured about 2 s per request, 30 times slower than my 5060 Ti. Two separate causes, each measured in isolation:

1. flash-linear-attention on Hopper spent about 1.3 s the first time it met each new sequence length; a repeated length took 0.069 s. JevBench lengths are nearly all different, so every request paid it. The torch reference path is a steady 0.146 s. Setting the fla functions to `None` before the model is built switches it off.
2. On the Modal container, GPU work on any thread except the main one took about 1.3 s even with warm kernels (0.078 s on the main thread), and one long-lived worker thread was just as slow as a new thread per request. The stock server handles each request on a new thread, so I served from the main thread for the H100 runs.

Neither showed up on the 4060 Ti or 5060 Ti, where fla stays on. I haven't confirmed whether the thread effect is specific to Modal.

## On my own data

This is what the work was for. I have 300 held-out judgments with stored answers from the hosted Jev, 21 questions each. Agreement with a stored answer measures matching Jev, which is not the same as accuracy. Measured on 20 of them:

| Setup | Seconds per judgment | Agreement |
|---|---:|---:|
| 9B, bf16 across both desktop cards, cache off | 83 | 83.57% |
| + prefix cache | 10.4 | 83.57% |
| + ragged batches, batch size 32 | 5.9 | 83.81% |
| One RTX 4060 Ti (Windows) | 6.2 | 83.81% |
| One RTX 5060 Ti (Linux) | 4.4 | 83.57% |

Against the uncached run, 1 to 3 of the 420 answers change depending on the setup, and the overall rate stays within a quarter point.

The biggest improvement in answer quality came from the input rather than the model. My evaluation file cut each judgment to 8,000 characters, but Jev had been asked with up to 20,000. On the 51 judgments long enough to be cut, agreement was 80.77% at 8,000 characters, 86.09% at 16,000, and 87.49% with exactly the text Jev saw. That needs `--max-length 12288`, which still fits the 5060 Ti at batch size 2.

## What didn't work

Grouping suffixes by approximate length to cut padding made more calls (49 against 43) and wasn't measurably faster; this path is limited by call count, not padding. Folding the question text into each suffix (`JEV_NO_QPREFILL=1`) went from 43 calls to 22 and was 11% faster, but cost 2 of 420 answers, so it stays off by default. Putting the embedding on the second GPU instead of the CPU failed until I found the rotary pinning above.

I also tried fine-tuning the 9B adapter on 3,000 judgments across both 16 GB cards. It runs at about 8.4 s per step once the heaviest 7% of examples are left out, but still ran out of memory eight steps into a real run. Training the 9B needs a bigger card.

## Setup

- Hardware: RTX 4060 Ti 16 GB and RTX 5060 Ti 16 GB on Windows 11; RTX 5060 Ti 16 GB on Ubuntu; an H100 80 GB HBM3 on Modal, which cost nothing beyond their monthly free credit.
- Software: torch 2.11.0 (cu128), transformers 5.10.2, peft 0.19.1, accelerate 1.15.0, flash-linear-attention 0.5.2, and triton-windows 3.8 on Windows.
- Weights: `Qwen/Qwen3.5-2B@15852e8`, `Qwen/Qwen3.5-9B@c202236`, `ZefanCai/Open-Jev-2B@0c7aa49`, `ZefanCai/Open-Jev-9B@47e9668`.
- Benchmark: JevBench `f8ce713`, scored with this repo's harness.
