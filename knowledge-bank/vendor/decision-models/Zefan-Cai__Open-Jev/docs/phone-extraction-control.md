# Phone extraction, explicit region and E.164 formatting

`phone-extraction-control-v1` adds a two-stage request API and a guarded phone
normalizer, with **200 original document families, 4,000 documents and 19,000
typed training records**. This corpus has not been trained or evaluated with a
model, and it is separate from both frozen training mixtures.

All contacts are labeled **fictional** in the model-visible text. The original
CC0-1.0 controls use US `202-555-0100..0199`, Canada `416-555-0100..0199` and UK
`07700 900000..900999` example styles, including deliberately malformed variants.
These are based on the NANPA 555 example range and Ofcom drama mobile range.
No number is dialed, no identity is queried, and no assignment or reachability
is asserted. There are no cookbook examples, external benchmark items or model
outputs in the corpus.

## Task contract

Stage A, `phone_selection`, receives the original text and the requested role:
`mobile`, `billing` or `support`. A regex scans the **complete text without
reading the query or any gold annotation**, keeping text and Python character
offsets for each candidate. Offsets are not UTF-8 byte offsets.

| Head | Type | Reference meaning |
| --- | --- | --- |
| `span` | Choice with `none` | Exact text and both offsets of the unique populated requested-role slot, or `none` |
| `target_present` | Noul | At least one requested-role phone slot is populated, regardless of candidate recall, format or region |

An empty slot, `not recorded` or a missing role is absent. Duplicate populated
requested-role fields are ambiguous, including duplicates with identical values.
A malformed or unrecalled phone value is still present. Consequently `none`
does not distinguish absence, ambiguity and an extractor miss; those cases remain
separate in the retained references.

Stage B, `phone_attributes`, accepts an **actual Stage A candidate ID** and copies
that candidate from a fresh scan. It rejects invented candidates or changed
text/offsets. Its input contains the original text, public policy and selected
candidate; no requested role or reference span is added. Passing `none` returns
`None`, so no Stage B request or normalization occurs.

| Head | Type | Reference meaning |
| --- | --- | --- |
| `region` | Choice: US, CA, GB, unknown, review | Explicit region of the actual complete candidate's field, subject to the visible format/conflict policy |

The runtime accepts the caller's discrete region decision. It does not invent a
probability threshold. In a model evaluation, B must receive A's predicted ID;
using a reference span to repair an incorrect selection is prohibited. A wrong
but complete billing candidate can legitimately normalize to that billing
number; this remains an end-to-end selection error.

## Visible grammar and country evidence

Each input includes its full public policy. Card fields have this form:

```text
Mobile: 07700 900123 | Region: GB
Billing: +1 416-555-0156 | Region: CA
Support: +1 202-555-0123 | Region: US
```

The OOD message layout uses disclosed alternative labels, for example
`On-call contact :: phone=07700 900123; region=GB`. This is a controlled field
grammar, not a general PDF, OCR or arbitrary-message parser. The role `mobile`
is a contact role supplied in the document, not a prediction of wireless line type.

The region suffix is field-local and may be missing. Missing, blank or
`not stated` gives `unknown`; there is no document-wide or US default.
Unsupported declarations such as `FR`, multiple declarations such as `US,CA`,
and conflicts require `review`.

**Both +1 and +44 are shared calling codes.** Neither is sufficient to select a
country in this policy. An explicit US/CA/GB field supplies the region; the
normalizer rejects a different parsed calling code or a different region
identified by the pinned metadata. Thus a Canadian 416 example labeled US is a
conflict. A missing region stays unknown even when the digits might allow a
library inference. Unresolved metadata does not override an explicit region:
the reserved UK examples have no metadata-inferred region in this library
version, while their visible GB declaration still supplies the task's region.
This declared-region contract does not prove physical location or ownership.

## Formatting, metadata validity and routability

`phonenumbers==9.0.14` is an optional, pinned dependency in the `phone` extra.
Request construction works without it; corpus generation and the guarded number
parsing step require it. A different installed
version is rejected so metadata changes cannot silently alter the corpus labels.

The public format accepts ASCII digits, an optional leading `+`, and single
ASCII spaces, dots or hyphens between digit groups. Parentheses, extensions,
vanity letters, Unicode digits/separators and IDD prefixes are unsupported.
Syntax and complete source-slot checks happen before calling the permissive
library parser. No extension is silently discarded or vanity letter converted.

