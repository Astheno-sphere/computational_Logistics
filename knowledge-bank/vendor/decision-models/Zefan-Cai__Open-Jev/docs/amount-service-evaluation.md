# HTTP evaluation of frozen amount controls

`python -m scripts.evaluate_amount_service` evaluates
`amount-extraction-control-v1` against an existing HTTP decision service. It
sends the original A request, builds B from A's actual selection, and retains
wire evidence and fixed held-out denominators. It does not start a service,
allocate GPUs, retrain a model or fit a temperature.

This addition has CPU software verification only, with no amount model-quality
result. The amount corpus was not in the pre-existing 2B/9B/27B training mixtures;
check future checkpoint provenance separately. GPU-backed execution must wait
for current training and its established final stages to release resources.

## Frozen population and routing

The default is all test and OOD cases, with no sampling or `max-cases` flag.
The manifest pin is
`6f89f81336ac36505c563193da27fca2155fa566175451854f0ac410979ea80b`.
The evaluator checks the manifest, every listed artifact and frozen producer
source before requests and rechecks them after the request loop. It also records
and rechecks evaluator/helper source hashes.

All family metadata is parsed for split separation and ID routing. Typed split
files are only hashed as bytes. Each case line's leading ID is decoded first;
the full JSON and references are decoded only when the indexed family belongs
to a requested test/OOD split. Neither training nor calibration/validation case
targets enter this loader or the request wire.

Ordering is `test`, then `ood`, then SHA-256 of `["group", group_id]`, then
SHA-256 of `["case", case_id]`, with compact canonical JSON hashing. References
and predictions do not choose order. `--splits test` or `--splits ood` makes an
explicit restricted run, recorded in its selection artifact.

The independent [held-out preflight](../reports/amount-service-eval/heldout-preflight.json)
establishes these populations:

| Population | Test | OOD | Total |
| --- | ---: | ---: | ---: |
| A documents | 224 | 640 | 864 |
| Unique populated requested targets | 168 | 480 | 648 |
| Exactly recalled unique targets | 140 | 400 | 540 |
| Unique target candidate misses | 28 | 80 | 108 |
| Target absent | 42 | 120 | 162 |
| Target ambiguous | 14 | 40 | 54 |
| Unique target with ready reference normalization | 84 | 240 | 324 |
| All possible candidate B requests | 1,036 | 2,960 | 3,996 |
| All candidates with defined reference credit | 966 | 2,760 | 3,726 |
| All candidates with undefined reference credit | 70 | 200 | 270 |

The last three rows describe the input corpus, not the B denominator of a
model run. A run sends at most one B request per A document, based on its actual
selection. Candidate recall is **540/648**. Reference-ready target coverage is
**324/648 = 50%**; this is separate from the candidate recall rate.

## Actual selection and conditional heads

A's wire body is the original `state` and `questions`, plus the routing `model`
alias. No label is added. If valid A chooses `none`, or A fails, B is skipped.
Otherwise B is exactly `amount_attributes(original_A, actual_selected_id)`.
The stored reference B request is never dispatched. Presence is scored
independently and does not gate B.

B declares currency Choice (`USD`, `EUR`, `GBP`, `review`), direction-known
Noul and credit Noul. All declared heads must pass protocol validation,
including the credit probability on unknown-direction cases. Noul values must
be finite numbers in `[0,1]`, and use the fixed threshold `p >= 0.5`. Choice
probabilities must cover exactly the offered options, sum to one, carry correct
confidence, and identify an actual maximum; ties preserve the service's choice.
Noul counts as one serving sequence despite having two probability outcomes.

**Raw credit accuracy is conditioned on the actual candidate's reference
direction being known.** It remains in that denominator even if the model
predicts unknown. An undefined reference credit is `null`, never `false`, and
is excluded from credit accuracy and from the joint defined-head comparison.
Any protocol-valid credit probability gives the same semantic score when that
reference head is undefined.

**Normalization uses the predicted direction-known flag.** When it is false,
the evaluator passes `is_credit=None`; when true, it passes the thresholded
credit prediction. It never uses the reference-known flag to gate execution.
The existing normalizer checks the actual source span and public grammar,
retains exact Decimal strings, and refuses partial amounts, unknown attributes
or sign/flow conflicts. Reference data is used for scoring, not for repair.

## Metrics and failures

