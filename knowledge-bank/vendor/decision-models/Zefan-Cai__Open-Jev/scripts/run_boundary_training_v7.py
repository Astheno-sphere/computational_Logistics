"""One declared v7 attempt from frozen source; CPU preflight never loads a model."""
import argparse
from datetime import datetime, timezone
import gc
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = '87eb8b419685d272f059b3696e0f547e47ebdcc6'
PLAN = ROOT/'reports/boundary-controls-v7-20261002/prepared-training/comparison-plan.json'
PLAN_SHA256 = 'bab40284419d8ff0bfcdca818047cc96581d0d4e69a7fb891f1c08fe0ec49f35'
PATHS = ('source_directory', 'dataset', 'released_checkpoint', 'training_run',
         'comparison_output', 'completion_receipt', 'resource_receipt')
RUNTIME_NAMES = ('torch', 'transformers', 'peft', 'triton', 'safetensors', 'accelerate')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def file_inventory(path):
    return {p.relative_to(path).as_posix(): sha(p) for p in sorted(Path(path).rglob('*')) if p.is_file()}


def write_once(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False)+'\n')


def git(directory, *args):
    environment = os.environ.copy()
    for name in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR'):
        environment.pop(name, None)
    return subprocess.check_output(['git', '-C', str(directory), *args], text=True,
                                   stderr=subprocess.DEVNULL, env=environment).strip()


def translated_argv(plan, request):
    """Transport paths only; no arbitrary saved command is executed."""
    argv = list(plan['training_argv'][3:])
    for flag, field in (('--data', 'dataset'), ('--output', 'training_run'),
                        ('--initial-checkpoint', 'released_checkpoint')):
        require(argv.count(flag) == 1, 'Missing/duplicate path flag: '+flag)
        argv[argv.index(flag)+1] = request[field]
    require(not any('/future-host/' in part for part in argv), 'Unresolved future-host path')
    return argv


def validate_paths(request):
    for name in PATHS:
        path = Path(request[name])
        require(path.is_absolute() and 'future-host' not in path.parts, 'Resolve host path: '+name)
    inputs = [Path(request[name]).resolve() for name in
              ('source_directory', 'dataset', 'released_checkpoint')]+[ROOT.resolve()]
    outputs = [Path(request[name]).resolve() for name in
               ('training_run', 'comparison_output', 'completion_receipt')]
    for output in outputs:
        require(not output.exists(), 'Refuse existing attempt artifact: '+str(output))
        for path in inputs:
            require(not output.is_relative_to(path) and not path.is_relative_to(output),
                    'Output overlaps immutable input: '+str(output))
    for i, output in enumerate(outputs):
        for other in outputs[i+1:]:
            require(not output.is_relative_to(other) and not other.is_relative_to(output),
                    'Attempt output paths overlap')
    require(len({path.parent for path in outputs}) == 1,
            'Attempt outputs must share a fresh task root outside source/data/checkpoint')