After parsing, international digits must exactly equal the E.164 digits when
separators are removed. National digits must exactly equal the library's
NATIONAL-format digits. This rejects implicit repairs such as `+44 07700...`,
an extra domestic `1` prefix, or `0044...`. National GB `07700...` is explicitly
accepted: conversion to `+447700...` removes its national trunk prefix as part
of the documented national-to-international format operation.

| Output | Meaning |
| --- | --- |
| `format_supported` | The actual candidate satisfies the restricted ASCII formatting grammar; it may still be partial or require review |
| `possible` | Pinned library's number-length/structure plausibility, including local-only numbers, or null when not assessed |
| `valid` | Pinned library numbering-plan metadata classification, or null when not assessed |
| `valid_for_region` | Pinned library validity for the explicit region, separately retained |
| `status=formatted`, `e164` | Complete candidate, supported consistent region, globally possible length, no implicit digit repair; exact E.164 representation returned |
| `routable=unverified` | Always unverified; no routing, identity or live network evidence is collected |

Formatting deliberately does **not** require `valid=true`. In the tested version,
`07700 900123` with explicit GB becomes `+447700900123`, with `possible=true`,
`valid=false` and `valid_for_region=false`. US/CA example styles can have
`valid=true`, but that does not establish assignment or reachability. None of
these booleans means the phone can be called.

Locally plausible numbers are an additional refusal case: in this library,
US/CA `555-0123` and `+1 555-0123` can have `possible=true` but are classified
`IS_POSSIBLE_LOCAL_ONLY`. Their missing area code prevents complete E.164
conversion. The guard preserves `possible=true`, returns `review` with reason
`local_only_number_missing_area_code`, and supplies no E.164 value.

Partial candidates, unknown/conflicting regions, unsupported syntax, impossible
lengths and mismatched predicted regions produce `status=review` and no E.164
value. The guard reads only the actual B input and public policy. Rejecting a
wrong model prediction is not counted as a correct model answer.

## Candidate recall and corpus scope

The scanner retains strings with at least seven ASCII digits. Extensions and
outer parentheses can leave partial candidates; narrow no-break spaces can make
a complete phone disappear from the candidate list. These failures are not
repaired with reference spans. More than 254 candidates plus `none` is rejected
explicitly so the caller can select a section.

Of **3,200** documents with one populated requested-role field, **2,600** have
an exact candidate and **600** do not: candidate recall is **81.25%**. The
denominator excludes 600 absent-target and 200 ambiguous-target documents, all
of which remain in the corpus. The 600 misses comprise 200 extension cases,
200 outer-parenthesis cases and 200 Unicode-space cases. This is a scanner
measurement on synthetic controls, not model accuracy.

Every actual candidate receives a conditional B request: **11,200** candidates,
including wrong-role distractors, partial spans and a phone in an unrelated note.
Region references contain 2,997 US, 2,996 CA, 3,007 GB, 400 unknown and 1,800 review.
Of their reference normalizations, 9,000 are formatted and 2,200 require review;
3,007 formatted examples are metadata-invalid UK examples. These are reference
outcomes, not model results.

The 200 no-candidate documents have a real API request with only the `none`
span option. Since training records require at least two options, those 200
forced span rows are omitted and counted; their presence rows and complete cases
are retained. A contributes 7,800 typed records and B contributes 11,200.

Each family contains 20 whole-document variants covering three requested roles,
national/international formats, missing roles/values/regions, unknown and
conflicting region declarations, duplicate target fields, repeated values at
different offsets, missed/partial candidates, impossible lengths and digit repair.
All related variants and both stages remain in one split. IDs visible in document
text are opaque hashes, and complete field lines are shuffled once per document
without examining a target or choosing a favorable order.

| Split | Families | Documents | Typed records |
| --- | ---: | ---: | ---: |
| Train | 130 | 2,600 | 12,350 |
| Calibration | 9 | 180 | 855 |
| Validation | 4 | 80 | 380 |
| Test | 17 | 340 | 1,615 |
| OOD | 40 | 800 | 3,800 |

The corpus contains 20 distinct field orders. Recalled targets appear at
`span_0`, `span_1`, `span_2`, `span_3` with counts 778, 897, 861, 64. No permutation
was chosen to improve these counts. OOD reserves the message layout and role
labels; it does not establish unseen-country generalization. The finite example
ranges can repeat across families and splits, so this is not a phone-number
identity holdout benchmark.

The independent audit counted **11,200 populated source slots** for raw-string
overlap and **9,000 accepted actual B candidates** for E.164 overlap. Raw slots
include unsupported/malformed values and exclude unrelated notes; E.164 values
come only from candidates accepted for formatting. These are different units.
The following counts are distinct values, not occurrence counts:

