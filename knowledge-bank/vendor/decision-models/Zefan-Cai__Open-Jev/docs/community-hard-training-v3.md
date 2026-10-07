# Broader community data and the next 27B stage

The [additional source review](community-research-broadening-20260921.md) verified
12 task families or protocol gaps using 20 primary code/cookbook sources and 17
public X post readbacks. The next bounded training stage covers natural intent
routing, executable SQL decisions, approval policies and CMS tagging. It does not
claim to implement every discovered community workflow. No benchmark question,
answer, model error or hosted teacher response was used to generate these data.

## Frozen sources

| Component | All new decision rows | Training rows |
| --- | ---: | ---: |
| [BANKING77 and CLINC150 routing](community-routing-v3.md) | 108,720 | 63,809 |
| [Original SQL business semantics](sql-semantics-v3.md) | 12,288 | 6,144 |
| [Original approval and CMS controls](community-workflow-v3.md) | 8,280 | 4,968 |
| New-source total | **129,288** | **74,921** |
| Earlier v2 training replay | — | 21,928 |
| Final training mixture | — | **96,849** |

Routing preserves published human labels and raw text: 36,640 retained catalog
utterances, or 36,632 normalized groups across two datasets. It provides bounded
2/4/8-option Choice, explicit abstention when the correct handler is absent, and
one Noul per utterance. These correlated views are not independent examples or
full-catalog classification results. The separately prepared 77/151-option
protocols remain unmeasured. BANKING77 is CC BY 4.0; CLINC150 is CC BY 3.0, with
original attribution retained. Public official-test/validation groups are reserved
before assigning any training rows.

SQL uses 6,144 original complete databases and twelve business operators. All
48,128 candidate executions were independently replayed against visible-input
business calculations. Multiple SQL candidates that return the requested answer
share target mass. Request counterfactuals change the desired metric over the same
database; they are not additional independently collected databases.

Approval and CMS have twenty authored rule cards, 360 semantic scenarios and
2,520 semantic contexts. CMS uses eighteen distinct secondary-claim combinations
per card, including supported, denied, unknown and conflicting evidence. Cosmetic
paragraph/prefix changes are excluded from semantic diversity counts. A portable
independent parser uses the declared phrase vocabulary, not generator oracles or
metadata, to verify labels. This is a finite English prose grammar, not natural
production logs. Both original synthetic sources are CC0-1.0.

The CMS Choice distribution is intentionally reported: 840 review, 220 apply and
20 untagged. A constant review prediction reaches 77.8% on that entire source's
Choice rows. The paired evaluation therefore also reports Noul class recalls,
balanced accuracy and an always-no reference. Raw accuracy alone is insufficient.
The mixture contains no app-review text with the unresolved source license.

Replay selects at most 300 existing training rows per source using a deterministic
round robin over parent groups, without oversampling. These are source IDs, not
domain counts. All previous held-out splits remain held out. The resulting dataset
has 331,249 rows: 96,849 train, 37,284 calibration, 36,135 validation, 70,378 test
and 90,603 OOD. A [frozen manifest](../reports/community-diversity-v3/training-mixture-manifest.json)
binds every input/output checksum. Independent integration and lexical-overlap
reports are provided with the [iteration evidence](../reports/community-diversity-v3/).
Lexical checks do not establish semantic or pretraining decontamination.

## Predeclared training and comparisons

The [fixed policy](../reports/community-diversity-v3/training-plan.json) precedes
new model results. The finite queue waits for the complete v2 37,160-step stage,
its calibration/reload checks, all 231 public JevBench requests and owned-process
cleanup. It then initializes a new Qwen3.8-27B stage from that final LoRA/head
snapshot, with a fresh optimizer, random streams and cursor. The old stopped
supervisors are not restarted. Only N1-1 physical H100 GPUs 0–3 are allowed.

The new run has 24,213 steps, global batch four, rank-eight LoRA, adapter/head
learning rates 1e-5 / 2e-5, Brier weight 0.1, context limit 4,096 and training seed
20260922. It is one shuffled pass, wrapping three rows to complete the final batch.
Complete snapshots are saved every 500 steps; there are no automatic retries.
Calibration/test/OOD sampling uses 512 rows per split. Only calibration fits
probability temperature. The predeclared final checkpoint is the reported model;
no benchmark score selects a checkpoint or changes the queued training recipe.

An additional [fixed new-task panel](../reports/community-diversity-v3/focus-panel-manifest.json)
contains 128 rows per source and test/OOD split: 1,280 rows over five source IDs,
840 distinct groups and 440 additional correlated views. Its selection depends
on source hashes and IDs, never predictions or labels. The paired evaluator runs
both completed v2-final and v3-final checkpoints on the same panel, with saved
temperatures, cache off and candidate batches of four. It retains errors, missing
rows and complete denominators, reports soft-target positive-set hits separately
from hard-label accuracy, and accepts unchanged checkpoint contents as a valid
negative result. Both checkpoints use the same pinned 27B base revision.
Row-weighted and equal-group accuracy are both reported; the
[internal evaluation guide](internal-evaluation.md) explains split roles,
correlated views, calibration and the limits of shared generation rules.

Finally, the v3 final checkpoint runs the same 231 pinned public JevBench tasks
once, using the established adapter and 16,384-token evaluation limit. Existing
hosted Jev/GPT calls are not repeated. This is not the private 534-task leaderboard.
Improvements, regressions and unchanged results require a separate postrun audit;
preparing data or a queued job does not establish a gain. A combined-data stage
cannot identify the contribution of any one source without further ablations.

## Reproduce

```bash
python -m jev.community_routing_v3 --source-dir runs/community-diversity-v3/source --output-dir data/community-routing-v3
python -m jev.sql_semantics_v3 --output-dir data/sql-semantics-v3
python -m jev.community_workflow_v3 --output-dir data/community-workflow-v3
python -m scripts.build_community_hard_mix \
  --new-inputs data/community-routing-v3 data/sql-semantics-v3 data/community-workflow-v3 \
  --replay-inputs data/community-hard-mix-v2-final --replay-cap 300 \
  --version community-hard-mix-v3 --output data/community-hard-mix-v3-final
python -m scripts.evaluate_community_pair build-panel \
  --data data/community-routing-v3 --data data/sql-semantics-v3 \
  --data data/community-workflow-v3 --output runs/community-diversity-v3/focus-panel
```

Use the pinned raw files and independent audit commands in each source document.
Outputs must be new directories. The panel and all five splits are checked before
inference. GPU queue state is operational evidence, separate from this immutable
recipe and from measured model quality.
