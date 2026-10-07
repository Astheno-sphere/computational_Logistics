# Contextual citation controls

`citation-control-v1` is a separate original synthetic corpus for the existing
`jev.recipes.citation_check(claim, source, quote=None)` request. It contains
**200 document groups, 4,000 semantic Choice records and 400 deterministic
quote-not-found cases**. It has not been used for training or model inference.
The frozen `release-v2` and `browser-drone-expansion-v1` corpora and the active
27B run were not changed or augmented.

## Exact task contract

The recipe asks whether the **complete supplied source** supports the claim in
its original context. Its existing choices remain unchanged:

- `supported`: the source entails the claim and any supplied quote is accurate
  in context;
- `contradicted`: the source contradicts the claim or the quote misrepresents it;
- `insufficient`: the source does not establish the claim.

The generator compiles every semantic record through that actual recipe and
`compile_request`. The model receives only `state`, `question`, `kind` and
`options`; the state is exactly `claim`, `source`, `quote`. Reference labels,
fact specifications, grouping and provenance stay outside those input fields.
One-hot targets are controlled reference labels, not model confidences.

An exact quote can appear in every semantic class. For example, the same general
eligibility sentence is supplied with an eligible request, a request barred by
the contextual visitor exception, and a request whose visitor status is
unrecorded. Its presence never overrides the full source or establishes the
claim. Negated claims are also judged against the complete policy; an unknown
eligibility value makes both positive and negative claims insufficient.

## Original construction and limits

Each template-generated document provides one complete voucher rule: an
inclusive USD amount ceiling and inclusive start date, with an explicit visitor
exclusion. It also says delivery charges are not covered and includes an
unrelated printing-budget/date paragraph. Six randomly named requests exercise
the exact amount/date boundary, an amount one unit above it, a date one day
before it, the visitor exception, an unknown date and an unknown visitor status.
The current corpus does **not** include requests with an unknown amount.

Positive and negative eligibility claims, delivery-charge claims, and selected
quotation variants produce 20 semantic rows per document: seven supported,
seven contradicted and six insufficient. Document request IDs and registry
order are randomized; each class includes context-only, exact-quote and
typography/whitespace-normalized quotation cases. No official cookbook example,
JF100 item, external evaluation outcome or model response supplies a label.

The 160 ID documents use policy sections; 40 dedicated OOD documents use a
different operations-note grammar and section layout. **OOD measures wording
and layout variation within this one rule family.** The documents share a small
controlled grammar; they are not 200 independent real-world policies. Success
on them would not establish arbitrary citation or factual verification.

All claims, negations, quotes and missing-quote controls from one document share
one `group_id` and split. ID groups are assigned by the existing deterministic
group hash; the operations-note groups are reserved for OOD.

| Split | Original documents | Semantic rows |
| --- | ---: | ---: |
| Train | 126 | 2,520 |
| Calibration | 10 | 200 |
| Validation | 9 | 180 |
| Test | 15 | 300 |
| OOD | 40 | 800 |

The total reference labels are 1,400 supported, 1,400 contradicted and 1,200
insufficient. These are data-construction counts, not measured model results.

## Quote gate

`locate_quote` checks normalized substring presence before a semantic record is
emitted. It only converts curly single/double quotation marks to straight ones
and collapses whitespace. Matching stays case-sensitive; it performs no
paraphrase, punctuation, ellipsis, Unicode compatibility or semantic matching.
Returned offsets refer to the normalized source, not original character/byte
positions. A missing quotation returns `quote_not_found`; no quotation returns
`context_only`.

Two additional controls per document reword or extend the exact quote so that
it no longer matches. These 400 cases retain their raw input and deterministic
gate in `cases.jsonl`, with no semantic request, target or confidence. They are
absent from the five training/evaluation JSONL files and from mixtures built by
`jev.mix_data`. A failed string match does not prove deliberate fabrication or
determine whether the underlying claim is true. This implementation has no
network fetcher, section-selection service or human-review queue.

## Generate and verify locally

Python 3.10+ and the repository checkout are sufficient; no model dependency or
GPU is needed. Use a new output directory; the generator refuses nonempty or
symlinked destinations.

```bash
python -m jev.case_citation \
  --output-dir data/citation-control-v1 --groups 200 --ood-groups 40 --seed 42
python -m jev.data validate data/citation-control-v1
python reports/citation-control-v1/verify.py \
  --data data/citation-control-v1 --output runs/citation-control-v1-audit.json
python -m unittest discover -s tests -p test_citation_control.py -v
```

`--groups` means the total document count, including `--ood-groups`. The ignored
output contains five standard split files, `documents.jsonl`, `cases.jsonl` and
`manifest.json`. The [tracked manifest](../reports/data-manifests/citation-control-v1.json)
records the exact source-code and data hashes. Generated original documents,
claims and records are CC0-1.0; that declaration does not relicense model weights
or upstream task documentation.

The independent [verifier](../reports/citation-control-v1/verify.py) parses the
final rendered source and claim, then enumerates possible completions of missing
fields. It does not call the generator's eligibility or label function. It
checks the recipe contract, semantic targets, quote gate, grouped splits and
artifact hashes. The [independent audit](../reports/citation-control-v1/independent-audit.json)
passed on all 4,000 semantic rows and 400 quote-not-found controls; 18 focused
citation tests and seven existing recipe tests also passed. Audit output must
be a new file outside the input data directory; existing files and symlinks are
refused. This report is a validation of controlled reference data, not
semantic accuracy, macro F1, Brier score or a calibrated review threshold from a
model. Those metrics require a later explicitly selected training/inference run.

The [build checks](../reports/citation-control-v1/build-verification.json), ordinary
dataset validator and a temporary one-source `mix_data` round trip
both preserved all 4,000 records and split counts. Only this new corpus was read
for that compatibility check; no mixture was added to an active training job.
