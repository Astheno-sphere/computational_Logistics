# Browser snapshot pilot: three-model evidence archive

**Complete proposal accuracy is 32/120 (26.67%) for 2B, 69/120 (57.50%) for 9B,
and 104/120 (86.67%) for 27B.** The 2B result is below the descriptive
always-BLOCKED baseline of 35/120 (29.17%). The 9B model correctly identifies
only 1/16 DONE cases; 27B incorrectly acts in 14/35 BLOCKED cases. Operation
accuracy and conditional-head accuracy do not remove these complete-proposal
failures. These results do not establish usable browser control or real web-task
completion.

**All three measurements are complete and archived here.** They ended on
2026-09-20 at 02:58:19.943662, 03:01:22.865957, and 03:09:12.167480 UTC for
2B, 9B, and 27B, respectively. Each has 120/120 requests, zero pending cases,
zero HTTP/schema/identity errors, and evaluator exit code 0. These are 360
requests over the same 120 snapshots, not 360 distinct evaluation examples.

The [final suite manifest](suite-manifest-final.json), captured at 03:10:48 UTC,
records `complete`/`finished` with suite end time 03:09:14.220117 UTC. Its SHA-256
is `ea3865db1056e4a7fefde45acc780e6a19354cf865ff00ef9797a912fa77eddc`.
The earlier running snapshots at
[02:59:02 UTC](suite-manifest-snapshot-20260920T025902Z.json) and
[03:05:58 UTC](suite-manifest-snapshot-20260920T030558Z.json) remain unchanged.

These checkpoints are the original [100-step engineering pilots](../pilot-results.md),
each of which consumed 400 training rows. They were not trained on the separately
generated browser corpus. This is a limited transfer test of those pilots, not
an evaluation of the active release-v2 training run or checkpoints trained on
browser data.

## Independently recomputed measurements

The fixed selection has 120 requests from 40 parent scenes: 60 requests from 20
test parents and 60 from 20 OOD parents, with three variants per parent. Parent
variants are correlated. Counts describe this fixed synthetic sample; no
independent-sample significance claim is made.

| Model | Metric | Overall | Test | OOD |
| --- | --- | ---: | ---: | ---: |
| 2B | Complete proposal exact match | **32/120 (26.67%)** | 18/60 (30.00%) | 14/60 (23.33%) |
| 9B | Complete proposal exact match | **69/120 (57.50%)** | 33/60 (55.00%) | 36/60 (60.00%) |
| 27B | Complete proposal exact match | **104/120 (86.67%)** | 53/60 (88.33%) | 51/60 (85.00%) |
| 2B | Operation exact match | 57/120 (47.50%) | 29/60 (48.33%) | 28/60 (46.67%) |
| 9B | Operation exact match | 72/120 (60.00%) | 36/60 (60.00%) | 36/60 (60.00%) |
| 27B | Operation exact match | 104/120 (86.67%) | 53/60 (88.33%) | 51/60 (85.00%) |
| 2B | Reference-active conditional heads, at least two candidates | 67/98 (68.37%) | 43/56 (76.79%) | 24/42 (57.14%) |
| 9B | Reference-active conditional heads, at least two candidates | 93/98 (94.90%) | 51/56 (91.07%) | 42/42 (100.00%) |
| 27B | Reference-active conditional heads, at least two candidates | 98/98 (100.00%) | 56/56 (100.00%) | 42/42 (100.00%) |
| 2B | Forced one-candidate reference-active heads | 16/16 | 9/9 | 7/7 |
| 9B | Forced one-candidate reference-active heads | 16/16 | 9/9 | 7/7 |
| 27B | Forced one-candidate reference-active heads | 16/16 | 9/9 | 7/7 |

The conditional metric uses heads active under the **reference** operation,
even when the predicted operation is wrong. Complete-proposal scoring uses the
operation and conditional branch the model actually selected. Forced
single-candidate accuracy is not evidence of learning to choose among options.
The evaluator retains all selected cases and applicable heads in their
denominators when HTTP, schema, or identity failures occur; none of these runs
had any.

## Reference distribution and constant-operation baselines

