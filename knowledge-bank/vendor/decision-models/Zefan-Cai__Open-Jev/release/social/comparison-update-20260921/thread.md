# Open-Jev benchmark update

1/13 Open-Jev benchmark update: quality + response latency vs Jev, GPT-5.6 Luna & GPT-6 Astra.

Our 2B: 85 ms median on a customer-service request, on a local H100.

Measured trade-offs, retrieval results & open artifacts below.
https://zefan-cai.github.io/open-jev/#comparison

---

2/13 Open-Jev is an independent, Jev-inspired implementation on Qwen 2B/9B.
Within each model, domains share a LoRA + decision head; candidates are dynamic.

Choice / Boolean / Score. Released adapters, heads and calibration require the pinned Qwen base weights.

---

3/13 Same 76 hard-label cases: reference matches
Open-Jev 2B: 65/76
Open-Jev 9B: 72/76
Jev: 66/76
Luna: 60/76
Astra: 71/76

2B/9B reuse verified historical predictions on identical inputs. Small frozen slice; six game cases have technical ambiguities. See next reply.

---

4/13 Post-hoc sensitivity check: exclude the SAME six ambiguous game cases for every model.
2B 60/70; 9B 67/70; Jev 64/70; Luna 57/70; Astra 69/70.

The 9B/Astra order reverses. This is reference agreement on a small slice, not evidence of overall model superiority.

---

5/13 Broader hard coverage (140):
Jev 117; Luna 109; Astra 135.

JF100, 100 items x 3 option rotations:
Jev 232/300; Luna 227/300; Astra 300/300.

Jev numbers here use categorical decisions; probability validity is separate. New Open-Jev evaluations remain pending.

---

6/13 More controlled probes (Jev / Luna / Astra):
IR pilot: 165 / 160 / 165 of 165.
FizzBuzz: 299 / 300 / 300 of 300.
Multilingual mailroom: 908 / 900 / 913 of 921.

These are correlated, constructed test cases. The IR pilot is separate from the real TREC holdout below.

---

7/13 Customer service: 8 Boolean questions.
Response latency P50 / P95 (ms):
2B: 85 / 134
Jev: 295 / 330
Luna: 918 / 1,443
Astra: 1,938 / 2,376

Warm 2B on one H100 over loopback HTTP vs hosted HTTPS APIs. Hardware/network differ; this measures deployments.

---

8/13 The larger candidate set changes the picture.
1,024 state tokens + 32 candidates, P50:
2B: 1,016 ms
Jev: 301 ms
Luna: 690 ms
Astra: 1,388 ms

Our current uncached 2B is slower than Jev and Luna here. Small-request latency does not predict every workload.

---

9/13 Timing method: 11 workloads; 20 measured calls after 3 warmups per path; concurrency 1.

Full validated response, including transport, rather than time to first token. Fresh connections; no retries. OpenAI server-side prompt caching did occur. P95 is descriptive.

---

10/13 Settings: Luna reasoning=none; Astra=low. Different reasoning budgets.

2B prefix caching is experimental: probability parity failed on 9/11 workloads, although selected decisions matched. We keep it OFF in the comparison. Throughput and energy were not measured.

---

11/13 Real TREC-DL, our listwise protocol. nDCG@10 (DL19 / DL20):
Saved BM25: .5058 / .4796
Jev strict: .2758 / .1907
Luna: .7299 / .7021
Astra: .7366 / .7145

Full 43/54 queries; BM25 top100. Open-Jev scores pending. Jev validation caveat next.

---

12/13 Jev: 108/873 requests failed our strict probability-mass check; 66 queries score zero in the primary metric.

Predeclared scalar-only analysis: .7282 / .7157, with no probability renormalization. Both views stay public. GPT returns integer grades, not probabilities.

---

13/13 Complete results, caveats and methods:
https://zefan-cai.github.io/open-jev/#comparison

Code: https://github.com/Zefan-Cai/Open-Jev
Data: https://huggingface.co/datasets/ZefanCai/Open-Jev
2B/9B: https://huggingface.co/collections/ZefanCai/open-jev-6ab049b9d43a267bae4dedc8

New Open-Jev domains/full evaluation are still pending.
