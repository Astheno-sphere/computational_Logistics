# IR evidence bundle

The full original corpus has 200 families, 400 queries, 8,800 request cases and
11,600 typed records. The independent body audit passes. Six complete runtime
algorithms and the graded metric/holdout loader are implemented. The independent
IR config is [published and anonymously verified](../ir-data-release-20260920/README.md).
**Hosted TREC evaluation is complete:** Jev 1.13.0, GPT-5.6 Luna and GPT-6 Astra
have audited results on all 97 DL19/DL20 queries. Released Open-Jev TREC results
remain pending. See the [TREC protocol and results](trec-holdout/README.md) and
[unified benchmark index](../../docs/benchmarks.md). No training on this corpus is claimed.

| Evidence | File |
| --- | --- |
| Original-source task interfaces and timing definitions | [source-code-research.json](source-code-research.json) |
| Visually inspected tweet table, author-reported only | [tweet-table-provenance.json](tweet-table-provenance.json) |
| Full dataset counts and file hashes | [manifest.json](manifest.json) |
| Labels re-derived from final text | [independent-audit.json](independent-audit.json), [verify.py](verify.py) |
| Pilot/full split preservation | [stable-split-verification.json](stable-split-verification.json) |
| Original frozen pilot source | [pilot-source/ir_data.py](pilot-source/ir_data.py) |
| 17 passing tests, no errors/failures/skips | [test-verification.json](test-verification.json), [test-output.txt](test-output.txt) |
| Real Jev pilot ranking replay | [jev-pilot-ranking.json](jev-pilot-ranking.json), [evaluate_pilot.py](evaluate_pilot.py) |
| Separate arithmetic check from raw fields | [pilot-ranking-arithmetic-check.json](pilot-ranking-arithmetic-check.json) |
| Correct linear-gain TREC metric provenance | [trec-ndcg-source.json](trec-ndcg-source.json) |
| Pending external input/evaluation contract | [external-evaluation-contract.json](external-evaluation-contract.json) |

Full manifest SHA-256:
`5305dad7326fbf32aa006447137c5a3eb92872d90cde71302bc7efb39f882590`.
Frozen pilot manifest SHA-256:
`beb827c63486e776d6d1abc0d178f557394dbebe57de72523ff4c3112f17d73b`.

The pilot's 132 real HTTP responses contain 174 typed decisions across only
6 queries / 3 correlated system families. Pointwise/listwise replay uses
8 candidates per query. The probability-mass-strict nDCG@10 results are Noul
0.974823, pointwise Score 0.833333, listwise Choice 0.940929 and listwise Score
1.0. Pointwise Score has 5/6 complete queries; the one invalid 0.99 probability
vector makes its query contribute zero. Two-decimal scalar/probability rounding
uses a separately declared consistency bound, without normalizing responses.
Pairwise/setwise fixed local probes cannot reconstruct an adaptive heap run.

Generation/audit manifests record the operations performed at generation time;
their `model_inference_performed: false` fields are not claims that no later
pilot model run exists. Raw provider outputs remain in
`runs/provider-comparison-20260920/jev-ir-pilot/`, bound by the ranking report.
All of this evidence is separate from the frozen 189-request comparison.

See the [data/runtime documentation](../../docs/ir-control-data.md) for commands,
label semantics, limitations and the external holdout contract.
