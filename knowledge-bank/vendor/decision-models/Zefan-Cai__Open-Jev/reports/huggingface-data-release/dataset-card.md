---
license: cc0-1.0
language:
  - en
  - zh
task_categories:
  - text-classification
tags:
  - open-jev
  - synthetic
  - typed-decisions
  - probability-estimation
  - control
size_categories:
  - 100K<n<1M
configs:
  - config_name: release-v2-redistributable
    default: true
    data_files:
      - split: train
        path: data/release-v2-redistributable/train-*.parquet
      - split: calibration
        path: data/release-v2-redistributable/calibration-*.parquet
      - split: validation
        path: data/release-v2-redistributable/validation-*.parquet
      - split: test
        path: data/release-v2-redistributable/test-*.parquet
      - split: ood
        path: data/release-v2-redistributable/ood-*.parquet
  - config_name: browser-drone-expansion-v1-redistributable
    data_files:
      - split: train
        path: data/browser-drone-expansion-v1-redistributable/train-*.parquet
      - split: calibration
        path: data/browser-drone-expansion-v1-redistributable/calibration-*.parquet
      - split: validation
        path: data/browser-drone-expansion-v1-redistributable/validation-*.parquet
      - split: test
        path: data/browser-drone-expansion-v1-redistributable/test-*.parquet
      - split: ood
        path: data/browser-drone-expansion-v1-redistributable/ood-*.parquet
  - config_name: citation-control-v1
    data_files:
      - split: train
        path: data/citation-control-v1/train-*.parquet
      - split: calibration
        path: data/citation-control-v1/calibration-*.parquet
      - split: validation
        path: data/citation-control-v1/validation-*.parquet
      - split: test
        path: data/citation-control-v1/test-*.parquet
      - split: ood
        path: data/citation-control-v1/ood-*.parquet
  - config_name: entity-alignment-control-v1
    data_files:
      - split: train
        path: data/entity-alignment-control-v1/train-*.parquet
      - split: calibration
        path: data/entity-alignment-control-v1/calibration-*.parquet
      - split: validation
        path: data/entity-alignment-control-v1/validation-*.parquet
      - split: test
        path: data/entity-alignment-control-v1/test-*.parquet
      - split: ood
        path: data/entity-alignment-control-v1/ood-*.parquet
  - config_name: amount-extraction-control-v1
    data_files:
      - split: train
        path: data/amount-extraction-control-v1/train-*.parquet
      - split: calibration
        path: data/amount-extraction-control-v1/calibration-*.parquet
      - split: validation
        path: data/amount-extraction-control-v1/validation-*.parquet
      - split: test
        path: data/amount-extraction-control-v1/test-*.parquet
      - split: ood
        path: data/amount-extraction-control-v1/ood-*.parquet
  - config_name: email-selection-control-v1
    data_files:
      - split: train
        path: data/email-selection-control-v1/train-*.parquet
      - split: calibration
        path: data/email-selection-control-v1/calibration-*.parquet
      - split: validation
        path: data/email-selection-control-v1/validation-*.parquet
      - split: test
        path: data/email-selection-control-v1/test-*.parquet
      - split: ood
        path: data/email-selection-control-v1/ood-*.parquet
  - config_name: phone-extraction-control-v1
    data_files:
      - split: train
        path: data/phone-extraction-control-v1/train-*.parquet
      - split: calibration
        path: data/phone-extraction-control-v1/calibration-*.parquet
      - split: validation
        path: data/phone-extraction-control-v1/validation-*.parquet
      - split: test
        path: data/phone-extraction-control-v1/test-*.parquet
      - split: ood
        path: data/phone-extraction-control-v1/ood-*.parquet
---

# Open-Jev: typed decision datasets