| Metric | Denominator and successful outcome |
| --- | --- |
| `a_presence`, `a_span` | Every selected document; correct corresponding raw A head |
| `a_nonforced_span`, `a_forced_span` | Separate cases with alternatives versus no candidates; even forced `none` requires a valid response |
| `a_span_on_recalled` | All exactly recalled unique targets, retaining failed calls |
| `a_none_target_absent`, `a_none_ambiguous_target`, `a_none_candidate_miss` | Separate reference-none strata; a correct miss/none does not extract a value |
| `b_currency_on_actual_selection`, `b_direction_known_on_actual_selection` | A-valid actual non-`none` selections, including wrong-role and partial candidates; failed/pending B is zero |
| `b_is_credit_on_reference_known_actual_selection` | Those actual selections with reference-known direction, independent of predicted direction-known |
| `b_defined_attributes_joint_on_actual_selection` | All actual non-`none` selections; currency and direction-known correct, plus credit correct only where reference-defined |
| `exact_raw_span_on_unique_target` | All 648 unique targets by default; actual ID, original text, start and end must match |
| `final_value_on_unique_target` | The same 648 targets; exact span, correct defined B heads, ready guard and exact `(currency, Decimal string)` pair |
| `complete_output_on_unique_target` | Final-value success plus positive A presence |
| `normalized_pair_on_reference_ready_target` | The fixed 324-target reference-ready subset; the same success condition as final-value accuracy |

The full unique-target metric keeps misses, unknown direction, unsupported
currency, review, errors and pending cases in its denominator. Its structural
ceiling in this control corpus is 50%; the separate reference-ready subset
reports extraction success where normalization is defined. Neither metric
counts `None == None`, miss/none, or matching review outcomes as extracted
values. A wrong-role amount can normalize correctly and still fail both.

`reference_ready` reports the fixed subset and coverage over unique targets.
`actual_b_undefined_credit` reports selected candidates whose credit reference
is undefined. `b_not_attempted` and `b_eligible_status_counts` distinguish A
skips from B failures. Guard execution, ready/review status and reasons are
reported separately; guard acceptance alone is not requested-target success.

HTTP, JSON, schema, identity and pipeline failures remain in their stated
populations. B failure preserves valid A scoring. Interruption keeps every
selected document in the report and outcome artifacts, including pending
documents. Request bytes are written before transport; response bytes are
retained whenever transport returns them.

## Identity and saved evidence

Expected model, supported method and exact 40-character base revision are
required. LoRA runs also require a 64-character checkpoint SHA-256. An optional
temperature pin checks a supplied value without fitting it. The first valid
metadata locks the service identity before answer-schema validation; model,
method, revision, checkpoint, temperature, code commit and context limit must
remain stable. This checks self-reported identity against expected pins; it is
not independent authentication of loaded weights.

A fresh output directory contains `selection.json` (ordered IDs, input and
implementation hashes, scope and configuration), `references.jsonl` (held-out
references), `requests.jsonl` (original JSON, base64 bytes and hashes),
`attempts.jsonl` (HTTP status, errors, raw response bytes and timing),
`outcomes.jsonl` (A/B predictions and guard outcomes) and `report.json`
(overall and split metrics, identity and limitations). Existing outputs,
symlinks and destinations within the immutable data root are rejected.

`is_model_quality_evidence` is true only for a completed HTTP-mode run with a
validated stable identity. Explicit fixture transports, errors, interruptions
and integrity failures are false. A clean completed run may still have low
semantic accuracy. Incomplete runs exit nonzero; any chosen rerun requires a
new output directory.

## Future invocation and CPU checks

The evaluator needs the base Python package; it does not require the optional
phone library or a training stack. After verifying a ready 2B service and the
completed checkpoint's hash, for example:

```bash
: "${AMOUNT_CHECKPOINT_SHA256:?Set the verified completed-checkpoint SHA-256}"
python -m scripts.evaluate_amount_service \
  --data-root data \
  --output-dir runs/amount-service-2b-test-ood-v1 \
  --endpoint http://127.0.0.1:8791/v1/systemone \
  --expected-model Qwen/Qwen3.5-2B \
  --expected-method lora_decision_head \
  --expected-revision 15852e8c16360a2fea060d615a32b45270f8a8fc \
  --expected-checkpoint-sha256 "$AMOUNT_CHECKPOINT_SHA256"
```

Use separate outputs and corresponding verified identity pins for 9B and 27B.
The CPU [tokenizer preflight](../reports/amount-service-eval/tokenizer-lengths.json)
checked all 864 A and all 3,996 possible B requests with each pinned model's
serving chat template, including credit where unsupervised. Each model had
29,700 serving sequences, ranging from **817 to 1,162 tokens**, with zero over
4,096. This measures input length, not selected B paths or model quality.

```bash
python3 -m unittest tests.test_amount_service -v
```

All **24 focused CPU tests** pass. They use small synthetic fixtures and mocked
transports, covering actual B binding, wrong offsets/roles, conditional credit,
exact signs/long Decimal values, review semantics, B failures, stable identity,
nonheldout target isolation, interruption and output protection. Temporary
fixture artifacts are discarded. The
[execution record](../reports/runtime-checks/amount-service-evaluator-cpu.json)
records source hashes and commands. No model was started, no GPU was used and
no full-heldout fake model evaluation was run. Frozen producers, API, recipes,
manifests, corpora and the contact evaluator remain unchanged.
