# Drone snapshot service evaluation

`scripts.evaluate_drone_service` evaluates the three heads of the existing
drone adapter on independently generated, held-out snapshots. The reference is
the disclosed geometry/evidence rule in [drone-data.md](drone-data.md). No action
is executed. These measurements do not establish flight safety, collision
probabilities, physical target-loss truth, or closed-loop performance.

## Run and freeze

Start a model service separately, then run:

```bash
python -m scripts.evaluate_drone_service \
  --cases data/drone-control-v1/cases.jsonl \
  --endpoint http://127.0.0.1:8791/v1/systemone \
  --split test ood --parents-per-split 20 --variants-per-parent 3 --seed 42 \
  --expected-model Qwen/Qwen3.5-2B --expected-method lora_decision_head \
  --expected-revision 15852e8c16360a2fea060d615a32b45270f8a8fc \
  --output-dir runs/drone-2b-snapshots-v1
```

Use `--expected-checkpoint-sha256` to bind a particular checkpoint. Every service
must report an exact 40-character base revision, model, accepted scorer method,
positive calibration temperature, and candidate-sequence count; a trained
checkpoint must report its SHA-256. Optional code commit and context limit are
recorded and checked for drift. Noul contributes **one scoring sequence**,
although its answer space has two labels. Identity changes invalidate the
affected response. There are no retries, repaired answers, or teacher fallbacks.

The output directory must be empty or absent. Exclusive creation of its
selection file also prevents concurrent evaluators overwriting one another.
Source cases must match their sibling manifest's hash and count. Selection
validates unique IDs and rejects parent groups or identical requests crossing
splits. It ranks parent IDs by SHA-256 of seed/split/ID, then case IDs by
seed/ID, without consulting answers or derivations. Up to three variants of
each selected parent are retained. `--max-cases` truncates the round-robin
split/parent order and constitutes a different configuration.

Selected requests must exactly reconstruct `drone_request`, preserving mapping
and candidate order. Saved answers and derivations must match the disclosed
visible-state teacher. Before the first HTTP call, the evaluator writes the
entire selection, all selected wire requests and references, and a byte-exact
copy of the source manifest. The wire body contains only `model`, `state`, and
`questions`; gold labels and derivations are not sent to the service.

## Metrics and failure accounting

Every answer must satisfy the complete Choice/Score/Noul contract: exact head
coverage, required typed fields, finite probabilities, candidate coverage and
probability mass, a maximal-probability Choice selection, derived confidence,
and the Score expectation and legend. Missing/extra heads or typed fields,
booleans in numeric fields, non-finite values, and duplicate JSON keys are
rejected. All three heads must validate before any receives scoring credit.
The common `format_response` implementation supplies the derived-field formulas;
the evaluator does not replace the received probabilities or choices with its
formatted response.

| Metric key | Meaning and denominator |
| --- | --- |
| `maneuver` | Correct maneuver Choice among selected cases with at least two legal candidates |
| `forced_maneuver` | Correct Choice when exactly one maneuver is permitted; reported separately |
| `risk_level` | Correct **modal** Score level, among all selected cases; ties choose the lowest ordered index |
| `target_loss` | Correct evidence label after thresholding Noul at `>= 0.5`, among all selected cases |
| `complete_decision` | Maneuver, modal risk level and thresholded loss label all correct, among all selected cases, including forced maneuvers |

Each accuracy has `{correct, total, accuracy}`. HTTP/schema/identity errors and
pending cases remain in every applicable denominator and receive zero credit.
This complete decision is a match of three discrete reference labels, not exact
equality of a probabilistic proposal with a one-hot teacher. In particular,
risk-level accuracy does **not** round the expected Score: probabilities
`[0.5, 0, 0.5]` have expectation 1 but modal level 0 under the declared tie rule.

`probability_metrics_valid_only` uses only cases whose **entire response** is
valid, with `valid_cases`, `selected_cases`, and `coverage` alongside every set of
averages. It contains:

- `risk_brier`: summed squared error over the three level probabilities versus
  the one-hot reference, not the mean over classes.
- `risk_scalar_absolute_error` and `risk_scalar_squared_error`: mean absolute
  and squared error of the returned expected Score against the integer grade.
- `target_loss_brier`: mean `(P(true) - y)^2`, the scalar binary convention.
- `risk_mean_probabilities`: mean returned probability for each level.

With zero valid cases, these averages are `null` and coverage is zero for a
nonempty selection (`null` for a split with no selected cases). Failed
cases are never inserted as zero probability error. Consequently, low error at
low coverage must not be presented as overall model quality. `risk_level_counts`
separately gives the reference distribution over all selected cases and modal
predictions over valid cases. Reference maneuvers and target-loss counts are
also retained. All metrics are reported overall and separately for test/OOD.

The frozen 500-parent source build currently selects 120 requests from 40
parents: 60/20 per split. Main maneuver denominators are 115 overall, 59 test,
56 OOD; forced maneuver denominators are 5 overall, 1 test, 4 OOD. The other
three accuracy denominators are 120 overall and 60 per split. These are counts
checked before model inference, not model results.

| Frozen input | SHA-256 |
| --- | --- |
| Cases | `d4ca0d575186dca4f6f0e04e113c14aaa6dadde1fcdad2ae98746600409bb107` |
| Source manifest | `6eefc11815640ad9ded3d6846fdc4483b8c867d270e8852835e8d0cb7cb7066a` |
| Default selection | `4d33a8347cf75fb329d2d3f0adf8c2238f62f0b1b78a97c3e5c281e7bc6a0845` |

## Artifacts and interruption

`selection.json` records configuration, case identities, thresholds, source and
evaluator hashes, plus hashes of imported runtime/helper modules.
`source-manifest.json` preserves the original manifest bytes. `requests.jsonl`
contains every selected exact JSON body and its SHA-256; `references.jsonl`
contains the corresponding saved answers and visible-rule derivations.
`outcomes.jsonl` preserves each completed attempt's HTTP status, elapsed time,
raw response bytes as base64 and their hash, parsed response, identity, errors,
discrete decision, typed proposal and per-case measurements. Partial transport
bodies are retained when supplied by the HTTP exception.

`report.json` is updated after each outcome. `attempted_cases` counts dispatched
attempts; `completed_attempts` counts recorded outcomes. `pending_cases` includes
an interrupted in-flight attempt as well as undispatched cases, while
`not_dispatched_cases` counts only the latter. These unresolved cases keep their
accuracy denominators but have no valid-only probability measurement. Check
`complete` before interpreting results; a partial report is not a finished run.

Exit 0 means all cases completed without HTTP/schema/identity errors, even if
their predictions were wrong. Exit 1 means all completed with at least one such
error; exit 2 indicates a configuration/source/artifact failure. Interruption
propagates after saving an interrupted report. Preserved partial output cannot
be overwritten by another run.

## Offline verification

```bash
python -m unittest discover -s tests -p test_drone_service_eval.py -v
```

Tests mock the HTTP transport in memory. They start no server, perform no
network request or GPU inference, and produce no claimed model results. Parent
variants are correlated, and all references share the disclosed synthetic
generator; reported accuracy is not broad real-world flight evidence.
