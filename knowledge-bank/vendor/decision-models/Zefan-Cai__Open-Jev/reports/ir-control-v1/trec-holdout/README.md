# TREC holdout protocol and results

These files are text-free provenance, structural checks and the recorded conversion source for TREC-DL19/DL20. Actual query/passages/qrels remain in ignored `runs/external/ir-holdout`. They are not Open-Jev training data or an MIT/CC0 dataset release.

DL19 has 43 judged queries and 4,300 candidate occurrences; DL20 has 54 queries and 5,400. Every query has 100 unique candidate documents, official query text and complete qrels. Manifests contain pinned public download URLs, checksums, preprocessing and reuse terms. Candidate-source bytes match the pinned Hugging Face LFS digests; qrels and queries match the official-file checksums recorded by ir_datasets.

The preparation verification files contain arithmetic on downloaded BM25 rankings, not a new retrieval run. The frozen provider protocol and completed model results are recorded separately below.

`prepare.py` is the exact recorded converter snapshot. It expects the raw/source layout described by the manifests next to it, and execution from the Open-Jev checkout. Reproduce in a new isolated directory outside training data, placing the source snapshot there; it refuses to overwrite prepared outputs. Do not place restricted external passages in this public evidence directory.

## Frozen provider run protocol

The [provider evaluation plan](provider-evaluation-plan.json) freezes all 97
queries and 9,700 candidate occurrences before any provider call. The separate
[preparation record](provider-input-preparation.json) binds the input-only
artifact by SHA256. `scripts/prepare_trec_provider_input.py` uses tiktoken 0.11.0
with `decode(encode(text)[:limit])`: 32 query tokens and 128 passage-prefix
tokens. Ten passage occurrences introduce a replacement character at the
prefix boundary; five re-encode to 129 tokens. These source-style strings are
preserved identically across providers, without a second truncation.

`scripts/evaluate_trec_provider.py` runs the existing independently authored
`general-ir-v1` listwise Score method, with a 20-passage window and step 10.
Each complete query consumes nine requests, or 873 requests per provider for
the full dataset. Initial candidate text/order and the algorithm match across
providers; later windows depend on each provider's earlier rankings. OpenAI
returns integer Score levels while Jev supplies scalar expected scores. This
is not an exact reproduction of the author's prompts, gateway or historical
model. Open-Jev checkpoint token limits require their own preflight before
GPU evaluation.

The runner reads no qrels. It saves exact inputs, each request before calling,
each raw response, every selected query ID, and complete/failed/pending states.
Full qrels remain separate for later nDCG@10 calculation. All 43/54 judged
queries stay in each benchmark's denominator. No result is claimed here by
preparing or starting the runner.

Strict Jev validation retains a 1e-6 probability-mass tolerance and 0.035
rounded-Score expectation tolerance. The predeclared supplementary scalar
analysis may continue only for the exact mass-only error with valid model,
keys, finite values and expectation consistency. It uses the actual scalar,
never renormalizes vectors, marks the primary query invalid and stores its
supplementary ranking separately. Primary strict metrics must give such
queries zero contribution. All other errors fail the query.

Each provider runs sequentially, without retries, with at most 873 requests,
a 60-second timeout and three-hour run limit. OpenAI has a 2,048 output-token
limit and an $80 threshold based on returned usage estimates, checked before
the next request. The final request can cross that estimate threshold; unknown
costs are counted, and this is not an invoice cap. Budget or endpoint stops
retain pending queries. Jev costs are unknown at runtime, not zero. Actual
query latency and request latency are separate; a simulated CPU run is not
model-quality evidence.

```bash
python -m pip install tiktoken==0.11.0
python -m scripts.prepare_trec_provider_input \
  --output runs/external/ir-holdout/provider-listwise-score-v1
python -m scripts.evaluate_trec_provider \
  --input runs/external/ir-holdout/provider-listwise-score-v1/input.json \
  --input-sha256 cc7bc949dbc269dacb61bdb61fc8982db14bc4df3698f9d32f5f1c8b6795eb83 \
  --output runs/trec-jev-listwise-score-v1 --model jev-1.13.0
```

Use `TYPESAFE_API_KEY` or `OPENAI_API_KEY` through the environment, never source
or command arguments. Output directories must be new; the runner does not
resume or resubmit prior requests. Real passage/input/response bundles remain
outside public code and training releases.

## Completed Jev collection

The [offline summary](jev-listwise-summary.json) replays all 873 saved requests
and responses, their nine adaptive windows per query, and every full
100-document permutation. All 97 queries returned usable scalar scores.
However, 108 requests failed the predeclared probability-mass check, affecting
66 queries. Only 31 queries passed every strict check. HTTP success alone
does not establish typed-response validity.

