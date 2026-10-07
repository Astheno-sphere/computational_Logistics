# New 27B: JevBench public subset

The new community-hard-mix-v2 27B model completed 37,160 optimizer steps and all 231 public JevBench tasks. Independent saved-response replay and standard-library scoring passed.

| Model | Overall / 231 | Accuracy | Hard / 111 | Hard accuracy |
|---|---:|---:|---:|---:|
| Released Open-Jev 2B | 150 | 64.94% | 46 | 41.44% |
| Released Open-Jev 9B | 179 | 77.49% | 66 | 59.46% |
| New Open-Jev 27B | 197 | 85.28% | 80 | 72.07% |
| Jev 1.13.0 | 200 | 86.58% | 81 | 72.97% |

The new 27B scored 69/72 Original, 48/48 Easy and 80/111 Hard. All 231 requests succeeded with strictly valid probability vectors; none required renormalization. It remains three correct answers behind Jev overall and one behind on Hard. The older 2B/9B rows are released checkpoints, not newly trained models.

This is the **231-task public subset**, not the full 534-task JevBench. All rows in this table use the same pinned public tasks and native scoring rules. The 27B executed directly across four shared H100 GPUs; its timings cannot establish a speedup relative to the previous single-GPU HTTP runs or hosted Jev HTTPS. No latency ranking is presented here.

[report.json](report.json) retains compact results, protocol, model identity and the audit hash. [audit.json](audit.json) records checksums, independent denominator/score checks and complete upstream-summary replay. Integer results and structure match exactly; cross-runtime floating-point differences are at most 2.23e-16 and pass a 1e-12 tolerance. Raw inputs, responses, labels and task IDs are retained only in the ignored run directory.

The audit issued no inference or hosted API calls and did not change running jobs.
