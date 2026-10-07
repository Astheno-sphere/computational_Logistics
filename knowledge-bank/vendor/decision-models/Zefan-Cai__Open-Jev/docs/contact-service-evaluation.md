# HTTP evaluation of the frozen contact controls

`python -m scripts.evaluate_contact_service` evaluates the frozen email-selection
and phone-extraction controls against an existing HTTP decision service. It sends
real requests when invoked normally, preserves the wire evidence and scores the
complete selected test/OOD sets. It does not launch a server, allocate GPUs,
generate data, retrain a model or recalibrate its temperature.

Only CPU software fixtures have been run for this new entry point. No contact
model-quality result is claimed by this implementation work. Future GPU-backed
execution must wait for the current 27B run and its established final evaluation
stages to finish and release resources. These contact corpora were not included
in the pre-existing 2B/9B/27B training mixtures; future checkpoint provenance must
be checked separately.

## Fixed inputs and order

The evaluator defaults to `--corpora email phone --splits test ood`. It reads the
two existing directories beneath `--data-root`, checks their exact manifest pins,
all listed file hashes and frozen producer-source hashes, and refuses mismatches.

| Corpus | Frozen manifest SHA-256 | Test documents | OOD documents |
| --- | --- | ---: | ---: |
| email-selection-control-v1 | `4c18cc791425003c5c8f052ce27ed034dfb54c79ddac24de13f7290ab3b3316c` | 224 | 560 |
| phone-extraction-control-v1 | `1001f1e04795308bf4f68db51076e8e1e1e47802986de54fc33b3b8d33548cfb` | 340 | 800 |

The default run therefore has **1,924 Stage A documents**. No label-based sample
selection, `max-cases` shortcut or retry-on-failure filter is provided. One may
explicitly select a single corpus or a single held-out split; the saved selection
records that scope.

All family metadata is parsed to validate group separation and obtain held-out
case IDs. Train, calibration and validation split files are hashed as bytes and
never decoded as records. For `cases.jsonl`, the loader decodes each line's leading
ID first and only JSON-decodes the complete case when its family belongs to the
requested test/OOD split. Training-case references are not parsed or supplied to
inference.

Order is fixed by corpus (`email`, then `phone`), split (`test`, then `ood`),
SHA-256 of `["group", group_id]`, then SHA-256 of `["case", case_id]`, using
compact canonical JSON for the hashes. Neither references nor outcomes choose
the order. `selection.json` records every case identity, original request hash
and the hash of the ordered case list. The independent
[held-out preflight](../reports/contact-service-eval/heldout-preflight.json)
retains the complete population and fixed denominators.

## Actual A → B execution

A sends the original case's `state` and `questions`, plus the routing `model`
alias. No reference answer or annotation is added to the wire payload.

Both A heads are checked: the span Choice must cover exactly the offered options,
sum to one, have valid confidence and name a maximum-probability option; Noul
must be a finite probability in `[0,1]`. A tie preserves the service's actual
chosen maximum instead of replacing it with a local argmax. Presence uses the
fixed threshold `p >= 0.5`.

**Only A's actual span controls phone B.** An A error or `none` sends no B request.
Otherwise `phone_attributes(original_A_request, actual_selected_id)` rebuilds B
from the real candidate and source offsets. The serialized reference B request
is never used for dispatch, and a gold candidate never repairs a wrong A.
Presence is independently scored and does not gate B: non-`none` with low
presence still sends B, while `none` with high presence is valid on an extractor
miss. Email copies the actual selected candidate through its existing guard.

Every B response receives the same strict typed/schema/probability checks.
Region accuracy is measured against the reference for the **actual selected
candidate**, including distractors and partial candidates. A wrong-role phone
can receive the correct region and format successfully while still failing
requested-target extraction.

The script uses the existing drone evaluator's strict JSON, HTTP capture, typed
response and service-identity helpers. The identity check counts Noul as one
scoring sequence, despite its two probability outcomes. Duplicate JSON keys,
nonfinite numbers, unknown candidates, malformed answers and incomplete
probability distributions are errors.

## Identity, failures and evidence

