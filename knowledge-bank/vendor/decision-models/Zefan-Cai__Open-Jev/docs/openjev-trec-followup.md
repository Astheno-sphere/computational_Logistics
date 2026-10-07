# Open-Jev TREC follow-up

The opt-in `trec` measurement in `scripts/run_service_suite.py` connects the
local Open-Jev collector and offline replay to the existing owned GPU 3 service
lifecycle. Actual Open-Jev TREC model inference is **pending**. This implementation
does not change published scores, the completed Jev/Luna/Astra collections, the
running post-training guard, or the separately deployed five-suite quality
checkout `88c8aef9cdb1ced5d557fc1be2a4e3128614588b`.

All 79 combined CPU tests pass, including full synthetic 873-request collection,
offline replay, interruption accounting and owned-service cleanup. An independent
review passed 31 targeted checks after fixes for raw JSON type/order binding,
fatal-error continuation and out-of-range Score accounting. The
[CPU evidence](../reports/runtime-checks/openjev-trec-cpu.json) also binds the
real frozen input and complete official qrels; these are not model results.

The same service update strengthens the five-suite quality replay's raw JSON
binding. Future provider-quality runs must use this updated reviewed checkout.
The prior `88c8aef` checkout and its preparation evidence remain unchanged and
must not be used to launch new quality inference.

The replacement isolated deployment uses commit
`e5188e7555bd8c706008b7a5e62a856b383a5cb6` under
`/data/zefan/open-jev/openjev-trec-20260921`. Its serving source is
`code-e5188e7`; frozen evaluation inputs are `private-inputs/input.json` and
`private-inputs/holdouts`. All 79 remote CPU tests passed without skips. Input
preflight verified the seven frozen TREC files and the original 808 provider
requests.
The [deployment record](../reports/runtime-checks/openjev-trec-deployment.json)
binds the source, transfer and test log hashes. The separate tokenizer proof
below also passed. No GPU or model inference was used.

The default service measurements are unchanged. Selecting `trec` requires
`--trec-input` and `--max-length 16384`. `--trec-holdout-root` points to the
isolated `dl19/manifest.json` and `dl20/manifest.json` directories used for
offline scoring. Input, holdout artifacts and raw output must remain outside
the repository's `data` and `train` trees, including through symlinks.

## Frozen protocol and CPU preflight

Before any GPU query, output directory creation, checkpoint load or subprocess,
the launcher validates the original input-only file using
`evaluate_trec_provider.load_input` and this pinned SHA256:

`cc7bc949dbc269dacb61bdb61fc8982db14bc4df3698f9d32f5f1c8b6795eb83`

The full input has 97 queries: 43 DL19 and 54 DL20 queries, each starting with
the same saved BM25 top-100 candidates. The CPU preflight also checks the fixed
DL19/DL20 manifest hashes, all candidate/qrel file hashes, complete query sets,
and candidate ID order. Full official qrels, including judgments outside the
top 100, are retained for the ideal DCG denominator. These labels and their
paths are never passed to the collector or model.

The collector uses nine adaptive 20-passage windows per successfully completed
query, stepping by ten: at most 873 requests per model. Later window contents
depend on that model's actual prior decisions. It uses Open-Jev's actual
expected Score values without rounding, probability renormalization or gold
substitution; equal scores preserve current window order. It records every
dispatch before sending and retains raw responses, failures and pending queries.
No Jev or OpenAI API call is made by this follow-up.

The owned loopback HTTP server uses the existing LoRA/decision head path with
prefix caching disabled. Successful responses must match all seven expected
identity fields: model, method, base revision, checkpoint hash, calibration
temperature, serving code commit and 16K maximum context length. Collection is
single-concurrency, without warmups or retries. The collector defaults cap it
at 873 requests, a 300-second request timeout and a 10,800-second budget checked
before each dispatch. An already dispatched request may take its remaining
timeout after that budget. Use an outer measurement timeout of 11,160 seconds
to leave room for the final request and journal cleanup. This collection is a
quality measurement, not a replacement for the repeated latency benchmark.

CPU-only input preflight from the separately prepared checkout is available as:

```python
import argparse
from pathlib import Path
from scripts.run_service_suite import preflight_trec_inputs

evidence = preflight_trec_inputs(argparse.Namespace(
    measurements=["trec"],
    trec_input=Path("/data/zefan/open-jev/openjev-trec-20260921/private-inputs/input.json"),
    trec_holdout_root=Path("/data/zefan/open-jev/openjev-trec-20260921/private-inputs/holdouts"),
    output_root=Path("/data/zefan/open-jev/openjev-trec-20260921/trec-release-v2-2b-9b"),
))
```

