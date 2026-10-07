# Compare Open-Jev, Jev and OpenAI on saved cases

This comparison has separate latency and quality tracks. The 11-workload
[latency experiment](inference-latency.md) does not cover every use case.
`scripts/build_provider_suite.py` indexes **73,333 frozen test/OOD decision
rows across 23 task-source identifiers** without changing training data. Its
first coverage pass contains 146 labelled requests plus all 43 existing saved
example requests. The examples have no new gold labels: response validity and
latency are measured, but they do not contribute to accuracy.

Two cases per source/split/task-type stratum are selected by a fixed SHA256
ordering before observing any provider result. This small deterministic suite
is a coverage check, not a representative population estimate. Some selected
rows share a family. Full test/OOD evaluation remains a separate pending stage.
The standalone JF100 suite preserves all 100 items and three option rotations;
TREC DL19/DL20 reranking remains a separate IR holdout. Neither enters training.

## Provider contract

For the fixed saved-case suites, all providers receive the same state, question,
candidate descriptions and order. The typed-row adapter checks byte-identical
candidate prompt round trips. TREC uses the same initial candidates, then its
later windows adapt to each provider's earlier rankings.
Targets, group labels, generation metadata and rationale remain in a separate
gold file. Snapshot choices do not establish complete game, browser or flight
success; those require closed-loop environment evaluation.

OpenAI Responses uses strict JSON Schema and returns a Choice key, a Boolean
Noul, or an integer Score level. It does not generate probability vectors.
The models are **GPT-5.6 Luna with reasoning `none`** and **GPT-6 Astra with
reasoning `low`**. These settings are supported by the official model pages;
only aliases were listed there at measurement time, so requests and returned
model IDs are recorded. They represent different quality/latency settings, not
an equal reasoning budget. Both completed the full 11-workload latency run:
220 measured requests and 33 warmups per model, with zero request errors.
Customer-service P50/P95 is 918.13/1443.13 ms for Luna and
1938.39/2375.71 ms for Astra. Their total standard list-price estimates for all
253 attempts are $0.027253 and $1.348982, respectively; these are not invoices.

The OpenAI timing covers full response completion and validation, including
generation, DNS/TCP/TLS and HTTP. Request-to-schema construction is outside its
timer; Open-Jev's Predictor timer includes compilation. Every remote request
uses a fresh connection, concurrency one, and no retries. Server-side automatic
prompt caching may still apply; returned cached-token usage is retained.
Client location, output token limits, reasoning settings and full request
payloads are recorded. OpenAI outputs are not substituted into the trained
decision head or treated as calibrated probabilities.

