# How internal evaluation works

Internal evaluation uses held-out rows, not the rows consumed by the fine-tuning optimizer. Related views of the same source scenario stay in one split. These checks establish separation within our prepared datasets; they do not establish that the foundation model never encountered similar material during pretraining or that every semantic paraphrase has been excluded.

## Completed 27B v1.1 full evaluation

The [complete internal audit](internal-full-evaluation.md) passed for all **127,787** expanded Test/OOD rows, with zero failed, missing or duplicate predictions. It reports four distinct panels: Old Test (10,532 rows), Old OOD (15,920), Expanded Test (43,301), and Expanded OOD (84,486). Old rows are content-identical subsets of expanded rows, so the panels overlap. Hard accuracy excludes soft targets; probability metrics include every row.

The audited 27B uses its saved calibration temperature, a 4,096-token limit without truncation, row batch size one and cache off. The old 512-row trainer diagnostics below are separate sampled comparisons. The V2–V3 focus panel and group-macro reporting described below are prepared protocols, not completed v1.1 measurements. New 2B training stopped and new 9B training did not start.

## Trainer evaluation and training loss

The current four-rank, final-checkpoint recipe separates the following roles:

| Data | Current use |
| --- | --- |
| `train` | Update LoRA and the decision head. V3 is configured for one pass over all 96,849 selected training rows, with three wrapped tail rows to fill its final batch of four. |
| `calibration` | Select 512 fixed rows and fit a scalar temperature after training; no optimizer updates use these rows. |
| `test` | Select 512 fixed rows for initialization-versus-final evaluation. |
| `ood` | Select 512 fixed rows for the corresponding source-defined OOD comparison. |
| `validation` | Reserved and included in integrity checks. This final-only recipe does not use it for training, temperature fitting or checkpoint selection. |

The 512-row selections are deterministic for the run seed, using round-robin source/kind buckets after shuffling. Their exact IDs and dataset hashes are saved in `run.json` and the training identity. They are subsets of the prepared split files, not evaluations over all prepared test/OOD rows. Initialization and final weights are evaluated on the same held-out rows to make their comparison meaningful. Each has a temperature fitted on the same calibration rows, and calibrated and uncalibrated metrics are retained. These calibration fits do not update the LoRA or head weights.

Training loss is a different measurement: the four-rank mean of target-distribution negative log likelihood plus 0.1 times Brier loss on the current **training** batch. A lower training loss shows a better fit to training examples; it is not a held-out accuracy score. Saved optimizer snapshots every 500 steps support reproducibility. The predeclared final checkpoint supplies evaluation results; test or benchmark scores do not choose a snapshot. Final completion also requires a successful checkpoint save/reload check.

## Fixed V2–V3 focus comparison

The additional focus panel contains **1,280 held-out rows from 840 source groups**. Each of five sources contributes 128 test and 128 OOD rows: BANKING77 routing, CLINC150 routing, SQL semantics, approval controls and CMS controls. These five source IDs represent two human-labeled routing datasets plus authored SQL/approval/CMS controls, not five independently collected natural datasets.

The panel was frozen before inference and selected by hash-ordered group round robin. Routing and SQL contribute 128 groups per source/split. Approval and CMS each have 18 groups per source/split, so their 128 rows include related views and counterfactuals. Across the panel, **440 rows are additional views beyond the first row of a group**. They are not 440 additional independent scenarios.

V2-final and V3-final run on exactly this same panel. The evaluator verifies both completed training identities, all five split hashes, saved calibration IDs, saved calibration predictions and temperatures. It applies each checkpoint's existing temperature rather than fitting a new one on the panel. The panel must not overlap either model's training, calibration or validation data by row ID, group ID or canonical model input, including candidate permutations. Source and checkpoint hashes are checked again after inference.

The focus panel can overlap the trainer's 512-row **test/OOD** selections because both are drawn from those held-out files. Such overlap is repeated evaluation of held-out cases; it is not optimizer training on test cases. The panel is an additional reporting view of the prepared holdouts, not an independent external dataset.

## Row accuracy and equal group weighting

The paired evaluator reports both ordinary row-weighted metrics and `group_macro` metrics overall and within each source/split/task-kind bucket:

- **Positive-set accuracy:** a prediction is correct when its highest-probability candidate has positive target mass. This includes SQL rows with several answer-equivalent candidates.
- **Hard-label accuracy:** only rows with a unique one-hot gold target contribute. Soft-target rows are excluded and counted explicitly.
- **Group-macro accuracy:** first compute the appropriate accuracy within each `(source, group_id)`, then average those group accuracies with equal group weight. A group with ten views contributes the same weight as a group with one view. Hard-label group accuracy uses only that group's hard-label rows; groups without any hard-label rows are excluded from that metric, with their count reported.

Errors and missing predictions remain incorrect in the row and group denominators. For example, if a four-view group is entirely correct and a one-view group fails, row accuracy is 4/5 while group-macro accuracy is 1/2. Group-macro averages groups; it does not give each source an additional equal weight. Per-source results remain available for inspecting that distinction.

The report preserves attempted, pending, error and valid-vector counts. Probability-distribution metrics are calculated only where valid vectors exist and are labeled with their coverage; failed calls do not receive invented probabilities. Noul-only buckets additionally expose class counts, sensitivity, specificity, balanced accuracy and an always-no reference so that label imbalance is visible.

## What split isolation can and cannot establish

The frozen V3 integration audit verifies unchanged source rows, all 74,921 new training rows, 21,928 replay rows capped at 300 per old training source, unique row IDs and globally disjoint source groups. It also verifies the focus panel's source bindings and its exclusion from source training/calibration/validation. See the [integration audit](../reports/community-diversity-v3/integration-audit.json) and [training policy](../reports/community-diversity-v3/training-plan.json).

Internal test/OOD data often share a dataset or generation grammar with training. BANKING77/CLINC preserve official heldouts; their additional OOD split holds out source-training utterance groups within the same catalogs. SQL holds out authored layout combinations, while approval/CMS hold out whole rule cards within a finite reporting grammar. Those controls measure the specified transfer; the `ood` filename alone does not demonstrate unrestricted generalization to new real-world domains.

The **231 pinned public JevBench tasks** are a separate external comparison, evaluated after final completion using their own documented protocol. They are not training examples, calibration rows or checkpoint-selection criteria in this recipe. This is the available public subset, not a claim to evaluate all 534 JevBench tasks. External results and internal results should be reported separately with their own denominators. See the [JevBench protocol and limitations](jevbench-public.md).

Prepared-data counts and planned group-macro reporting do not establish a model-quality result. The completed v1.1 measurements are the audited full internal and public JevBench results linked above; future checkpoints require their own completed runs and independent audits.