Open-Jev turns a state and a question into a typed decision: a yes/no probability, a distribution over choices, independent label probabilities, or a discrete numeric/ordinal decision. This repository publishes seven separate, frozen data configs from the [Open-Jev project](https://github.com/Zefan-Cai/Open-Jev-Dev), together with original manifests, exact raw records, source code and reconstruction instructions.

These are controlled, mostly synthetic tasks and reference labels. They are not official TypeSafe/Jev training data, model predictions, or evidence of general capability. Open-Jev is independently implemented and is not affiliated with TypeSafe.

## Configs and exact split counts

| Config | Train | Calibration | Validation | Test | OOD | Total |
|---|---:|---:|---:|---:|---:|---:|
| `release-v2-redistributable` | 79,116 | 4,672 | 3,723 | 10,356 | 15,701 | 113,568 |
| `browser-drone-expansion-v1-redistributable` | 108,624 | 6,794 | 5,493 | 14,726 | 25,160 | 160,797 |
| `citation-control-v1` | 2,520 | 200 | 180 | 300 | 800 | 4,000 |
| `entity-alignment-control-v1` | 6,944 | 728 | 280 | 1,008 | 2,240 | 11,200 |
| `amount-extraction-control-v1` | 32,984 | 2,232 | 992 | 3,472 | 9,920 | 49,600 |
| `email-selection-control-v1` | 3,618 | 81 | 189 | 432 | 1,080 | 5,400 |
| `phone-extraction-control-v1` | 12,350 | 855 | 380 | 1,615 | 3,800 | 19,000 |

**The configs overlap.** `release-v2-redistributable` is contained in `browser-drone-expansion-v1-redistributable`; do not add config totals and call them unique examples. Counts are typed decision rows. Several heads may come from the same conversation, document, family or game trajectory.

The original frozen `release-v2` used to train the 2B/9B models has **80,816 training rows** and **115,821 rows across all splits**. The public projection above is not that exact training dataset. Each of the two composite configs excludes exactly **2,253 Wikispeedia rows**: 1,700 train, 89 calibration, 69 validation, 176 test and 219 OOD. The original expansion mixture has 163,050 rows, including 110,324 train. Original manifests and hashes are preserved without modification; [REPRODUCTION.md](REPRODUCTION.md) explains how to restore both exact original mixtures with separately obtained source data.

The five citation/entity/amount/email/phone corpora were prepared and audited after those 2B/9B runs. **They have not been used for training or actual model inference at the time of this release.** The expansion mixture belongs to a separate 27B experiment; this dataset publication makes no completed-training or performance claim for that experiment.

## Load and decode

```python
import json
from datasets import load_dataset

ds = load_dataset("ZefanCai/Open-Jev", "release-v2-redistributable")
example = ds["train"][0]
state = json.loads(example["state_json"])
metadata = json.loads(example["metadata_json"])
original_record = json.loads(example["record_json"])
```

For reproducibility, pass `revision="<dataset commit SHA>"`. Choose a config explicitly; loading the default does not include the five newly prepared corpora.

| Column | Meaning |
|---|---|
| `id`, `group_id`, `split`, `source` | Original identity, grouping, split and generator/source version. |
| `kind` | Original decision type; interpret with the source task definition. |
| `question`, `options` | Model-visible question and ordered answer space. |
| `target` | Original numeric reference targets, represented as a float64 list. These are labels, not measured model confidence. |
| `state_json` | JSON encoding of the original state. Decoding returns a string or structured object, depending on the source. |
| `metadata_json` | Original provenance and audit metadata. It can include privileged teacher/control labels and must not be used as model input. |
| `record_json` | Complete original JSON record, retaining original object key order and numeric representation. |
| `original_line_number` | One-based row position in the original frozen split, including positions of excluded rows. |

The Parquet representation avoids imposing one nested schema on different task states. `raw/<config>/<split>.jsonl.gz` preserves the source JSONL bytes after decompression. For the filtered composites, retained lines preserve exact bytes and order. For the five other configs, decompressed files match the original frozen split hashes exactly.

Use only `state`, `question`, `kind` and `options` as model inputs. Do not expose `target`, `metadata`, identities, split assignments or provenance fields to the model. Distribution, binary, multilabel and ordinal targets have different semantics; do not reduce every row to a single-class accuracy calculation.

## Domains and construction

- The base release covers controlled customer-support routing and triage; local workflow decisions; geometric painting probability requests; Snake and tic-tac-toe; simplified T-Rex/runner and platformer controls; numeric ViZDoom Basic trajectories; and controlled reasoning decisions.
- The expansion additionally includes controlled browser state/action and drone state/control examples. These represent the declared simulated task forms, not unrestricted browser use or real aircraft operation.
- Citation data uses original policy documents, quotes, visible facts and claims, with supported/contradicted/insufficient decisions. It tests those controlled relations, not arbitrary factual verification.
- Entity alignment uses original catalog families, records, aliases and visible matching policies with multiple decision heads.
- Amount, email and phone extraction separate deterministic candidate generation from typed selection/attribute decisions. Known candidate misses and partial matches are retained rather than replaced using gold answers. Conditional attribute heads and omitted-supervision counts are documented in the original manifests.

The new corpora include compressed documents/families/cases in `artifacts/`. These are reproduction/audit artifacts, not additional typed rows to add to the totals. Citation has 200 documents and 4,400 cases: 4,000 typed semantic cases plus 400 quote-not-found controls. Entity alignment has 200 families and 2,800 cases; amount has 200 families and 3,200 documents; email has 200 families and 2,800 documents; phone has 200 families and 4,000 documents.

Original data and split policies are recorded per corpus in `provenance/original-manifests/`. Related documents/entities/trajectories remain grouped within splits. OOD is source-specific, commonly reserved wording, layouts, control families or goals, and is not a universal unseen-domain benchmark. Local export verification checks unique IDs and cross-split group separation within each config.

## Evaluation boundaries

Train, calibration, validation, test and OOD are published separately. Train on the train split; use calibration only for the declared calibration procedure and validation for model selection. Test/OOD labels are public, so future work must disclose any use of them for development. Scores measured on the original full frozen mixtures must not be described as scores on these smaller public projections without recomputation.

No Jev Frontier 100 question/answer payload is included. The external [jev-frontier-100 benchmark](https://github.com/softpudding/jev-frontier-100) remains separate from training and generation. No official private examples, game ROMs, game assets, model weights or credentials are included.

## Licensing and provenance

Original generated records are marked **CC0-1.0** in their existing provenance. This dedication covers our generated content, not upstream wording, external assets, source data or model weights. Original source code is **MIT**. Customer-control provenance retains its original note that short upstream question descriptions come from TypeSafe documentation without a verified source license; this release does not relicense those descriptions. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

The [Wikispeedia archive](https://snap.stanford.edu/data/wikispeedia.html) does not declare a verified separate graph/path redistribution license. Therefore its task rows are excluded from the two public mixture projections. We do not infer that a current Wikipedia license covers the archived graph/path dataset. We publish its original manifest, source URL, archive SHA-256, exact exclusion positions and a local reconstruction utility, not its graph, paths or task payload.

Wikispeedia references:

- West and Leskovec. *Human Wayfinding in Information Networks.* WWW 2012.
- West, Pineau and Precup. *Wikispeedia: An Online Game for Inferring Semantic Distances between Concepts.* IJCAI 2009.

`export-manifest.json` records original and public split counts/hashes, source counts, exclusion positions, source-code fingerprints and published file hashes. [REPRODUCTION.md](REPRODUCTION.md) documents exact restoration and generator commands. The dataset repository's Git commit pins this complete release.
