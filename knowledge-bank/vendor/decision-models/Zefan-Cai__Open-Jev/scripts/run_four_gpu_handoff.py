"""Wait for 2B/9B, retire the identified old 27B, evaluate, then train on four GPUs.

This supervisor never modifies the original runs or their checkout. It only
signals the explicitly recorded old 27B process, through a Linux pidfd, after
both smaller runs have completed and their inference artifacts are verified.
"""

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import time

from jev.train import _file_sha256, _json_sha256, read_training_checkpoint
from scripts.run_service_suite import checkpoint_identity, gpu_snapshot, require_free_gpu

ROOT = Path(__file__).resolve().parents[1]
GPUS = [0, 1, 2, 3]
PYTHON = '/mnt/localssd/open-jev/runtime/venv/bin/python'
BASE = '/data/zefan/open-jev'
REVISIONS = {'2b': ('Qwen/Qwen3.5-2B', '15852e8c16360a2fea060d615a32b45270f8a8fc'),
             '9b': ('Qwen/Qwen3.5-9B', 'c202236235762e1c871ad0ccb60c8ee5ba337b9a'),
             '27b': ('Qwen/Qwen3.8-27B', '1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0')}


def now():
    return datetime.now(timezone.utc).isoformat()


def interrupt(signum, frame):
    raise KeyboardInterrupt(f'Supervisor received signal {signum}')


def process_identity(pid):
    proc = Path('/proc') / str(pid)
    try:
        fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
        if fields[0] == 'Z':
            return None
        env = dict(part.split(b'=', 1) for part in (proc / 'environ').read_bytes().split(b'\0') if b'=' in part)
        return {'pid': pid, 'start_ticks': int(fields[19]), 'uid': proc.stat().st_uid,
                'cwd': os.readlink(proc / 'cwd'),
                'command': (proc / 'cmdline').read_bytes().decode().rstrip('\0').split('\0'),
                'cuda_visible_devices': env.get(b'CUDA_VISIBLE_DEVICES', b'').decode()}
    except FileNotFoundError:
        return None


def validate_process(actual, expected):
    keys = ('pid', 'start_ticks', 'uid', 'cwd', 'command', 'cuda_visible_devices')
    if actual is None or any(actual.get(k) != expected.get(k) for k in keys):
        raise RuntimeError('Original process identity changed; no signal permitted')


def completed_model(job, commit):
    """Reaching the last optimizer step alone is not completion."""
    output = Path(job['output'])
    actual = process_identity(job['pid'])
    if actual is not None:
        validate_process(actual, job)
        return None
    summary_path = output / 'summary.json'
    if not summary_path.is_file():
        raise RuntimeError(f"{job['model']} exited without a complete summary")
    summary = json.loads(summary_path.read_text())
    reload_error = summary.get('checkpoint_reload_max_error')
    if (summary.get('status') != 'complete' or summary.get('model') != job['model']
            or summary.get('steps') != job['steps'] or type(reload_error) not in (int, float)
            or not math.isfinite(reload_error) or not 0 <= reload_error <= 0.05):
        raise ValueError('Completed run summary failed identity/reload checks')
    run = json.loads((output / 'run.json').read_text())
    if run.get('run_identity_sha256') != job['run_identity_sha256']:
        raise ValueError('Original run identity changed')
    temperature = json.loads((output / 'checkpoint/temperature.json').read_text())
    ids = run['calibration_ids']
    if (temperature.get('split') != 'calibration' or temperature.get('n') != len(ids)
            or temperature.get('ids_sha256') != hashlib.sha256(json.dumps(ids).encode()).hexdigest()):
        raise ValueError('Temperature calibration provenance differs')
    identity = checkpoint_identity(output / 'checkpoint', job['tag'], commit)
    if identity['base_revision'] != job['revision']:
        raise ValueError('Final checkpoint has the wrong upstream revision')
    return {'summary_sha256': _file_sha256(summary_path), 'identity': identity,
            'checkpoint_reload_max_error': reload_error}


def acquire_locks(stack, names):
    for name in names:
        handle = stack.enter_context(open(name, 'a+'))
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