Expected model, method and exact 40-character base revision are required. A LoRA
run also requires its expected 64-character checkpoint hash. Optional
`--expected-temperature` pins a known temperature; no temperature is fitted here.

The first metadata-valid response locks model, method, revision, checkpoint,
temperature, code commit and context limit before answer-schema validation. That
same identity is required across all email/phone A/B responses. An early malformed
answer cannot let a later temperature or checkpoint change establish a new
identity. This is consistency checking of service-reported metadata against
expected pins, not independent authentication of loaded weights.

The evaluator retains the following artifacts in a fresh output directory:

| Artifact | Contents |
| --- | --- |
| `selection.json` | Full ordered population, corpus/source hashes, expected identity, configuration and evaluator/helper hashes |
| `requests.jsonl` | Exact request JSON, base64 wire bytes and SHA-256, written before each transport call |
| `attempts.jsonl` | Matching request, HTTP status, raw response bytes as base64, response hash, transport errors and timing |
| `references.jsonl` | Held-out A references and candidate-conditioned B references, kept separate from wire requests |
| `outcomes.jsonl` | Per-case A/B status, parsed responses, actual predictions, identities, selected offsets and guard result |
| `report.json` | Case counts, error/pending counts, metrics by corpus/split, guard coverage and limitations |

HTTP, JSON, schema, identity and pipeline errors remain in their declared
denominators. B failure does not erase a valid A score, but does fail B and final
value success. Interrupted runs retain pending documents in the original fixed
population; already written requests and responses are preserved.

Only a completed real HTTP run with a validated stable identity has
`is_model_quality_evidence=true`. Completed-with-errors, interrupted, changed-input
and explicit fixture-transport runs are marked false. Semantic accuracy can still
be low in a clean completed run. Non-complete runs exit nonzero; create a new
output directory for an explicitly chosen retry, preserving prior evidence.

## Denominators and interpretation

All ratios retain failed/pending cases in their stated population. There is no
combined score that adds easy absent-target refusals to successful extraction.

| Report field | Population / successful outcome |
| --- | --- |
| `a_presence`, `a_span` | All selected documents; correct raw A head |
| `a_nonforced_span`, `a_forced_span` | Separate span decisions with alternatives versus no actual candidates; forced cases still require valid service responses |
| `a_span_on_recalled` | All documents whose unique target was exactly recalled by the scanner, including failed calls |
| `a_none_target_absent`, `a_none_ambiguous_target`, `a_none_candidate_miss` | Separate reference-none strata; returning none on a miss is policy-correct but not successful extraction |
| `exact_raw_span_on_unique_target` | Every uniquely populated target; actual A must match its original text, start and end |
| `final_value_on_unique_target` | The same full unique-target population; exact offsets plus correct copied email or actual-B region and formatted E.164; undefined values never succeed via `None == None` |
| `complete_output_on_unique_target` | Final-value success plus correctly positive A presence |
| `e164_on_reference_formattable_target` | Phone's fixed subset of unique targets whose reference rule permits formatting; A/B failures and wrong selections remain zero |
| `b_region_on_actual_selection` | A-valid actual non-`none` phone selections; failed/pending B remains zero, regardless of whether A chose the requested role |
| `b_region_on_actual_unknown_or_review` | The subset whose actual-candidate region reference is unknown/review; raw B Choice must match, not merely yield the same guard refusal |

The independently checked default populations are:

| Population | Test | OOD | Total |
| --- | ---: | ---: | ---: |
| Email unique populated target | 128 | 320 | 448 |
| Email exactly recalled/copyable target | 80 | 200 | 280 |
| Phone unique populated target | 272 | 640 | 912 |
| Phone exactly recalled target | 221 | 520 | 741 |
| Phone reference-formattable target | 85 | 200 | 285 |

`reference_value_available` means visible raw reference-value availability for
email (**448/448**), but reference E.164 formatting availability for phone
(**285/912 = 31.25%**). It does not claim all 448 email targets are copyable by the
scanner: email candidate recall/copyability is **280/448 = 62.5%**. Phone's
all-unique-target final-value metric keeps the remaining 627 unknown, unsupported,
conflicting or unrecalled targets in its denominator; its separate E.164 metric
uses all 285 reference-formattable targets. Correct unknown/review decisions are
visible through B strata and guard outcomes, not counted as a copied/formatted
requested-target value.

