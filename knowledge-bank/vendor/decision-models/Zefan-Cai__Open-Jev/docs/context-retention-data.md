# Original tool-history retention controls

`context-retention-control-v1` contains **400 task groups, 1,200 request cases
and 9,834 unique Noul records**. It is original CPU-generated data under a
declared retention policy, with no model inference or training. Existing
release-v2, browser/drone expansion, active training checkouts and JF100 were
not changed or used to build it.

This corpus follows the interface shape of
[`fast-jev-compaction`](https://github.com/tamaratran/fast-jev-compaction/blob/e3f262a7f4d42bd8dd32ced30d26176f7cb545b0/src/compact.ts#L55):
one shared history, two Noul questions for each eligible completed tool call.
Its source commit is `e3f262a7f4d42bd8dd32ced30d26176f7cb545b0`.
The task instances, grammar, hard labels and fixed policy are Open-Jev's own;
they do not reproduce Jev's hidden training method or arbitrary session-level
judgment. No upstream demonstration transcript or model answer was copied.

## What the model sees

Every request has exactly `state = {context, goal, history}`. The context states
the complete local retention policy. `goal` names the current work item. History
entries have `i`, `role`, `text` and optional `tool_calls`, whose fields are
`id`, `tool`, stringified `input`, and an outcome/length `result` note such as
`ok, 281 chars (omitted)`. **The full tool output is not in the model input.**

Each non-pinned completed call has `call_<id>` and `result_<id>` Nouls:

- Keep the call record/input if its work item is the current goal or a
  recursively required prerequisite.
- Keep its full output only when the needed work item requires exact result
  content, and the earlier result cannot be read from an archive or recreated
  exactly by re-running the call.

The visible register states dependencies, evidence requirements and whether
the earlier output was archived, can be exactly reproduced, came from an
overwritten input, or was a transient sample without another copy. Those facts
determine the labels. Error/success notes do not override this explicit policy.
The raw output's hidden contents and the auxiliary generator specification
cannot decide a label.

For example, suppose the current deliverable depends on an earlier inspection
and needs its exact output. If the original input has since been overwritten
and no external copy exists, both Nouls are yes. If the exact output has been
archived, keep the call record but not the full output in history. If a changed
goal no longer depends on that inspection, both Nouls are no. The model does
not have to infer an unstated retention preference.

The [complete generated example](../reports/context-retention-control-v1/example.json)
includes the actual request, hard reference decisions and software gates. Every
training row is compiled with `compile_request`; only `state`, `question`,
`kind` and `options` enter model prompts. Targets are `[no, yes]` hard labels,
not model confidences or claimed real-world uncertainty.

## Diversity and split boundary

Each task graph has three grouped variants: its initial current goal, a
different current goal, and changed output recoverability. Calls are shuffled
independently of the graph/task order and use dynamic IDs. Six original tool
names and multiple coding-task descriptions accompany three to five eligible
calls, yielding six to ten semantic questions per request.

The 320 ID groups use star or chain dependencies and two controlled writing
forms. The 80 OOD groups reserve a **diamond graph with a shared prerequisite**
and a separate dependency/evidence writing form. OOD therefore includes an
unseen graph structure as well as wording. It still uses the same declared
policy and small synthetic task world. These are 400 parameterized examples
from a finite grammar, not 400 unrelated real user sessions; no multilingual
or arbitrary agent-compaction competence is implied.

| Split | Whole task groups | Noul records |
| --- | ---: | ---: |
| Train | 255 | 6,138 |
| Calibration | 21 | 456 |
| Validation | 24 | 558 |
| Test | 20 | 522 |
| OOD | 80 | 2,160 |
| Total | 400 | 9,834 |

All goal/recoverability counterfactuals, calls and questions from one graph
share one `group_id` and split. ID splitting uses the existing deterministic
group hash with seed 942. There are no duplicate model inputs in this build.

There are 2,958 yes / 1,959 no call-retention labels and 923 yes / 3,994 no
full-result labels. Applying the declared code mapping gives 923 keep-pair,
2,035 retain-call/truncate-result and 1,959 drop-pair decisions. These are
reference-data counts, not learned model outcomes or measured compression.

## Software gates are separate

The first message and last six messages are pinned by code. A call without a
matching result is preserved as pending and not sent for semantic judgment.
Each generated case has two pinned completed calls and one unmatched call:
**2,400 pinned and 1,200 pending gate instances**, across the 1,200 variants.
They remain in `cases.jsonl` as software controls without probabilities or
training rows. Case variants do not make these 3,600 independent histories.

The raw synthetic source messages are auxiliary evidence for gate and
output-omission checks. No real account, code session, private conversation or
external tool output is used. This addition supplies a request builder and
reference data; it does not replace a coding agent's live compaction mechanism.

## Reproduce and verify

Use a new empty directory; generation refuses to overwrite existing data or a
symlink destination. No GPU, model weights, network call or optional training
library is needed.

```bash
python -m jev.context_retention_data \
  --output-dir data/context-retention-control-v1 \
  --groups 400 --ood-groups 80 --seed 942
python -m jev.data validate data/context-retention-control-v1
python reports/context-retention-control-v1/verify.py \
  --data data/context-retention-control-v1 \
  --output runs/context-retention-audit.json
python -m unittest discover -s tests -p test_context_retention_data.py -v
```

The [manifest](../reports/context-retention-control-v1/manifest.json) records
source and output hashes. The [independent verifier](../reports/context-retention-control-v1/verify.py)
does not import the generator. It parses the final visible register, computes
graph closure, rederives labels, reconstructs the output-omitting history from
synthetic source messages, and checks exact question coverage and software
gates. It ignores `auxiliary_spec` and the output contents. Changing hidden
outputs to same-length unrelated text must leave labels valid; changing the
visible goal, policy, matched reference/target, call/result pairing, or adding
probabilities to a software gate must fail the relevant audit.

The [full audit](../reports/context-retention-control-v1/independent-audit.json)
passed all 9,834 rows. Eleven focused tests and ordinary schema validation
passed. A temporary one-source `mix_data` round trip preserved every row and
split count; it read only this new corpus. The
[build record](../reports/context-retention-control-v1/build-verification.json)
records those checks. No tokenizer-length or GPU preflight has been performed.

Before claiming useful learned compaction, evaluate false deletion of required
evidence, exact retained dependency sets, byte reduction and downstream task
completion on a separate corpus. A smaller retained history alone does not
prove preserved utility. Generated original data is CC0-1.0; project code keeps
the repository license and the source interface documentation keeps its terms.