def prepare(args):
    from scripts.compare_boundary_training_v7 import source_identity
    from scripts.compare_policy_training_v6 import checkpoint_identity, directory_sha, read
    from jev.data import read_split_directory, validate_records
    from jev.train import read_rows
    request_path = Path(args.request).resolve()
    request = json.loads(request_path.read_text())
    require(request.get('schema_version') == 1, 'Unknown execution request schema')
    require(request.get('evaluation_commit') == args.expected_commit, 'Execution/evaluation commit mismatch')
    implementation = source_identity(args.expected_commit, SOURCE_COMMIT)
    require(not git(ROOT, 'status', '--porcelain'), 'Evaluation checkout must be clean')
    validate_paths(request)
    task = Path(request['completion_receipt']).parent.resolve()
    require(request_path.parent == task, 'Execution request must be in its task root')
    require(not (task/'attempt.lock.json').exists(), 'This declared attempt has already started; no retry')
    require(sha(PLAN) == request.get('plan_sha256') == PLAN_SHA256, 'Frozen plan changed')
    plan = json.loads(PLAN.read_text())
    require(plan['source_commit'] == SOURCE_COMMIT, 'Frozen training source changed')
    source = Path(request['source_directory'])
    require(git(source, 'rev-parse', 'HEAD') == SOURCE_COMMIT, 'Training checkout differs from frozen source')
    require(not git(source, 'status', '--porcelain'), 'Training checkout must be clean')
    for name, digest in plan['implementation_sha256'].items():
        require(sha(source/name) == sha(ROOT/name) == digest, 'Frozen implementation changed: '+name)
    for name in ('model', 'train', 'api', 'metrics', 'data'):
        require((source/f'jev/{name}.py').read_bytes() == (ROOT/f'jev/{name}.py').read_bytes(),
                'Training/evaluation model implementation mismatch: '+name)
    data = Path(request['dataset'])
    require(sha(data/'manifest.json') == plan['data_manifest_sha256'], 'Mixture manifest changed')
    manifest = json.loads((data/'manifest.json').read_text())
    hashes = {name: sha(data/name) for name in
              {**manifest['files_sha256'], **plan['heldout_files_sha256']}}
    require(hashes == {**manifest['files_sha256'], **plan['heldout_files_sha256']}, 'Mixture/retained data changed')
    require(sha(data/'comparison-plan.json') == PLAN_SHA256, 'Staged plan changed')
    summary = validate_records(read_split_directory(data))
    selected = read_rows(data/'train.jsonl', 3792, 20261003, balanced=False)
    require(summary['splits'] == {'train': 3792, 'calibration': 436, 'validation': 436, 'test': 256, 'ood': 256},
            'Mixture split counts changed')
    require(len(selected) == len({row['id'] for row in selected}) == 948*4, 'Not one configured full Train pass')
    require(sum(len(read(data/f'observed-regression/{v}/{s}.jsonl'))
                for v in ('v4', 'v5', 'v6') for s in ('test', 'ood')) == 392, 'Observed selection changed')
    initial = checkpoint_identity(request['released_checkpoint'], request['training_run'], plan)
    expected = plan['expected_initial_checkpoint']
    require(initial['files_sha256'] == expected['files_sha256'] and
            directory_sha(request['released_checkpoint']) == expected['directory_sha256'],
            'Exact published checkpoint required')
    runtime = {name: version(name) for name in RUNTIME_NAMES}
    require(runtime == request.get('runtime'), 'Staged package versions changed')
    require(re.fullmatch(r'GPU-[0-9a-f-]+', request.get('gpu_uuid', '')), 'Use one physical GPU UUID')
    # Snapshot and optional overlay contents are recorded at CPU staging, not inferred from version strings.
    stage_path = task/'cpu-stage-receipt.json'
    require(sha(stage_path) == request.get('cpu_stage_receipt_sha256'), 'CPU staging receipt changed')
    stage = json.loads(stage_path.read_text())
    require(stage.get('status') == 'cpu_staged_no_cuda_initialization' and stage.get('cuda_initialized') is False
            and stage.get('source_commit') == SOURCE_COMMIT and stage.get('runtime') == runtime,
            'Staging source/runtime is not verified')
    snapshot = Path(stage['base_snapshot'])
    require(snapshot.name == initial['config']['revision'], 'Base snapshot revision changed')
    require(bool(stage['base_snapshot_files_sha256']), 'Empty base snapshot proof')
    require(file_inventory(snapshot) == stage['base_snapshot_files_sha256'], 'Base snapshot inventory/content changed')
    overlay = stage.get('overlay')
    if overlay:
        require(bool(stage.get('overlay_files_sha256')), 'Overlay requires content hashes')
        require(file_inventory(Path(overlay)) == stage['overlay_files_sha256'], 'Runtime overlay inventory/content changed')
    return request, plan, {'status': 'cpu_preflight_passed_no_model_load',
        'source_commit': SOURCE_COMMIT, 'evaluation_source': implementation,
        'request_sha256': sha(request_path), 'cpu_stage_receipt_sha256': sha(stage_path),
        'plan_sha256': PLAN_SHA256, 'data_files_sha256': hashes, 'runtime': runtime,
        'configured_train_rows': len(selected), 'direct_per_row_consumption_observed': False,
        'initial_checkpoint': initial, 'stage': stage, 'resolved_training_argv': translated_argv(plan, request)}


