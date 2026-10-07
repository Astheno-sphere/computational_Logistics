# OpenAI categorical IR pilot ranking replay

The completed Luna and Astra IR responses support full rankings for three methods. This report adds **zero API calls** and uses only the frozen pilot test/OOD requests: six queries from three correlated synthetic system families, with eight candidate passages per query. It is not a TREC result or a broad IR benchmark.

| Model | Reasoning | Pointwise Noul nDCG@10 | Pointwise Score nDCG@10 | Listwise Score nDCG@10 |
|---|---|---:|---:|---:|
| gpt-5.6-luna | none | 0.933359 | 1.000000 | 0.996324 |
| gpt-6-astra | low | 0.933359 | 1.000000 | 1.000000 |

Every model/method combination completed 6/6 queries and placed a best-grade passage first in 6/6 queries. Per provider, all 132 saved HTTP responses and 174 typed decisions were audited; 102 requests containing 144 document decisions support these three full-ranking methods. The remaining Choice/pairwise/setwise outputs are retained in the original typed-decision quality report but do not establish a complete ranking.

Noul uses the actual Boolean response: true ranks before false. Score uses the actual returned integer level from 0 to 3. Equal signals retain the original candidate input order. Noul therefore has only two ordering levels: even completely correct Booleans cannot order the different relevance grades among false candidates. The 0/1 ordering keys are not probabilities. No probability vectors were fabricated or responses normalized.

nDCG uses direct qrel grades, matching `trec_eval ndcg_cut`, and keeps all six queries in the denominator. The candidate set is smaller than the cutoff of 10, so the metric covers all eight candidates. Qrels are passed only to evaluation, never to the reranker or provider payload. Candidate input order is deterministically shuffled synthetic order, not BM25.

These signals have different resolution from Jev's returned Noul probabilities or expected Score scalars. The figures support an account of the saved runs; they do not establish overall provider superiority. A single categorical listwise Choice winner cannot order the other seven candidates. Fixed pairwise and setwise probes lack the adaptive comparisons needed for full heap-based ranking. None is promoted into an invented full ranking here. No candidate permutations, repeat trials, latency measurement, or TREC evaluation were added.

`evaluate.py` verifies the frozen manifest, every corpus hash through the independent body auditor, provider suite hashes, request and payload identities, raw response equality, exact model and reasoning setting, one successful measured attempt per request, and categorical response types. It then replays the existing reranker with scalar envelopes and checks its output against stable categorical sorting. `verify.py` independently decodes the raw response text, sorts with explicit input positions, and recalculates all 36 rankings and nDCG values without importing the evaluator or API adapter.

Run from the repository root:

```bash
python3 reports/provider-comparison-20260920/openai-ir-ranking/evaluate.py
python3 reports/provider-comparison-20260920/openai-ir-ranking/verify.py
```

- [Results, per-query rankings, returned categorical signals, and input hashes](results.json)
- [Independent verification and report hash](verification.json)
- [Frozen pilot Jev ranking methodology](../../ir-control-v1/evaluate_pilot.py)
- [Original Luna typed-decision audit](../openai-gpt-5.6-luna-ir-pilot-audit.json)
- [Original Astra typed-decision audit](../openai-gpt-6-astra-ir-pilot-audit.json)

Raw API responses remain in the ignored run bundles. Public artifacts contain derived rankings and hashes, not API response IDs or credentials.
