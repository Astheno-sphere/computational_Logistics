# Evaluate the final checkpoints

Run this phase **after the new four-GPU 27B job has completed calibration,
checkpoint reload and process cleanup**. It evaluates final 2B/9B release-v2
checkpoints and the new 27B expansion checkpoint. It does not schedule training
or replace the already queued four-card handoff.

Do not pull, checkout, edit or run this suite inside any active training,
evaluation or handoff checkout. Use two separate pinned checkouts: the newly
reviewed expansion evaluator first, then the existing service-suite revision.
The commands run on N1-1 only; GPUs 0–3 must first be free. Complete the 27B
full-data evaluation on those four cards, release its workers and leases, then
run task evaluation on **physical GPU 3 serially**. Cards 4–7 are excluded.

## What each evaluation measures

| Evaluation | Records/attempts per model | Meaning and limits |
| --- | ---: | --- |
| Existing four-GPU internal data evaluation | 10,532 test + 15,920 OOD = **26,452 records** | Every release-v2 held-out decision row; implemented for final 2B/9B only. Not JF100 or end-to-end task success. |
| New 27B four-GPU internal data evaluation | 14,902 test + 25,379 OOD = **40,281 records** | Every expansion held-out decision row, using the explicit `browser-drone-expansion-v1` profile. CPU-verified evaluator; GPU execution awaits completed DDP training. |
| JF100 | **100 items × 3 option rotations = 300 trials** | Fixed external Choice benchmark, 50 correlated counterfactual pairs; all trials remain in the denominator. |
| Workflows | **96 cases** | Four workflows × 12 distinct parents × test/OOD; one variant per parent, selected by IDs with seed 42. Synthetic customer-service, invoice, security and agent-trace policy/action-set judgments. |
| Games, including Doom | **45 episodes** | Five games × seeds 10001/10002/10003 × model/random/teacher policies; at most 40 decisions per episode. Only 15 episodes use the learned model. Local simplified games, tiny Wiki graph and ViZDoom basic; not an official-game benchmark or guaranteed unseen episode layouts. |
| Browser | **120 snapshots from 40 parents** | 20 parents per test/OOD split, three variants, seed 42. Operation/conditional heads and complete proposals; no browser executor or real website completion. |
| Drone | **120 snapshots from 40 parents** | Same parent/variant selection rule. Maneuver, risk, target-loss and complete decisions; no flight simulator or physical-flight success. |

The scheduled new 27B uses browser/drone expansion data; 2B/9B use release-v2.
Their comparison therefore changes both model size and training mixture. Keep
the fixed cases and their selection hashes identical across models and label
the different training data. Do not describe improvements as size-only effects.

The new expansion profile is implemented and passed CPU unit tests; its
independent real-data preflight records all IDs, split hashes and the four
assignments. This is preparation evidence, not a model evaluation result.
The DDP trainer's configured `--eval-rows 512` still measures only 512 test and
512 OOD rows. Only the complete evaluation below closes the 40,281-row gap.

## 1. Evaluate all 40,281 expansion records from a new checkout

These are future execution commands, not evidence that evaluation has run.
Use an authenticated noninteractive Git credential helper already available
on N1-1; no credentials belong in these commands or artifacts.

The expansion evaluator is pinned to reviewed implementation commit
`0b6e4fcca3306b9fe98b96a08074e78b4674fd16`. The guard validates the full commit
format before cloning. Revision `ceb1ea85d7905d18972afb39da0f5f0baef2097a`
contains the service-suite interfaces but not this expansion profile.
Use a new checkout and output directory, leaving the active four-card checkout
unchanged.