This callable validates inputs and labels on CPU; it does not tokenize or run
a model. The separate [tokenizer proof](../reports/runtime-checks/openjev-trec-tokenizer.json)
and its [source](../reports/runtime-checks/check_openjev_trec_tokenizer.py)
establish a sufficient upper bound of **13,680 tokens**, below 16,384, for both
pinned 2B/9B tokenizers across every adaptive 20-passage window from these 97
frozen queries. It verifies NFC stability of all 9,700 JSON-escaped passages
and 97 queries using the actual normalizers, plus the byte-level BPE and fixed
chat-envelope assumptions, and checks 7,760 candidate frames per model.

This sufficient bound applies to the frozen corpus and pinned formatting and
tokenizers. The separate actual-token sanity check covers 97 constructed
candidates per model, with a sample maximum of 3,055; it is not an exhaustive
actual-token maximum. The server never truncates overlong candidate sequences.

## Launch only after the existing queue and follow-ups release resources

This stage is separate from the current guard's fixed plan. Before launching,
verify that all three core stages completed, the independent expansion audit
and original manifests passed, the contact/amount follow-up completed, the
five-suite provider-quality follow-up completed, and all schedule/GPU leases
and owned servers released. Do not edit or restart those controllers. An
existing output must be inspected, not overwritten or retried silently.

The following command names the isolated replacement checkout and private
inputs. Check every queue prerequisite above before using it. The command
does **not** wait for those prerequisites and no waiting controller has been launched.
`HF_HUB_CACHE` must point directly to the existing model cache; using only
`HF_HOME` would append an incorrect `hub` path.

```bash
cd /data/zefan/open-jev/openjev-trec-20260921/code-e5188e7
HF_HUB_CACHE=/mnt/localssd/open-jev/hf-cache \
PYTHONPATH=/data/zefan/open-jev/openjev-trec-20260921/code-e5188e7 \
/mnt/localssd/open-jev/runtime/venv/bin/python -m scripts.run_service_suite \
  --expected-hostname kwade5342000001 --gpu 3 \
  --models 2b 9b \
  --checkpoint-root /data/zefan/open-jev/runs/release-v2-fullpass-n1-v1 \
  --checkpoint-template '{tag}/checkpoint' \
  --trec-input /data/zefan/open-jev/openjev-trec-20260921/private-inputs/input.json \
  --trec-holdout-root /data/zefan/open-jev/openjev-trec-20260921/private-inputs/holdouts \
  --measurements trec --max-length 16384 --batch-size 1 \
  --measurement-timeout 11160 \
  --output-root /data/zefan/open-jev/openjev-trec-20260921/trec-release-v2-2b-9b
```

This uses N1-1 physical GPU 3, serially for 2B then 9B. The existing GPU lease,
UUID binding, owned-child checks and cleanup remain active. GPUs 4–7 and N4-4
are prohibited. Any later 27B run needs its independently audited final
checkpoint and a distinct output directory after prior runs release resources.

## Replay, cleanup and publication

Each model writes `trec/input.json`, `requests.jsonl`, `samples.jsonl` and
`report.json`. The launcher only accepts stopped collection statuses:
`complete`, `completed_with_query_failures`, `stopped_budget`, `stopped_fatal`
or `interrupted_or_failed`. It rejects any in-flight dispatch or mismatch with
the owned model's expected identity and frozen input.

`summarize_openjev_trec.summarize` then independently replays adaptive requests,
checks source/raw response/journal hashes and complete query coverage, and
scores against the full isolated qrels. Only after this audit passes does the
launcher create a new, text-free `summary.json`, exclusively, and record its
SHA256 and metrics in the enclosing service manifest. Existing summaries are
never replaced. No raw passages, queries, qrels or responses belong in a public
MIT/CC0 export or training corpus.

`completed_with_query_failures` may continue to the next model after normal
cleanup, retaining each failed query as zero in the full 43/54 denominator.
A budget stop, fatal error or interruption preserves any auditable partial
summary, then stops the owned server before another identity probe, model or
latency stage. An unsettled or inconsistent journal is refused for scoring and
also stops the server. Partial metrics remain labelled provisional lower
bounds; they are not completed model results. A hard-killed client may leave
an unmatched dispatch, which must not be silently retried.

Before publishing new model metrics, independently review the retained evidence
and service cleanup manifest. Keep TREC nDCG separate from categorical accuracy,
preserve the saved BM25 baseline and Jev's strict versus supplemental results,
and report the full query denominator and failure counts. No Open-Jev TREC
quality result is claimed by this implementation or its CPU tests.
