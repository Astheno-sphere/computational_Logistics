# Human-labeled routing v3

This preparation converts two pinned, human-labeled intent datasets into bounded Open-Jev routing decisions: BANKING77 banking support and CLINC150 assistant requests. It adds **108,720 decision rows from 36,640 retained catalog utterances**, corresponding to **36,632 normalized utterance groups** shared globally across splits. The 77 and 150 intent labels are candidate catalogs within **two datasets**; they are not 151 independently collected domains.

The data are prepared and audited only. No model was trained or evaluated by this converter, no provider requests were sent, and no model improvement is claimed. The deployed v2 training source and its datasets remain unchanged.

## Source labels and attribution

| Dataset | Pinned repository revision | Original rows | License |
| --- | --- | ---: | --- |
| BANKING77 | [PolyAI-LDN/task-specific-datasets at 57ec275](https://github.com/PolyAI-LDN/task-specific-datasets/tree/57ec275d8078af65b7731c2a98be812d844a6d6b) | 10,003 train; 3,080 test | CC-BY-4.0 |
| CLINC150 | [clinc/oos-eval at 828f809](https://github.com/clinc/oos-eval/tree/828f8093932c8fe6ca7936c3d2e52903b1c523de) | 15,000 train; 3,000 validation; 4,500 test; 100/100/1,000 corresponding out-of-scope rows | CC-BY-3.0 |

BANKING77 attribution: Casanueva et al. (2020), *Efficient Intent Detection with Dual Sentence Encoders*, PolyAI BANKING77. CLINC150 attribution: Larson et al. (2019), *An Evaluation Dataset for Intent Classification and Out-of-Scope Prediction*, CLINC150. Each derived record retains its source URL, revision, exact input-file SHA-256, zero-based source row ID, original split, human label, license and attribution in provenance.

The converter preserves each raw utterance exactly. It changes the task contract and supplies readable handler descriptions, constructed by replacing label underscores with spaces and applying a small explicit expansion table for ambiguous intent names. These descriptions are deterministic label renderings, not model-generated labels or independently annotated paraphrases. Source-file pins and full attributions are in the [source manifest](../reports/community-routing-v3/source-manifest.json).

## Decision contracts

For each in-scope utterance, one Choice view includes its correct handler, a second omits that handler and requires abstention, and one Noul view asks whether a proposed handler matches. Each out-of-scope utterance gets one abstention Choice and one negative Noul view. This produces **72,080 Choice and 36,640 Noul rows**; related views are not independent utterances.

Choice has **2, 4 or 8 total options, including abstention**. Sizes cycle within each dataset/split. Correct-answer positions and abstention positions are balanced within each dataset/split/view/size, with counts differing by at most one. Noul uses one candidate per utterance and balances positive and negative targets within every dataset/split, with counts differing by at most one. There is no expansion of each utterance across every label.

Negative selection combines readable intent-name token overlap with random negatives. A small lexical alias table merges variants such as `payment` and `pay`. Out-of-scope negatives use the request's token overlap because there is no positive intent. This is lexical selection, not embedding-based semantic mining. Candidate subsets use the human gold label to include or exclude the correct handler deliberately; performance on these small sets must not be reported as original full-catalog intent-classification accuracy.

Every input explicitly names its catalog. Model inputs are only `state`, `question`, `kind`, and `options`; the human label, target, source IDs and selection details stay outside those fields. The routing contract asks the model to classify the request rather than perform it. Human intent labels and rendered descriptions can still be ambiguous or imperfect.

## Split integrity and retained counts

Normalization uses Unicode NFKC, casefolding, word tokens and collapsed whitespace. Original official-test groups are reserved globally across both catalogs first; official-validation groups are also excluded from source training. Test takes precedence over validation. Within each catalog, conflicting labels are excluded and duplicate normalized utterances are deduplicated. Different labels across catalogs are reported, with catalog context made explicit, rather than assumed to be equivalent or contradictory.

Remaining official-training groups receive a deterministic global 85/5/5/5 train/calibration/validation/OOD assignment. Original CLINC validation groups are assigned 50/50 to calibration/validation; original tests remain test. The same normalized request always occupies one split across both datasets. **OOD here means held-out original-training utterance groups within a source**, not new intents, new domains or new-language generalization.

| Split | BANKING77 utterances | CLINC150 utterances | Decision rows |
| --- | ---: | ---: | ---: |
| Train | 8,484 | 12,813 | 63,809 |
| Calibration | 455 | 2,279 | 8,156 |
| Validation | 502 | 2,283 | 8,289 |
| Test | 3,075 | 5,496 | 24,713 |
| OOD | 501 | 752 | 3,753 |
| Total | 13,017 | 23,623 | 108,720 |

The 36,783 raw rows yield 36,640 retained catalog utterances after removing 68 source-training rows reserved for official heldouts, 61 within-catalog duplicates, eight within-catalog conflicting-label rows, and six validation rows reserved for original test. Eighteen cross-catalog normalized components are reported; eight shared groups remain after screening, explaining the difference between 36,640 catalog utterances and 36,632 global groups.

## Separate full-catalog evaluation protocol

A prepared [evaluation-only protocol](../reports/community-routing-v3/full-catalog-eval-only.json) binds the complete label catalogs to eligible original-test IDs and pinned sources. It contains no expanded training rows and has not been run:

| Protocol | Total options | Retained official-test utterances | Original denominator |
| --- | ---: | ---: | ---: |
| BANKING77 full catalog | 77 | 3,075 | 3,080 |
| CLINC150 full catalog plus abstention | 151 | 5,496 | 5,500 including out-of-scope test |

Here, “full catalog” describes option coverage. The eligible test sets are screened subsets, with five BANKING77 and four CLINC rows excluded; they must not be represented as all original test rows. Original CLINC out-of-scope labels map to abstention. This protocol remains separate from the maximum-eight-option training views.

## Reproduction and audit

Stage these exact upstream files under a source directory, retaining the listed local names:

- `banking-train.csv`: [`banking_data/train.csv`](https://raw.githubusercontent.com/PolyAI-LDN/task-specific-datasets/57ec275d8078af65b7731c2a98be812d844a6d6b/banking_data/train.csv)
- `banking-test.csv`: [`banking_data/test.csv`](https://raw.githubusercontent.com/PolyAI-LDN/task-specific-datasets/57ec275d8078af65b7731c2a98be812d844a6d6b/banking_data/test.csv)
- `clinc-data-full.json`: [`data/data_full.json`](https://raw.githubusercontent.com/clinc/oos-eval/828f8093932c8fe6ca7936c3d2e52903b1c523de/data/data_full.json)

```bash
python -m jev.community_routing_v3 \
  --source-dir runs/community-diversity-v3/source \
  --output-dir data/community-routing-v3 \
  --seed 20260921
python -m unittest tests.test_community_routing_v3 -v
python -m jev.data validate data/community-routing-v3
python reports/community-routing-v3/independent_audit.py \
  --source-dir runs/community-diversity-v3/source \
  --data-dir data/community-routing-v3 \
  --output-dir runs/community-routing-v3-independent-recheck
```

The output directory must be new or empty; the converter refuses to overwrite existing artifacts or contain/replace the pinned source directory. It verifies source hashes and raw split counts before conversion. It uses the standard library and existing schema writer without downloads or provider calls.

Seven CPU tests cover global official-heldout reservation, catalog context, exact target contracts, bounded per-utterance views, target/abstention position balance, Noul label balance, deduplication/conflicts, input-order invariance, evaluation-only catalogs, source mutation and immutable output. A second agent reviewed the code read-only and independently reran all seven tests.

The [independent full-output audit](../reports/community-routing-v3/integrity-audit.json) imports no converter functions. It parses the pinned CSV/JSON directly, resolves every generated row back to its exact raw utterance and human label, checks all target contracts, verifies global split separation and official-heldout reservations, recomputes position histograms, and verifies that full-catalog IDs refer only to screened original tests. All 108,720 decision rows passed. File checksums and complete aggregate counts are in the [data manifest](../reports/community-routing-v3/data-manifest.json); [CPU test evidence](../reports/community-routing-v3/cpu-tests.txt) records seven passes and zero skips.

The preparation establishes reproducible transformation and contract integrity. Any training mixture, quality comparison, or larger-catalog provider evaluation requires a separate run and must retain the denominators and protocol distinctions above.