```bash
set -euo pipefail
export JEV_EXPANSION_REV=0b6e4fcca3306b9fe98b96a08074e78b4674fd16
if [[ ! "$JEV_EXPANSION_REV" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'Set JEV_EXPANSION_REV to the reviewed expansion evaluator commit.' >&2
  exit 1
fi
export JEV_EXPANSION_CHECKOUT="/mnt/localssd/open-jev/expansion-eval-${JEV_EXPANSION_REV:0:8}"
export JEV_EXPANSION_OUTPUT=/data/zefan/open-jev/evals/expansion-27b-four-gpu-data-v1
export JEV_EXPANSION_PY=/mnt/localssd/open-jev/runtime/venv/bin/python
export HF_HUB_CACHE=/mnt/localssd/open-jev/hf-cache
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
test ! -e "$JEV_EXPANSION_CHECKOUT"
test ! -e "$JEV_EXPANSION_OUTPUT"
GIT_TERMINAL_PROMPT=0 git clone --no-checkout \
  https://github.com/Zefan-Cai/Open-Jev-Dev.git "$JEV_EXPANSION_CHECKOUT"
git -C "$JEV_EXPANSION_CHECKOUT" checkout --detach "$JEV_EXPANSION_REV"
test "$(git -C "$JEV_EXPANSION_CHECKOUT" rev-parse HEAD)" = "$JEV_EXPANSION_REV"
cd "$JEV_EXPANSION_CHECKOUT"
"$JEV_EXPANSION_PY" -m scripts.evaluate_checkpoints_parallel \
  --dataset-profile browser-drone-expansion-v1 --models 27b \
  --data /data/zefan/open-jev/data/browser-drone-expansion-v1 \
  --checkpoint-27b /data/zefan/open-jev/runs/browser-drone-expansion-v1-27b-ddp-n1-v1/checkpoint \
  --output-root "$JEV_EXPANSION_OUTPUT"
```

Do not launch until the new DDP run has completed 27,581 optimizer steps,
110,324 consumed rows, its fixed 512-row calibration, final checkpoint reload
and process cleanup. The evaluator verifies this provenance, including seed
20260920 and matching four-rank CUDA/NCCL metadata, before model loading. It
requires the saved 4,096-token limit and calibration; it does not refit a
temperature. The frozen manifest, all five split hashes and checkpoint/log
hashes bind the recorded plan and outputs.

The `concatenated_test_ood` partition assigns 10,071/10,070/10,070/10,070 records
to GPUs 0/1/2/3. This differs from the unchanged per-split release-v2 partition.
Missing/duplicate/mismatched rows fail the merge; inference errors remain in
the full denominators and produce a nonzero exit. Preserve all shard logs,
raw results, plan, merged split outputs, summary and root manifest. A complete
manifest must confirm cleanup before the task suite starts. See
[parallel-data-eval.md](parallel-data-eval.md) for the exact contract.

### Capture and independently audit the completed expansion results

The separate [expansion auditor](../reports/full-data-eval-expansion-n1-v1/README.md)
checks the new 40,281-row partition. Keep the historical 2B/9B auditor and its
26,452-row results unchanged. The new tools are CPU preparation only; no final
27B capture, inference package or audit result exists yet.

After training completes, create the real final 27B package using the
[checkpoint packager](checkpoint-package.md), then copy it unchanged to the
local `runs/model-packages/browser-drone-expansion-v1/27b` directory. After the
four-card expansion evaluation completes and its controller confirms cleanup,
run these commands from the local repository containing the new auditor, with
`python3` pointing to Python 3.12 or later:

```bash
python3 reports/full-data-eval-expansion-n1-v1/capture.py \
  --output runs/full-data-eval-expansion-n1-v1/27b
python3 reports/full-data-eval-expansion-n1-v1/verify.py \
  --evidence runs/full-data-eval-expansion-n1-v1/27b \
  --data data/browser-drone-expansion-v1 \
  --package runs/model-packages/browser-drone-expansion-v1/27b \
  --output reports/full-data-eval-expansion-n1-v1/27b-audit.json
```

Capture returns `not_ready` with exit code 2 while completion artifacts are
missing. It copies the original evaluation outputs and completed training
evidence, including actual final checkpoint bytes, with stable hashes before
and after copying. Verification independently recomputes all split/source/kind/
group metrics and checks every row, calibration selection, saved reload logits
and packaged inference file. Missing, duplicate or failed predictions prevent
a passing audit; preserve their original artifacts. Neither tool loads tensors,
runs inference or refits calibration. Require a passing real audit before
reporting full 27B results or continuing to the service suite below.

## 2. Prepare the separate service-suite checkout

After the complete expansion evaluation exits successfully, use this second
checkout for JF100, workflows, games, browser and drone. These commands keep the
existing reviewed service-suite revision and do not assume it supports the
new expansion data-evaluation CLI.

