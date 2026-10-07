# Invoice amounts: selection, attributes and exact normalization

`amount-extraction-control-v1` supplies two callable request builders, a guarded
Decimal normalizer and a separate original synthetic corpus: **200 document
families, 3,200 documents and 49,600 typed records**. It has not been trained,
evaluated with a model or added to either frozen training mixture. Email
selection, phone-country prediction and E.164 normalization remain outside
this addition.

The documents and annotations are original CC0-1.0 controls. They contain no
official cookbook samples, JF100 items, external benchmark rows or model outputs.
The existing recipe, API, data, citation and entity-alignment modules are unchanged.

## Two stages with separate meanings

Stage A, `amount_selection`, receives a document, a requested role and an explicit
US or EU number convention. Its local regex scans the complete document without
reading the query or any reference annotation. It produces exact text/start/end
candidates and two heads:

| Head | Type | Reference meaning |
| --- | --- | --- |
| `span` | Choice, including `none` | The candidate exactly matches the unique populated requested-role field, including both offsets; otherwise `none` |
| `target_present` | Noul | At least one requested-role field is populated, independently of candidate recall or supported number format |

Missing role lines and `not recorded` values are absent. Two populated fields
with the requested role are ambiguous, even when their numbers are identical.
An unsupported populated amount still counts as present. Thus `none` can mean
absence, ambiguity or an extractor miss; it never proves that the target is absent.

Stage B, `amount_attributes`, accepts an actual Stage A candidate ID. It copies
that candidate from a fresh scan of the original text and rejects invented or
altered candidates. Its state contains text, policy and the actual selected
candidate, with no requested role, reference span or family specification.
Passing `none` returns `None`, so no attribute request or normalization is run.

| Head | Type | Reference meaning |
| --- | --- | --- |
| `currency` | Choice: USD, EUR, GBP, review | Supported currency of the complete valid candidate; partial, invalid, unsupported or unknown currency requires review |
| `direction_known` | Noul | The complete valid candidate has an explicit attached credit/charge flow consistent with any sign |
| `is_credit` | Conditional Noul | Credit versus charge, defined only when `direction_known` is yes |

Unknown direction has **no supervised `is_credit` target**. It is not labeled
false or assigned a 0.5 probability. The runtime builder still declares this
conditional head; consumers must ignore it whenever the known condition fails.
A known credit/charge flow can coexist with unknown currency: the direction
head is then defined, but normalization still requires review.

The corpus creates Stage B requests for **all 14,800 actual candidates**, including
distractors and partial spans. These are conditional attribute examples, not
end-to-end extraction results. There are 13,800 defined `is_credit` records and
1,000 explicitly counted omissions. Another 200 documents have no candidates:
their real Stage A request has only `none`, which the API accepts. The training
schema requires at least two options, so those 200 forced `span` rows are omitted
and counted; their `target_present` rows and complete cases remain present.

## Public grammar and exact numbers

Every input contains the full policy. This implementation accepts two controlled
document layouts, with a declared locale and currency header:

```text
Number format: US
Currency declaration: USD
Amount due: USD 1,234.50 | Flow: charge
```

The held-out ledger layout uses lines such as
`Payable now :: flow=debit; value=1.234,50 EUR`. Visible tables disclose the role
and flow meanings. This is a controlled field grammar, not arbitrary PDF/OCR
understanding. Missing, conflicting or unsupported locale declarations are
rejected instead of guessed.

Numbers use ASCII digits and exactly two fractional digits. US uses decimal dot
and optional comma grouping. EU uses decimal comma and optional dot **or narrow
no-break-space** grouping; grouping styles cannot be mixed. A marker can precede
or follow the number. ISO USD/EUR/GBP are explicit; under this declared policy,
€ means EUR and £ means GBP. The symbols $ and ¤ require the document's supported
currency declaration. CAD is unsupported and leads to review.

An explicit minus sign or surrounding parentheses requires a credit flow; an
explicit plus requires charge. A conflicting or missing flow is unknown even
when a sign is present. Unsigned magnitudes may be either credit or charge.
Normalization takes the exact Decimal magnitude and applies credit negativity
once, using `copy_abs` and `copy_negate`; it does not use context-rounded unary
arithmetic or quantization. The corpus includes amounts exceeding 28 digits.

`normalize_amount` performs **deterministic checks of the public grammar** as
well as numeric conversion. It checks the actual selected offsets against the
complete source field and validates currency and sign/flow consistency from that
field. It reads no requested role, reference offset or hidden generator record.
Partial spans, malformed numbers, unknown facts and conflicting predicted
attributes produce `review`, even if a predicted head says the value is known.
The function accepts discrete decisions; it does not select probability thresholds.

## Candidate recall is measured separately

The new local regex recognizes currency-prefixed or currency-suffixed ASCII
number strings, including ordinary signs. It deliberately retains its observed
limitations: narrow no-break-space grouping and outer parentheses can produce
partial candidates. Candidate construction never adds a missing reference span
or drops a failed document. More than 254 candidates plus `none` is explicitly
rejected; a caller must select a section rather than truncate candidates.

