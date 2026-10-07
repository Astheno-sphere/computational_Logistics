# Released 27B H100 smoke validation

The released 27B checkpoint executed real GPU inference with PyTorch, Triton-tail and fast-cuda on an H100 80GB. **Fast-cuda failed output parity**, so the planned complete three-backend comparison did not run and no fast-cuda speedup is accepted.

The single example contained seven candidates across Choice, Noul and Score. Triton-tail passed: maximum probability error was `2.81536e-8` and maximum Score-expectation error was `2.88825e-8`. Fast-cuda exceeded the unchanged `1e-4` tolerance: probability error was `0.00593285` and Score-expectation error was `0.000268743`. Its Noul value changed from `0.7258142051` to `0.7317470526`. This example had no changed decisions or audited threshold flips; that does not establish probability parity. Both in-process and loopback HTTP checks recorded the failure.

| Backend | Probability parity | One warm in-process sample (ms) | One warm loopback HTTP sample (ms) |
|---|---|---:|---:|
| PyTorch | Reference | 104.13 | 102.27 |
| Triton-tail | Passed on this request | 108.85 | 105.61 |
| fast-cuda | Failed | 32.32 | 34.97 |

These are diagnostic single samples, collected sequentially with zero requested warmups. They are not a complete latency or throughput result. Cold load/checksum/JIT and first-observed request measurements remain separately recorded in the raw report. Allocator figures are retained without making a training-memory claim.

Source commit: `42e46481da6dd8191d6f510fc3680c70fd4f051d`. Released checkpoint SHA256: `c49994563c3c4f04a99d9130203c4e526f4ae5086c84deec57698d18cb652e71`. Qwen/Qwen3.8-27B revision: `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`. All 18 base shards were fully hashed before launch. Runtime: Python 3.11.15, Torch 2.8.0+cu128, Transformers 5.10.2, PEFT 0.19.1, Triton 3.4.0, task-local FLA/fla-core 0.5.2 and CUDA 12.8.93; sm90 extension compilation and real kernel/model execution were observed.

The current fleet scope is six nodes and 48 GPUs: N1-1, N1-3 and N4-1 through N4-4. Historical probes of other node names do not define current fleet membership. This statement is not a live occupancy count.

Operational verification retained a complete paired checkpoint before the temporary allocation. The original model, optimizer and sampler tree resumed from that checkpoint and returned to actual sampling, with the original failure retry budget preserved. The unfinished batch was replayed; no completed checkpoint was lost. The optional second-GPU pilot did not start during this smoke window.

Artifacts: [immutable raw smoke report](ms-27b-smoke-42e464.json) and [verification receipt](ms-27b-smoke-receipt.json). The existing 2B H200 results retain their own model/hardware scope. Safe-backend validation over all eight workloads and correction of fast-cuda numerical differences remain separate next steps.