```bash
set -euo pipefail
export JEV_FINAL_REV=ceb1ea85d7905d18972afb39da0f5f0baef2097a
export JEV_FINAL_CHECKOUT=/mnt/localssd/open-jev/final-eval-ceb1ea85
export JEV_FINAL_OUTPUT=/data/zefan/open-jev/evals/final-checkpoints-task-suite-v1
export JEV_FINAL_PY=/mnt/localssd/open-jev/runtime/venv/bin/python
export HF_HUB_CACHE=/mnt/localssd/open-jev/hf-cache
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
test ! -e "$JEV_FINAL_CHECKOUT"
test ! -e "$JEV_FINAL_OUTPUT"
GIT_TERMINAL_PROMPT=0 git clone --no-checkout \
  https://github.com/Zefan-Cai/Open-Jev-Dev.git "$JEV_FINAL_CHECKOUT"
git -C "$JEV_FINAL_CHECKOUT" checkout --detach "$JEV_FINAL_REV"
test "$(git -C "$JEV_FINAL_CHECKOUT" rev-parse HEAD)" = "$JEV_FINAL_REV"
cd "$JEV_FINAL_CHECKOUT"
mkdir -p "$JEV_FINAL_OUTPUT"
```

That revision contains the required service-suite interfaces. If a later reviewed
revision is selected, record its full 40-character hash and use another new
checkout/output directory; do not update an active checkout to change protocols
mid-evaluation. Source datasets and checkpoint directories below are read only.

## 3. Verify real final runs, saved calibration and allocation

The service suite itself verifies loaded checkpoint identity, but it does not
independently require a completed full-pass training summary. Run this CPU/read
preflight before starting it. It refuses unfinished runs, wrong dataset bytes,
short training logs, an old 27B checkpoint, invalid calibration provenance or
failed reload checks. Its GPU query does not allocate a GPU.

