# Customer support: source-inspired multi-question control

This dataset addresses the **customer-support fan-out case**. It is not the original launch demo's private dataset or complete query. The [launch post](https://x.com/CompleteSkeptic/status/2099925682726002904) links a [shared playground](https://console.typesafe.ai/playground?share=shr_13a74b495fb786c4bd7964f11597301e7c9) that redirects anonymous access to login. Source research could confirm the name **Churn likelihood level**, but not its complete instructions or criteria.

The five fully inspectable question forms instead come from the official [Speculative fan-out: support ticket triage](https://docs.typesafe.ai/patterns/fan-out.md) example. Their names, types, category identifiers, and score descriptions are retained. Instructions include additional operational rules for this local controlled experiment. A sixth, locally defined ordinal churn-intention question uses the name confirmed in the post. Its type, three criteria, and labeling rubric are our design.

| Question | Type | Source relationship |
| --- | --- | --- |
| `category` | Choice: bug_report, billing, feature_request, account | Official public fan-out form; explicit-priority/tie rule added locally. |
| `bug_severity` | Score: cosmetic; workaround available; blocking without workaround | Official public form; unknown-workaround distribution and no-malfunction handling added locally. |
| `has_reproducible_steps` | Noul | Official public form; two ordered actions plus observed outcome required locally. |
| `refund_requested` | Noul | Official public form; current explicit requests distinguished from negations and historical refunds. |
| `frustration` | Score: calm; frustrated but civil; very angry | Official public form; controlled ambiguous-tone treatment added locally. |
| `churn_likelihood_level` | Score: continue; conditional/undecided; definite cancellation | Only the question name is confirmed from the post. Rubric is local and is **not** an empirically calibrated churn forecast. |

Each original conversation yields all six questions together. State is a natural-language customer/agent exchange with payment, access, feature, or malfunction details, expressed emotion, and renewal intent. Roughly 15% of conversations contain a short Chinese customer follow-up. These Chinese lines supply account/context information; they do not constitute a Chinese-language task benchmark. Machine label fields and latent variables are stored only in metadata and never inserted into state or model prompts.

Conversations and labels are **synthetic controls, not official annotations**. The generator samples task variables, realizes their observations as conversation text, and calculates labels from the specified rules. It includes direct requests, negative refund requests, historical refunds, concrete versus missing reproduction steps, competing priorities, conditional renewal intent, and incomplete information. Independently scored candidates have self-contained descriptions; no score level relies on another candidate being visible.

Ambiguous targets are exact marginals in a deliberately defined finite latent experiment:

- Two expressly equal-priority issues yield equal category mass on those two categories.
- An explicitly unknown workaround yields equal mass on severity levels 1 and 2.
- Two specified ambiguous reaction phrases have equally likely calm/civil-frustration readings under the synthetic generator.
- Withheld continuation intent has equal prior mass on the three local intention levels.

These distributions are not estimated human agreement, real customer behavior, or model-generated confidence. The task instructions expose the synthetic interpretation rules. All other labels are hard one-hot targets. Metadata includes the sampled control variables, per-question source relationship, and `annotation_status=synthetic_control_not_official_labels` for auditing.

For the default 1,000-group, seed-42 build, Choice has 900 hard and 100 soft records; Noul has 2,000 hard records; Score has 2,725 hard and 275 soft records. Noul is imbalanced (1,701 no; 299 yes), and bug severity often defaults to no functional impact because the fan-out request includes speculative questions even for non-bug tickets. Report metrics per question and, separately, on the relevant workflow subset (bug questions where `bug_report` occurs among metadata control categories; refund where `billing` occurs). Overall accuracy alone is insufficient. The delivered `target-statistics.json` includes hard class counts and total probability mass by primitive and question for this build.

## Build and use

```bash
python -m jev.case_customer --output-dir data/case-customer --groups 1000 --seed 42
python -m unittest discover -s tests -p 'test_case_customer.py'
```

`groups` counts original conversations, including the OOD groups. The default produces 1,000 workflows and 6,000 question records. Every tenth conversation is assigned to OOD before any label generation; the remaining groups use the existing deterministic 80/5/5/10 train/calibration/validation/test hash split. All questions from a conversation share one split. OOD has disjoint dialogue envelopes, complete utterance banks, and account namespaces. It tests controlled rephrasing and entity transfer; the task definitions and logical rubric stay fixed.

The five named split JSONL files use the existing dataset schema and pass `validate_records`. Since the shared validator restricts synthetic `family` to its original vocabulary, these records use routing/rubric/evidence by primitive and additionally carry `case_name=customer_support_fanout_control` and `question_id` for accurate reporting. Report results by this case and each of its six questions.

`workflow_cases.jsonl` contains `{group_id, split, state, questions, targets}`. Send **only `state` and `questions`** to `compile_request` or the prediction API. Each `targets[question_id]` vector follows the option order produced by compiling that workflow; Choice criteria insertion order is intentionally preserved in this file. Targets and group/split identifiers are evaluation data, not request contents. `manifest.json` records split counts and checksums for both representations.

The auxiliary workflow file intentionally has a different schema. `python -m jev.data validate data/case-customer` reads only the five named split files and ignores this auxiliary file. The mixing CLI likewise reads exactly those five split files. The builder validates all ordinary records before writing. A counterfactual test holds observed conversation text constant while changing each allowed hidden severity, frustration, or continuation-intent world; the full target distribution stays identical in every such case.

The public documentation's downstream example routes bug reports to engineering only when severity exceeds 1.5 and reproduction exceeds 0.6; otherwise it uses a bug backlog. Billing is flagged when refund probability exceeds 0.7, feature requests are logged, and frustration above 1.5 triggers a priority flag. Its account branch is not implemented. This dataset does not invent an official account-routing branch or claim that these synthetic targets reproduce an official model's outputs.

Generated conversations are released as CC0-1.0. Question descriptions are attributed to the TypeSafe documentation; its upstream license was not independently verified. This is a task and mechanics experiment; it does not establish performance on real support logs or real retention outcomes.
