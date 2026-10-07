# Frozen public-development comparison: released 2B and fixed-step pilot

The released Open-Jev-2B and the completed 64-step continued-training pilot each answered the same frozen 64 requests, with **64 successes, zero failures and zero invalid distributions per model**. Choice and Noul accuracy did not improve. Mean normalized Score error decreased on this sample; the subset competence increase comes entirely from its seven Score cases.

| Metric | Released 2B | Fixed-step pilot |
| --- | ---: | ---: |
| Choice correct | 17/34 (50.00%) | 17/34 (50.00%) |
| Noul correct, v1.5 thresholds | 9/23 (39.13%) | 9/23 (39.13%) |
| Noul coverage | 17/23 (73.91%) | 18/23 (78.26%) |
| Noul abstentions | 6 | 5 |
| Score mean normalized MAE | 0.22392971 | 0.20645096 |
| Score auxiliary argmax correct | 2/7 | 2/7 |
| Equal-type subset competence | 22.834944 | 24.257338 |

The normalized MAE change is **−0.01747875**. The descriptive subset competence change is **+1.422394 points**, from Score tier-weighted competence increasing from 39.585240 to 43.852421. Choice and Noul tier-weighted competence remain unchanged. These subset values are not an official JevBench score or rank.

## Paired audit

Strict replay of both durable request journals reproduces the saved aggregates and comparison exactly. All 34 Choice decisions remain unchanged. For Noul, one abstention becomes an incorrect answer; the other 22 decisions remain unchanged. Higher Noul coverage therefore adds no correct answer. All seven Score argmax decisions remain unchanged; expected-value normalized MAE improves on four cases and regresses on three. All 128 returned distributions pass the upstream strict probability-sum tolerance without renormalization.

The paired diagnostics are descriptive. No uncertainty estimate or significance claim is made.

## Frozen procedure and identity

The pinned accessible public source contains 231 items. Before either run, the collector froze 64 requests using metadata strata and a deterministic seed: 32 from historically weak priority families and 32 from the remaining coverage pool. The sample contains 34 Choice, 23 Noul and seven Score tasks; its tiers are 48 hard, eight standard and eight easy. Selection used task ID, family, type and source tier, without individual gold labels or pilot predictions.

Both models use Qwen/Qwen3.5-2B revision `15852e8c16360a2fea060d615a32b45270f8a8fc`, serving commit `80ca8e81d08992cb2a4cbb6a0caa1355ad3e5aee`, the Torch backend, BF16 base weights and FP32 adapter/head parameters, batch size 32, and prefix caching disabled. Both servers override their saved 4096-token settings with `--max-length 16384` for this comparison. Requests were sent sequentially to the same loopback API bridge, without retries or warmups.

| Identity | Released 2B | Fixed-step pilot |
| --- | --- | --- |
| Serving checkpoint SHA256 | `3076462e6356412082e79af909227b39b2863b90def79155ca0821aa506b7ded` | `61e22c91bfbcdcba02ea1c62d039d8169cdf4f73f79cfe2c170322da2bb7c037` |
| Independently fitted temperature | 1.518796342858676 | 1.5446931834967927 |

The shared request SHA256 is `1c85c5db7b7804544e26dd96defd18a0ab152a582df0cc5db9198eb2c6e50cb9`. The public source is pinned to `bb05a335bc809e61b20c0f745d25499a82b326fc`. The pilot completed its fixed 64-step schedule before this comparison. These results were not used to select a checkpoint, temperature or training configuration.

Scoring follows the documented public v1.5 rules: Noul predicts no for p(yes) ≤ 0.2, yes for p(yes) ≥ 0.8, and otherwise abstains; abstentions count as incorrect. Score uses the probability-weighted expected level and normalized absolute error. Score argmax accuracy is an auxiliary diagnostic.

## Limits and next decision

The method documents 601 published-open and 904 total open items; an additional 370 documented published-open items are absent from this pinned source. This check uses only the accessible subset. Public items and historical public error summaries already informed development, so this is public development evidence. All three task types lack the judge tier, and Score also lacks the easy tier; competence weights are renormalized over present tiers. Only seven Score cases contribute to the observed improvement.

The models have different independently fitted temperatures. The comparison measures the combined weight and calibration change and does not isolate a weight effect. It establishes no blind or sealed improvement, official I_open, calibration axis, speed/cost axis, composite, rank or broad generalization gain. Request wall times are heterogeneous quality-run diagnostics and do not establish a latency change.

Retain the pilot as a reproducible development checkpoint. Its synthetic held-out improvements have not yet produced Choice or Noul accuracy gains on this public sample. A future generalization decision needs a separately frozen evaluation and an explicit acceptance rule; this run does not justify promoting a categorical benchmark claim.

## Artifacts

- [Released aggregate](released-2b-frozen64.json), [pilot aggregate](pilot-2b-frozen64.json), and [comparison](pilot-vs-released-frozen64.json).
- [Paired aggregate audit](paired-frozen64.json) and [execution/provenance receipt](execution-receipt.json).
- [Completed training receipt](../frontier-controls-v4/continued-2b-20261002/completion-receipt.json).

Inputs, gold labels and raw responses remain in ignored private run storage. Public artifacts contain aggregates and hashes only. Upstream MIT coverage of the harness and 72 original items does not authorize redistribution of all benchmark text.