```bash
"$JEV_FINAL_PY" - <<'PY' > "$JEV_FINAL_OUTPUT/checkpoint-readiness.json"
import hashlib, json, math, os
from pathlib import Path
from scripts.evaluate_checkpoints_parallel import load_data, checkpoint_identity, require_free_gpus
from scripts.run_service_suite import checkpoint_identity as service_identity, enforce_resource_policy

def read(path):
    return json.loads(Path(path).read_text())

def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()

plan = read('configs/n1-four-gpu-handoff.json')
proof = {'evaluation_revision': os.environ['JEV_FINAL_REV'], 'models': {}}
expansion_eval = Path('/data/zefan/open-jev/evals/expansion-27b-four-gpu-data-v1')
expansion_manifest = read(expansion_eval/'manifest.json')
expansion_summary = read(expansion_eval/'27b/summary.json')
assert expansion_manifest['status'] == 'complete' and expansion_manifest['gpus_free_after_cleanup'] is True
assert expansion_manifest['dataset_profile'] == expansion_summary['dataset_profile'] == 'browser-drone-expansion-v1'
assert expansion_summary['status'] == 'complete' and expansion_summary['total_rows'] == 40281
assert expansion_summary['data_identity']['counts'] == {'test': 14902, 'ood': 25379}
proof['expansion_full_data'] = {'manifest_sha256': sha(expansion_eval/'manifest.json'),
    'summary_sha256': sha(expansion_eval/'27b/summary.json'), 'implementation_sha256': expansion_manifest['implementation_sha256']}
policy = enforce_resource_policy(3, 'kwade5342000001')
_, release_identity, release_cal_ids = load_data('/mnt/localssd/open-jev/repo/data/release-v2')
for tag in ('2b', '9b', '27b'):
    if tag == '27b':
        output = Path(plan['training_output'])
        data = Path('/data/zefan/open-jev/data/browser-drone-expansion-v1')
        steps, consumed = 27581, 110324
        model, revision = 'Qwen/Qwen3.8-27B', plan['fresh_27b_training']['upstream_revision']
    else:
        job = plan['jobs'][tag]
        output, data = Path(job['output']), Path(job['data'])
        steps, consumed, model, revision = 20204, 80816, job['model'], job['revision']
    run, summary = read(output/'run.json'), read(output/'summary.json')
    checkpoint = output/'checkpoint'
    config, temp = read(checkpoint/'model.json'), read(checkpoint/'temperature.json')
    assert summary['status'] == 'complete' and run['model'] == summary['model'] == config['model_id'] == model
    assert run['revision'] == config['revision'] == revision
    assert run['steps'] == summary['steps'] == steps and summary['trained_rows_consumed'] == consumed
    assert run['accumulation'] == 4 and run['train_rows'] == 0 and run['training_sampling'] == 'shuffled'
    assert config['max_length'] == run['max_length'] == 4096 and config['lora_rank'] == run['lora_rank'] == 8
    reload_error = summary['checkpoint_reload_max_error']
    assert type(reload_error) in (int, float) and math.isfinite(reload_error) and 0 <= reload_error <= 0.05
    training = [json.loads(line) for line in (output/'training.jsonl').read_text().splitlines() if line.strip()]
    assert [row['step'] for row in training] == list(range(1, steps + 1))
    assert all(type(row[key]) in (int, float) and math.isfinite(row[key])
               for row in training for key in ('loss', 'gradient_norm', 'elapsed_seconds'))
    manifest = read(data/'manifest.json')
    assert run['data_sha256'] == manifest['sha256']
    for split, digest in manifest['sha256'].items():
        path = data/(split+'.jsonl')
        assert sha(path) == digest == plan['input_sha256'][str(path)]
    ids = run['calibration_ids']
    available = {json.loads(line)['id'] for line in (data/'calibration.jsonl').read_text().splitlines() if line.strip()}
    assert ids and len(set(ids)) == len(ids) and set(ids) <= available
    assert temp['split'] == 'calibration' and type(temp['n']) is int and temp['n'] == len(ids)
    assert temp['ids_sha256'] == hashlib.sha256(json.dumps(ids).encode()).hexdigest()
    assert type(temp['temperature']) in (int, float) and math.isfinite(temp['temperature']) and temp['temperature'] > 0
    assert summary['temperature'] == temp['temperature']
    assert (checkpoint/'head.pt').is_file() and (checkpoint/'adapter/adapter_config.json').is_file()
    assert any((checkpoint/'adapter'/name).is_file() for name in ('adapter_model.safetensors', 'adapter_model.bin'))
    if tag == '27b':
        assert sha(data/'manifest.json') == plan['fresh_27b_training']['dataset_manifest_sha256']
        assert run['initialization'] in ('fresh_pinned_upstream', 'strict_same_run_ddp_resume')
        assert run['distribution'] == summary['distribution']
        assert run['distribution']['world_size'] == run['distribution']['global_batch_size'] == 4
        assert run['distribution']['local_rows_per_step'] == 1
        completed = expansion_summary['checkpoint']
        assert completed['model'] == model and completed['revision'] == revision
        assert completed['training_completion']['run_sha256'] == sha(output/'run.json')
        assert completed['training_completion']['summary_sha256'] == sha(output/'summary.json')
        assert completed['training_completion']['training_log_sha256'] == sha(output/'training.jsonl')
        assert completed['training_completion']['calibration_predictions_sha256'] == sha(output/'calibration.jsonl')
        assert completed['calibration'] == temp
    else:
        checkpoint_identity(checkpoint, tag, release_identity, release_cal_ids)
    loaded_identity = service_identity(checkpoint, tag, os.environ['JEV_FINAL_REV'], max_length=16384)
    if tag == '27b':
        assert loaded_identity['checkpoint_sha256'] == expansion_summary['checkpoint']['checkpoint_sha256']
    proof['models'][tag] = {'run_sha256': sha(output/'run.json'), 'summary_sha256': sha(output/'summary.json'),
        'checkpoint': str(checkpoint), 'identity': loaded_identity}
proof.update(policy=policy, idle_gpu_uuids=require_free_gpus())
print(json.dumps(proof, indent=2))
PY
```

Completion files alone do not release GPUs. This preflight requires all four
cards to be idle; each actual suite invocation additionally takes the existing
GPU-3 lease and checks its physical UUID, occupancy and port 8791. The DDP
supervisor owns the four-card leases until its children exit. Never bypass a
busy-card/lease failure or stop an unrelated process to run these commands.

## 4. Freeze the external benchmark and separation proof

JF100 is fixed at upstream commit
`9abacec47394f3b393f81fbe3cdd524f028bc088`, dataset SHA-256
`dd107ba90de381eaa479408492e81d7222115782e5fe601ab43986f94cd1d0fa`.
It stays outside training/calibration data. Its gold answers, rationales,
published outcomes and evaluation errors must not drive training, temperature
selection or case selection. Reuse all 300 trials; do not rerun only prior
failures or choose the best rotation.