| Reference operation | Overall | Test | OOD | 2B operation matches | 9B operation matches | 27B operation matches |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BLOCKED | 35 | 17 | 18 | 2/35 | 13/35 | 21/35 |
| DONE | 16 | 8 | 8 | 0/16 | 1/16 | 14/16 |
| WAIT | 5 | 1 | 4 | 0/5 | 4/5 | 5/5 |
| CLICK | 14 | 3 | 11 | 11/14 | 13/14 | 14/14 |
| TYPE_TEXT | 15 | 6 | 9 | 15/15 | 8/15 | 15/15 |
| SELECT | 35 | 25 | 10 | 29/35 | 33/35 | 35/35 |

The 2B model predicts CLICK 27 times, TYPE_TEXT 32, SELECT 49, DONE 8, BLOCKED 4,
and WAIT zero times. It misses every reference DONE and WAIT case. Matching the
operation alone also leaves 25 cases where the complete target/value proposal
is wrong: 57 operation matches become only 32 complete proposal matches.

The 9B model predicts CLICK 26 times, TYPE_TEXT 14, SELECT 49, DONE 1, BLOCKED
24, WAIT 4, and SCROLL_DOWN 2. Seven reference TYPE_TEXT cases are incorrectly
blocked, and 15 of 16 completed snapshots receive a different operation. Its
72 operation matches become 69 complete proposal matches. The OOD conditional
42/42 result is measured on reference-active heads and does not imply success
on all OOD snapshots: complete proposals match only 36/60.

The 27B model predicts CLICK 17 times, TYPE_TEXT 19, SELECT 44, DONE 14,
BLOCKED 21, and WAIT 5. Its 16 complete-proposal errors consist of 14 BLOCKED
cases incorrectly sent to CLICK (3), TYPE_TEXT (4), or SELECT (7), plus two
DONE cases incorrectly sent to SELECT. All 98 reference-active multi-candidate
heads match, but that does not prevent these operation failures. The remaining
errors concern whether an action should happen at all.

| Constant prediction | Overall operation and proposal matches | Test | OOD |
| --- | ---: | ---: | ---: |
| Always BLOCKED | **35/120 (29.17%)** | 17/60 | 18/60 |
| Always DONE | 16/120 (13.33%) | 8/60 | 8/60 |
| Always WAIT | 5/120 (4.17%) | 1/60 | 4/60 |

These three operations require no target/value, so their constant-operation
and complete-proposal match counts are identical. These are descriptive
agreement baselines calculated from the frozen references, not simulated
rollouts or evidence that always refusing a task is useful. No model outputs
were replaced with baseline or teacher outputs.

## Identity and source binding

| Model | Base revision | Checkpoint SHA-256 | Temperature |
| --- | --- | --- | ---: |
| `Qwen/Qwen3.5-2B` | `15852e8c16360a2fea060d615a32b45270f8a8fc` | `1d3c0e4e37bf04731edee447363ddc02d084a9c1f10ab829ac4d424f7d7c413b` | 1.7360720317205194 |
| `Qwen/Qwen3.5-9B` | `c202236235762e1c871ad0ccb60c8ee5ba337b9a` | `7aa5f62fa39b83aee07915e7e351da5c4c38b4ce5f751cf22c7d45edf7dfc0ef` | 1.4205161837096647 |
| `Qwen/Qwen3.8-27B` | `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0` | `68ff078d7a83a92f3a4b6458d4c349b81bf533baf373d0361135f53e684357a2` | 1.4870151221815284 |

| Shared field | Recorded value |
| --- | --- |
| Method | `lora_decision_head` |
| Serving and evaluation commit | `5b11fe38401831a24c886d28040d55f9a6f03b41` |
| Context limit / candidate batch size | 16,384 / 1 |
| Host / physical GPU | `kwade5342000001` / GPU 3, NVIDIA H100 80GB |
| GPU UUID | `GPU-9ab08bcc-ce17-0461-aaf2-5d57ddcb4775` |
| Frozen cases SHA-256 | `608b0c0623f920c68001c07af2c87234ef1fe95a96102f6a25d5ff0cecc61537` |
| Source manifest SHA-256 | `ed2443c14eb5d63a827a0bca569f5369537e59334481bccb4cf6651521325c0d` |
| Selection SHA-256 | `d6845a2e259967d99fd886f381a4150a3812aa79b0c1c855826fdcfff0030707` |

