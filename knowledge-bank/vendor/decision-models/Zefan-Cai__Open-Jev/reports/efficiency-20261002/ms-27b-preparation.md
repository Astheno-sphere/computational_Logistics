# MS 27B preparation status — 2026-10-02

The released 27B checkpoint is prepared for a Torch, Triton-tail and attributed fast-cuda comparison on MS N1-1. **No GPU inference or performance run has started.** The bounded fleet check at 18:33:25 UTC reached six of 15 nodes; all 48 visible GPUs were occupied. The other nine nodes' GPU state is unknown.

Preparation uses clean [source commit `42e4648`](https://github.com/Zefan-Cai/Open-Jev/tree/42e46481da6dd8191d6f510fc3680c70fd4f051d), the released checkpoint SHA256 `c49994563c3c4f04a99d9130203c4e526f4ae5086c84deec57698d18cb652e71`, and Qwen/Qwen3.8-27B base revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`. All 18 base shards were fully hashed against their HF blob identities; indexed tensors, file lengths, tokenizer/chat template and both fast architecture profiles passed validation.

The selected read-only runtime is Python 3.11.15, Torch 2.8.0+cu128, Transformers 5.10.2, PEFT 0.19.1 and Triton 3.4.0. Exact FLA 0.5.2 and fla-core 0.5.2 wheels are installed in a task-local overlay, with all required internal symbols verified. The shared runtime was not modified. This is selected runtime preparation; a complete environment lock and fresh Linux installation have not been verified by this report.

The attributed CUDA extension compiled and loaded for explicit sm90 using CUDA 12.8.93, at most two compiler workers and an isolated extension cache, with GPU visibility disabled. Its SHA256 is `7d417b84ca91278cad26bc5f443c6a6304a3cbfcc3dd150dbab87c44f8f58835`. Compilation establishes no kernel-execution parity or model speedup.

A prepared launch guard requires the pinned source/checkpoint and a genuinely empty GPU before loading weights. Its rejection of an occupied GPU was verified without launching a model. Existing jobs and allocations remain untouched. Once a GPU allocation is resolved, the prepared smoke check precedes the eight-workload comparison with latency, allocator memory, output/decision parity and threshold crossings. Those results remain unavailable.

The [machine-readable preparation receipt](ms-27b-preparation.json) records public hashes, selected package versions and the current aggregate allocation state. Private operational paths, process IDs, command lines and other users' allocation details are excluded. The existing [released 2B H200 report](h200-2b-summary.md) retains its original hardware/model scope.
