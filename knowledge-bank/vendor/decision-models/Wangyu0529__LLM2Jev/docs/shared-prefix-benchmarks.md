# Shared prefixes: performance benchmarks

[简体中文](shared-prefix-benchmarks_zh.md) · [Shared-prefix concepts](shared-prefix-cache.md)

A cold-KV request here has no relevant cached input prefix, but the model and computation kernels are already warmed up. A warm request can reuse existing prefixes. These measurements compare `all` and `staged` submission in the local Python `SGLangBackend`.

The following local measurements use Qwen3-1.7B, BF16, an RTX 5090, SGLang 0.5.20 and Triton attention, with decode CUDA Graph and chunked prefill disabled. Tests used the current default prompt, serialized requests, five warm-up iterations and 30 measurements per configuration. Values are median end-to-end cold-KV latency, including rendering, tokenization and response assembly, excluding model loading and cache flushing.

| Workload | All at once | Staged |
| --- | ---: | ---: |
| Baseline: 3 questions, 9 candidates | 84.00 ms | 36.43 ms |
| Long context: 4 questions, 8 candidates | 611.77 ms | 125.15 ms |
| Mixed question types: 9 candidates | 93.09 ms | 40.88 ms |
| Short input: 1 question, 2 candidates | 11.49 ms | 19.11 ms |

The long-context cold request was about 4.9 times faster, while the short request became slower. With fully warm cache, that same long-context workload took about 25.88 ms with all-at-once submission and 50.79 ms with staging. Choose based on your requests; these measurements do not predict every model, device or concurrent workload.

See [Usage guide](usage.md) for configuration examples and mode selection.
