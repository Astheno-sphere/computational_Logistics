# Contact and amount service follow-up

`scripts.run_service_suite` now accepts the optional measurements `contact` and
`amount`, plus `--control-data-root` (default: this checkout's `data` directory).
Its existing default measurements remain `demo_requests workflows frontier_100
games`. A controls-only run needs no workflow, Frontier, browser or drone input.

The separate N1 environment is provisioned from source commit
`9cdf6711d2af3cf7bca0763e0c859b46606c12d3` and passed all 76 CPU tests and the
full-data preflight. It has not run against a model. The active post-training
supervisor, its pinned checkouts and three stage commands remain unchanged;
contact and amount remain pending until that core sequence finishes. The
[deployment record](../reports/runtime-checks/contact-amount-service-followup-deployment.json)
binds the reviewed source, dependency, input and remote-test hashes.

For each selected checkpoint, the existing lifecycle acquires the physical
GPU-3 lease, starts its own server, checks readiness and full checkpoint identity,
then runs contact followed by amount. Both commands receive the verified model,
method, base revision, checkpoint SHA-256 and saved temperature. The runner keeps
the measurement logs and failures, probes identity between measurements, stops
its own server and verifies GPU cleanup before advancing to the next model.
A nonzero contact result is retained and does not skip amount while the server
remains alive and identity-valid. Service loss or an identity mismatch stops
the suite. With an otherwise healthy service, the suite finishes with
`complete_with_measurement_failures` and exits nonzero when any measurement
fails. Existing outputs are refused.

## Prerequisites

1. The actual core supervisor **1603179** must finish expansion, service 2B/9B
   and service 27B. Its complete manifests and the independent expansion audit
   must pass, and its scheduling/GPU leases must be released. Do not start this
   follow-up during training, between core stages or while the audit is pending.
2. Provision a separate checkout pinned to the reviewed follow-up commit. It
   needs the frozen email, phone and amount data directories and their matching
   producer files. All 24 frozen files have now been copied and hash-verified
   under the separate data root below.
3. Provide **`phonenumbers==9.0.14`** in an isolated dependency directory or
   environment. It is now installed in the separate dependency directory below.
   A per-process `PYTHONPATH` uses it with the existing runtime Python; nothing
   was installed into the active training environment.
4. Run the CPU preflight below. It must validate all frozen manifests, data and
   producer hashes and select **1,924 contact documents** (784 email, 1,140
   phone) and **864 amount documents**. Each model evaluates the entire test/OOD
   population; there is no success filter or case limit.
5. Verify the final checkpoint identities and saved calibration, the released
   scheduling allocation, the GPU lease and physical GPU 3. Use **16,384 tokens,
   batch size 1**, serial models and fresh output directories. Do not refit
   calibration or modify the completed checkpoints.

These corpora were not in the active training mixture. Their results measure
transfer on the original controlled documents, not broad real-world extraction
ability. The existing evaluators retain actual A selections and dependent B
requests; no gold selection repairs a prediction. See the
[contact protocol](contact-service-evaluation.md) and
[amount protocol](amount-service-evaluation.md) for denominators and evidence.

## CPU preflight for the isolated environment

The provisioned paths are:

```bash
OPENJEV_CONTROL_CHECKOUT=/data/zefan/open-jev/control-eval-20260921/code-9cdf671
OPENJEV_CONTROL_COMMIT=9cdf6711d2af3cf7bca0763e0c859b46606c12d3
OPENJEV_CONTROL_DATA_ROOT=/data/zefan/open-jev/control-eval-20260921/data
OPENJEV_CONTROL_DEPS=/data/zefan/open-jev/control-eval-20260921/deps
```

This exact environment passed the following CPU preflight. The command can
be repeated without starting a model:

```bash
: "${OPENJEV_CONTROL_CHECKOUT:?Set the separately provisioned checkout path}"
: "${OPENJEV_CONTROL_COMMIT:?Set its reviewed full commit SHA}"
: "${OPENJEV_CONTROL_DATA_ROOT:?Set the provisioned frozen control data root}"
: "${OPENJEV_CONTROL_DEPS:?Set the isolated phonenumbers9.0.14 dependency directory}"
export OPENJEV_CONTROL_DATA_ROOT
cd "$OPENJEV_CONTROL_CHECKOUT"
test "$(git rev-parse HEAD)" = "$OPENJEV_CONTROL_COMMIT"
CUDA_VISIBLE_DEVICES='' \
PYTHONPATH="$OPENJEV_CONTROL_CHECKOUT:$OPENJEV_CONTROL_DEPS" \
/mnt/localssd/open-jev/runtime/venv/bin/python - <<'PY'
from argparse import Namespace
import json
import os
from pathlib import Path
from scripts.run_service_suite import preflight_control_inputs

result = preflight_control_inputs(Namespace(
    measurements=["contact", "amount"],
    control_data_root=Path(os.environ["OPENJEV_CONTROL_DATA_ROOT"]).resolve(),
))
assert result["contact"]["selected_cases"] == 1924
assert result["contact"]["inputs"]["email"]["selected_cases"] == 784
assert result["contact"]["inputs"]["phone"]["selected_cases"] == 1140
assert result["amount"]["selected_cases"] == 864
print(json.dumps(result, indent=2))
PY
```

The callable performs no network, GPU, subprocess or output-directory work.
The suite repeats this validation before creating outputs or acquiring its
lease, records it under `control_inputs` in `manifest.json`, and the evaluators
check the frozen inputs again during their own runs. Default suites do not load
control datasets or require the optional phone dependency.

## Future GPU-3 execution

Only after all prerequisites pass, use the same pinned checkout and isolated
dependencies for these two invocations, in order. The first evaluates 2B and
9B serially; the second evaluates the final expansion 27B checkpoint. These
commands do not themselves wait for the core supervisor or its audit gate.

```bash
PYTHONPATH="$OPENJEV_CONTROL_CHECKOUT:$OPENJEV_CONTROL_DEPS" \
/mnt/localssd/open-jev/runtime/venv/bin/python -m scripts.run_service_suite \
  --expected-hostname kwade5342000001 --gpu 3 \
  --models 2b 9b \
  --checkpoint-root /data/zefan/open-jev/runs/release-v2-fullpass-n1-v1 \
  --checkpoint-template '{tag}/checkpoint' \
  --measurements contact amount \
  --control-data-root "$OPENJEV_CONTROL_DATA_ROOT" \
  --max-length 16384 --batch-size 1 \
  --output-root /data/zefan/open-jev/evals/contact-amount-followup-v1/release-v2-2b-9b
```

Verify the complete manifest, both evaluator reports and GPU cleanup before
the second invocation:

```bash
PYTHONPATH="$OPENJEV_CONTROL_CHECKOUT:$OPENJEV_CONTROL_DEPS" \
/mnt/localssd/open-jev/runtime/venv/bin/python -m scripts.run_service_suite \
  --expected-hostname kwade5342000001 --gpu 3 \
  --models 27b \
  --checkpoint-root /data/zefan/open-jev/runs \
  --checkpoint-template 'browser-drone-expansion-v1-{tag}-ddp-n1-v1/checkpoint' \
  --measurements contact amount \
  --control-data-root "$OPENJEV_CONTROL_DATA_ROOT" \
  --max-length 16384 --batch-size 1 \
  --output-root /data/zefan/open-jev/evals/contact-amount-followup-v1/expansion-27b
```

## Implementation checks

`python3 -m unittest tests.test_service_suite -v` passes all **29 CPU tests**,
including optional dependency/input isolation, preflight rejection before GPU
or subprocess work, exact evaluator identity arguments, contact-before-amount
ordering, failure retention and serial cleanup. CLI help and `git diff --check`
also pass. With the isolated, hash-verified `phonenumbers==9.0.14` wheel, the
combined runner/contact/amount regression run passes **all 76 tests with no
skips**. The real frozen-data CPU preflight also selects exactly 1,924 contact
and 864 amount documents. The [CPU validation record](../reports/runtime-checks/contact-amount-service-followup-cpu.json)
binds source, dependency and input hashes. This closes the six optional-phone
test skips observed before the isolated dependency was installed.

```bash
python3 -m unittest tests.test_service_suite tests.test_contact_service tests.test_amount_service -v
python3 -m scripts.run_service_suite --help
```

All implementation checks use CPU fixtures. They are not model-quality results
and did not start a server, use a GPU or call an API.
