# Select a current contact email and copy it verbatim

`email-selection-control-v1` adds a callable request builder, an exact-copy
helper and a separate original corpus: **200 contact families, 2,800 documents
and 5,400 typed records**. It has not been trained, run through a model or added
to the active training mixtures. The shared email regex and all previously
sealed task modules remain unchanged.

All addresses are original controls under reserved `.example` or `.test` domains.
No personal contact data, official examples or external benchmark records were
used. The generated documents and annotations are CC0-1.0.

## Visible roles and current-contact rules

The request contains the original document, the requested role, a complete
policy and candidates from the existing
`jev.recipes.extract_candidates(text, "email")`. Candidate scanning receives
the text alone; it does not read the query, reference spans or generation metadata.

The controlled message-field layout is:

```text
Receipt destination | status=current | email: Mixed.Box@relay.example
Receipt destination | status=superseded | email: Older.Box@relay.example
```

The held-out contact-card layout uses
`Receipt mailbox :: email: Mixed.Box@relay.example; status=active`.
The complete visible policy maps both layouts' role and status labels. Roles
include receipt, billing, support, sender, recipient and reply-to contacts.
Only `current`/`active` fields are eligible; superseded/retired contacts never
provide a fallback. Physical field order conveys no priority. Unknown statuses
on recognized fields are rejected instead of guessed.

| Head | Type | Reference meaning |
| --- | --- | --- |
| `span` | Choice, including `none` | The actual candidate exactly equals the sole populated current requested-role field, including both original offsets |
| `target_present` | Noul | At least one current requested-role field is populated, independently of regex recall |

Empty fields and literal `not recorded` values are unpopulated. A superseded-only
contact does not establish a current target. Two populated current fields with
the requested role are ambiguous **even if the address text is identical**.
Quoted or Unicode email fields remain populated when the ASCII regex misses
them. Consequently `none` may represent absence, ambiguity or a missing exact
candidate; it does not by itself prove target absence.

These are explicit rules for controlled message fields and contact cards, not
an unrestricted email-thread, timestamp or sender-authority parser.

## Copying is separate from selecting the correct role

`selected_email(request, selected_id)` rescans the actual text, checks candidate
binding and copies the selected candidate without changing any character. It
preserves local-part and domain case, plus tags and punctuation. It performs no
lowercasing, Unicode normalization or address generation.

The helper uses the public field grammar and actual offsets to reject a
recognizable partial or unbound candidate. It reads no requested role or
reference annotation. A complete superseded or wrong-role candidate can still
return `copied`: this only verifies full-field copying, not selection correctness.
`none` returns `no_selection`; rejected partials return `review` with no email
value. Neither copying nor regex recognition establishes RFC/EAI validity,
mailbox existence or deliverability. No delivery attempt is made.

## Actual candidate recall and omissions

The existing ASCII regex is used unchanged. It can miss quoted local parts and
return only a suffix or prefix of a Unicode address. Its limitations remain in
the saved data; no reference span is inserted into the candidate set and no
missed document is dropped.

For the **1,600 documents with one populated current requested-role field**,
the regex recalls **1,000 exact candidates and misses 600: 62.5% recall**.
The misses comprise 200 quoted-local-part, 200 Unicode-local-part and 200
Unicode-domain controls. The 800 absent-target and 400 ambiguous-target documents
are retained but excluded from this recall denominator. These counts measure
the regex on these controls, not model selection accuracy.

There are 17,400 actual candidates: the deterministic copy checks classify
17,000 as complete fields and 400 as partials. These are software reference
outcomes and do not show that a model selected the correct current contact.

The 200 documents with no candidates retain their real runtime request containing
only `none`. Because the training schema requires at least two options, their
forced span rows are omitted and counted; their presence rows and full cases
remain. More than 254 candidates plus `none` is explicitly rejected. A caller
must narrow the document before retrying rather than truncate the candidate set.

## Example request

```python
from jev.case_email_selection import email_selection

text = "\n".join([
    "Message bundle example",
    "From | status=current | email: Sender.Box@relay.example",
    "Receipt destination | status=superseded | email: Older.Box@relay.example",
    "Billing contact | status=current | email: Accounts.Box@relay.test",
    "Receipt destination | status=current | email: MiXeD.Box+Tag@Relay.Example",
    "To | status=current | email: Reader.Box@relay.test",
])
request = email_selection(text, "receipt")
```

The [request-only example](../examples/email-selection.json) contains no answer
or reference target. It compiles through the existing API and is discoverable
through `/examples.json`. Any later copying call must receive the actual selected
candidate ID. No model response is fabricated for this example.

## Original grouped controls

Each family contains 14 complete document counterfactuals: current receipt
selection, another requested role, current/superseded status swaps, absent and
unrecorded targets, superseded-only targets, two distinct current addresses,
two identical current addresses at different offsets, another role sharing the
same value, quoted/Unicode misses, no candidates and mixed case with a plus tag.

Addresses have opaque local identifiers that do not encode their role. Visible
document IDs use opaque hash suffixes, not variant ordinals. Complete field
lines are shuffled with a deterministic seed from the family and document nonce,
without reading the query, reference or labels or choosing permutations to
improve an outcome. All related documents stay in one split.

| Split | Families | Documents | Typed records |
| --- | ---: | ---: | ---: |
| Train | 134 | 1,876 | 3,618 |
| Calibration | 3 | 42 | 81 |
| Validation | 7 | 98 | 189 |
| Test | 16 | 224 | 432 |
| OOD | 40 | 560 | 1,080 |

There are 2,291 distinct role/status field orders. Recalled target IDs `span_0`
through `span_6` occur 145, 142, 145, 131, 139, 155 and 143 times respectively.
OOD reserves the contact-card layout and role/status vocabulary; the underlying
current-contact rule and explicit policy remain the same. This is a controlled
layout/wording shift, not evidence of arbitrary real-email generalization.

## Generate and verify

Use a fresh directory; generation refuses nonempty or symlinked outputs.

```bash
python -m jev.case_email_selection \
  --output-dir data/email-selection-control-v1 --groups 200 --ood-groups 40 --seed 42
python -m jev.data validate data/email-selection-control-v1
python reports/email-selection-control-v1/verify.py \
  --data data/email-selection-control-v1 --output runs/email-selection-control-v1-audit.json
python3 -m unittest tests.test_email_selection_control -v
```

The ignored corpus stores standard split files, `families.jsonl`, `cases.jsonl`
and `manifest.json`. The [tracked manifest](../reports/data-manifests/email-selection-control-v1.json)
binds source and data hashes. References are independently derived from final
visible fields, status rules and exact offsets; family IDs do not supply labels.

Saved verification is available in the [independent audit](../reports/email-selection-control-v1/independent-audit.json),
[build and example checks](../reports/email-selection-control-v1/build-verification.json),
[test execution record](../reports/email-selection-control-v1/test-verification.json)
and [shared frozen-input checks](../reports/runtime-checks/contact-controls-frozen-inputs-20260920.json).
The independent audit passed all 5,400 records and 17,400 candidates, recomputing
status rules, offsets, copy results, omissions and order diversity. The single
unit-test run passed all 19 tests, with zero failures, errors or skips; its exact
command and output are retained.

Future model evaluation must report conditional span accuracy when the target
was recalled, `none` behavior by absence/ambiguity/miss category, and end-to-end
exact-offset/email accuracy starting from the model's actual selection. Report
copy-guard coverage separately; copying a wrong-role address or rejecting a
partial prediction cannot be counted as a correct model selection. No such
model metrics or new checkpoint capability are established here.