The suite records the GPU idle before loading and after shutting down each
model. These are endpoint snapshots, not continuous proof of GPU exclusivity.
The reference generator and model-input limits are documented in
[browser-data.md](../../docs/browser-data.md); the evaluation contract is in
[browser-eval.md](../../docs/browser-eval.md). Saved synthetic references were
checked against the frozen cases, not independently relabeled by this audit.

## Original evidence and offline audit

Each model's five original evaluator files are copied byte-for-byte:

| Evidence | 2B | 9B | 27B |
| --- | --- | --- | --- |
| Selection | [JSON](2b/browser/selection.json) | [JSON](9b/browser/selection.json) | [JSON](27b/browser/selection.json) |
| Wire requests | [JSONL](2b/browser/requests.jsonl) | [JSONL](9b/browser/requests.jsonl) | [JSONL](27b/browser/requests.jsonl) |
| Active references | [JSONL](2b/browser/references.jsonl) | [JSONL](9b/browser/references.jsonl) | [JSONL](27b/browser/references.jsonl) |
| Raw responses and outcomes | [JSONL](2b/browser/outcomes.jsonl) | [JSONL](9b/browser/outcomes.jsonl) | [JSONL](27b/browser/outcomes.jsonl) |
| Final report | [JSON](2b/browser/report.json) | [JSON](9b/browser/report.json) | [JSON](27b/browser/report.json) |
| Evaluator log | Log (`2b/browser.log`, operational record retained in the development archive) | Log (`9b/browser.log`, operational record retained in the development archive) | Log (`27b/browser.log`, operational record retained in the development archive) |
| Server log | Log (`2b/server.log`, operational record retained in the development archive) | Log (`9b/server.log`, operational record retained in the development archive) | Log (`27b/server.log`, operational record retained in the development archive) |
| Source manifest | [JSON](2b/source-manifest.json) | [JSON](9b/source-manifest.json) | [JSON](27b/source-manifest.json) |
| Transfer record | [JSON](2b/transfer.json) | [JSON](9b/transfer.json) | [JSON](27b/transfer.json) |

Each transfer record contains source paths, capture time, file sizes, remote
hashes before/after reading, and hashes of local bytes. All eight files per model
matched: 1,608,654 bytes for 2B, 1,608,982 bytes for 9B, and 1,616,071 bytes for
27B. The root suite manifest is retained both in the earlier running snapshots
and as a separate completed final manifest; no snapshot was overwritten. The
2B and 9B original files and audit records were not changed when 27B was added.
The three models' `requests.jsonl` and `references.jsonl` files are byte-identical.

The standalone standard-library audit scripts for [2B](2b/audit.py),
[9B](9b/audit.py), and [27B](27b/audit.py) import no evaluator, adapter, teacher,
HTTP client, model, or training library. Each independently
recreates the ID-based selection; validates all wire/request/source/selection
hashes and response bytes; checks all Choice probabilities, selected options,
derived confidence fields and service identities; reconstructs reference and
predicted proposals; and recomputes row scores, every denominator, aggregates,
the operation confusion table, and constant baselines.
The [2B audit](2b/audit.json) and [9B audit](9b/audit.json) each record
**7,737 passed checks, zero errors** and the per-case recomputation. The
[27B audit](27b/audit.json) records **7,746 passed checks, zero errors**, including
nine additional checks on the completed suite manifest and all three archived
model identities. Run them from a checkout containing the frozen browser data
and the recorded Git commit:

```bash
python reports/pilot-browser-n1/2b/audit.py
python reports/pilot-browser-n1/9b/audit.py
python reports/pilot-browser-n1/27b/audit.py
```

Copying and auditing these completed artifacts performed no additional model
inference, GPU allocation, or training-data modification. Subsequent training
must use a separately versioned corpus and retain these pilot results,
including the 2B result below the constant BLOCKED baseline.
