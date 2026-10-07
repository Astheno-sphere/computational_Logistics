# Released 2B H200 inference validation

Both the PyTorch reference and the Triton final-row backend loaded the published Open-Jev-2B adapter, FP32 head and temperature. All five inference files, the checkpoint directory digest and all 13 pinned upstream model/tokenizer files were verified before execution. No checkpoint or calibration value was changed.

All eight workloads passed. The accelerated run contains 168 in-process comparisons with the reference and 168 additional loopback HTTP comparisons. Maximum probability error was 1e-07; decision changes: 0; audited threshold flips: 0. Question/candidate order, finite normalized distributions and input-token usage matched. The smallest measured candidate margin to the audited thresholds was 0.00142582. This evidence is confined to the recorded workloads.

Observed warm P50 in-process ratios were 1.006–1.020×; loopback HTTP ratios were 1.002–1.034×. These small differences came from sequential model runs with 20 samples and three warmups per workload. The experiment does not establish statistically significant whole-model gains. The separately measured 2.63–2.75× final-row operator ratio must retain its isolated scope.

## In-process Predictor timings

P50/P95 include tokenization, model scoring, response formatting and synchronized CUDA completion. Cold load/checksum and first-observed request timings are recorded separately in the raw JSON. Batch size was 32 and concurrency was one.

| Workload | State tokens | Candidates | Torch P50 / P95 (ms) | Triton P50 / P95 (ms) | P50 ratio |
|---|---:|---:|---:|---:|---:|
| Example request | 26 | 7 | 75.06 / 84.65 | 74.04 / 74.65 | 1.014× |
| Short mixed types | 69 | 6 | 77.28 / 79.04 | 75.78 / 76.55 | 1.020× |
| Medium mixed types | 422 | 12 | 144.32 / 144.84 | 141.56 / 141.96 | 1.019× |
| Long mixed types | 1478 | 20 | 631.69 / 949.00 | 622.97 / 625.05 | 1.014× |
| Risk just below 0.2 | 47 | 1 | 72.38 / 73.62 | 71.80 / 72.47 | 1.008× |
| Risk just above 0.2 | 47 | 1 | 72.50 / 83.70 | 71.83 / 72.79 | 1.009× |
| Support just below 0.8 | 47 | 1 | 72.20 / 73.59 | 71.78 / 73.04 | 1.006× |
| Support just above 0.8 | 57 | 1 | 73.27 / 73.64 | 71.87 / 72.90 | 1.019× |

Candidate sequence lengths were 66–1,539 tokens; the released checkpoint context limit is 4,096. The seven original synthetic fixtures cover short, medium and long mixed Choice/Noul/Score requests plus policy values surrounding 0.2/0.8. Actual probability margins are recorded independently of those policy values.

## Loopback HTTP timings

Each request used a fresh local TCP connection to an already warmed model, including JSON serialization and the server path. These measurements do not describe WAN latency or a hosted third-party API.

| Workload | Torch P50 / P95 (ms) | Triton P50 / P95 (ms) | P50 ratio |
|---|---:|---:|---:|
| Example request | 73.33 / 74.35 | 71.99 / 75.89 | 1.019× |
| Short mixed types | 75.50 / 76.23 | 73.76 / 75.40 | 1.024× |
| Medium mixed types | 144.88 / 145.27 | 142.49 / 142.91 | 1.017× |
| Long mixed types | 633.11 / 807.45 | 624.55 / 626.88 | 1.014× |
| Risk just below 0.2 | 70.15 / 72.67 | 69.96 / 70.53 | 1.003× |
| Risk just above 0.2 | 70.01 / 70.46 | 69.84 / 70.24 | 1.002× |
| Support just below 0.8 | 70.15 / 70.55 | 69.44 / 69.79 | 1.010× |
| Support just above 0.8 | 71.92 / 72.57 | 69.57 / 69.95 | 1.034× |

## Memory and provenance

Resident Torch CUDA allocation after loading was 3.515 GiB; Triton-tail was 3.515 GiB. Maximum observed per-request peak allocation was 6.917 GiB and 6.917 GiB respectively. The report retains allocated/reserved/device-used figures separately. These tail results do not establish tree-backbone or training-memory reductions.

Runtime: NVIDIA H200 sm90, CUDA 12.8, driver 595.71.05, Python 3.12.13, Torch 2.9.0+cu128, Triton 3.5.0, Transformers 5.10.2 and PEFT 0.19.1. BF16 backbone weights and FP32 LoRA/head were resident on GPU0. The optional flash-linear-attention distribution was absent; both backends used the same reference backbone runtime.

Checkpoint: `3076462e6356412082e79af909227b39b2863b90def79155ca0821aa506b7ded`. Base/tokenizer revision: `15852e8c16360a2fea060d615a32b45270f8a8fc`. Public package revision: `0c7aa498b1627be8da4acf34c863ff0ee0a92785`. Clean pushed source commit: `ed28a2fd9237814fd8175b6c0bdd05f18eadff76`.

Reference report digest: `ab0cc377e5e6da5eba53344b070ec14866ccdd119b84160d2a7885a294458d81`. Accelerated report digest: `7ba3c85695061439760ecf788d56f2057de98082fbff6bb7cd801ee434f5bc91`. Both digests were rechecked after retrieving the raw reports.

Artifacts: `h200-2b-torch-ed28.json`, `h200-2b-triton-tail-ed28.json`, `h200-2b-package-provenance.json`, `cache-provenance-2b.json`, and `h200-kernel-summary.md`.

Full 9B/27B checkpoint inference, the vendored tree CUDA backbone, CUDA compilation, broader probability-boundary coverage, application quality and training performance remain unmeasured in this report.