def validate_resource(request):
    receipt = json.loads(Path(request['resource_receipt']).read_text())
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    require(receipt.get('status') == 'ready_for_single_attempt' and receipt.get('ownership_verified') is True,
            'Fresh resource acquisition proof required')
    require(receipt.get('gpu_uuid') == request['gpu_uuid'] and receipt.get('boot_id') == boot,
            'Resource UUID/boot identity changed')
    checked = datetime.fromisoformat(receipt['checked_at_utc'])
    require(checked.tzinfo is not None and 0 <= (datetime.now(timezone.utc)-checked).total_seconds() <= 120,
            'Resource acquisition proof is stale')
    require(type(receipt.get('restoration_required')) is bool, 'Declare resource restoration policy')
    if receipt['restoration_required']:
        guard = receipt['restoration_guard_identity']
        proc = Path('/proc')/str(guard['pid'])
        stat = proc.joinpath('stat').read_text().rsplit(')', 1)[1].split()
        require(stat[0] not in ('Z', 'X', 'T', 't') and guard['boot_id'] == boot and proc.stat().st_uid == guard['uid'] == os.getuid()
                and int(stat[19]) == guard['start_ticks'], 'Restoration guard identity changed')
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == request['gpu_uuid'], 'Assigned UUID must be the only visible GPU')
    pids = subprocess.check_output(['nvidia-smi', '-i', request['gpu_uuid'],
        '--query-compute-apps=pid', '--format=csv,noheader,nounits'], text=True, timeout=12).strip()
    require(not pids, 'Assigned GPU still has compute processes')
    gpu = subprocess.check_output(['nvidia-smi', '-i', request['gpu_uuid'],
        '--query-gpu=uuid,memory.used,utilization.gpu', '--format=csv,noheader,nounits'], text=True, timeout=12).strip().split(',')
    require(len(gpu) == 3 and gpu[0].strip() == request['gpu_uuid'] and int(gpu[1]) <= 256 and int(gpu[2]) == 0,
            'Assigned GPU is not at an idle memory/utilization baseline')
    return receipt


def validate_completed_run(run):
    summary = json.loads((run/'summary.json').read_text())
    require(summary.get('status') == 'complete' and summary.get('steps') == 948
            and summary.get('trained_rows_consumed') == 3792, 'Training did not complete its fixed schedule')
    journal = [json.loads(line) for line in (run/'training.jsonl').read_text().splitlines()]
    require([row.get('step') for row in journal] == list(range(1, 949)), 'Training journal is incomplete/duplicated')
    for row in journal:
        for name in ('loss', 'gradient_norm', 'elapsed_seconds', 'peak_memory_gib'):
            require(isinstance(row.get(name), (int, float)) and math.isfinite(row[name])
                    and row[name] >= 0, 'Nonfinite/invalid journal field: '+name)
    require(not (run/'training-checkpoints').exists(), 'This attempt must not create resumable snapshots')
    return summary