Of the 2,400 documents with one populated requested-role field, **2,000 have an
exact candidate and 400 do not: candidate recall is 2,000/2,400 = 83.33%**.
The denominator excludes 600 absent-target and 200 ambiguous-target documents,
which are retained and reported separately. These are properties of the regex
and synthetic documents, not model accuracy. Missing spans remain extraction
failures for future end-to-end evaluation.

The 400 miss controls comprise 200 EU space-grouped amounts and 200 amounts
enclosed in parentheses. Their partial Stage B candidates receive review;
`target_present` remains true in Stage A.

## Call the builders

```python
from jev.case_amount_extraction import amount_selection, amount_attributes

text = "\n".join([
    "Invoice example-217",
    "Number format: EU",
    "Currency declaration: EUR",
    "Subtotal: EUR 100,00 | Flow: charge",
    "Tax: EUR 21,50 | Flow: charge",
    "Amount due: EUR -121,50 | Flow: credit",
    "Credit balance: EUR 14,00 | Flow: credit",
])
selection = amount_selection(text, "due", locale="EU")
attributes = amount_attributes(selection, "span_2")
```

The [selection request](../examples/amount-extraction-selection.json) and
[candidate-conditioned attribute request](../examples/amount-extraction-attributes.json)
contain no targets or answer objects. The illustrative `span_2` selection above
is caller-supplied, not an inference claim. In evaluation, Stage B must receive
Stage A's actual predicted ID; reference selection must never repair a wrong
first-stage prediction.

## Grouping and recorded supervision

Each family has 16 complete document counterfactuals covering due/subtotal/tax/
credit roles, distractors, missing roles and values, repeated values at distinct
offsets, duplicate target roles, unknown attributes, signs and conflicts, regex
misses, no candidates, and large exact decimals. All related documents and both
stages remain in one split.
Document identifiers use opaque hash suffixes; variant ordinals and reference
metadata are not embedded in the model's document text.
Complete field lines are shuffled once per document using a deterministic seed
from its family and opaque document nonce. This ordering does not read the query,
reference target or label; headers stay fixed and duplicate-role lines are
shuffled too. The final corpus has 303 distinct field orders. Recalled targets
occur at candidate IDs `span_0` through `span_4` with counts 419, 426, 380, 395 and
380 respectively; no permutation was selected to improve these counts.

| Split | Families | Documents | Typed records |
| --- | ---: | ---: | ---: |
| Train | 133 | 2,128 | 32,984 |
| Calibration | 9 | 144 | 2,232 |
| Validation | 4 | 64 | 992 |
| Test | 14 | 224 | 3,472 |
| OOD | 40 | 640 | 9,920 |

OOD reserves the ledger layout, different role/flow labels and suffix currency
placement. Both US and EU conventions are explicitly supplied in both domains;
these controls do not establish generalization to undisclosed locales or arbitrary
document structures. Stage A contributes 6,200 records; Stage B contributes
43,400. Their reference outcomes and guard decisions are not model results.

## Generate and verify

Use a fresh directory; the generator refuses nonempty or symlinked outputs.

```bash
python -m jev.case_amount_extraction \
  --output-dir data/amount-extraction-control-v1 --groups 200 --ood-groups 40 --seed 42
python -m jev.data validate data/amount-extraction-control-v1
python reports/amount-extraction-control-v1/verify.py \
  --data data/amount-extraction-control-v1 --output runs/amount-extraction-control-v1-audit.json
python3 -m unittest tests.test_amount_extraction_control -v
```

The ignored corpus includes standard split files, `families.jsonl`, `cases.jsonl`
and `manifest.json`. The [tracked manifest](../reports/data-manifests/amount-extraction-control-v1.json)
binds its source and artifact hashes. An earlier uncommitted candidate that lacked
GBP/symbol coverage was preserved with its source under
`data/amount-extraction-control-v1-draft-currency-coverage/` before regeneration.
A later candidate was preserved under
`data/amount-extraction-control-v1-draft-invoice-identifiers/` before ordinal
document-ID suffixes were replaced with opaque hashes to remove that shortcut.
The candidate before field-order shuffling and its build evidence are preserved
under `data/amount-extraction-control-v1-draft-field-order/`.

Saved verification is available in the [independent audit](../reports/amount-extraction-control-v1/independent-audit.json),
[build and example checks](../reports/amount-extraction-control-v1/build-verification.json),
[test execution record](../reports/amount-extraction-control-v1/test-verification.json)
and [frozen-input checks](../reports/amount-extraction-control-v1/frozen-inputs-check.json).
The independent audit passed all 49,600 records, recomputing the candidate recall,
conditional-head omissions, original offsets, exact normalization and observed
field-order diversity. The single unit-test run passed all 21 tests, with zero
failures, errors or skips; its exact command and output are retained.

Future evaluation must report raw span selection, attribute accuracy conditional
on the actual selected candidate, and end-to-end exact offsets/currency/signed
value beginning from Stage A predictions. Report the guard's ready/review coverage
and error rates separately. Rejecting an incorrect prediction must not be counted
as a correct model answer; evaluating Stage B on reference candidates is not an
end-to-end result. No such model metrics, calibrated thresholds or new checkpoint
capabilities are claimed by this data preparation.
