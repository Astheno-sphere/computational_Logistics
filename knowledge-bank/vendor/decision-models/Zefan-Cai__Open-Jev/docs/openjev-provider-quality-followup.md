# Open-Jev evaluation of the five frozen provider suites

The optional `provider_quality` measurement in `scripts/run_service_suite.py`
collects one uncached response for each original provider request. It closes the
local collection gap for the five small suites already evaluated by Jev, Luna
and Astra. It does not run TREC or the full 73,333/107,922-row held-out registries.
GPU inference with this follow-up has not started, and current published results
remain unchanged.

The [TREC follow-up update](openjev-trec-followup.md) also strengthens this
runner's raw JSON type/order verification. The original `88c8aef` preparation
below is historical. Future quality inference must use the replacement commit
`e5188e7555bd8c706008b7a5e62a856b383a5cb6`. Its isolated remote deployment passed
all 79 CPU tests without skips and the 808-request provider preflight. Its 15
frozen input files remain the same. No GPU run used the old collection path,
and no completed result was rescored. The
[replacement deployment record](../reports/runtime-checks/openjev-trec-deployment.json)
binds the new code, remote tests and unchanged frozen inputs.

The [CPU validation record](../reports/runtime-checks/openjev-provider-quality-cpu.json)
binds the original four implementation/test files and real frozen input preflight.
At that revision, all 48 focused CPU tests passed without skips. An independent review verified
the failure accounting, including real subprocess SIGTERM/SIGKILL tests with
a CPU loopback fixture. This is implementation evidence, not model performance.
The separate N1 deployment of commit
`88c8aef9cdb1ced5d557fc1be2a4e3128614588b` also passed all 48 tests and the
15-file frozen-input preflight. It does not run a controller or use a GPU.
The [deployment record](../reports/runtime-checks/openjev-provider-quality-deployment.json)
and [tokenizer check](../reports/runtime-checks/openjev-provider-quality-tokenizer.json)
retain their evidence hashes. Both pinned 2B/9B tokenizers fit all 808 requests
within 16,384 tokens: the maximum candidate input is 9,813 tokens in JF100.
No model weights were loaded for this check.

| Frozen suite directory | Requests per model | Labelled decisions | Hard targets |
| --- | ---: | ---: | ---: |
| `provider-comparison-v1` | 189 | 146 | 140 |
| `provider-comparison-jf100-v1` | 300 | 300 | 300 |
| `provider-ir-pilot-v1` | 132 | 174 | 165 |
| `provider-fizzbuzz-control-v1` | 100 | 300 | 300 |
| `provider-mailroom-probe-v1` | 87 | 921 | 921 |
| Total | 808 | 1,841 | 1,826 |

The complete frozen coverage suite is collected into a fresh run, including its
43 unlabelled examples. This produces a standalone new result; it does not
replace the 82 reused historical predictions or mix duplicate attempts into one
quality report. The common 76-hard-case historical comparison stays separately
identified. JF100 rotations, related IR controls and mailroom questions remain
correlated observations. None of these totals measures independent problems or
closed-loop task success.

## CPU preflight and collection contract

Before any GPU query, checkpoint load, output creation or child process, the
launcher binds all five original manifest hashes, their request and gold file
hashes, fixed counts, per-request hashes, unique identities, and gold question,
kind and candidate order. It only passes each request file and its SHA256 to
`scripts/evaluate_openjev_provider.py`. Gold is read later by the launcher's
offline summarizer, not by that client or the model.

The same preflight can run without a server or GPU from the reviewed checkout,
using the original private frozen inputs:

```bash
python3 - <<'PY'
import argparse
import json
from pathlib import Path
from scripts.run_service_suite import preflight_provider_inputs

result = preflight_provider_inputs(argparse.Namespace(
    measurements=['provider_quality'],
    provider_data_root=Path('/data/zefan/open-jev/provider-quality-20260921/data')))
print(json.dumps(result, indent=2))
PY
```

This callable checks the request contract and frozen identities without loading
a tokenizer. The separate deployment check above tokenized every candidate with
each pinned Qwen tokenizer; it found no inputs exceeding 16K. Serving never
truncates; any later context or request validation error remains a failed attempt.

The owned server runs the existing LoRA/decision head path with prefix caching
disabled. Every successful response must match all seven identity fields:
base model, method, base revision, checkpoint SHA256, calibration temperature,
serving code commit and maximum context length. Its metadata must explicitly
show caching disabled. Responses retain their actual probability vectors and
typed answers. The client uses loopback HTTP, concurrency one, no warmups and
no retries; it makes no remote Jev or OpenAI calls.