```bash
"$JEV_FINAL_PY" -m jev.eval_frontier \
  --source /mnt/localssd/open-jev/evals/jev-frontier-100 \
  --audit-only --output-dir "$JEV_FINAL_OUTPUT/jf100-source-audit"
"$JEV_FINAL_PY" -m scripts.check_eval_separation \
  --benchmark-root /mnt/localssd/open-jev/evals/jev-frontier-100 \
  --dataset /mnt/localssd/open-jev/repo/data/release-v2 \
  --output "$JEV_FINAL_OUTPUT/release-v2-separation.json"
"$JEV_FINAL_PY" -m scripts.check_eval_separation \
  --benchmark-root /mnt/localssd/open-jev/evals/jev-frontier-100 \
  --dataset /data/zefan/open-jev/data/browser-drone-expansion-v1 \
  --output "$JEV_FINAL_OUTPUT/expansion-separation.json"
```

These commands do not perform model inference. Exact/embedded overlap checks
are integrity screens, not proof against every form of semantic contamination.

## 5. Evaluate the three models serially

Use **16,384 tokens and candidate batch size 1** for this task-suite condition.
Earlier JF100 runs at 4,096 rejected 6,167/9,813-token requests. The 16K condition
re-evaluates the complete benchmark, preserves the earlier 4K failures, and does
not alter checkpoint weights or its saved temperature. Applying the same
service settings to all task families avoids an extra model reload per family.
These settings are explicit in every identity/manifest; do not mix their
timings with older 4K/batch-16 runs or the four-GPU data evaluation.

```bash
jev_final_suite() {
  "$JEV_FINAL_PY" -m scripts.run_service_suite \
    --expected-hostname kwade5342000001 --gpu 3 \
    --frontier-source /mnt/localssd/open-jev/evals/jev-frontier-100 \
    --workflow-cases /mnt/localssd/open-jev/repo/data/workflows-v1/workflow_cases.jsonl \
    --browser-cases /data/zefan/open-jev/data/browser-v1/cases.jsonl \
    --drone-cases /data/zefan/open-jev/data/drone-control-v1/cases.jsonl \
    --measurements workflows frontier_100 games browser drone \
    --include-doom --doom-decision-mode typed-v1 \
    --max-length 16384 --batch-size 1 "$@"
}
jev_final_suite --models 2b 9b \
  --checkpoint-root /data/zefan/open-jev/runs/release-v2-fullpass-n1-v1 \
  --checkpoint-template '{tag}/checkpoint' \
  --output-root "$JEV_FINAL_OUTPUT/release-v2-2b-9b"
jev_final_suite --models 27b \
  --checkpoint-root /data/zefan/open-jev/runs \
  --checkpoint-template 'browser-drone-expansion-v1-{tag}-ddp-n1-v1/checkpoint' \
  --output-root "$JEV_FINAL_OUTPUT/expansion-27b"
```

Each model runs workflows, JF100, games, browser and drone in that fixed order.
Browser/drone must be named explicitly because the suite does not include them
by default. The normal Doom default is `combined-v1`; the explicit `typed-v1`
above uses the training-aligned movement Choice, attack Noul and alignment
Score (nine candidate sequences per request). Movement and attack drive the
buttons; alignment is recorded and does not replace an action. ViZDoom must be
installed in the selected runtime; no mock game substitutes for it. Keep these
results separate from historical combined-action Doom runs.

The two checkpoint layouts require separate suite calls. The new 27B checkpoint
must come from `browser-drone-expansion-v1-27b-ddp-n1-v1/checkpoint`; the retired
single-GPU `release-v2-fullpass-n1-v1/27b` is not its replacement.

## Retain failures and interpret completion

Keep `checkpoint-readiness.json`, all suite manifests/server logs, selected
cases and hashes, original requests/responses, game trajectories and reports.
Match each suite's expected checkpoint identity with the saved readiness proof
before reporting results. Fixed browser/drone selections should match across
all models; retain their parent correlations rather than treating variants as
independent examples.

HTTP/schema/model-identity failures and incomplete runs remain visible. Browser,
drone and JF100 system metrics retain their selected-case/trial denominators;
game native success among valid episodes is conditional and must be shown with
attempt/error counts. A workflow exception preserves partial outputs and
`failure.json`, not a complete success score. A suite may finish with
`complete_with_measurement_failures`; this is not a clean result. The shell
stops after a nonzero suite exit: inspect and preserve those artifacts before
explicitly continuing or creating a separately named retry.

Low accuracy is a valid measured outcome. Do not drop cases, invoke teacher
fallbacks, change the frozen benchmark, overwrite failed artifacts or infer
real browser/flight/game competence from schema-valid responses. These commands
perform no optional latency-generation comparison and make no proprietary Jev
speed claim.