def validate_commands(plan):
    original = '/mnt/localssd/open-jev/repo'
    if (plan['original_checkout'] != original
            or plan['original_commit'] != '99e881108c6cacadafd364088505e84975ca43fc'):
        raise ValueError('Wrong original training checkout')
    for tag, job in plan['jobs'].items():
        expected = [PYTHON, '-u', '-m', 'jev.train', '--model', REVISIONS[tag][0],
                    '--revision', REVISIONS[tag][1], '--data', original + '/data/release-v2',
                    '--output', BASE + '/runs/release-v2-fullpass-n1-v1/' + tag,
                    '--steps', '20204', '--train-rows', '0', '--max-length', '4096',
                    '--eval-rows', '512', '--calibration-rows', '512', '--seed', '20260919',
                    '--checkpoint-every', '500', '--training-sampling', 'shuffled']
        if (job['command'] != expected or job['cwd'] != original
                or (job['model'], job['revision']) != REVISIONS[tag] or job['steps'] != 20204
                or job['output'] != BASE + '/runs/release-v2-fullpass-n1-v1/' + tag
                or job['data'] != original + '/data/release-v2'):
            raise ValueError('Recorded job does not match the original Open-Jev command')
    expected_eval = [PYTHON, '-m', 'scripts.evaluate_checkpoints_parallel', '--data', original + '/data/release-v2',
                     '--checkpoint-root', BASE + '/runs/release-v2-fullpass-n1-v1', '--output-root', plan['evaluation_output']]
    expected_train = [PYTHON, '-m', 'torch.distributed.run', '--standalone', '--nnodes=1', '--nproc-per-node=4',
                      '--max-restarts=0', '-m', 'jev.train_distributed', '--model', REVISIONS['27b'][0],
                      '--revision', REVISIONS['27b'][1], '--data', BASE + '/data/browser-drone-expansion-v1',
                      '--output', plan['training_output'], '--steps', '27581', '--train-rows', '0',
                      '--training-sampling', 'shuffled', '--accumulation', '4', '--max-length', '4096',
                      '--eval-rows', '512', '--calibration-rows', '512', '--checkpoint-every', '500',
                      '--seed', '20260920', '--lora-rank', '8', '--lr', '5e-5', '--head-lr', '1e-4', '--brier-weight', '0.1']
    if plan['evaluation_command'] != expected_eval or plan['training_command'] != expected_train:
        raise ValueError('Phase command differs from the verified data-eval/fresh-training protocol')
    expected_inputs = {f'{directory}/{split}.jsonl' for directory in
                       (original + '/data/release-v2', BASE + '/data/browser-drone-expansion-v1')
                       for split in ('train', 'calibration', 'validation', 'test', 'ood')}
    if set(plan['input_sha256']) != expected_inputs:
        raise ValueError('Both frozen datasets must bind all five split files')
    if (not Path(plan['evaluation_output']).is_relative_to(BASE + '/evals')
            or not Path(plan['training_output']).is_relative_to(BASE + '/runs')
            or plan['training_output'] in [job['output'] for job in plan['jobs'].values()]):
        raise ValueError('Phase outputs must be separate project paths')


def validate_plan(plan, expected_commit, *, evaluation_started=False):
    if (plan.get('schema_version') != 1 or socket.gethostname() != 'kwade5342000001'
            or plan.get('expected_hostname') != socket.gethostname()):
        raise ValueError('Four-GPU handoff is restricted to N1-1')
    policy = json.loads((ROOT / 'state/auto_research/resource_policy.json').read_text())
    if (policy.get('allowed_gpu_indices') != GPUS
            or policy.get('parallel_data_evaluation_gpu_indices') != GPUS
            or policy.get('distributed_training_gpu_indices') != GPUS):
        raise ValueError('Repository policy does not authorize these four-GPU phases')
    actual_commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    if actual_commit != expected_commit:
        raise ValueError('Handoff checkout commit differs')
    subprocess.run(['git', '-C', str(ROOT), 'diff', '--quiet', 'HEAD', '--'], check=True)
    old_commit = subprocess.check_output(['git', '-C', plan['original_checkout'], 'rev-parse', 'HEAD'], text=True).strip()
    if old_commit != plan['original_commit']:
        raise ValueError('Original training checkout changed')
    if set(plan['jobs']) != {'2b', '9b', '27b'} or len(set(plan['gpu_uuids'])) != 4:
        raise ValueError('Missing jobs or distinct GPU identities')
    validate_commands(plan)
    for tag, job in plan['jobs'].items():
        if job['tag'] != tag or job['uid'] != os.getuid() or job['gpu'] != {'2b': 0, '9b': 1, '27b': 2}[tag]:
            raise ValueError('Invalid original job ownership/allocation')
        if job['cuda_visible_devices'] != plan['gpu_uuids'][job['gpu']]:
            raise ValueError('Original job GPU UUID differs')
    for path, digest in plan['input_sha256'].items():
        if _file_sha256(path) != digest:
            raise ValueError(f'Frozen input changed: {path}')
    if (not evaluation_started and Path(plan['evaluation_output']).exists()) or Path(plan['training_output']).exists():
        raise ValueError('Evaluation/training outputs must be fresh')
    if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        raise RuntimeError('Linux pidfd signaling is required')
    return actual_commit


