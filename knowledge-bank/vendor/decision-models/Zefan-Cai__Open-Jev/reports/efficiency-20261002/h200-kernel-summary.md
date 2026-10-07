# H200 final-row operator validation

This report measures the isolated final-row gather, BF16 residual addition, RMSNorm and FP32 scalar head. No Qwen backbone or released decision checkpoint is loaded. These timings do not establish whole-model or HTTP speedups.

The H200 run passed all 12 tests: two CUDA tests covering all three released hidden widths, residual fusion and invalid-row guards, plus ten profile, ownership and reference checks. All nine seeded activation cases passed probability, decision and threshold parity at tolerance 1e-4. There were zero decision changes and zero threshold flips across the audited thresholds 0.2, 0.5, 0.7, 0.8, 0.9, 0.95 and 0.99.

Maximum logit error: 1.12e-07; maximum probability error: 2.09e-08. Observed warm P50 operator speedup: 2.63–2.75×. Each case has 100 timed iterations after 10 warmups. Timings include Python dispatch and synchronized CUDA completion; first-observed cold calls are retained separately in the JSON.

| Hidden width | State tokens | Candidates | Torch P50 (ms) | Triton P50 (ms) | Torch P95 (ms) | Triton P95 (ms) | P50 ratio |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2048 | 128 | 2 | 0.09778 | 0.03707 | 0.11804 | 0.04248 | 2.64× |
| 2048 | 512 | 8 | 0.09768 | 0.03683 | 0.10593 | 0.04012 | 2.65× |
| 2048 | 1024 | 32 | 0.10229 | 0.03764 | 0.12021 | 0.04124 | 2.72× |
| 4096 | 128 | 2 | 0.10769 | 0.04031 | 0.11918 | 0.04542 | 2.67× |
| 4096 | 512 | 8 | 0.09869 | 0.03744 | 0.11423 | 0.04119 | 2.64× |
| 4096 | 1024 | 32 | 0.10262 | 0.03732 | 0.11939 | 0.04073 | 2.75× |
| 5120 | 128 | 2 | 0.09785 | 0.03682 | 0.10162 | 0.03964 | 2.66× |
| 5120 | 512 | 8 | 0.09847 | 0.03746 | 0.11092 | 0.04008 | 2.63× |
| 5120 | 1024 | 32 | 0.10242 | 0.03748 | 0.11242 | 0.04089 | 2.73× |

Runtime: Python 3.12.13, Torch 2.9.0+cu128, Triton 3.5.0, CUDA 12.8, driver 595.71.05, H200 sm90. TF32 matmul is disabled. A CUDA compiler is not required for this Triton operator and was absent from this run's PATH.

Source commit: `ed28a2fd9237814fd8175b6c0bdd05f18eadff76`. Source digest: `5bfeef9c9716d8a451732d03ab32b104c86013154931c628ff01810e584145d6`. Environment digest: `816ee72a7bbca4e9aa4271b2ec7e41ce96236e6962f8eecd86b1acdafa856109`. Verified report digest: `9aeb0f993199bfa5a29640631ca412169739332b64eed65bd11fafceb5ae92ba`.

Artifacts: `h200-kernel-results-ed28.json` contains all raw samples, first-observed cold calls, numerical margins, allocator measurements and provenance. `h200-kernel-tests-ed28.txt` records the 12 passing tests; the test source came from an archive of the same pushed commit and is bound by `h200-kernel-test-source-manifest.json`. The timed run used a clean sparse Git checkout of that commit.

Released-checkpoint end-to-end, loopback HTTP, tree-prefix CUDA, and training measurements remain separate requirements. No deployment, training-memory reduction, or full-backbone performance claim follows from this operator test.
