# Benchmark results and scope

This index consolidates completed measurements from the published reports. Each table keeps its own metric and denominator. Tables label each checkpoint. Open-Jev 27B v1.1 has audited full internal and JevBench public-subset results; the historical provider-control and latency tables retain their Open-Jev-2B and Open-Jev-9B identities.

[Project website](https://zefan-cai.github.io/open-jev/) · [Website benchmark tables](https://zefan-cai.github.io/open-jev/benchmarks/) · [Hugging Face collection](https://huggingface.co/collections/ZefanCai/open-jev)

## Versioned independent results

The [evaluation ledger](evaluation-ledger.md) preserves the old 231-public
protocol, historical v1.4 report, and observed independent v1.5.4 snapshot.
v1.4 used different public/sealed difficulty mixtures; v1.5 uses matched tier
mixtures and chance-corrected competence. Neither its competence nor its
composite is raw accuracy. On v1.5.4, 9B is #46 / 24.356 and 2B #65 / 9.073.
The old v1.4 29.9% sealed figure is a historical report, not current 9B performance.

Fresh independent 27B v1.1 evaluation remains pending. The [executable handoff](../scripts/prepare_independent_evaluation.py)
pins code, model/base/checkpoint identity and request settings without claiming
new sealed results. See the [machine-readable snapshot](../site/evaluation-ledger.json).

## Operator and released 2B efficiency on H200

The isolated Triton final-row gather, optional BF16 residual, RMSNorm and FP32
scalar head measured **2.63–2.75× warm P50 operator speedup** against the Torch
reference on one NVIDIA H200. All nine seeded activation cases passed parity:
maximum logit error **1.12e-7**, maximum probability error **2.09e-8**, with zero
decision changes or threshold flips. Each case used ten warmups and 100 timed
iterations. The separate suite passed two CUDA checks and ten profile,
ownership and reference checks.

The released 2B comparison separately measured **1.006–1.020× whole-model
warm P50 ratios** and **1.002–1.034× loopback HTTP ratios** across eight
workloads. Twenty samples and three warmups per workload came from sequential
model runs. These small differences do not establish statistically significant
whole-model gains. Both paths had the same **6.917 GiB** maximum observed
per-request peak allocation. The isolated operator ratio does not describe
whole-model or HTTP performance.

All 168 in-process and 168 loopback HTTP comparisons passed on the recorded
workloads, with maximum probability error 1e-7, zero decision changes and zero
audited threshold flips. The published 2B checkpoint, all five inference files
and all 13 pinned base/tokenizer files were verified before execution. The
frozen public-development comparison is described separately below. The Python 3.12.13
runtime used existing `runtime312` packages plus a selected dependency overlay;
it was not a fresh clean Linux installation. See the
[reproducibility receipt](reproducibility-receipt-20261002.md).

Sources: [measured operator report](https://github.com/Zefan-Cai/Open-Jev/blob/4898a2923cecb2fd62b25b5cde8d64741d9cfe2e/reports/efficiency-20261002/h200-kernel-summary.md),
[raw measurements](https://github.com/Zefan-Cai/Open-Jev/blob/4898a2923cecb2fd62b25b5cde8d64741d9cfe2e/reports/efficiency-20261002/h200-kernel-results-ed28.json).
The [released 2B report](https://github.com/Zefan-Cai/Open-Jev/blob/42e46481da6dd8191d6f510fc3680c70fd4f051d/reports/efficiency-20261002/h200-2b-summary.md)
retains all workloads, cold calls, allocator figures and both raw JSON reports.
[Implementation PR #14](https://github.com/Zefan-Cai/Open-Jev/pull/14) tracks the changes.

### One fixed synthetic continued-training pilot

The released 2B checkpoint completed 64 fixed steps on original synthetic
counterfactual controls, with temperature fitted only on separate synthetic
calibration rows. The adapted checkpoint is experimental, not a released
model. Argmax accuracy rose from **84/128 (65.625%) to 99/128
(77.34375%)** on Test and **83/128 (64.84375%) to 95/128 (74.21875%)** on
controlled OOD variants. This is one seed and a released-checkpoint baseline,
not a pretrained-base comparison or broad real-world generalization result.

Regressions and unsolved families remain visible: numeric Test stayed
30%→30%, numeric OOD fell 35%→30%, and timeline OOD fell 58.33%→54.17%.
Saved/reloaded probability error was zero. Training source was `80ca8e8`.
These synthetic results do not establish natural-support or JevBench transfer;
the separate public-development comparison below retains its limited scope.

Sources: [full training summary](https://github.com/Zefan-Cai/Open-Jev/blob/42e46481da6dd8191d6f510fc3680c70fd4f051d/reports/frontier-controls-v4/continued-2b-20261002/summary.json),
[completion and checkpoint receipt](https://github.com/Zefan-Cai/Open-Jev/blob/42e46481da6dd8191d6f510fc3680c70fd4f051d/reports/frontier-controls-v4/continued-2b-20261002/completion-receipt.json).
The nonweight artifacts retain all four prediction journals and their locks.

### Frozen 64-task public-development comparison

On the same locked requests, Choice stayed **17/34**, and Noul stayed **9/23**
under documented v1.5 inclusive 0.2/0.8 abstention rules. Noul answered coverage
changed 17/23 → 18/23; the extra answer was incorrect. All Choice decisions
were unchanged. Across seven Score items,
expected-position normalized MAE fell **0.22393 → 0.20645**; auxiliary argmax
correct stayed 2/7, with four MAE improvements and three regressions.
Equal-type, available-tier-weighted subset competence rose
**22.835 → 24.257**, driven only by Score. No Choice or Noul accuracy gain was
observed.

Both source/base identities and the 16,384-token limit matched. Checkpoint
weights and saved temperature changed together (1.518796342858676 →
1.5446931834967927), so weight adaptation and recalibration are not isolated.
This is one development sample with no uncertainty estimate. It draws from
231 accessible public tasks; the pinned source lacks the additional documented
published-open items. Historical public feedback informed the controls. These
subset metrics are not official I_open, blind/sealed performance, a leaderboard
composite or a rank. Raw benchmark text, gold and responses remain private.

Sources: [released baseline](https://github.com/Zefan-Cai/Open-Jev/blob/42e46481da6dd8191d6f510fc3680c70fd4f051d/reports/jevbench-public-development-20261002/released-2b-frozen64.json),
[experimental pilot](https://github.com/Zefan-Cai/Open-Jev/blob/42e46481da6dd8191d6f510fc3680c70fd4f051d/reports/jevbench-public-development-20261002/pilot-2b-frozen64.json),
[paired comparison](https://github.com/Zefan-Cai/Open-Jev/blob/42e46481da6dd8191d6f510fc3680c70fd4f051d/reports/jevbench-public-development-20261002/pilot-vs-released-frozen64.json),
[per-item transition aggregates](https://github.com/Zefan-Cai/Open-Jev/blob/42e46481da6dd8191d6f510fc3680c70fd4f051d/reports/jevbench-public-development-20261002/paired-frozen64.json).

## Community evidence and a local support trial

[Five source-bound community excerpts](https://github.com/Zefan-Cai/Open-Jev/blob/1c4347841ce942b8009d9187735fe5686adbbb1b/docs/community-evidence.md)
motivate natural-text workflow tests. These describe TypeSafe Jev and related
experiments; they are not Open-Jev customer endorsements.

The [support-routing trial guide](https://github.com/Zefan-Cai/Open-Jev/blob/1c4347841ce942b8009d9187735fe5686adbbb1b/docs/support-routing.md)
runs on the reader's local checkpoint server. BANKING77 messages go through
eight retrieved intent candidates plus a review option, a frozen confidence
policy, named human corrections and CSV export. This is a local application,
not a live GPU demo on the static website. Completed external human trials
remain zero until a saved pilot establishes otherwise.

The measured released 2B trial is a **negative result** on 256 natural official
test utterances: **166/256 correct (64.8%)**, versus **211/256 (82.4%)** for
retrieval top-1 BM25. The fixed eight-candidate recall is 249/256 (97.3%). The
locked calibration policy accepted 88/256 rows (34.4% coverage); **14/88 were
wrong (15.9% accepted error)**, missing its 90% accepted-accuracy calibration
target on test. The remaining 168/256 rows require review. The threshold was
not retuned on test. Browser automation exercised 12 natural training examples
against the real checkpoint API, with all 12 left unresolved for review and
zero human corrections. This engineering check is not an external human trial.

Sources: [natural support evaluation and lock](https://github.com/Zefan-Cai/Open-Jev/tree/42e46481da6dd8191d6f510fc3680c70fd4f051d/reports/support-routing-20261002),
[actual-model browser smoke](https://github.com/Zefan-Cai/Open-Jev/blob/42e46481da6dd8191d6f510fc3680c70fd4f051d/reports/support-routing-20261002/browser-smoke.json).
The model ranker needs improvement before it can replace the stronger retrieval baseline.

## Full internal evaluation

| Model | Old Test | Old OOD | Expanded Test | Expanded OOD |
|---|---:|---:|---:|---:|
| Open-Jev-2B | 9,515 / 10,046 (94.71%) | 13,287 / 15,446 (86.02%) | Not evaluated | Not evaluated |
| Open-Jev-9B | 9,799 / 10,046 (97.54%) | 14,205 / 15,446 (91.97%) | Not evaluated | Not evaluated |
| Open-Jev-27B-v1.1 | 9,876 / 10,046 (98.31%) | 14,825 / 15,446 (95.98%) | 41,357 / 42,789 (96.65%) | 80,934 / 83,924 (96.44%) |

All 127,787 expanded held-out rows were independently audited for 27B v1.1, with zero failures, missing rows or duplicates. Old Test/OOD cover all 10,532 / 15,920 rows; expanded Test/OOD cover all 43,301 / 84,486. The cells use exact hard-label denominators. Their 486 / 474 / 512 / 562 soft-target rows remain in probability metrics. Old panels are unchanged-content subsets of expanded panels and overlap with them. Expanded evaluations for Open-Jev-2B and Open-Jev-9B have not run; new 2B training stopped and new 9B did not start.

Source: [complete full internal method and results](internal-full-evaluation.md), [audited aggregate](../reports/new27b-internal-full-20260923/report.json). Internal max length is 4,096 without truncation; JevBench uses a separate 16,384-token protocol. Shared multi-GPU timing is not single-GPU or HTTP/API latency.

## External decision benchmarks

| Evaluation / metric | Open-Jev-2B | Open-Jev-9B | Open-Jev-27B-v1.1 | Jev 1.13.0 | GPT-5.6 Luna (none) | GPT-6 Astra (low) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| JevBench public · correct / 231 | 150/231 · 64.94% | 179/231 · 77.49% | 197/231 · 85.28% | 200/231 · 86.58% | 206/231 · 89.18% | 231/231 · 100.00% |
| JevBench original · correct / 72 | 56/72 | 65/72 | 69/72 | 71/72 | 69/72 | 72/72 |
| JevBench easy · correct / 48 | 48/48 | 48/48 | 48/48 | 48/48 | 48/48 | 48/48 |
| JevBench hard · correct / 111 | 46/111 | 66/111 | 80/111 | 81/111 | 89/111 | 111/111 |
| JF100 · correct / 300 rotations | Pending | Pending | Not evaluated | 232/300 | 227/300 | 300/300 |

JevBench covers all 231 available public tasks out of 534 total: 72 original, 48 easy and 111 hard. The other 303 private/judge tasks were unavailable. All six streams completed and passed independent replay audits. Native and GPT adapters use different candidate orders on 119 of 139 Choice tasks. Open-Jev and Jev return native probabilities; GPT returns verbalized probability vectors in constrained JSON, not token logprobs. Jev had one vector normalized under the upstream rounding policy (230/231 strict-valid); the other five streams had 231/231 strict-valid vectors.

27B v1.1 scores 197/231 overall and 80/111 Hard, improving over Open-Jev-2B and Open-Jev-9B while remaining three overall and one Hard answer behind Jev. Its four-rank direct-execution timings are not included in the HTTP/HTTPS latency comparison.

JF100 has 100 external items in three option rotations: 300 correlated decisions, not 300 independent problems. Jev’s 232/300 is categorical-only accounting and retains two probability-mass flags. The earlier Open-Jev pilot checkpoints are different from the released models; their archived scores do not fill the pending released-model cells.

Sources: [JevBench method and audits](jevbench-public.md), [JevBench aggregate](../site/jevbench.json), [provider comparison and JF100](provider-comparison.md), [provider aggregate](../site/provider-quality.json).

## Retrieval: primary strict nDCG@10

| Evaluation / metric | Open-Jev-2B | Open-Jev-9B | Jev 1.13.0 | GPT-5.6 Luna (none) | GPT-6 Astra (low) |
| --- | ---: | ---: | ---: | ---: | ---: |
| TREC-DL19 · 43 queries | Pending | Pending | 0.275836 | 0.729911 | 0.736610 |
| TREC-DL20 · 54 queries | Pending | Pending | 0.190667 | 0.702082 | 0.714484 |

TREC uses the downloaded BM25 top 100, nine adaptive 20-passage windows per query and full official qrels with direct-grade gains. Each hosted model completed 97 queries / 873 requests. Strict failures contribute zero over the full 43/54 query denominators. Jev had 108 mass-validation failures affecting 66 queries: 15/43 DL19 and 16/54 DL20 queries were strict-complete. Luna and Astra had no transport or strict-validation failures.

Jev’s predeclared supplementary actual-scalar nDCG@10 is 0.728218 on DL19 and 0.715734 on DL20. These scalar scores do not validate the probability vectors and do not replace the strict scores. Downloaded BM25 is 0.505831 / 0.479637. Later windows adapt to each provider’s rankings; Jev expected scores and GPT integer grades have different resolution. This is an independently authored protocol, not an exact reproduction of the community demo.

Usage-based standard-list estimates for the full TREC run are $0.799273 for Luna and $39.62622 for Astra. These are estimates, not invoices; Jev cost is unknown. Open-Jev compute is unmetered, not free.

Source: [TREC protocol, all summaries and independent audits](../reports/ir-control-v1/trec-holdout/README.md).

## Prepared-data reference matches and controlled probes

| Evaluation / metric | Open-Jev-2B | Open-Jev-9B | Jev 1.13.0 | GPT-5.6 Luna (none) | GPT-6 Astra (low) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Release-v2 test · hard reference matches | 9,515/10,046 · 94.71% | 9,799/10,046 · 97.54% | Not evaluated | Not evaluated | Not evaluated |
| Release-v2 OOD · hard reference matches | 13,287/15,446 · 86.02% | 14,205/15,446 · 91.97% | Not evaluated | Not evaluated | Not evaluated |
| Same 76 hard coverage cases | 65/76 | 72/76 | 66/76 | 60/76 | 71/76 |
| Broader coverage · 140 hard cases | Partial: 64 pending | Partial: 64 pending | 117/140 | 109/140 | 135/140 |
| IR controls · 165 hard decisions | Pending | Pending | 165/165 | 160/165 | 165/165 |
| FizzBuzz · 300 typed decisions | Pending | Pending | 299/300 | 300/300 | 300/300 |
| Mailroom · 921 labeled decisions | Pending | Pending | 908/921 | 900/921 | 913/921 |

Release-v2 evaluates every 26,452 test/OOD row per model: 10,532 test and 15,920 OOD rows. Hard accuracy uses only 10,046 test and 15,446 OOD one-hot targets; the 960 soft-target rows are excluded from these fractions. These are reference matches in prepared task data, not end-to-end workflow success or game win rates. There was no full-data base-model comparison.

The same-76 row is the matched coverage comparison: historical 2B/9B predictions were reused only after exact row and checkpoint checks, adding no new latency. Their additional 64 hard cases remain pending in the broader 140-case suite. A later label audit found equivalent platformer actions and omitted ViZDoom policy constants. The separately labeled post-hoc six-case exclusion gives 2B 60/70, 9B 67/70, Jev 64/70, Luna 57/70 and Astra 69/70; it does not replace the original row.

The IR pilot contains six original query instances and is separate from TREC. FizzBuzz tests integers 1–100 with three typed questions each. Mailroom uses 87 requests, shared families and 921 labeled decisions; 36 inapplicable questions have no gold. These finite controls and correlated views are not representative population or production-success estimates. In these suites GPT emits categorical decisions, not probability vectors.

Sources: [full-data evaluation audit](../reports/full-data-eval-n1-v1/README.md), [full-data aggregate](../site/results.json), [provider comparison and label review](provider-comparison.md), [IR ranking replay](../reports/provider-comparison-20260920/openai-ir-ranking/README.md).

## Repeated workload latency

| Evaluation / metric | Open-Jev-2B | Open-Jev-9B | Jev 1.13.0 | GPT-5.6 Luna (none) | GPT-6 Astra (low) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Customer service · 8 questions | 85.03 / 133.91 ms | Not measured | 295.26 / 330.37 ms | 918.13 / 1443.13 ms | 1938.39 / 2375.71 ms |
| 1,024 state tokens · 32 candidates | 1015.90 / 1369.72 ms | Not measured | 301.37 / 361.21 ms | 690.12 / 787.92 ms | 1388.07 / 1741.09 ms |

The repeated latency study uses 11 fixed workloads, 20 measured requests and three warmups per workload and provider, concurrency one and no retries. The table shows two workloads; all 11 remain in the linked full report. Open-Jev uses a warm local H100 and loopback HTTP with prefix cache off. Hosted providers use fresh HTTPS connections, including Internet/TLS/routing/scheduling. These are client-observed deployment times, not matched-hardware model speedups, throughput or energy-efficiency measurements. Response validity does not establish equal task quality.

The larger candidate workload is an unfavorable case for uncached Open-Jev-2B. Experimental prefix caching exceeded the probability tolerance on 9/11 workloads despite all 440 paired selected decisions matching; it remains off by default.

Source: [all 11 workloads, methods and raw attempts](inference-latency.md), [latency aggregate](../site/latency.json).

### Separate JevBench timing diagnostics

| Model | P50 | P95 |
| --- | ---: | ---: |
| Open-Jev-2B | 138.0 ms | 205.8 ms |
| Open-Jev-9B | 189.2 ms | 839.3 ms |
| Jev 1.13.0 | 291.3 ms | 353.7 ms |
| GPT-5.6 Luna | 953.8 ms | 1307.5 ms |
| GPT-6 Astra | 2206.4 ms | 3581.6 ms |

JevBench timing is a separate diagnostic: one full-response observation per heterogeneous task, no warmups or retries. It must not be pooled with the repeated-workload latency study. Local model loading is outside the timer; full response completion and validation are inside.

## Model identities and pending work

| Model | Recorded identity | Configuration |
| --- | ---: | ---: |
| Open-Jev-2B | Qwen/Qwen3.5-2B | LoRA + scalar head + saved calibration; base revision 15852e8c16360a2fea060d615a32b45270f8a8fc |
| Open-Jev-9B | Qwen/Qwen3.5-9B | LoRA + scalar head + saved calibration; base revision c202236235762e1c871ad0ccb60c8ee5ba337b9a |
| Open-Jev 27B v1.1 | Qwen/Qwen3.8-27B | LoRA rank 8 + FP32 scalar head + saved temperature 2.5343690298472983; base revision 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0 |
| Jev | jev-1.13.0 | Recorded hosted version |
| GPT-5.6 Luna | gpt-5.6-luna | Reasoning none; recorded alias, no dated snapshot available |
| GPT-6 Astra | gpt-6-astra | Reasoning low; recorded alias, no dated snapshot available |

The [27B v1.1 package](https://huggingface.co/ZefanCai/Open-Jev-27B-v1.1) uses checkpoint tree SHA-256 `c49994563c3c4f04a99d9130203c4e526f4ae5086c84deec57698d18cb652e71`. The original released HF package revisions are `0c7aa498b1627be8da4acf34c863ff0ee0a92785` (2B) and `47e966881e489511c0c7f5633a9e1960a676a551` (9B). They require upstream base weights and the Open-Jev loader. Model settings differ between providers; these are not equal reasoning budgets. Exact request options, checkpoints and hashes are retained in the linked experiment reports.

Released Open-Jev JF100, TREC and the remaining provider-control suites are pending. 27B v1.1 has completed full internal and public JevBench audits. Prepared V3 data has no completed new-model result. The prepared 107,922-row broader held-out registry and the fixed 1,280-row / 840-group v2–v3 panel are evaluation plans, not completed results. Historical pilots remain archived under their original identities.

See [internal evaluation](internal-evaluation.md) for split roles, calibration and group weighting. Archived pilots: [4K suite](../reports/pilot-suite-n1-4k/) and [16K JF100](../reports/pilot-frontier-n1-16k/). No pilot score is presented here as a released-model or new 27B result.
