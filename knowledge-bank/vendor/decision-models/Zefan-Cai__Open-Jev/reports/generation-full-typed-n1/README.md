# Full typed-output generation comparison

This experiment requires the autoregressive model to emit all probabilities and derive Choice/Score/confidence/legend fields itself. The decision scorer derives those fields in software. These different arithmetic demands are material to the validity failures below. This is not a comparison of decision accuracy.

| Model | Decision valid | Generation valid | Decision median | Generation median, invalid attempts | Valid-output ratio |
|---|---:|---:|---:|---:|---|
| 2b | 3/3 | 0/3 | 34.4 ms | 3.609 s | unavailable |
| 9b | 3/3 | 0/3 | 41.3 ms | 5.270 s | unavailable |
| 27b | 3/3 | 0/3 | 121.8 ms | 15.116 s | unavailable |

Each path has one excluded warmup and three timed greedy repeats. All models and immutable revisions match within each pair; actual prompt/input/output tokens and raw generations are retained in the JSON files. All three generative baselines fail derived-field schema checks, so no successful-output speedup is reported.

The 2B report was collected by the original suite. The 9B/27B runs use the same request and benchmark version, and their manifest records no foreign GPU processes at sampled two-second checks. Sampling cannot exclude activity between checks. These are small descriptive H100 measurements, not production latency distributions or Jev speed comparisons.

A separate [probability-only generation comparison](../generation-probabilities-n1/README.md) with common software postprocessing is now complete. Its new outputs leave these original failures and null ratios intact.
