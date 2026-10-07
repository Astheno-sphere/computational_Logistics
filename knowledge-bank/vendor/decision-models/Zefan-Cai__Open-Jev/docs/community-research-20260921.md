# Jev community cases, benchmark candidates and publication status

Research snapshot: September 21, 2026 UTC. This report adds source research and
evaluation proposals, not new trained capabilities or benchmark scores. The user
has since authorized the dedicated JevBench evaluation on N1 H100 GPUs 0–3,
followed by resuming 27B training; code preparation is not a completed run.

## Where the existing results are published

- [Website comparison](https://zefan-cai.github.io/open-jev/#comparison),
  [latency](https://zefan-cai.github.io/open-jev/#latency) and
  [released-model results](https://zefan-cai.github.io/open-jev/#results).
- [GitHub quality method and results](provider-comparison.md),
  [latency method](inference-latency.md),
  [full release-v2 evaluation](../reports/full-data-eval-n1-v1/README.md), and
  [TREC protocol and reports](../reports/ir-control-v1/trec-holdout/README.md).
- [Published X comparison thread](https://x.com/Zefan_Cai/status/2101845509170417784):
  the main post and 12 replies cover accuracy, latency, TREC, caveats and links.
  All 13 posts were verified through public post readback during this audit.

| Existing measurement | Open-Jev 2B | Open-Jev 9B | Jev | GPT-5.6 Luna | GPT-6 Astra |
| --- | ---: | ---: | ---: | ---: | ---: |
| Same 76 hard-reference decisions, correct | 65 | 72 | 66 | 60 | 71 |
| Same 70 after excluding six ambiguous game references, correct | 60 | 67 | 64 | 57 | 69 |
| Customer-service latency P50, ms | 85 | Pending | 295 | 918 | 1,938 |
| 1,024 state tokens / 32 candidates latency P50, ms | 1,016 | Pending | 301 | 690 | 1,388 |

The 70-case sensitivity analysis is post hoc and uses identical exclusions
for every model. Its ordering differs from the primary 76-case result; neither
supports a claim that 9B generally beats Astra. Local 2B latency is warm H100
loopback HTTP with caching off, whereas hosted providers use HTTPS. Each
latency workload has 20 measured requests after three warmups at concurrency
one. This is deployment latency, not hardware-matched speed, throughput or
energy efficiency. The larger-candidate example is unfavorable to 2B.

Each released model completed **26,452** internal test/OOD decision predictions.
Test/OOD hard-label accuracy is **94.71% / 86.02% for 2B**, and
**97.54% / 91.97% for 9B**. These primarily synthetic reference-label scores
are distinct from task completion and external benchmark performance.
Jev, Luna and Astra completed the five small external quality suites and the
97-query TREC collection. Released Open-Jev measurements on those complete
suites and TREC remain pending. Earlier pilot checkpoint results must not be
relabeled as released-model results.

The publication audit found six missing GitHub evidence files referenced by
the live comparison JSON, plus stale training and legacy-summary status text.
The six original aggregate/decision-record files are restored byte-for-byte;
the repair changes no measured result. The original audit is retained as
[publication-check.json](../reports/community-research-20260921/publication-check.json).

## Search scope and evidence

This pass follows public links from
[JevGuide](https://github.com/2456868764/jevguide), linked source repositories,
the project's [earlier X inventory](community-research-20260920.md), and
[source follow-up](source-coverage-followup-20260920.md). Original post text was
checked through public FxTwitter representations. Authenticated Chrome search
was unavailable in this pass. This is a bounded source review, not an exhaustive
search of X; curator categories, post counts, and video summaries are not
independent verification. No third-party video was downloaded or reproduced.
Author-reported scores below are not our measurements.

Direct post checks and interpretation are recorded in
[x-direct-checks.json](../reports/community-research-20260921/x-direct-checks.json).

## Data additions worth prioritizing

| Priority and source | What to add to the decision data | How to evaluate it | Current coverage |
| --- | --- | --- | --- |
| P1: [CUAD contract review](https://x.com/matu79go/status/2101878714917429488) | A document page as state; 41 separate clause-presence questions, supporting-span references, difficult negatives and cross-page cases. | Micro/macro F1, per-clause precision/recall and page-level latency. A page-classification adapter is a derived task, distinct from official span extraction. | New legal-document task proposal. The post reports 820 decisions and comparison with Claude Haiku 4.5; not reproduced here. |
| P1: [IR community example](https://x.com/ShengyaoZhuang/status/2101212268440723895) and [RAG benchmark](https://github.com/emretheus/jev-rag-benchmark) | Relevance scores, answerability, evidence selection, irrelevant-but-plausible passages, contradictions and abstention. Keep training corpora separate from frozen public evaluation documents/queries. | TREC-DL and BEIR/SciFact ranking; XQuAD-derived retrieval plus answerability. Freeze retrieval candidates before comparing rankers. | Synthetic IR data and TREC infrastructure exist. Real-document training and full Open-Jev retrieval results are gaps. |
| P1: [Judge methodology](https://x.com/HamelHusain/status/2101533413010440593) | Response + evidence + explicit rubric as state; groundedness, compliance with rubric, pairwise preference, and abstention. Use independently checked human labels and adversarial minimal pairs. | Held-out human agreement, precision/recall on rubric violations, calibration and order sensitivity. A fast judge must first agree with humans. | New dedicated judge dataset/protocol proposal; generic workflow classification is insufficient evidence. |
| P2: [Unreal Tournament](https://x.com/loktar00/status/2101851403790512615) and [racing](https://x.com/edwartnoyola/status/2101799243811876866) | Simulator trajectories with legal dynamic actions, delayed rewards, weapon/target/navigation decisions, and lap feedback. Separate high-level planning from fast control. | Fixed seeds/opponents/maps, complete episodes, win/finish rate, lap time or score, timeouts, decision latency and total planner/controller cost. | Existing Snake/ViZDoom/etc. data are not UT99 or racing training. These are new environment proposals, not demonstrated capability. |
| P2: [Terminal suggestions](https://x.com/khajanpandey/status/2101837339387437384) | Synthetic command histories and task descriptions; select a relevant candidate or abstain, with near-match flags/path arguments and stale-history negatives. | Top-1, MRR and erroneous-selection rate on held-out templates/repositories. Evaluate selection offline. | New shell-history ranking proposal; avoid importing users' private histories. |
| P2: [Japanese complaint handling](https://x.com/aad34210/status/2101837143576662211) | Japanese/Korean customer-policy paraphrases, negation, mixed-language entities, escalation and multi-intent cases. | BANKING77/CLINC150 where applicable, plus a separately labeled multilingual policy holdout; macro F1 and out-of-scope rejection. | Extension of customer support, not a new domain merely because language changes. Existing mailroom data does not establish complaint-policy performance. |
| P2: [Dynamic browser actions](https://x.com/gregpr07/status/2100411066966749359) | Changing DOM/action candidates, stale elements, disabled buttons, goal-state checks and explicit typing fallback. | Complete browser tasks, invalid actions and end-to-end cost including fallback. | Browser data exist; a valid per-step action is not a successful browser task. |
| P2: [Tool-history compaction](https://x.com/tamarajtran/status/2100694549362553153) | Required facts and dependencies across tool traces, duplicate output, misleading recent content and token-budgeted retention. | Downstream answer/task preservation against retained-token fraction, not just keep/drop label accuracy. | 9,834 retention rows are already prepared; this is an evaluation/realism gap, not a new data-count claim. |

The current prepared corpus contains **408,884 rows across 25 source
identifiers**; source identifiers are not interchangeable with domain counts.
The released 2B/9B models each trained on the original **80,816-row** mixture.
Prepared expansion data must not be advertised as already learned by those
models. The new proposals above have not been generated or mixed into training.

For new data, retain a source/label provenance record and use the existing
state + question + dynamic candidates contract. Split by document, template,
environment/seed, or repository before generating related variants. Freeze
benchmark inputs/gold outside the training builders. Failure cases should be
retained in evaluation even when the public demo gallery contains successful
examples only.

## Benchmarks and models to compare

The newly authorized run targets the 231 public JevBench decisions;
[CPU preparation](../reports/community-research-20260921/jevbench-public-readiness.json)
pins all inputs and preserves upstream scoring. The full 534-decision leaderboard
includes unavailable private/judge items, so a public-subset run cannot claim
its full composite score. No JevBench measurement is reported in this snapshot.
The already frozen Open-Jev JF100, five-suite and TREC protocols remain pending.
Add the following separately
versioned comparisons rather than silently changing their inputs or denominators:

| Benchmark/protocol | Useful comparison | Metric and interpretation |
| --- | --- | --- |
| [JF100](https://github.com/softpudding/jev-frontier-100) | Released Open-Jev 2B/9B; pinned unmodified Qwen 2B/9B; Jev; Luna/Astra. | Accuracy across fixed option permutations and a declared reasoning budget. The new upstream reasoning-budget matrix is a separate upstream experiment, not a replacement for our frozen results. |
| [TREC-DL](../reports/ir-control-v1/trec-holdout/README.md), [BEIR](https://github.com/beir-cellar/beir), SciFact | BM25; Open-Jev; Jev; Qwen3-Reranker-0.6B/4B; BGE reranker; existing GPT baselines. | nDCG@10, MRR/recall and latency under an identical candidate pool. Preserve Jev strict failures and supplementary actual-scalar analysis separately. |
| [XQuAD/SciFact community RAG protocol](https://github.com/emretheus/jev-rag-benchmark) | Add explicitly named ZefanCai checkpoints as their own branches; preserve the original retrieval/gating ablations. | Ranking metrics and answerability precision/recall. Retrieval adapters need separate names from the original QA or fact-verification benchmark scores. |
| CUAD | Open-Jev; Jev; pinned Qwen bases; Luna/Astra; optionally reproduce the author's Haiku setting when available. | 41-label page classification F1 plus page latency and cost; official span extraction requires a separate extraction-capable protocol. |
| BANKING77 / CLINC150 | Open-Jev; Jev; Qwen bases; embedding or dataset-supervised classifiers; Luna. | Macro F1, accuracy and out-of-scope rejection. Do not label a baseline that trained on BANKING77 as unseen-task zero-shot. |
| BFCL-style tool selection | Open-Jev versus Jev/Qwen/GPT under the same tool catalog. | Tool choice, argument selection and abstention; a candidate-restricted adapter does not earn a full BFCL function-generation or multi-turn score. |
| Human-labeled judge and closed-loop games | Human/heuristic reference; Jev; Open-Jev; Qwen and gpt-oss-20b where appropriate. | Human agreement for judging; episode success and full pipeline latency for games. Do not mix snapshot accuracy with these metrics. |

The highest-value ablation is **our released adapter/head versus its exact
pinned Qwen base** under identical input/candidate sets. This tests the benefit
of training; comparing only to a hosted proprietary API cannot isolate it.
Keep the current `gpt-5.6-luna` and `gpt-6-astra` baselines and their recorded
reasoning settings. OpenAI's [official model catalog](https://developers.openai.com/api/docs/models)
also lists `gpt-5.6-terra`/`gpt-5.6-sol` as optional intermediate comparisons;
these are proposals, with no measurements or account-access verification here.
The [documentation check](../reports/community-research-20260921/openai-model-docs.json)
records the source. Dedicated reranker cards:
[Qwen 0.6B](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B),
[Qwen 4B](https://huggingface.co/Qwen/Qwen3-Reranker-4B),
[BGE v2 m3](https://huggingface.co/BAAI/bge-reranker-v2-m3).

**Model-name collision:** the community RAG repository's branch J is
[configured as Codiv `openjev-0.1`](https://github.com/emretheus/jev-rag-benchmark/blob/f02b0f1e44d5277a5d5ee5575cc3c3f16590b7b1/configs/default.yaml#L32),
and its [reranker source](https://github.com/emretheus/jev-rag-benchmark/blob/f02b0f1e44d5277a5d5ee5575cc3c3f16590b7b1/src/jev_rag_bench/rerank.py#L11)
identifies that provider explicitly. It does **not** evaluate our
`ZefanCai/Open-Jev-2B` or `ZefanCai/Open-Jev-9B`. Its reported result must not be
attributed to this project.

For efficiency, record identical task quality targets, context length,
candidate/question counts, P50/P95, failures, cost, concurrency, hardware and
network boundary. Compare cold and warm runs separately; include any retrieval,
planner and fallback cost. Prefix-cache speed claims require probability parity
to pass first. No new GPU work, model API benchmark request or X post was made
for this research update.

Additional pinned source and protocol details: [community source contracts](../reports/community-research-20260921/benchmark-discovery.json) and [model/benchmark options](../reports/community-research-20260921/model-benchmark-options.json).