The launcher rechecks raw successful responses and file bindings before using
`summarize_provider_quality`. Failed decisions contribute zero and unattempted
decisions remain pending. Noul ties select false, Choice uses the first maximum,
and categorical Score compares the most probable level. Soft targets remain
separate from hard accuracy. A fatal transport/identity error, timeout, interrupted
collection or exhausted time budget retains available partial quality and ends
the owned server before another probe or suite. A completed collection with
nonfatal request errors may continue, keeping those errors in the denominator.
Every dispatch is first recorded and synced in `attempts.jsonl`. The offline
summary requires an exact journal/sample identity match and zero in-flight
requests. A hard-killed client can leave a dispatch without a returned sample;
such a bundle is refused for scoring, the owned server is cleaned up, and the
request must not be silently retried. Graceful interrupts retain a failed sample
for an in-flight request when the client can finish its journal update.

## Run only after the existing queue releases the allocation

This follow-up is not part of the running post-training guard's fixed plan.
Neither that plan nor its pinned checkouts should be edited to add it. Before
launch, verify that all three core stages completed, the independent expansion
audit and original manifests passed, the contact/amount follow-up completed,
and all scheduling/GPU leases and owned servers released. If an output already
exists, inspect it instead of overwriting it or repeating its requests. No new
user approval is needed for these evidence checks.

The original `/data/zefan/open-jev/provider-quality-20260921/data` directory
retains the same 15 frozen private files. The original `code-88c8aef` directory
and evidence remain historical. The replacement serving source is deployed to
`/data/zefan/open-jev/openjev-trec-20260921/code-e5188e7` and passed remote CPU
verification. After the prerequisites above pass, run from this replacement
checkout with the existing Python runtime and per-process import path. The
following command does **not** wait for those checks:

```bash
cd /data/zefan/open-jev/openjev-trec-20260921/code-e5188e7
HF_HUB_CACHE=/mnt/localssd/open-jev/hf-cache \
PYTHONPATH=/data/zefan/open-jev/openjev-trec-20260921/code-e5188e7 \
/mnt/localssd/open-jev/runtime/venv/bin/python -m scripts.run_service_suite \
  --expected-hostname kwade5342000001 --gpu 3 \
  --models 2b 9b \
  --checkpoint-root /data/zefan/open-jev/runs/release-v2-fullpass-n1-v1 \
  --checkpoint-template '{tag}/checkpoint' \
  --provider-data-root /data/zefan/open-jev/provider-quality-20260921/data \
  --measurements provider_quality --max-length 16384 --batch-size 1 \
  --measurement-timeout 86460 \
  --output-root /data/zefan/open-jev/provider-quality-20260921/release-v2-2b-9b
```

Only N1-1 physical GPU 3 is selected here, serially for 2B then 9B. The
launcher's existing GPU lease, UUID binding, owned process identity and cleanup
checks remain active. Physical GPUs 4–7 and N4-4 are prohibited. The other
measurement defaults, existing core deployment and contact/amount commands are
unchanged. The replacement deployment passed CPU verification; model inference
has not started. `HF_HUB_CACHE` points directly at the existing cache directory; setting
only `HF_HOME` to that path would incorrectly append a missing `hub` directory.

Each model writes `provider_quality/<suite>/requests.json`, `attempts.jsonl`,
`samples.jsonl`, `report.json` and `quality.json` inside its new output directory. The enclosing
manifest records input/checkpoint identities, commands, subprocess outcomes,
quality file hashes, and server cleanup. Require all 808 requests accounted for
per model before describing the five suites as complete; inspect failed and
pending counts separately. Wall times in these one-attempt runs are diagnostic,
not replacements for the published repeated latency measurements.

## Publication and remaining work

The coverage input includes original Wikispeedia material whose redistribution
permission is unresolved. Original request, gold and response bundles therefore
stay private; the public sanitized projection cannot perform this exact
preflight using a replacement request file. Publish audited derived results,
hashes and permitted evidence. Never add TREC/MS MARCO passages or qrels to these
inputs, training data or a public MIT/CC0 export.

Before publishing new scores, independently audit the saved responses and
aggregates. Update the site's archive-only Open-Jev report selection separately,
while retaining the common historical slice and frozen reference labels. The
current post-hoc label sensitivity analysis remains explicitly post-hoc.

The separate [Open-Jev TREC collector and offline replay](openjev-trec-followup.md)
now implement the same 97-query input, nine adaptive windows, full qrel
denominator and expected Score semantics. Its
[tokenizer proof](../reports/runtime-checks/openjev-trec-tokenizer.json) establishes
a sufficient 13,680-token bound for the frozen adaptive windows with both
pinned 2B/9B tokenizers. TREC model inference is pending and
must follow this five-suite stage after all leases release. Its collector uses
the actual Open-Jev identity; the completed external-provider collections remain
unchanged. Full-registry GPU inference and new-domain retraining also remain
separate pending work.