def verify_evaluation(plan, completed):
    directory = Path(plan['evaluation_output'])
    manifest_path = directory / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get('status') != 'complete' or set(manifest.get('models', {})) != {'2b', '9b'}
            or manifest.get('gpu_uuids') != plan['gpu_uuids'] or not manifest.get('gpus_free_after_cleanup')):
        raise ValueError('Four-card evaluation has no complete matching manifest')
    expected_data = {split: plan['input_sha256'][plan['original_checkout'] + f'/data/release-v2/{split}.jsonl']
                     for split in ('train', 'calibration', 'validation', 'test', 'ood')}
    source = json.loads(Path(plan['original_checkout'] + '/data/release-v2/manifest.json').read_text())
    if manifest.get('data_identity', {}).get('split_sha256') != expected_data:
        raise ValueError('Evaluation manifest dataset differs')
    proofs = {}
    for tag in ('2b', '9b'):
        summary_path = directory / tag / 'summary.json'
        summary = json.loads(summary_path.read_text())
        identity = completed[tag]['identity']
        if (manifest['models'][tag].get('status') != 'complete'
                or manifest['models'][tag].get('exit_codes') != [0, 0, 0, 0]
                or summary.get('status') != 'complete'
                or summary.get('checkpoint', {}).get('checkpoint_sha256') != identity['checkpoint_sha256']
                or summary['checkpoint'].get('model') != REVISIONS[tag][0]
                or summary['checkpoint'].get('revision') != REVISIONS[tag][1]
                or summary['checkpoint'].get('temperature') != identity['temperature']
                or set(summary.get('splits', {})) != {'test', 'ood'}):
            raise ValueError('Evaluation model identity/status differs')
        workers = summary.get('workers', [])
        if len(workers) != 4 or {worker.get('rank') for worker in workers} != set(GPUS):
            raise ValueError('Evaluation is missing a shard')
        for worker in workers:
            rank = worker['rank']
            if (worker.get('status') != 'complete' or worker.get('gpu_uuid') != plan['gpu_uuids'][rank]
                    or worker.get('output_sha256') != _file_sha256(directory / tag / f'shard-{rank}.jsonl')):
                raise ValueError('Evaluation shard bytes or GPU identity changed')
        for split, values in summary['splits'].items():
            count = source['counts'][split]
            if values.get('count') != count or values.get('successful') != count or values.get('failed') != 0:
                raise ValueError('Evaluation has missing/failed rows')
        proofs[tag] = {'summary_sha256': _file_sha256(summary_path), 'checkpoint_sha256': identity['checkpoint_sha256']}
    return {'manifest_sha256': _file_sha256(manifest_path), 'models': proofs}


def latest_verified_snapshot(job):
    snapshots = sorted(Path(job['output']).glob('training-checkpoints/step-[0-9]*'))
    if not snapshots:
        raise ValueError('No retained training snapshot; old process will not be stopped')
    snapshot = snapshots[-1]
    metadata = json.loads((snapshot / 'resume.json').read_text())
    identity = metadata['identity']
    if _json_sha256(identity) != job['run_identity_sha256']:
        raise ValueError('Retained snapshot differs from original run identity')
    verified = read_training_checkpoint(snapshot, identity)
    return {'path': str(snapshot), 'completed_step': verified['completed_step'],
            'resume_sha256': _file_sha256(snapshot / 'resume.json'),
            'files_sha256': verified['files_sha256'], 'inference_ready': False}


def retire_old_27b(job, before_signal):
    actual = process_identity(job['pid'])
    if actual is None:
        return {'already_exited': True, 'output_retained': job['output']}
    validate_process(actual, job)
    retained = latest_verified_snapshot(job)
    fd = os.pidfd_open(job['pid'])
    try:
        validate_process(process_identity(job['pid']), job)
        before_signal({'pid': job['pid'], 'start_ticks': job['start_ticks'], 'retained_snapshot': retained})
        signal.pidfd_send_signal(fd, signal.SIGTERM)
        if not select.select([fd], [], [], 30)[0]:
            raise TimeoutError('Identified old 27B did not exit; no SIGKILL escalation or next phase')
    finally:
        os.close(fd)
    log = Path(job['output']) / 'training.jsonl'
    return {'pid': job['pid'], 'start_ticks': job['start_ticks'], 'signal': 'SIGTERM',
            'retained_snapshot': retained, 'training_log_sha256': _file_sha256(log),
            'output_retained': job['output'], 'retired_at': now(),
            'scope': 'Fresh replacement authorized. Original files retained; unsaved in-memory updates are not resumed.'}


