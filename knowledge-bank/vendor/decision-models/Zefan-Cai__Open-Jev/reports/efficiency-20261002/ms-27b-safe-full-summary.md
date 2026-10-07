# Released 27B H100 inference validation

PyTorch and Triton-tail completed all eight workloads with the released 27B checkpoint. All 168 in-process comparisons and 168 separate loopback HTTP comparisons passed the unchanged `1e-4` tolerance. Maximum probability error was `1.88970e-6`; maximum Score-expectation error was `3.53247e-6`. Decision changes and audited threshold flips were zero. The smallest measured candidate margin to an audited threshold was `0.00189528`. These findings apply to the recorded workloads.

Observed warm in-process P50 ratios were 1.004–1.020×; loopback HTTP ratios were 1.002–1.029×. Models ran sequentially with 20 samples and 3 warmups per workload. A separate short 2B pilot on another GPU overlapped part of the Torch run and finished in 185.15 seconds. This design and these small differences do not establish statistically significant whole-model gains.

The earlier [fast-cuda smoke](ms-27b-smoke.md) failed probability parity and remains unchanged. Its complete run was skipped and its diagnostic latency is not an accepted speedup.

## In-process Predictor timings

Timings include tokenization, scoring, response formatting and synchronized CUDA completion. Cold model load/checksum/JIT and first-observed request timings remain separate in raw JSON. Batch size was 32 and concurrency was 1.

| Workload | State tokens | Candidates | Torch P50 / P95 (ms) | Triton P50 / P95 (ms) | P50 ratio |
|---|---:|---:|---:|---:|---:|
| Example request | 26 | 7 | 101.77 / 110.98 | 100.52 / 103.12 | 1.013× |
| Short mixed types | 69 | 6 | 108.45 / 108.92 | 107.08 / 108.21 | 1.013× |
| Medium mixed types | 422 | 12 | 669.62 / 670.96 | 666.88 / 670.90 | 1.004× |
| Long mixed types | 1478 | 20 | 3557.68 / 3563.57 | 3540.02 / 3545.85 | 1.005× |
| Risk just below 0.2 | 47 | 1 | 97.95 / 99.95 | 96.11 / 96.52 | 1.019× |
| Risk just above 0.2 | 47 | 1 | 97.36 / 98.05 | 95.43 / 96.69 | 1.020× |
| Support just below 0.8 | 47 | 1 | 97.63 / 98.26 | 95.93 / 96.62 | 1.018× |
| Support just above 0.8 | 57 | 1 | 97.58 / 98.23 | 95.80 / 97.27 | 1.019× |

Candidate sequence lengths were 66–1539 tokens, within the checkpoint 4096-token limit. The seven original synthetic fixtures contain short/medium/long mixed Choice/Noul/Score requests and policy values around 0.2/0.8. Actual probability margins are audited independently of those policy values.

## Loopback HTTP timings

Each request used a fresh local TCP connection to an already warmed model, including JSON serialization and the server path. This is not WAN or hosted-third-party API latency.

| Workload | Torch P50 / P95 (ms) | Triton P50 / P95 (ms) | P50 ratio |
|---|---:|---:|---:|
| Example request | 102.44 / 104.16 | 99.55 / 101.38 | 1.029× |
| Short mixed types | 110.87 / 111.59 | 109.29 / 109.82 | 1.014× |
| Medium mixed types | 670.64 / 675.12 | 669.05 / 672.73 | 1.002× |
| Long mixed types | 3565.97 / 3573.70 | 3544.94 / 3550.09 | 1.006× |
| Risk just below 0.2 | 98.71 / 101.07 | 97.04 / 98.72 | 1.017× |
| Risk just above 0.2 | 97.36 / 101.03 | 97.13 / 100.64 | 1.002× |
| Support just below 0.8 | 98.71 / 99.63 | 96.13 / 97.28 | 1.027× |
| Support just above 0.8 | 97.74 / 99.64 | 96.21 / 97.15 | 1.016× |

## Memory and provenance

Resident CUDA allocation after load was 47.787 GiB for Torch and 47.787 GiB for Triton-tail. Maximum observed request peak allocation was 54.124 GiB and 54.124 GiB respectively. Raw reports keep allocated, reserved and device-used figures separate. This does not establish backbone or training-memory reductions.

Runtime: NVIDIA H100 80GB sm90, Python 3.11.15, Torch 2.8.0+cu128, Transformers 5.10.2, PEFT 0.19.1, Triton 3.4.0 and task-local FLA/fla-core 0.5.2. CUDA compiler 12.8.93 and driver 570.195.03. Both used BF16 backbone weights with FP32 LoRA/head and the same calibrated temperature.

Source: `42e46481da6dd8191d6f510fc3680c70fd4f051d`. Released checkpoint: `c49994563c3c4f04a99d9130203c4e526f4ae5086c84deec57698d18cb652e71`. Pinned base/tokenizer revision: `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`.

The current fleet scope is six nodes and 48 GPUs: N1-1, N1-3 and N4-1 through N4-4. Historical probes do not expand current membership. This is not a live occupancy count.

Artifacts: [Torch full](ms-27b-torch-full-42e464.json), [Triton-tail full](ms-27b-triton-tail-full-42e464.json), [machine-readable summary](ms-27b-safe-full-receipt.json). Both raw files are byte-identical to their retrieved originals; canonical report digests were rechecked. The 2B H200 report retains its own hardware/model scope.

The temporary allocation ended with the original model, optimizer and sampler tree verified to resume from the preserved checkpoint and enter actual sampling, with four live training workers. All three original sampler services subsequently returned successful actual completion requests. The original failure retry budget and completed jobs were preserved. The unfinished batch was replayed; no completed checkpoint was lost. Both owned benchmark and pilot sessions were gone before the queue restart.