| Unit | Unique values | Reused across families | Reused across splits | Train/test intersection | Train/OOD intersection |
| --- | ---: | ---: | ---: | ---: | ---: |
| Raw phone-slot strings | 1,439 | 336 | 229 | 49 | 146 |
| Independently formatted E.164 | 424 | 179 | 124 | 34 | 81 |

Full split-pair counts are retained in the
[independent audit](../reports/phone-extraction-control-v1/independent-audit.json).
These controls hold out document families and layout/role combinations; they
provide no evidence of generalization to previously unseen phone numbers.

## Install, call and regenerate

From the repository root, use a fresh isolated environment. This extra does not
install the training stack.

```bash
python3 -m venv runs/phone-extraction-control-v1-venv
runs/phone-extraction-control-v1-venv/bin/python -m pip install -e '.[phone]'
```

The exact extra installation was verified with Python 3.14.5 and phonenumbers
9.0.14 in an ignored environment; the existing environments were not modified.
The [installation record](../reports/phone-extraction-control-v1/installation-verification.json)
retains the installed distribution requirements and library source-tree hash.

```python
from jev.case_phone_extraction import phone_selection, phone_attributes, normalize_phone

text = "\n".join([
    "Fictional contact; demonstration only; do not dial.",
    "Billing: +1 416-555-0156 | Region: CA",
    "Mobile: 07700 900123 | Region: GB",
])
selection = phone_selection(text, "mobile")
attributes = phone_attributes(selection, "span_1")  # Caller-supplied example decision.
result = normalize_phone(attributes, region="GB")
```

The [selection example](../examples/phone-extraction-selection.json) and
[attribute example](../examples/phone-extraction-attributes.json) contain only
requests, with no answer or target objects. The example's candidate and region
decisions illustrate caller input; they are not model predictions.

Choose a fresh empty data directory; the generator rejects nonempty or symlinked
outputs.

```bash
runs/phone-extraction-control-v1-venv/bin/python -m jev.case_phone_extraction \
  --output-dir data/phone-extraction-control-v1 --groups 200 --ood-groups 40 --seed 42
runs/phone-extraction-control-v1-venv/bin/python -m jev.data validate data/phone-extraction-control-v1
runs/phone-extraction-control-v1-venv/bin/python -m unittest tests.test_phone_extraction_control -v
runs/phone-extraction-control-v1-venv/bin/python reports/phone-extraction-control-v1/verify.py \
  --data data/phone-extraction-control-v1 \
  --output runs/phone-extraction-control-v1-audit.json
```

The ignored corpus contains five split files, `families.jsonl`, `cases.jsonl`
and `manifest.json`. The [tracked manifest](../reports/data-manifests/phone-extraction-control-v1.json)
binds the source and artifact hashes. The [build record](../reports/phone-extraction-control-v1/build-verification.json)
includes schema validation and request-only example checks; the
[runtime test record](../reports/phone-extraction-control-v1/test-verification.json)
records 22 passed tests, zero failures/errors/skips, including actual library
boundaries. A separate run without the optional phone library passed the 12
dependency-free tests and explicitly skipped ten library-dependent tests; base
installation test discovery therefore does not require the phone extra. The
missing-library path is tested and supplies an installation hint.
The [independent corpus audit](../reports/phone-extraction-control-v1/independent-audit.json)
verified all 19,000 records and separately recomputes visible field labels,
original offsets, region decisions and E.164 digit conversion. Library
`possible`/`valid` checks that use the same dependency are metadata consistency
checks, not independent confirmation of its numbering-plan database.
Its command and behavioral checks are retained in the
[audit execution record](../reports/phone-extraction-control-v1/audit-verification.json).

The initial corpus, source, tests and build evidence were preserved in ignored
`data/phone-extraction-control-v1-draft-local-only/` before adding the explicit
local-only refusal. The final corpus was rebuilt against that visible policy;
its document and row counts are unchanged. Seven-digit local-only cases are
runtime regression tests, not additional training documents.

The shared [frozen-input check](../reports/runtime-checks/contact-controls-frozen-inputs-20260920.json)
records whether the existing source pins and frozen corpora remained unchanged.

Future model evaluations must retain A's raw predictions, B's actual selected
candidate, region errors, review coverage and end-to-end exact span/region/E.164
outcomes. No new checkpoint capability, model score, calibrated threshold or
real-world phone-extraction claim follows from this data preparation.