| Benchmark | Queries | Downloaded BM25 | Jev strict nDCG@10 | Jev supplementary scalar nDCG@10 | Strict-complete queries |
| --- | ---: | ---: | ---: | ---: | ---: |
| DL19 | 43 | 0.505831 | 0.275836 | 0.728218 | 15/43 |
| DL20 | 54 | 0.479637 | 0.190667 | 0.715734 | 16/54 |

Each column uses the full 43/54-query denominator and full official qrels,
including judgments outside the candidate top 100, to compute ideal DCG.
Relevance grades are direct gains. Strict-failed queries contribute zero in
the primary column; the supplementary column uses the actual returned scalar
without modifying probabilities. The query-weighted combined values are
0.228422 strict, 0.721268 supplementary and 0.491249 BM25. The strict score
therefore reflects response validity as well as ranking quality; the scalar
score does not validate Jev's probability vectors.

The completed Luna and Astra collections are reported below.
Open-Jev TREC inference remains pending until the authorized GPU allocation
is available. Jev API cost is unknown, not zero; its collection has no
transport errors or retries.

The collector used Python 3.10 and local replay uses Python 3.14. Compensated
float summation introduced in Python 3.12 changes 25 derived diagnostic records
by at most 2.22e-16. The scorer accepts only an exact current or exact legacy
recomputation of the entire diagnostic list. It preserves the original raw
bytes, strict flags, IDs, scalar values and both validation tolerances; it
does not apply an approximate-equality escape hatch.

```bash
python -m scripts.summarize_trec_provider \
  --run runs/provider-trec-20260920/jev-1.13.0 \
  --holdout-root runs/external/ir-holdout/prepared \
  --output runs/jev-trec-offline-summary.json
```

The offline command makes no API requests. The published summary binds all
private snapshot files, frozen manifests and replay source by SHA256.
The [independent audit](jev-result-independent-audit.json) reconstructs all
873 windows and 17,460 Score heads without importing the runner, reranker or
scorer, and independently recomputes the metrics from the full qrels. Its
[verification source](verify_jev_result.py) is included for inspection.

## Completed Luna collection

[GPT-5.6 Luna with reasoning `none`](luna-listwise-summary.json) completed
all 873 requests and all 97 queries, with no transport or strict-validation
failures and no retries. It uses the same frozen initial candidates, token
prefixes and adaptive window algorithm. Later window payloads depend on the
provider's earlier rankings; Luna returns integer grades while Jev returns
expected scalar scores.

| Benchmark | Full query denominator | Luna strict nDCG@10 | Strict-complete queries |
| --- | ---: | ---: | ---: |
| DL19 | 43 | 0.729911 | 43/43 |
| DL20 | 54 | 0.702082 | 54/54 |

The combined query-weighted nDCG@10 is **0.714419**. The
[independent audit](luna-result-independent-audit.json) reconstructs all
17,460 raw integer grades and all 873 adaptive windows without importing the
runner, provider adapter, reranker or scorer. Every per-query score matches
the offline summary exactly. [Audit source](verify_openai_results.py) also
checks request/response identities, saved JSON schema and reasoning settings.

Returned usage totals 3,200,189 input tokens and 132,696 output tokens, with
zero cached or reasoning tokens and no unknown-cost requests. An independent
Decimal calculation gives a **$0.799273 standard-list usage estimate**, not
an invoice amount. This is separate from the earlier five small quality suites.

Open-Jev has no published TREC score in this snapshot. These results do not
establish an overall provider winner or reproduce the community demo's exact
prompts, model revision or gateway.

## Completed Astra collection

[GPT-6 Astra with reasoning `low`](astra-listwise-summary.json) completed
all 873 requests and all 97 queries, with no transport or strict-validation
failures and no retries. It uses the same frozen initial candidates and
adaptive window protocol; its later windows follow its own earlier rankings.

| Benchmark | Full query denominator | Astra strict nDCG@10 | Strict-complete queries |
| --- | ---: | ---: | ---: |
| DL19 | 43 | 0.736610 | 43/43 |
| DL20 | 54 | 0.714484 | 54/54 |

The combined query-weighted nDCG@10 is **0.724292**. The
[independent audit](astra-result-independent-audit.json) checks all 17,460
integer grades and 873 adaptive windows without importing the runner, provider
adapter, reranker or scorer. Every per-query score matches the offline summary
exactly. The unchanged [audit source](verify_openai_results.py) verifies the
request/response identities, saved JSON schema, reasoning settings and usage.

Returned usage totals 3,204,672 input tokens and 151,590 output tokens, including
18,174 reported reasoning output tokens. Cached input tokens and unknown-cost
requests are both zero. Independent Decimal arithmetic gives a **$39.62622
standard-list usage estimate**, not an invoice amount. This is separate from
the earlier five small quality suites and their costs.
