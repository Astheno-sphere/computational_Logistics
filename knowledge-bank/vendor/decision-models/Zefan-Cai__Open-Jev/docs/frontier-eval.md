# Jev Frontier 100: held-out external evaluation

Open-Jev supports [softpudding/jev-frontier-100](https://github.com/softpudding/jev-frontier-100) as an external evaluation set. It is kept outside all training-data directories and is never converted into train/calibration records by this integration. Do not tune on its answers, rationales, or evaluation outcomes.

The adapter pins upstream commit **`9abacec47394f3b393f81fbe3cdd524f028bc088`**, the MIT license, protocol, request builder/scorer sources, public results and dataset. The original 100-item dataset is version **0.1.0**, with SHA-256:

```text
dd107ba90de381eaa479408492e81d7222115782e5fe601ab43986f94cd1d0fa
```

The published experiment protocol/results are called **v0.2-budget**; this did not change the frozen questions. The benchmark has 50 counterfactual pairs across 10 domains: customer service, policy rules, discourse, formal logic, relations, mathematics, temporal reasoning, code semantics, algorithms and evidence integration. All are AI-assisted synthetic English questions, without independent expert review. Designed difficulty levels are not calibrated difficulty estimates.

## Obtain and audit the source

```bash
git clone https://github.com/softpudding/jev-frontier-100.git /path/outside/training/jev-frontier-100
git -C /path/outside/training/jev-frontier-100 checkout 9abacec47394f3b393f81fbe3cdd524f028bc088
python -m jev.eval_frontier \
  --source /path/outside/training/jev-frontier-100 \
  --output-dir reports/jf100/source-audit \
  --audit-only
```

`--audit-only` makes **zero inference requests**. It verifies the pinned files, reconstructs all 300 original Jev requests and checks their hashes/golds against the published outcomes. It also recomputes the published Jev score and statistics. The offline audit passes:

| Reused published Jev 1.13.0 reference | Recomputed value |
|---|---:|
| Correct requests | 231 / 300 |
| Accuracy | 77.0% |
| 95% paired-template bootstrap interval | 70.33%–83.67% |
| Pair joint accuracy | 67.33% |
| Semantic consistency across option rotations | 85.0% |

These are upstream reference results, **not Open-Jev model results and not fresh Jev API calls**. All ten domain breakdowns and difficulty breakdowns also reproduce exactly.

## Native Choice protocol

Every one of the 100 items is submitted three times, with option positions rotated left by 0, 1 and 2. Gold letters are mapped after each rotation without changing answer meanings. The HTTP request follows the upstream native Jev Choice form:

```json
{
  "model": "open-jev",
  "state": "Only the original visible state",
  "questions": {
    "answer": {
      "type": "choice",
      "instructions": "Only the original question",
      "criteria": {"A": "Rotated option", "B": "Rotated option", "C": "Rotated option", "D": "Rotated option"}
    }
  }
}
```

The actual original option descriptions are used. Item gold, rationale, difficulty, oracle metadata and prior answers never enter requests. The key `questions.answer` is the upstream question ID, not a supplied answer. Item/trial IDs are kept alongside the request only in local audit artifacts.

Task ordering uses upstream seeds 101/202/303, but **no sampling seed is sent to the model**. These are three option-position trials of a deterministic discriminative scorer, not three independent stochastic generations. All 300 trials contribute directly to accuracy; there is no majority vote, best-of selection, early stopping or adaptive prompt change.

## Run a learned model service

Once the desired Open-Jev service is ready:

```bash
python -m jev.eval_frontier \
  --source /path/outside/training/jev-frontier-100 \
  --endpoint http://127.0.0.1:8791/v1/systemone \
  --expected-model Qwen/Qwen3.5-2B \
  --expected-method lora_decision_head \
  --output-dir reports/jf100/2b-run1
```

Use the corresponding expected model and endpoint for 9B/27B. Each invocation uses a fresh output directory and evaluates the entire benchmark. `manifest.json` records source/version/license/file hashes and every request/state hash. `requests.jsonl` contains exact target-free request objects; `UPSTREAM_LICENSE.txt` preserves the original license. `attempts.jsonl` retains every HTTP attempt and its raw response body. `outcomes.jsonl` retains every scored request, response, grade and reported model/checkpoint/base-revision/code identity. No completed trial is silently replaced.

On the allocated N1-1 node, `scripts.run_service_suite` can start and stop its
own checkpoint server on physical GPU 3. Once a run has a complete `summary.json`
and calibrated checkpoint, `--models 2b` evaluates it without requiring the
9B/27B checkpoint files. The default still evaluates all three models serially.
For a final full-pass checkpoint, from the separate evaluation checkout:

```bash
python -m scripts.run_service_suite \
  --expected-hostname kwade5342000001 --gpu 3 --models 2b \
  --checkpoint-root /data/zefan/open-jev/runs/release-v2-fullpass-n1-v1 \
  --checkpoint-template '{tag}/checkpoint' \
  --frontier-source /mnt/localssd/open-jev/evals/jev-frontier-100 \
  --measurements frontier_100 --max-length 16384 --batch-size 1 \
  --output-root /data/zefan/open-jev/evals/fullpass-2b-frontier-16k-v1
```

Use a fresh output path for every run. Model selection does not change the
300-trial benchmark, checkpoint identity checks, resource restriction or
cleanup behavior. Do not point inference at training-resume-only snapshots.

A network error, HTTP 429 or selected 5xx response is retried once, following the upstream retry categories. Wrong answers and invalid outputs are never retried. Invalid outputs and persistent service failures score zero in system accuracy; valid completion rate and accuracy among valid responses are reported separately. Authentication/access errors or a changed model/checkpoint identity abort the run, preserve partial artifacts, and produce `failure.json` without a final summary. Fixture/oracle methods are rejected.

`summary.json` reports accuracy, valid completion, status counts, domain/difficulty breakdowns, pair joint accuracy and semantic consistency. It compares the learned model with the audited, reused Jev reference using **5,000 stratified paired-template bootstrap draws, seed 92026**, over the same 50 pairs stratified by domain. Reported uncertainty treats counterfactual pairs as the sampling unit, not 300 independent questions. The paired difference includes domain-level deltas.

## Interpretation and limits

The published Qwen baselines used Q8_0 GGUF weights, llama-server, temperature 1, explicit autoregressive thinking budgets, and an Apple M5 Max. Open-Jev uses its own non-generative candidate scorer, checkpoint precision/calibration and GPU backend. Matching the visible questions and Choice interface does not make those compute budgets, precision, hardware, confidence semantics or latency measurements equivalent. Timing here is descriptive and includes HTTP/model execution; it is not a controlled speed comparison.

The source release selected complete conditions after observing results. Its intervals and our comparison are exploratory, not confirmatory evidence of model equivalence, universal reasoning capacity, or a Jev parameter count. Do not train against this benchmark to improve the released score. New benchmark-driven changes require a separately held-out evaluation rather than silently reusing these 100 questions as development data.

Tests are dependency-free; the optional frozen-source test uses an external checkout:

```bash
JF100_SOURCE=/path/outside/training/jev-frontier-100 python -m unittest tests.test_eval_frontier -v
```

## Upstream attribution

Protocol, question data, native request construction and statistical design originate from JF100. The external source is not executed or installed by the adapter. Original questions exported into evaluation artifacts retain this notice:

```text
MIT License

Copyright (c) 2026 JF100 contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
