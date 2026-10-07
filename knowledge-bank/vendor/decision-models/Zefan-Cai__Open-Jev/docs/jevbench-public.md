# JevBench public subset: 27B v1.1 and released baselines

**All six model streams are complete and independently audited.** Each model was evaluated on all 231 public tasks. Saved-response replay, exact upstream aggregate reproduction, request accounting, and model identities passed their respective audits.

We evaluated **Open-Jev 27B v1.1 and the already released Open-Jev 2B and 9B adapters and decision heads** on the 231 public tasks in [JevBench](https://github.com/fstandhartinger/jevbench). The 2B/9B rows remain historical released checkpoints; 27B v1.1 is the new completed checkpoint, which also passed the [full internal audit](internal-full-evaluation.md). This experiment is separate from the [76-case provider comparison](provider-comparison.md) and the release-v2 test/OOD evaluation; their scores and denominators are unchanged.

The public subset contains 72 original, 48 easy, and 111 hard tasks: 74 Noul, 139 Choice, and 18 Score. The full benchmark contains 534 tasks; its other 303 private/judge tasks were unavailable. We do not report a full-534 score or composite. ZefanCai's Qwen-based Open-Jev is a different system from the Kotoba and Codiv projects also named OpenJev.

**Comparison limits:** Open-Jev and Jev return native probabilities. GPT returns verbalized probabilities in constrained JSON, not token logprobs. The pinned native and GPT adapters present candidates in different orders on **119 of 139 Choice tasks**. All runs use the same public task definitions and upstream scoring, but this is not an identical-wire or fully order-controlled comparison.

## Aggregate results

Each stream attempted and scored all 231 planned tasks. Accuracy is correct / 231; operational success and probability validity are separate checks. Every planned task is included, including unsuccessful decisions.

| Model | Correct / 231 | Accuracy | Strict-valid vectors | Renormalized vectors | Audit |
|---|---:|---:|---:|---:|---|
| Released Open-Jev 2B | 150 / 231 | 64.94% | 231 / 231 | 0 | Passed |
| Released Open-Jev 9B | 179 / 231 | 77.49% | 231 / 231 | 0 | Passed |
| Open-Jev 27B v1.1 | 197 / 231 | 85.28% | 231 / 231 | 0 | Passed |
| Jev 1.13.0 | 200 / 231 | 86.58% | 230 / 231 | 1 | Passed |
| GPT-5.6 Luna | 206 / 231 | 89.18% | 231 / 231 | 0 | Passed |
| GPT-6 Astra | 231 / 231 | 100.00% | 231 / 231 | 0 | Passed |

All six streams each have 231 operationally successful requests, zero failed requests, and no remaining or in-flight requests. Jev returned one hard-tier vector that was outside strict tolerance but within the upstream rounding tolerance; it was normalized and scored under the upstream policy. This does not mean its actual probability-sum error was exactly 2%.

| Model | Original / 72 | Easy / 48 | Hard / 111 |
|---|---:|---:|---:|
| Released Open-Jev 2B | 56 / 72 | 48 / 48 | 46 / 111 |
| Released Open-Jev 9B | 65 / 72 | 48 / 48 | 66 / 111 |
| Open-Jev 27B v1.1 | 69 / 72 | 48 / 48 | 80 / 111 |
| Jev 1.13.0 | 71 / 72 | 48 / 48 | 81 / 111 |
| GPT-5.6 Luna | 69 / 72 | 48 / 48 | 89 / 111 |
| GPT-6 Astra | 72 / 72 | 48 / 48 | 111 / 111 |

The 27B v1.1 result is 197/231 (85.28%) overall and 80/111 (72.07%) Hard, higher than the released 2B/9B baselines and still three overall and one Hard answer behind Jev. Model scale, data and prior training all differ, so this does not isolate a data-only training gain. The aggregate JSON also retains family-level results; no accuracy by task type is inferred from the type inventory.

## Timing diagnostics

These timings come from the quality run: **one full-response wall-time observation per heterogeneous task**, concurrency one, no warmups and no retries. They are not a repeated latency benchmark, a matched-hardware comparison, or a throughput or energy-efficiency measurement.

| Model | P50 | P95 | Request boundary |
|---|---:|---:|---|
| Released Open-Jev 2B | 138.0 ms | 205.8 ms | Local H100, loopback HTTP |
| Released Open-Jev 9B | 189.2 ms | 839.3 ms | Local H100, loopback HTTP |
| Jev 1.13.0 | 291.3 ms | 353.7 ms | Hosted HTTPS |
| GPT-5.6 Luna | 953.8 ms | 1,307.5 ms | Hosted HTTPS |
| GPT-6 Astra | 2,206.4 ms | 3,581.6 ms | Hosted HTTPS |

The released 2B/9B used one NVIDIA H100 80GB HBM3, with 2B and 9B evaluated serially. Candidate batch size was 1, maximum length 16,384, and prefix caching was **off**. The timer includes full loopback response and validation; model loading is outside it. Hosted timings include full HTTPS requests and response validation. Network, hosting, model architecture, and request payload differ, so these numbers cannot establish a hardware-normalized speedup over Jev or GPT.

27B v1.1 used four-rank frozen-base FSDP2 direct execution on shared H100 GPUs, candidate batch size 1, maximum length 16,384 and prefix cache off. It started no HTTP server. Its per-task timings include collectives and validation; they are not comparable to the earlier single-GPU HTTP or hosted HTTPS measurements and are omitted from the latency table. No 27B speedup is claimed.

Local compute cost was not metered and is not free. Hosted usage × configured tariff estimates are retained in the JSON, rather than treated as billing receipts: $0.03842 per 1,000 Jev decisions, $0.17914 per 1,000 Luna decisions, and $8.81978 per 1,000 Astra decisions for this task mixture. They do not establish a local-versus-hosted cost comparison.

## Scoring and probability metrics

We use the pinned upstream scoring policy: strict probability-sum tolerance 0.001; rounding/renormalization tolerance 0.02. Vectors outside strict tolerance but inside the rounding band are normalized and scored. Vectors outside the rounding band are invalid and incorrect. Argmax ties select the lexicographically smallest label. Score accuracy uses argmax level = gold level; expected-value ordinal mean absolute error is reported separately.

| Model | Brier mean ↓ | Top-label ECE ↓ | Score ordinal MAE ↓ |
|---|---:|---:|---:|
| Released Open-Jev 2B | 0.4751 | 0.1274 | 0.3622 |
| Released Open-Jev 9B | 0.3219 | 0.0858 | 0.2350 |
| Open-Jev 27B v1.1 | 0.2420 | Not reported | 0.3798 |
| Jev 1.13.0 | 0.1811 | 0.0318 | 0.1484 |
| GPT-5.6 Luna | 0.2074 | 0.0932 | 0.2898 |
| GPT-6 Astra | 0.0085 | 0.0149 | 0.0003 |

Brier uses 231 returned probability vectors per completed model. The compact 27B report does not export ECE; where reported for the five historical streams, ECE uses the upstream 10-bin top-label calculation. Ordinal MAE concerns the 18 Score tasks. Native probabilities and verbalized GPT probabilities do not measure equivalent intrinsic model confidence; the table describes the returned distributions under this protocol.

GPT-5.6 Luna uses `reasoning_effort="none"`; GPT-6 Astra uses `reasoning_effort="low"`. Both use `max_completion_tokens=4096` and omit `temperature` and legacy `max_tokens`. Open-Jev and Jev preserve the upstream criteria-map order. GPT uses the upstream adapter's `task.labels` order. No candidate shuffling or adapter rewrite was introduced for these runs.

## Reproducibility and release identities

- Upstream benchmark: [`f8ce71361165846101d02ebc83ad44e47ae44fc3`](https://github.com/fstandhartinger/jevbench/tree/f8ce71361165846101d02ebc83ad44e47ae44fc3).
- Original five-stream execution code commit: `3c5bb4a5451ccfd81a5b9f2e05edaf2103805c94`.
- Frozen input SHA-256: `2e20ff5f94dd04d015b3a7b9abd955757b6c5be25b55b97fcd141cb52f88b4aa`.
- Dataset SHA-256: `dc3995d8ae1e2fc8e81ce38431add509eb8bb39b85aadfd0c7c32079382dde51`.
- [Open-Jev 2B](https://huggingface.co/ZefanCai/Open-Jev-2B/tree/0c7aa498b1627be8da4acf34c863ff0ee0a92785), based on `Qwen/Qwen3.5-2B` revision `15852e8c16360a2fea060d615a32b45270f8a8fc`; released package content SHA-256 `3076462e6356412082e79af909227b39b2863b90def79155ca0821aa506b7ded`.
- [Open-Jev 9B](https://huggingface.co/ZefanCai/Open-Jev-9B/tree/47e966881e489511c0c7f5633a9e1960a676a551), based on `Qwen/Qwen3.5-9B` revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`; released package content SHA-256 `9302c52feba99d079918755f2469f4f088266e9786327bab550248f3d83716d3`.

The [combined site aggregate](../site/jevbench.json) retains both sets of results. The [27B report and independent audit](../reports/new27b-jevbench-20260922/README.md) bind checkpoint `c49994563c3c4f04a99d9130203c4e526f4ae5086c84deec57698d18cb652e71`, Qwen base revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`, temperature `2.5343690298472983` and execution code `7ac6bab261bd97efc3d446152999e94ae432e5b0`. They independently replay all 231 raw responses; integer results match exactly and floating-point replay is within 1e-12.

The [original five-stream aggregate report](../reports/jevbench-public-20260921/baseline-summary.json) records exact source-summary hashes, model identities, and hashes of all three audit artifacts. The [Open-Jev replay audit](../reports/jevbench-public-20260921/openjev-independent-replay-audit.json) recomputes all scores from saved responses, verifies request accounting and checkpoint hashes, and reproduces the pinned upstream summaries without new inference. The [independent hosted aggregate audit](../reports/jevbench-public-20260921/hosted-independent-summary-audit.json) reproduces every saved aggregate and tier result from saved result records, and verifies all 693 saved model identities and request accounting. The separate [hosted raw-response replay audit](../reports/jevbench-public-20260921/hosted-raw-replay-audit.json) verifies all 693 raw hashes, exactly reconstructs the upstream requests, checks actual resolved model IDs, and replays adapter parsing and upstream scoring offline. All three audits passed; no audit issued new provider requests.

Public artifacts contain only allowlisted aggregates, protocol, and provenance hashes. Raw tasks, states, labels, task IDs, provider responses, credentials, and absolute node paths are not exported. Upstream benchmark data remains evaluation data and is not added to the training mixture.

27B v1.1 completed training and both its full internal and public JevBench audits. New 2B training stopped; new 9B training did not start. Those new checkpoints have no reported scores, and the historical released 2B/9B rows remain unchanged.