def only_original_27b_on_cards(plan):
    snapshots = [gpu_snapshot(gpu) for gpu in GPUS]
    for gpu, snapshot in enumerate(snapshots):
        if snapshot['uuid'] != plan['gpu_uuids'][gpu]:
            raise RuntimeError('Physical GPU UUID mapping changed')
        permitted = {plan['jobs']['27b']['pid']} if gpu == 2 else set()
        if any(p['pid'] not in permitted for p in snapshot['compute_processes']):
            return False
        if not snapshot['compute_processes'] and (snapshot['memory_used_mib'] > 512 or snapshot['utilization_percent'] > 5):
            return False
    return True


def run_child(command, log_path, env, update, phase):
    with open(log_path, 'x') as log:
        child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            update(phase, child_pid=child.pid, command=command, child_log=str(log_path))
            code = child.wait()
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=30)
        if code:
            raise RuntimeError(f'{phase} exited {code}; original logs retained at {log_path}')


def run(args):
    plan = json.loads(Path(args.plan).read_text())
    commit = validate_plan(plan, args.expected_commit)
    if args.prepare_only:
        print(json.dumps({'status': 'prepared', 'commit': commit, 'actions_started': False}))
        return
    output = Path(args.output_root)
    output.mkdir(parents=True, exist_ok=False)
    state = {'created_at': now(), 'supervisor_pid': os.getpid(), 'code_commit': commit,
             'plan_sha256': _file_sha256(args.plan), 'status': 'running'}
    (output / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')

    def update(phase, **fields):
        state.update(phase=phase, updated_at=now(), **fields)
        temporary = output / '.status.json.tmp'
        temporary.write_text(json.dumps(state, indent=2) + '\n')
        os.replace(temporary, output / 'status.json')
        with (output / 'events.jsonl').open('a') as handle:
            handle.write(json.dumps({'ts': now(), 'phase': phase, **fields}) + '\n')

    deadline = time.monotonic() + args.wait_timeout
    try:
        with ExitStack() as supervisor_stack:
            acquire_locks(supervisor_stack, ['/tmp/open-jev-n1-four-gpu-schedule.lock'])
            update('waiting_for_2b_9b_completion')
            while True:
                ready = {tag: completed_model(plan['jobs'][tag], commit) for tag in ('2b', '9b')}
                if all(ready.values()) and only_original_27b_on_cards(plan):
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError('Smaller models or four cards did not become ready')
                time.sleep(args.poll_seconds)
            update('smaller_models_verified', completed_models=ready)
            lock_names = ['/tmp/open-jev-n1-gpu-0-3.lock', *[f'/tmp/open-jev-eval-gpu-{gpu}.lock' for gpu in GPUS]]
            with ExitStack() as transition_stack:
                acquire_locks(transition_stack, lock_names)
                validate_plan(plan, args.expected_commit)
                if not only_original_27b_on_cards(plan):
                    raise RuntimeError('GPU ownership changed before retirement; no process stopped')
                retirement = retire_old_27b(plan['jobs']['27b'], lambda evidence: update('retiring_old_27b', retirement_intent=evidence))
                update('old_27b_retired', retirement=retirement)
                for gpu in GPUS:
                    require_free_gpu(gpu, release_wait=30)
            # The evaluation controller obtains these same locks itself.
            env = {**os.environ, **plan['environment'], 'CUDA_VISIBLE_DEVICES': ''}
            run_child(plan['evaluation_command'], output / 'evaluation.log', env, update, 'parallel_data_evaluation')
            evaluation_proof = verify_evaluation(plan, ready)
            update('parallel_data_evaluation_complete', evaluation_proof=evaluation_proof)
            with ExitStack() as training_stack:
                acquire_locks(training_stack, lock_names)
                validate_plan(plan, args.expected_commit, evaluation_started=True)
                free = [require_free_gpu(gpu, release_wait=30) for gpu in GPUS]
                if [card['uuid'] for card in free] != plan['gpu_uuids']:
                    raise RuntimeError('GPU UUID mapping changed after evaluation')
                env['CUDA_VISIBLE_DEVICES'] = ','.join(plan['gpu_uuids'])
                run_child(plan['training_command'], output / 'training.log', env, update, 'four_gpu_fresh_27b_training')
                for gpu in GPUS:
                    require_free_gpu(gpu, release_wait=30)
            update('finished', status='complete')
    except BaseException as error:
        update('failed', status='failed', error=f'{type(error).__name__}: {error}')
        raise


def main():
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--poll-seconds', type=float, default=30)
    parser.add_argument('--wait-timeout', type=float, default=86400)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if args.poll_seconds <= 0 or args.wait_timeout <= 0:
        parser.error('Polling interval and wait timeout must be positive')
    run(args)


if __name__ == '__main__':
    main()