Actual input, cached input, output and reasoning-token usage are retained where
returned. Cost is a standard list-price estimate, not an invoice: Luna
$0.20/$0.02/$1.20 and Astra $10/$1/$50 per million input/cached-input/output
tokens for this short-context workload. The captured official sources are
[Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna),
[Astra](https://developers.openai.com/api/docs/models/gpt-6-astra),
[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
and [Responses](https://developers.openai.com/api/reference/resources/responses/methods/create),
accessed September 20, 2026.

## Quality accounting

`scripts/summarize_provider_quality.py` counts failed decisions as zero and
keeps unattempted cases pending. One-hot targets contribute to hard accuracy;
soft targets contribute their selected probability mass to expected accuracy
and are excluded from hard accuracy. Score is compared by discrete most likely
level here, not by expected numeric score. No fabricated one-hot model
probabilities are used for Brier, calibration or likelihood metrics.

The first Jev coverage run completed all 189 requests with HTTP 200. Four
responses had probability mass 0.99 and failed the predeclared strict 1e-6 mass
check; three were labelled cases. Original errors and raw probabilities are
retained. A separate categorical-only analysis accepts those three usable
finite choices, without renormalizing their probabilities or claiming strict
probability validity. On the 140 hard targets Jev answers 117 correctly; six
soft-target cases are separate. This is the small coverage suite, not all
73,333 rows.

The existing 2B/9B release evaluation contains byte-bound predictions for 82
of these same selected rows (76 hard, six soft). Historical predictions are
reused only after matching the whole row hash, checkpoint hash, target and
audited prediction-file hash. They supply quality evidence and no new latency.
On those **same 76 hard cases**, Open-Jev 2B scores 65, Open-Jev 9B scores 72,
newly measured Jev scores 66, GPT-5.6 Luna scores 60, and GPT-6 Astra scores 71.
The 64 newer selected rows still require
Open-Jev inference. Do not compare the 82-row and 146-row denominators.

The new Jev JF100 run completed all 300 rotations with 232 correct categorical
answers; two responses had non-unit probability mass and are explicitly
identified in the separate decision-only analysis. Further independent probes
cover all integers 1–100 in FizzBuzz (299/300 typed decisions correct) and
132 controlled IR requests (165/165 hard decisions, nine soft targets). The
IR probe covers six original query instances and is not TREC evaluation.
These additional suites do not alter the frozen 189-request coverage pass.
The completed original OpenAI stages used 721 requests per model: coverage,
JF100, IR and FizzBuzz. All returned valid structured decisions with zero request
errors. Reference matches are:

| Suite | Open-Jev 2B | Open-Jev 9B | Jev 1.13.0 | GPT-5.6 Luna (none) | GPT-6 Astra (low) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Same hard coverage cases | 65/76 | 72/76 | 66/76 | 60/76 | 71/76 |
| Broader hard coverage | 64 pending | 64 pending | 117/140 | 109/140 | 135/140 |
| JF100, three rotations | Pending | Pending | 232/300 | 227/300 | 300/300 |
| Graded IR pilot | Pending | Pending | 165/165 | 160/165 | 165/165 |
| FizzBuzz | Pending | Pending | 299/300 | 300/300 | 300/300 |
| Multilingual mailroom | Pending | Pending | 908/921 | 900/921 | 913/921 |

The first row reuses the verified historical 2B/9B predictions. Their 76
completed hard coverage cases are a subset of the broader 140; the other 64
remain unattempted. These fractions measure agreement with frozen references;
the label audit below documents why some references are not unique answers.
JF100 rotations and controls within a family are correlated, so these totals
are not counts of independent problems.

The original multilingual mailroom probe contains 87 requests, 957 runtime
questions and 921 labelled decisions; 36 inapplicable category questions remain
in the requests but have no gold. Jev and Luna have completed all 87 requests
with valid responses. Astra also completed all 87, matching 913/921 references.
Across the five suites, each OpenAI model made 808 requests; all **1,616**
completed successfully. Saved response hashes, frozen gold identities and
all ten aggregates passed a [local recheck](../reports/provider-comparison-20260920/completed-openai-verification.json).

Standard list-price cost estimates from actual returned usage are shown below;
these are not invoices and exclude latency runs:

| Quality suite | Luna estimate (USD) | Astra estimate (USD) |
| --- | ---: | ---: |
| Coverage | 0.03442948 | 1.83997 |
| JF100 | 0.04262940 | 2.20712 |
| IR pilot | 0.015046 | 0.74017 |
| FizzBuzz | 0.0108868 | 0.51095 |
| Mailroom | 0.0312876 | 1.50899 |

The common Noul decision rule is argmax of `[1-p, p]`, with exact ties selecting
false. No probability vector is invented for OpenAI's categorical decisions.

A [ranking replay](../reports/provider-comparison-20260920/openai-ir-ranking/README.md)
uses the existing IR outputs without further API calls. On the six queries,
Luna/Astra nDCG@10 is 0.933359/0.933359 for Boolean pointwise Noul,
1.000000/1.000000 for integer pointwise Score, and 0.996324/1.000000 for
listwise Score. Equal outputs retain candidate input order. Boolean Noul
cannot rank different relevance grades within each true/false group; these
signals differ in resolution from Jev's probabilities and expected scores.
A categorical Choice winner does not define a full ranking. All 36 reconstructed
rankings passed independent checks.

The separate [real TREC evaluation](../reports/ir-control-v1/trec-holdout/README.md)
now has a completed Jev collection: 97 queries, 873 HTTP-successful requests.
108 requests failed strict probability-mass validation, so 66 queries contribute
zero under the predeclared strict metric. DL19/DL20 nDCG@10 is
**0.275836/0.190667 strict**, and **0.728218/0.715734** in the separately declared
actual-scalar analysis. Downloaded BM25 is 0.505831/0.479637. All metrics use
full official qrels and the full 43/54 query denominators. This independently
authored listwise Score protocol is not an exact community-demo reproduction.
Luna also completed all 97 TREC queries and 873 requests, with no transport or
strict-validation failures. Its DL19/DL20 nDCG@10 is **0.729911/0.702082**;
the [independent audit](../reports/ir-control-v1/trec-holdout/luna-result-independent-audit.json)
reproduces every query score and the **$0.799273** usage-based cost estimate.
Astra also completed all 97 queries and 873 requests, with no transport or
strict-validation failures. Its DL19/DL20 nDCG@10 is **0.736610/0.714484**;
the [independent audit](../reports/ir-control-v1/trec-holdout/astra-result-independent-audit.json)
reproduces every query score and the **$39.62622** usage-based cost estimate.
Open-Jev TREC inference remains pending. A separate
[local collector and offline replayer](openjev-trec-followup.md) now supports
the frozen 97-query protocol, with strict probability and identity validation,
unrounded expected Scores, full official qrels and failure-preserving journals.
Its CPU checks do not constitute new model results. These Open-Jev TREC follow-up
evaluations remain pending. The separate [JevBench public-subset evaluation](jevbench-public.md)
is complete for all five model streams; it does not complete the pending Open-Jev
TREC run. The [benchmark index](benchmarks.md) keeps these scopes and results together.
The five earlier small quality suites and their costs above are unchanged.

The [live comparison](https://zefan-cai.github.io/open-jev/#comparison) separates
completed counts from unattempted decisions. The dedicated JevBench run does
not complete these earlier quality suites. A
[reviewed five-suite service runner](openjev-provider-quality-followup.md) is now provisioned:
808 requests and 1,841 labelled decisions per model, with frozen inputs and
per-response checkpoint identity checks. Its local and N1 CPU tests pass; it has not yet
produced new model results. The core, contact/amount and provider follow-up queues
remain pending under the updated execution order.
The existing results do not complete the 73,333-row frozen test/OOD registry. A separate
additive v2 registry includes the new IR and mailroom corpora: **107,922 held-out
rows across 25 source identifiers**. Its 209-request selection contains 166
labelled requests and the same 43 examples; it has not been evaluated.
Every old request, gold record and all 73,333 original registry lines remain
unchanged, verified in the [extension audit](../reports/provider-comparison-20260920/registry-v2-extension-audit.json).
The results above continue to use the original frozen suites.

A subsequent [label audit](../reports/provider-comparison-20260920/astra-error-label-review.json)
reviewed all 12 ViZDoom and both platformer decisions in this coverage suite,
plus one customer severity case. Two airborne platformer decisions have an
alternative action producing the same next state; all four ViZDoom movement
Choices depend on omitted policy constants. The eight ViZDoom Noul/Score
questions do state their required thresholds and remain in the analysis.
The customer case has a separate semantic ambiguity; it does not justify
automatically replacing its reference answer with a model's answer.

Original labels and primary scores remain frozen. A **post-hoc sensitivity
analysis** applies the same six technical exclusions to every provider.
Removing the customer case as well is a second, separately labelled analysis:

| Provider | Original broader coverage | Exclude six technical cases | Also exclude customer ambiguity |
| --- | ---: | ---: | ---: |
| Jev | 117/140 | 115/134 | 115/133 |
| GPT-5.6 Luna | 109/140 | 106/134 | 106/133 |
| GPT-6 Astra | 135/140 | 133/134 | 133/133 |

On the [common released-model slice](../reports/provider-comparison-20260920/common-case-label-sensitivity.json),
the same six exclusions yield 2B 60/70, 9B 67/70, Jev 64/70, Luna 57/70 and
Astra 69/70. These narrower post-hoc counts do not replace the original scores,
establish a corrected benchmark, or support population-level rankings.
Future task versions must specify the policy or accept equivalent actions
before evaluation; neither frozen training data nor current requests changed.

The [full-corpus repair inventory](../reports/provider-comparison-20260920/reference-repair-plan.json)
found 1,097 of 1,697 platformer Choice rows with a non-gold action producing
identical physical next state, reward and terminal status. It also found 3,031
ViZDoom movement Choice prompts with omitted policy parameters; their stored
labels all match the generating script, so this is not a count of incorrect
labels. The customer template occurs in 171 Score rows: one reviewed ambiguity
and 170 awaiting semantic review. These are shared rows in the two mixtures
and must not be counted twice. The report specifies a future separate task
version; no current data, label, model or score was changed.

## Reproduce

Build from the frozen local corpora, then use the environment variables
`TYPESAFE_API_KEY` and `OPENAI_API_KEY`. Never store keys in source or results.

```bash
python -m scripts.build_provider_suite --output data/provider-comparison-v1
python -m scripts.benchmark_jev_api_latency \
  --requests data/provider-comparison-v1/requests.json \
  --output runs/jev-coverage --warmup 0 --repetitions 1 --max-seconds 1800
python -m scripts.benchmark_openai_api \
  --requests data/provider-comparison-v1/requests.json \
  --model gpt-5.6-luna --output runs/luna-coverage \
  --warmup 0 --repetitions 1 --max-seconds 3600
python -m scripts.summarize_provider_quality \
  --gold data/provider-comparison-v1/gold.json \
  --samples runs/jev-coverage/samples.jsonl --categorical-only \
  --output runs/jev-coverage-quality.json
```

Create the expanded registry in a new directory without changing v1:

```bash
python -m scripts.build_provider_suite --output data/provider-comparison-v2 \
  --extra-corpus ir-control-v1 --extra-corpus mailroom-control-v1
```

The original frozen inventory includes Wikispeedia records whose redistribution
permission has not been confirmed. Both the full registry and the selected
request/payload/raw-response bundles can contain those records; do not publish
them wholesale. Publish per-source statistics, hashes and explicitly filtered
redistributable evidence. The public HF projection omits those original rows.

The [September 21 community research](community-research-20260921.md) maps new X
use cases to proposed data and benchmarks, with source and model-identity checks.
It does not add new model measurements. The [published comparison thread](https://x.com/Zefan_Cai/status/2101845509170417784)
contains the existing results and their limitations.
