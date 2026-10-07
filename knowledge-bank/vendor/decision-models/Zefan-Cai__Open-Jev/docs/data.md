# Data card: explicit-rule typed decisions

`python -m jev.data build --output-dir data/synthetic-v1 --groups 6000 --seed 42`

This standard-library generator is a verifiable mechanics baseline, not evidence of real-world judgment quality. Six thousand primary groups yield roughly 5,760 training examples; the exact count follows a stable group hash. Every fifth group also has a paraphrased question. A separate 600-group OOD set uses new question templates, entity namespaces, relation names, and, where applicable, numeric ranges. `--ood-groups` overrides its size.

Every JSONL row contains exactly these fields:

| Field | Meaning |
| --- | --- |
| `id`, `group_id` | Unique example identifier and shared identifier for variants of the same case. |
| `split` | `train`, `calibration`, `validation`, `test`, or `ood`. |
| `source` | Generator/family version or declared imported dataset name. |
| `state` | Observations and the explicit rules, facts, or rubric; a JSON object. |
| `question` | The decision being requested. |
| `kind` | `choice`, `noul`, or `score`. |
| `options` | Label strings in the order corresponding to `target`. |
| `target` | Finite nonnegative probabilities summing to one. |
| `metadata` | Provenance and evaluation attributes, excluded from model input. |

Model input consists **only of `state`, `question`, `kind`, and `options`**. Serialize object states as JSON. Never include targets, split identifiers, or provenance in the prompt. Outcome names in the stated rules describe the decision specification; there is no computed answer field in `state`.

`choice` has a fixed finite set of options, shuffled together with its target mapping. `noul` always uses `['no', 'yes']`; its returned value is the probability of the stated proposition being established. `score` preserves its ordered options and supplies increasing `metadata.score_values`; its expectation is the probability-weighted sum of those values. Each generated score option is a complete, independently meaningful statement, such as “Exactly 2 of the four conditions in the supplied rubric are satisfied.” It does not refer to another option or an adjacent level. Imported ordinal labels receive rank values `0..K-1`, which are ranks and should not be interpreted as calibrated physical distances.

## Synthetic families

| Family | Rule and ground truth | Task forms |
| --- | --- | --- |
| Policy | Evaluate ordered fraud/age exclusions, then exact income and debt-ratio thresholds. Boundary values include equality and one-unit differences. | Choice among eligible/manual review/ineligible, or whether eligibility is established. |
| Support routing | Apply security, outage/user-count, billing-topic, then fallback priorities. | Four-way routing choice or whether a candidate queue is required. |
| Evidence | Match explicit subject/relation/object facts, including true and false facts. Missing facts produce unknown. | Entailed/contradicted/unknown choice, or whether explicit support exists. |
| Rubric | Sum four independently satisfied numerical conditions under the stated rubric. | Ordered score from 0 through 4. |

All synthetic targets are hard, exact one-hot targets derived from the rules. An unknown factual claim is **not** assigned a made-up probability of 0.5; in the binary evidence task, missing evidence means explicit support is absent. Model uncertainty may still produce nontrivial probabilities. Soft targets require an independently specified annotator distribution or stochastic experiment and are not synthesized here. Generated records declare CC0-1.0 provenance.

The primary hash split is 80% training, 5% calibration, 5% validation, and 10% test, at the **group** level. A group's paraphrases and label permutations never span splits. Synthetic entities are unique to their group. The extra OOD split has disjoint template IDs and entity namespaces; policy income thresholds and routing/rubric magnitudes also extend beyond the training range. Shared logical rules remain the same, so this evaluates controlled transfer, not unseen task semantics. No calibration or test labels should be used in optimization; fit calibration parameters only on the calibration set and report test/OOD once the recipe is fixed.

## Import existing classification data

Prepare one JSON object per line with `text`, `label`, and, where available, `group_id` and an official `split`. Then run:

```bash
python -m jev.data import-jsonl \
  --input data/raw/reviews.jsonl --output-dir data/reviews \
  --labels negative positive --kind noul \
  --question 'Is this review positive?' \
  --source my-reviewed-dataset \
  --source-url https://example.org/dataset \
  --license Apache-2.0
```

Replace the example source and license with the dataset's actual provenance. The importer does not download or verify third-party licenses. Configurable field names support common JSONL formats. Labels are matched exactly after string conversion, including integer source labels supplied as CLI strings. For binary `noul`, the first source label maps to `no` and the second to `yes`. For `score`, provide source labels in their intended increasing order; use full, independently interpretable descriptions rather than references to adjacent levels. If the source labels are numeric codes, rewrite those labels into the descriptions before importing. The question must define the intended classification semantics.

Declared `test`, `validation`, `calibration`, and `ood` rows remain in their official split. Declared `train` groups are hash-partitioned 80/10/10 into train/calibration/validation and never become test rows. Without a source split, the four-way 80/5/5/10 hash policy applies. Unknown split names are rejected. Group identifiers should connect paraphrases, windows, source documents, or repeated entities; if no group is supplied, identical whitespace-normalized text is grouped automatically. This fallback cannot discover semantic duplicates or paraphrases. Conflicting source partitions or duplicated inputs across partitions fail validation. Input SHA-256, original row identifier, label, split, source URL, and license are retained in provenance.

## Verification

`python -m jev.data validate data/synthetic-v1`

Validation checks exact schema, unique IDs, probability lengths/ranges/normalization, binary order, ordinal values, provenance, group separation, conflicting repeated targets, and duplicate inputs across splits even when choices are shuffled. It also checks synthetic entity and OOD template separation. The manifest records dataset counts, generation settings, model-input fields, and per-file SHA-256 hashes. It is deterministic for a fixed seed and configuration.

`python -m unittest discover -s tests -p 'test_data.py'` exercises threshold boundaries, fact absence, oracle/target consistency, split leakage detection, import mapping, official-split preservation, and disk round trips. Exact input deduplication does not replace a semantic contamination audit for imported public benchmarks.
