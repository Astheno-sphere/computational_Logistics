# Detect a failed operation from its response body

`silent-failure-control-v1` contains **9,600 original response bodies**, grouped
into 400 provider/contract families and 4,800 success/failure counterfactual
pairs. All 9,600 labels passed an independent audit that parses the final body.
These are synthetic data and software checks: no training or model inference
was performed, and the frozen datasets and active training mixtures were not
changed.

The task follows the community integration in
[Vicente-MD/jev-resilience, pinned to c490e0d](https://github.com/Vicente-MD/jev-resilience/blob/c490e0dc7830758f84bd9d5acb806655e327113e/src/main/java/ai/jev/resilience/client/JevEvaluationService.java#L50-L55).
That integration sends the stringified response body as state and asks a single
Noul question. Its
[configured question key](https://github.com/Vicente-MD/jev-resilience/blob/c490e0dc7830758f84bd9d5acb806655e327113e/src/main/java/ai/jev/resilience/config/JevResilienceProperties.java#L27-L31)
is `is_silent_failure`. Our question wording, generator, bodies and annotations
are independently authored. No community source code or example data was
imported into the implementation or corpus. Generated data are CC0-1.0 and use
fictional providers under `.example`.

## Runtime contract

```python
from jev.silent_failure_data import silent_failure_request

body = '{"success":true,"terms":"A receipt ID is required.","receipt":{}}'
request = silent_failure_request(body)
# {"state": <the exact original body string>,
#  "questions": {"is_silent_failure": {"type": "noul", "instructions": ...}}}
```

The builder preserves the body string, including whitespace and Unicode, and
compiles through the existing `jev.api.compile_request`. Its sole Noul has the
usual `no`, `yes` options. The model predicts the probability of a current
failure. Training targets are `[1.0, 0.0]` for no and `[0.0, 1.0]` for yes.

HTTP 200 is the surrounding integration's transport condition; no status code,
request wrapper, oracle output or generation metadata is added to model state.
Judge timeouts, authentication failures and malformed judge replies do not
supply negative training labels. In particular, the community implementation's
fallback to `0.0` when its judge is unavailable is software behavior, not a
ground-truth judgment about the response body.

The builder accepts nonempty strings and does not parse or label their contents.
The independent auditor is an offline checker for this corpus's controlled
grammar, not a general-purpose production failure detector.

## What establishes a label

A positive label requires visible evidence of a current failed operation or an
unmet requirement stated in the body. An optimistic `success: true` field does
not override a current rejection, absent required output or failed required
checks. A historical error, quoted diagnostic text or legitimate empty result
is insufficient by itself.

Each family contains one pair of each of the following controls. Every row's
target can be derived from its body without the pair name or family metadata.

| Pair | Nonfailure body | Failure body |
| --- | --- | --- |
| Maintenance HTML | Maintenance ended and the requested document is returned | Maintenance is active and the document is absent |
| Sign-in HTML | Requested document is present; sign-in text is informational | Sign-in page replaces the requested document |
| Business reservation | Current reservation is confirmed | Current reservation is rejected despite a success claim |
| Required receipt | Required nonempty `receipt_id` is present | Receipt is null/empty, or its required ID is null, empty or whitespace |
| Empty search | Search completed with zero matches | Search did not execute and reports a current error, also with zero matches |
| Current versus history | Earlier failure and current completion | Earlier completion and current failure |
| Quoted diagnostic | Requested document contains quoted error text | Document retrieval failed; the quoted example remains visible |
| Asynchronous work | Work entered the queue with a job ID; final output is not yet required | Work was rejected and no job ID exists |
| Partial batch | A smaller nonempty result is explicitly permitted | The same returned items violate an all-items requirement |
| Check counts | All current checks passed despite archived failures | Current required checks failed despite a success claim |
| Cached revision | Delivered revision meets or exceeds the stated minimum | Cached revision is below that minimum |
| Complete segments | Every requested segment is delivered | Delivered count is below the stated requirement |

For empty receipts, the requirement is explicitly present in the body. A bare
`{}` or acknowledgment without such a requirement is ambiguous and receives no
synthetic label here. The audit rejects unsupported or contradictory grammar
instead of interpreting it as a negative example. Only generated, fully
specified controls enter the five split files; no scraped bodies or ambiguous
examples were filtered after looking at a model result.

## Splits and diversity

There are 6,400 JSON, 1,600 HTML and 1,600 plain-text bodies, with exactly 4,800
positive and 4,800 negative targets. All 24 bodies of a fictional provider and
contract family stay together. Each counterfactual pair shares an opaque request
ID and differs in operational evidence. IDs do not contain labels or pair names.
Complete JSON/HTML/text fields and history events are ordered using a
deterministic seed without selecting permutations by label or outcome.

| Split | Families | Bodies | No | Yes |
| --- | ---: | ---: | ---: | ---: |
| Train | 268 | 6,432 | 3,216 | 3,216 |
| Calibration | 11 | 264 | 132 | 132 |
| Validation | 15 | 360 | 180 | 180 |
| Test | 26 | 624 | 312 | 312 |
| OOD | 80 | 1,920 | 960 | 960 |

The 320 in-distribution families use English bodies, two JSON envelope schemas,
HTML paragraphs and text response records. Whole-family hashing assigns their
splits. OOD reserves 80 additional families with Chinese requirements and
operational wording, JSON entry arrays or a differently nested delivery schema,
HTML definition lists, and a Chinese text receipt layout. Provider identities,
request identities, counterfactuals and reserved layouts do not cross splits.
Low-level JSON business fields such as `receipt_id` remain shared where that is
part of the API's visible contract.

These are controlled template, schema and language shifts. The 9,600 records are
not 9,600 independently observed real API behaviors, and passing the data audit
does not establish generalization to arbitrary services.

## Reproduce and inspect

Use a fresh output directory; generation refuses to overwrite a nonempty
directory or follow an output symlink.

```bash
python3 -m jev.silent_failure_data \
  --output-dir data/silent-failure-control-v1 --groups 400 --ood-groups 80 --seed 42
python3 -m jev.data validate data/silent-failure-control-v1
python3 reports/silent-failure-control-v1/verify.py \
  --data data/silent-failure-control-v1 \
  --output reports/silent-failure-control-v1/independent-audit.json \
  --audit-rows data/silent-failure-control-v1/body-derived-audit.jsonl
python3 -m unittest tests.test_silent_failure_data -v
```

The generated directory contains the five standard JSONL splits and
`manifest.json`; the optional audit file contains one body hash and independently
derived decision/evidence record per body. It is not a training input. The
repository ignores `data/`, so generation does not silently publish these files.

The [tracked manifest](../reports/silent-failure-control-v1/manifest.json) binds
all five split hashes and the generator, shared API/schema and independent
auditor source hashes. The
[independent audit](../reports/silent-failure-control-v1/independent-audit.json)
recomputes every label, provider/request grouping, pair completeness, split
assignment and reserved layout from the final files. The auditor never imports
the generator or its label construction code.

The [build record](../reports/silent-failure-control-v1/build-verification.json)
records the exact generation and audit commands. The
[test record](../reports/silent-failure-control-v1/test-verification.json)
records 17 passing tests, including target corruption after checksum resealing,
cross-split pair leakage, input-wrapper rejection, unknown/ambiguous grammar,
historical/current swaps, valid empty results, partial-result permission,
queued jobs and deterministic byte-for-byte regeneration of a smaller corpus.

Future model evaluation should report accuracy, macro F1 and Brier score,
failure recall by failure type and format, and false-positive failure rates on
empty, recovered, quoted-error, queued and permitted-partial responses. Judge
timeouts and parse failures need separate operational counts. No such model
metrics are claimed by this data release.