Guard statistics separately report eligible actual non-`none` selections,
executions, copied/formatted/review counts and refusal reasons. Failed or skipped
execution is not a guard refusal. Guard acceptance is not model correctness;
offset/role checks prevent a copied or formatted distractor from passing the
end-to-end metrics. `b_not_attempted` exposes A failures/pending and A-none skips;
`b_eligible_status_counts` exposes the outcomes of eligible B stages.

Phone normalization preserves the existing distinctions between supported
format, possible length, metadata validity and unverified routability. Reserved
GB numbers may be possible but metadata-invalid and still format. Local-only
numbers without an area code require review, even if `possible=true`.

The finite fictional phone pool repeats across splits: the full frozen corpus
has 424 different formatted E.164 values, including 124 reused across splits.
These are document-family/layout/role controls, not an unseen-number benchmark.
See the [phone control audit](../reports/phone-extraction-control-v1/independent-audit.json)
for exact raw/canonical overlap counts.

## Future invocation against a ready service

Use the existing Python environment with the optional phone extra, or install
`.[phone]` in a separate environment. It supplies pinned `phonenumbers==9.0.14`
without installing a training stack. An email-only run needs no phone library.
The corpus hash checks require the matching frozen producer files in this checkout.

For example, after the completed 2B checkpoint and ready service have been
verified, set `CONTACT_CHECKPOINT_SHA256` to its hash from the checkpoint readiness
proof. The following command uses that explicit identity and an unused output
directory; it does not prepare or start the service:

```bash
: "${CONTACT_CHECKPOINT_SHA256:?Set the verified completed-checkpoint SHA-256}"
python -m scripts.evaluate_contact_service \
  --data-root data \
  --output-dir runs/contact-service-2b-test-ood-v1 \
  --endpoint http://127.0.0.1:8791/v1/systemone \
  --expected-model Qwen/Qwen3.5-2B \
  --expected-method lora_decision_head \
  --expected-revision 15852e8c16360a2fea060d615a32b45270f8a8fc \
  --expected-checkpoint-sha256 "$CONTACT_CHECKPOINT_SHA256"
```

Use a separate run and the corresponding model/revision/checkpoint pins for 9B
and 27B. `--corpora email` or `--corpora phone` selects one task family;
`--splits test` selects only test and makes that restriction explicit in evidence.

The offline CPU [tokenizer preflight](../reports/contact-service-eval/tokenizer-lengths.json)
checked all 1,924 A requests and all 3,192 possible phone B requests under each
of the three pinned model tokenizers and the serving chat template. Each model
had 27,872 candidate sequences, ranging from 570 to **1,208 tokens**, with zero
over 4,096. This provides input-length evidence for the new corpora; it neither
predicts which B requests a model will select nor measures model quality.
The [raw length archive](../reports/contact-service-eval/tokenizer-lengths-raw.json.gz)
and [archive audit](../reports/contact-service-eval/tokenizer-archive-audit.json)
retain independently checkable lengths. No 16K service change is required by
these contact inputs.

## CPU software verification

```bash
runs/phone-extraction-control-v1-venv/bin/python -m unittest tests.test_contact_service -v
python3 -m unittest tests.test_contact_service -v
```

The phone-extra environment passed all **23 tests**. The base environment without
the optional library passed 17 and explicitly skipped six phone-dependent tests.
Fixtures cover real-pipeline control flow with simulated transport: wrong-role
copy/format, repeated values at different offsets, miss/none, actual B binding,
raw HTTP error bytes, malformed JSON/probabilities, identity changes, forced
choices, interrupted denominators and report classification. All fixture
artifacts live in temporary directories and are discarded.

The [CPU execution evidence](../reports/runtime-checks/contact-service-evaluator-cpu.json)
records commands, versions and source hashes. These tests did not make network
requests, start a model or produce a real-service model-quality report. The
frozen generators, API, recipes, manifests and corpora are unchanged by this
addition.