def execute(args):
    request, plan, preflight = prepare(args)
    task = Path(request['completion_receipt']).parent
    require(os.getsid(0) == os.getpid(), 'Driver must lead its own controller-owned session')
    resource = validate_resource(request)
    write_once(task/'attempt.lock.json', {**{k: v for k, v in preflight.items() if k != 'stage'},
        'status': 'single_attempt_started_no_retry', 'pid': os.getpid(),
        'resource_receipt_sha256': sha(request['resource_receipt']), 'resource': resource})
    removed = [name for name in os.environ if name.startswith('JEV_')]
    for name in removed:
        os.environ.pop(name)
    os.environ['JEV_TORCH_DTYPE'] = 'bfloat16'
    cache = str(Path(preflight['stage']['base_snapshot']).parents[2])
    os.environ.update(HF_HUB_CACHE=cache, HUGGINGFACE_HUB_CACHE=cache,
                      HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    sys.path.insert(0, request['source_directory'])
    # Preflight imported CPU helpers from evaluation source. The model call must resolve frozen source.
    for name in list(sys.modules):
        if name == 'jev' or name.startswith('jev.'):
            del sys.modules[name]
    from jev import train
    require(Path(train.__file__).resolve() == Path(request['source_directory']).resolve()/'jev/train.py',
            'Training module resolved outside the frozen checkout')
    import torch
    from safetensors.torch import load_file
    from scripts.compare_policy_training_v6 import directory_sha
    require(not torch.cuda.is_initialized(), 'Preflight must not initialize CUDA')
    training_runtime = {'torch': str(torch.__version__), 'transformers': version('transformers'), 'peft': version('peft')}
    original_initialize, original_step, original_argv = train.initialize_model, torch.optim.AdamW.step, sys.argv
    observed, first_step = [], False

    def initialize(profile, model_class, identity):
        require(identity is not None and identity['files_sha256'] == plan['expected_initial_checkpoint']['files_sha256'],
                'Released initialization identity changed')
        model = original_initialize(profile, model_class, identity)
        checkpoint = Path(request['released_checkpoint'])
        saved = load_file(str(checkpoint/'adapter/adapter_model.safetensors'))
        loaded, counts = {}, {'lora_A': 0, 'lora_B': 0, 'head': 0, 'base': 0}
        for name, parameter in model.named_parameters():
            group = 'head' if name.startswith('head.') else 'lora_A' if '.lora_A.' in name else 'lora_B' if '.lora_B.' in name else 'base'
            counts[group] += parameter.numel()
            require(parameter.requires_grad == (group != 'base'), 'Trainable parameter mismatch: '+name)
            require(parameter.dtype == (torch.bfloat16 if group == 'base' else torch.float32), 'Parameter dtype mismatch: '+name)
            if group in ('lora_A', 'lora_B'):
                loaded[name.removeprefix('backbone.').replace('.default.', '.')] = parameter.detach().cpu()
        require(all(counts.values()) and loaded.keys() == saved.keys(), 'Actual LoRA parameter inventory changed')
        require(all(torch.equal(value, saved[name].float()) for name, value in loaded.items()), 'Loaded LoRA differs from publication')
        saved_head = torch.load(checkpoint/'head.pt', map_location='cpu', weights_only=True)
        require(model.head.state_dict().keys() == saved_head.keys() and
                all(torch.equal(value.detach().cpu(), saved_head[name].float()) for name, value in model.head.state_dict().items()),
                'Loaded head differs from publication')
        layers = [layer for layer in model.backbone.modules() if hasattr(layer, 'lora_A')]
        require(list(model.backbone.active_adapters) == ['default'] and layers
                and all(not layer.merged and not layer.disable_adapters for layer in layers), 'Adapter is not active/unmerged')
        write_once(task/'initial-load-verification.json', {'status': 'passed', 'loaded_lora_and_head_exact': True,
            'base_frozen': True, 'parameter_numel': counts, 'checkpoint_directory_sha256': directory_sha(checkpoint),
            'training_source_commit': SOURCE_COMMIT, 'training_runtime': training_runtime,
            'removed_environment_names': removed, 'driver_sha256': sha(__file__)})
        observed.append(model)
        return model

    def step(optimizer, *step_args, **step_kwargs):
        nonlocal first_step
        if not first_step:
            gradients = {'lora_A': [], 'lora_B': [], 'head': []}
            for name, parameter in observed[0].named_parameters():
                group = 'head' if name.startswith('head.') else 'lora_A' if '.lora_A.' in name else 'lora_B' if '.lora_B.' in name else 'base'
                if group == 'base':
                    require(parameter.grad is None, 'Base gradient unexpectedly present: '+name)
                else:
                    require(parameter.grad is not None and torch.isfinite(parameter.grad).all().item(), 'Missing/nonfinite gradient: '+name)
                    gradients[group].append(float(parameter.grad.detach().abs().max().item()))
            require(all(gradients.values()) and all(max(values) > 0 for values in gradients.values()), 'Inactive LoRA/head gradients')
            write_once(task/'first-step-gradient-verification.json', {'status': 'passed', 'finite': True,
                'lora_A_nonzero': True, 'lora_B_nonzero': True, 'head_nonzero': True, 'base_gradients_absent': True,
                'gradient_parameter_counts': {key: len(values) for key, values in gradients.items()},
                'gradient_max_abs': {key: max(values) for key, values in gradients.items()},
                'checked_after_clipping_before_first_optimizer_update': True})
            first_step = True
            observed.clear()
        return original_step(optimizer, *step_args, **step_kwargs)

    train.initialize_model, torch.optim.AdamW.step = initialize, step
    started = time.time()
    sys.argv = ['jev.train', *preflight['resolved_training_argv']]
    try:
        train.main()
    finally:
        train.initialize_model, torch.optim.AdamW.step, sys.argv = original_initialize, original_step, original_argv
    require(first_step, 'No verified optimizer update')
    observed.clear()
    gc.collect()
    torch.cuda.empty_cache()
    run = Path(request['training_run'])
    validate_completed_run(run)
    checkpoint = run/'checkpoint'
    write_once(request['completion_receipt'], {'status': 'complete', 'source_commit': SOURCE_COMMIT,
        'training_runtime': training_runtime,
        'artifacts_sha256': {name: sha(run/name) for name in ('run.json', 'summary.json', 'training.jsonl', 'calibration.jsonl')},
        'checkpoint': {'files_sha256': {p.relative_to(checkpoint).as_posix(): sha(p) for p in checkpoint.rglob('*') if p.is_file()},
                       'directory_sha256': directory_sha(checkpoint)},
        'driver_sha256': sha(__file__), 'execution_request_sha256': preflight['request_sha256'],
        'execution_request_path': str(Path(args.request).resolve()),
        'cpu_stage_receipt_sha256': preflight['cpu_stage_receipt_sha256'],
        'initial_load_verification_sha256': sha(task/'initial-load-verification.json'),
        'first_step_gradient_verification_sha256': sha(task/'first-step-gradient-verification.json'),
        'elapsed_seconds': time.time()-started, 'gpu_uuid': request['gpu_uuid'],
        'direct_per_row_consumption_observed': False})
    require(sha(args.request) == preflight['request_sha256'], 'Execution request changed during training')
    environment = {**os.environ, 'PYTHONPATH': os.pathsep.join(
        [path for path in (preflight['stage'].get('overlay'), str(ROOT)) if path])}
    command = [sys.executable, '-m', 'scripts.compare_boundary_training_v7',
        '--dataset', request['dataset'], '--released-checkpoint', request['released_checkpoint'],
        '--training-run', request['training_run'], '--completion-receipt', request['completion_receipt'],
        '--output', request['comparison_output'], '--expected-commit', args.expected_commit, '--device', 'cuda']
    with (task/'comparison.log').open('x') as log:
        result = subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
    write_once(task/'experiment-completion.json', {'training_status': 'complete', 'comparison_returncode': result.returncode,
        'training_completion_receipt_sha256': sha(request['completion_receipt']),
        'execution_request_sha256': preflight['request_sha256'], 'automatic_promotion': False})
    return result.returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args()
    if args.preflight_only:
        _, _, receipt = prepare(args)
        print(json.dumps({k: v for k, v in receipt.items() if k != 'stage'}, indent=2))
        return 0
    request = json.loads(Path(args.request).read_text())
    task = Path(request['completion_receipt']).parent
    attempt_already_exists = (task/'attempt.lock.json').exists()
    try:
        return execute(args)
    except BaseException as error:
        if not attempt_already_exists and (task/'attempt.lock.json').exists() and not (task/'attempt-failure.json').exists():
            write_once(task/'attempt-failure.json', {'status': 'single_attempt_failed_no_retry',
                'exception_type': type(error).__name__, 'message': str(error), 'automatic_promotion': False})
        raise


if __name__ == '__main__':
    raise SystemExit(main())
