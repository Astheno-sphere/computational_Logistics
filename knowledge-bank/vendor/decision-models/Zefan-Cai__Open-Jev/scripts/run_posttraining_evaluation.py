"""One-shot N1 continuation: final training -> expansion -> audit gate -> services.

This CPU supervisor never starts/stops training, clones repositories, retries a
measurement, or bypasses an existing GPU lease. Contact/amount remain pending.
"""
import argparse
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
HOST = 'kwade5342000001'
BASE = Path('/data/zefan/open-jev')
PYTHON = '/mnt/localssd/open-jev/runtime/venv/bin/python'
TRAIN = BASE / 'runs/browser-drone-expansion-v1-27b-ddp-n1-v1'
TRAIN_CHECKOUT = Path('/mnt/localssd/open-jev/four-gpu-repo')
TRAIN_COMMIT = '99c5361d83edd5f9dbd11cb3f4bd9f9c54b5973e'
RUN_IDENTITY = '24c861e3a7937db09c8ba68b240600cb33c743d200e91375246b724a062b5bdb'
STATUS = BASE / 'latency/interlude-v2-20260920/status.json'
EXPANSION = Path('/mnt/localssd/open-jev/expansion-eval-0b6e4fcc')
EXPANSION_COMMIT = '0b6e4fcca3306b9fe98b96a08074e78b4674fd16'
EXPANSION_OUTPUT = BASE / 'evals/expansion-27b-four-gpu-data-v1'
SERVICE = Path('/mnt/localssd/open-jev/final-eval-ceb1ea85')
SERVICE_COMMIT = 'ceb1ea85d7905d18972afb39da0f5f0baef2097a'
SERVICE_OUTPUT = BASE / 'evals/final-checkpoints-task-suite-v1'
PROFILE = 'browser-drone-expansion-v1'
MEASUREMENTS = ['workflows', 'frontier_100', 'games', 'browser', 'drone']
GPUS = ['GPU-fc42ba52-5802-1120-aef6-87fb880ddb8e', 'GPU-00cda577-7982-b822-3c12-f6dc8b8db809',
        'GPU-2f1ea441-6f3c-76fa-5184-5049fb2450d2', 'GPU-9ab08bcc-ce17-0461-aaf2-5d57ddcb4775']
PROCESS_STARTS = {1437936: 941487074, 1444386: 941507371,
                  **{pid: 941507490 for pid in range(1444414, 1444418)}}
GPU_LOCKS = ['open-jev-n1-gpu-0-3.lock', *[f'open-jev-eval-gpu-{i}.lock' for i in range(4)]]
PENDING = {'contact': 'No reviewed pinned service-lifecycle command is prepared.',
           'amount': 'No reviewed pinned service-lifecycle command is prepared.'}


def read(path):
    return json.loads(Path(path).read_bytes())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def file_info(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Missing or symlinked evidence: ' + str(path))
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            sha.update(block)
    return {'bytes': path.stat().st_size, 'sha256': sha.hexdigest()}


def stages():
    common = [PYTHON, '-m', 'scripts.run_service_suite', '--expected-hostname', HOST, '--gpu', '3',
              '--frontier-source', '/mnt/localssd/open-jev/evals/jev-frontier-100',
              '--workflow-cases', '/mnt/localssd/open-jev/repo/data/workflows-v1/workflow_cases.jsonl',
              '--browser-cases', str(BASE / 'data/browser-v1/cases.jsonl'),
              '--drone-cases', str(BASE / 'data/drone-control-v1/cases.jsonl'),
              '--measurements', *MEASUREMENTS, '--include-doom', '--doom-decision-mode', 'typed-v1',
              '--max-length', '16384', '--batch-size', '1']
    return [
        {'name': 'expansion', 'checkout': str(EXPANSION), 'commit': EXPANSION_COMMIT,
         'output': str(EXPANSION_OUTPUT), 'command': [PYTHON, '-m', 'scripts.evaluate_checkpoints_parallel',
          '--dataset-profile', PROFILE, '--models', '27b', '--data', str(BASE / 'data' / PROFILE),
          '--checkpoint-27b', str(TRAIN / 'checkpoint'), '--output-root', str(EXPANSION_OUTPUT)]},
        {'name': 'service_2b_9b', 'checkout': str(SERVICE), 'commit': SERVICE_COMMIT,
         'output': str(SERVICE_OUTPUT / 'release-v2-2b-9b'), 'command': common + ['--models', '2b', '9b',
          '--checkpoint-root', str(BASE / 'runs/release-v2-fullpass-n1-v1'), '--checkpoint-template',
          '{tag}/checkpoint', '--output-root', str(SERVICE_OUTPUT / 'release-v2-2b-9b')]},
        {'name': 'service_27b', 'checkout': str(SERVICE), 'commit': SERVICE_COMMIT,
         'output': str(SERVICE_OUTPUT / 'expansion-27b'), 'command': common + ['--models', '27b',
          '--checkpoint-root', str(BASE / 'runs'), '--checkpoint-template',
          'browser-drone-expansion-v1-{tag}-ddp-n1-v1/checkpoint', '--output-root', str(SERVICE_OUTPUT / 'expansion-27b')]},
    ]


def validate_plan(plan):
    if (plan.get('schema_version') != 1 or plan.get('hostname') != HOST or plan.get('gpu_uuids') != GPUS
            or plan.get('stages') != stages() or plan.get('pending') != PENDING):
        raise ValueError('Plan differs from the prepared N1 continuation')
    processes = plan.get('predecessors', [])
    if {p['pid']: p['start_ticks'] for p in processes} != PROCESS_STARTS or len(processes) != 6:
        raise ValueError('Expected the actual six predecessor processes; never the retired supervisor')
    for p in processes:
        parent = 1 if p['pid'] == 1437936 else 1437936 if p['pid'] == 1444386 else 1444386
        if (p['uid'] != 1000 or p['ppid'] != parent or len(p['command_sha256']) != 64
                or set(p) != {'pid', 'ppid', 'start_ticks', 'uid', 'cwd', 'command_sha256', 'cuda_visible_devices'}):
            raise ValueError('Incomplete predecessor identity')
        if p['pid'] != 1437936 and (p['cwd'] != str(TRAIN_CHECKOUT) or p['cuda_visible_devices'] != ','.join(GPUS)):
            raise ValueError('Predecessor checkout/allocation differs')
    output = Path(plan['output'])
    if not output.is_absolute() or output.parent != BASE / 'queues' or output.name == 'n1-four-gpu-handoff-v1':
        raise ValueError('Use a separate queue output directory')


def process_identity(pid):
    proc = Path('/proc') / str(pid)
    try:
        fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
        if fields[0] == 'Z':
            return None
        command = (proc / 'cmdline').read_bytes().decode().rstrip('\0').split('\0')
        env = dict(x.split(b'=', 1) for x in (proc / 'environ').read_bytes().split(b'\0') if b'=' in x)
        return {'pid': pid, 'ppid': int(fields[1]), 'start_ticks': int(fields[19]), 'uid': proc.stat().st_uid,
                'cwd': os.readlink(proc / 'cwd'), 'command_sha256': digest(command),
                'cuda_visible_devices': env.get(b'CUDA_VISIBLE_DEVICES', b'').decode()}
    except (FileNotFoundError, ProcessLookupError):
        return None


def predecessors_finished(plan):
    status = read(STATUS)
    if status.get('status') == 'failed':
        raise RuntimeError('Actual training supervisor reported failure; no evaluation may start')
    alive = []
    for expected in plan['predecessors']:
        actual = process_identity(expected['pid'])
        if actual is not None:
            if actual != expected:
                raise RuntimeError('Predecessor PID identity changed; no process will be signalled')
            alive.append(actual['pid'])
    if alive:
        return False
    if (status.get('status') != 'complete' or status.get('phase') != 'resumed_training_finished'
            or status.get('training_exit_code') != 0 or status.get('child_pid') != 1444386):
        raise RuntimeError('Predecessors ended without successful final training completion')
    return True


def check_checkout(path, commit):
    if Path(path).resolve() == TRAIN_CHECKOUT.resolve() and Path(path) != TRAIN_CHECKOUT:
        raise ValueError('An evaluation checkout resolves to the active training checkout')
    actual = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != commit:
        raise ValueError('Unexpected pinned checkout commit: ' + str(path))
    subprocess.run(['git', '-C', str(path), 'diff', '--quiet', 'HEAD', '--'], check=True)


@contextmanager
def leases(names, lock_root=Path('/tmp')):
    with ExitStack() as stack:
        for name in names:
            handle = stack.enter_context((lock_root / name).open('a+'))
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def cards_free():
    raw = subprocess.check_output(['nvidia-smi', '-i', '0,1,2,3',
                                  '--query-gpu=index,uuid,memory.used,utilization.gpu', '--format=csv,noheader,nounits'], text=True)
    cards = [[x.strip() for x in line.split(',')] for line in raw.splitlines()]
    if [int(c[0]) for c in cards] != list(range(4)) or [c[1] for c in cards] != GPUS:
        raise RuntimeError('Physical GPU0-3 UUID mapping changed')
    raw = subprocess.check_output(['nvidia-smi', '-i', '0,1,2,3',
                                  '--query-compute-apps=gpu_uuid,pid', '--format=csv,noheader,nounits'], text=True)
    busy = any(line.split(',')[0].strip() in GPUS for line in raw.splitlines())
    return not busy and all(float(c[2]) <= 512 and float(c[3]) <= 5 for c in cards)


def allocation_available():
    try:
        with leases(GPU_LOCKS):
            return cards_free()
    except BlockingIOError:
        return False


def environment(checkout):
    env = {**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'PYTHONPATH': str(checkout),
           'HF_HUB_CACHE': '/mnt/localssd/open-jev/hf-cache', 'HF_HUB_OFFLINE': '1',
           'TRANSFORMERS_OFFLINE': '1', 'TOKENIZERS_PARALLELISM': 'false', 'PYTHONUNBUFFERED': '1'}
    for key in ('OPENAI_API_KEY', 'JEV_API_KEY'):
        env.pop(key, None)
    return env


def final_checkpoint_readiness():
    # This pinned CPU implementation checks all frozen data bytes, final steps,
    # calibration IDs/logits, finite training history, saved reload and weights.
    code = '''import json
from pathlib import Path
from scripts.evaluate_checkpoints_parallel import load_data,checkpoint_identity,implementation_identity
base=Path('/data/zefan/open-jev'); result={'models':{}}
for profile,tags,data in [('release-v2',['2b','9b'],Path('/mnt/localssd/open-jev/repo/data/release-v2')),
                         ('browser-drone-expansion-v1',['27b'],base/'data/browser-drone-expansion-v1')]:
 _,identity,calibration=load_data(data,profile_name=profile)
 for tag in tags:
  run=base/('runs/browser-drone-expansion-v1-27b-ddp-n1-v1' if tag=='27b' else 'runs/release-v2-fullpass-n1-v1/'+tag)
  result['models'][tag]=checkpoint_identity(run/'checkpoint',tag,identity,calibration,profile_name=profile)
  if tag=='27b':
   metadata=json.loads((run/'run.json').read_bytes())
   assert metadata['identity_sha256']=='24c861e3a7937db09c8ba68b240600cb33c743d200e91375246b724a062b5bdb'
   assert metadata['commit']=='99c5361d83edd5f9dbd11cb3f4bd9f9c54b5973e'
   result['data_identity']=identity
result['implementation_sha256']=implementation_identity()
print(json.dumps(result))
'''
    result = subprocess.run([PYTHON, '-c', code], cwd=EXPANSION, env=environment(EXPANSION),
                            capture_output=True, text=True, timeout=600, check=True)
    return json.loads(result.stdout)


def verify_expansion(ready):
    manifest = read(EXPANSION_OUTPUT / 'manifest.json')
    summary = read(EXPANSION_OUTPUT / '27b/summary.json')
    if (manifest.get('status') != 'complete' or manifest.get('gpus_free_after_cleanup') is not True
            or manifest.get('model_order') != ['27b'] or set(manifest.get('models', {})) != {'27b'}
            or manifest['models']['27b'].get('exit_codes') != [0] * 4
            or manifest.get('gpu_uuids') != GPUS or manifest.get('dataset_profile') != PROFILE
            or manifest.get('implementation_sha256') != ready['implementation_sha256']
            or summary.get('status') != 'complete' or summary.get('total_rows') != 40281
            or summary.get('checkpoint') != ready['models']['27b']
            or summary.get('data_identity') != ready['data_identity']):
        raise ValueError('Expansion did not produce the complete matching 40,281-row evidence')
    return {'manifest': file_info(EXPANSION_OUTPUT / 'manifest.json'),
            'summary': file_info(EXPANSION_OUTPUT / '27b/summary.json')}


def independent_audit_ready(gate, ready):
    report_path, capture_path = gate / '27b-audit.json', gate / 'capture.json'
    if not report_path.exists() or not capture_path.exists():
        return False
    report, capture = read(report_path), read(capture_path)
    expected = {'expected_rows': 40281, 'unique_ids': 40281, 'shard_rows': [10071, 10070, 10070, 10070],
                'missing': 0, 'duplicate': 0, 'failed': 0}
    if (report.get('status') != 'passed' or report.get('evaluation_source_commit') != EXPANSION_COMMIT
            or report.get('model_evaluation_complete') is not True or report.get('coverage') != expected
            or report.get('controller_complete_at_capture') is not True
            or report.get('checkpoint') != ready['models']['27b']
            or report.get('data_identity') != ready['data_identity']
            or report.get('verification', {}).get('capture_sha256') != file_info(capture_path)['sha256']):
        raise ValueError('Independent expansion audit failed or belongs to other evidence')
    source = capture.get('source_before', {})
    if (source != capture.get('source_after') or source.get('status') != 'ready'
            or source.get('source_commit') != EXPANSION_COMMIT or source.get('source_root') != str(EXPANSION_OUTPUT)
            or capture.get('status') != 'copied_completed_expansion' or capture.get('read_only_remote') is not True):
        raise ValueError('Independent capture identity differs')
    required = {'evaluation/' + name for name in ('plan.json', 'summary.json', 'merged-test.jsonl', 'merged-ood.jsonl')}
    required |= {f'evaluation/shard-{rank}.{suffix}' for rank in range(4) for suffix in ('json', 'jsonl', 'log')}
    required |= {'training/' + name for name in ('run.json', 'summary.json', 'training.jsonl', 'calibration.jsonl',
                                                'trained_test.jsonl', 'reload_check.jsonl')}
    required |= {'training/checkpoint/' + name for name in ('head.pt', 'model.json', 'temperature.json',
                                                          'adapter/adapter_config.json', 'adapter/adapter_model.safetensors')}
    if (set(source.get('files', {})) not in (required, required | {'training/checkpoint/adapter/README.md'})
            or set(capture.get('controller_manifests', {})) != {'before', 'after'}):
        raise ValueError('Independent capture lacks the complete evidence file set')
    auditor = ROOT / 'reports/full-data-eval-expansion-n1-v1'
    if report.get('verification', {}).get('audit_code_sha256') != {
            name: file_info(auditor / name)['sha256'] for name in ('verify.py', 'expansion_contract.py')}:
        raise ValueError('Independent audit code differs from the reviewed verifier')
    for name, expected_info in source['files'].items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or relative.parts[0] not in ('evaluation', 'training'):
            raise ValueError('Unsafe audit evidence path')
        base = EXPANSION_OUTPUT / '27b' if relative.parts[0] == 'evaluation' else TRAIN
        if file_info(base.joinpath(*relative.parts[1:])) != expected_info:
            raise ValueError('Audited evidence changed: ' + name)
    for info in capture.get('controller_manifests', {}).values():
        if info != file_info(EXPANSION_OUTPUT / 'manifest.json'):
            raise ValueError('Audited controller manifest changed')
    return {'audit': file_info(report_path), 'capture': file_info(capture_path)}


def benchmark_separation(output):
    source = '/mnt/localssd/open-jev/evals/jev-frontier-100'
    commands = [[PYTHON, '-m', 'jev.eval_frontier', '--source', source, '--audit-only',
                 '--output-dir', str(output / 'jf100-source-audit')]]
    for tag, data in (('release-v2', '/mnt/localssd/open-jev/repo/data/release-v2'),
                      ('expansion', str(BASE / 'data' / PROFILE))):
        commands.append([PYTHON, '-m', 'scripts.check_eval_separation', '--benchmark-root', source,
                         '--dataset', data, '--output', str(output / (tag + '-separation.json'))])
    for index, command in enumerate(commands):
        with (output / f'benchmark-preflight-{index}.log').open('x') as log:
            subprocess.run(command, cwd=SERVICE, env=environment(SERVICE), stdout=log,
                           stderr=subprocess.STDOUT, timeout=600, check=True)


def verify_service(stage, ready):
    manifest = read(Path(stage['output']) / 'manifest.json')
    tags = ['2b', '9b'] if stage['name'] == 'service_2b_9b' else ['27b']
    if (manifest.get('status') != 'complete' or manifest.get('code_commit') != SERVICE_COMMIT
            or manifest.get('physical_gpu') != 3 or set(manifest.get('models', {})) != set(tags)):
        raise ValueError('Service suite incomplete or failed; preserve every measurement')
    configuration = manifest.get('configuration', {})
    if (configuration.get('max_length') != 16384 or configuration.get('batch_size') != 1
            or configuration.get('measurements') != MEASUREMENTS or configuration.get('include_doom') is not True
            or configuration.get('doom_decision_mode') != 'typed-v1'):
        raise ValueError('Service settings differ from the prepared 16K/batch1 typed-Doom condition')
    for tag in tags:
        model = manifest['models'][tag]
        identity = model['expected_identity']
        measurements = model['measurements']
        if (identity.get('checkpoint_sha256') != ready['models'][tag]['checkpoint_sha256']
                or identity.get('max_length') != 16384 or set(measurements) != set(MEASUREMENTS)
                or any(v.get('exit_code') != 0 for v in measurements.values())
                or model.get('gpu_after_shutdown', {}).get('compute_processes') != []):
            raise ValueError('Service checkpoint, cases, measurement result or cleanup differs')
    return file_info(Path(stage['output']) / 'manifest.json')


def run_child(stage, log_path, update):
    with log_path.open('x') as log:
        child = subprocess.Popen(stage['command'], cwd=stage['checkout'], env=environment(stage['checkout']),
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            update('running_' + stage['name'], child_pid=child.pid, command=stage['command'])
            code = child.wait()
            if code:
                raise RuntimeError(f"{stage['name']} exited {code}; no next stage or retry")
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                child.wait()  # Retain scheduling lease until this owned child is reaped.


def wait_for(check, phase, update, deadline, poll_seconds):
    update(phase)
    while True:
        proof = check()
        if proof:
            return proof
        if time.monotonic() >= deadline:
            raise TimeoutError('Wait budget exhausted in ' + phase)
        time.sleep(poll_seconds)


def run(args):
    plan = read(args.plan)
    validate_plan(plan)
    if args.prepare_only:
        return {'status': 'prepared_not_launched', 'stages': plan['stages'], 'pending': PENDING,
                'audit_gate': str(Path(plan['output']) / 'audit-gate')}
    if socket.gethostname() != HOST or os.getuid() != 1000 or os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise ValueError('Run the CPU supervisor on N1-1 as its recorded owner with CUDA_VISIBLE_DEVICES empty')
    check_checkout(ROOT, args.expected_commit)
    check_checkout(TRAIN_CHECKOUT, TRAIN_COMMIT)
    for path, commit in ((EXPANSION, EXPANSION_COMMIT), (SERVICE, SERVICE_COMMIT)):
        check_checkout(path, commit)
    output = Path(plan['output'])
    output.mkdir(parents=True, exist_ok=False)  # One-shot: never replay an earlier queue.
    (output / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    state = {'status': 'running', 'phase': 'starting', 'pid': os.getpid(), 'plan_sha256': digest(plan),
             'code_commit': args.expected_commit, 'completed': [], 'pending': PENDING}
    def update(phase, **fields):
        state.update(phase=phase, updated_at=datetime.now(timezone.utc).isoformat(), **fields)
        temporary = output / '.status.json.tmp'
        temporary.write_text(json.dumps(state, indent=2) + '\n')
        temporary.replace(output / 'status.json')
    deadline = time.monotonic() + args.wait_hours * 3600
    try:
        if any(Path(s['output']).exists() for s in plan['stages']):
            raise ValueError('Existing evaluation output; no automatic retry or overwrite')
        wait_for(lambda: predecessors_finished(plan), 'waiting_for_training', update, deadline, args.poll_seconds)
        update('checking_final_checkpoint')
        ready = final_checkpoint_readiness()
        (output / 'checkpoint-readiness.json').write_text(json.dumps(ready, indent=2) + '\n')
        # The children take their own GPU leases. Holding those leases here
        # would deadlock them; the schedule lease excludes another DDP handoff.
        schedule = ExitStack()
        with schedule:
            def acquire_schedule():
                try:
                    schedule.enter_context(leases(['open-jev-n1-four-gpu-schedule.lock']))
                    return True
                except BlockingIOError:
                    return False
            wait_for(acquire_schedule, 'waiting_for_schedule_lease', update, deadline, args.poll_seconds)
            benchmark_checked = False
            for stage in plan['stages']:
                check_checkout(stage['checkout'], stage['commit'])
                wait_for(allocation_available, 'waiting_for_gpu_leases_' + stage['name'], update, deadline, args.poll_seconds)
                if stage['name'] != 'expansion':
                    wait_for(lambda: independent_audit_ready(output / 'audit-gate', ready),
                             'waiting_for_expansion_audit', update, deadline, args.poll_seconds)
                    if final_checkpoint_readiness() != ready:
                        raise ValueError('Final checkpoint changed after expansion/audit')
                    if not benchmark_checked:
                        update('checking_benchmark_separation')
                        benchmark_separation(output)
                        benchmark_checked = True
                run_child(stage, output / (stage['name'] + '.log'), update)
                wait_for(allocation_available, 'checking_cleanup_' + stage['name'], update, deadline, args.poll_seconds)
                evidence = verify_expansion(ready) if stage['name'] == 'expansion' else verify_service(stage, ready)
                state['completed'].append({'stage': stage['name'], 'evidence': evidence})
                update('finished_' + stage['name'], child_pid=None)
        update('prepared_stages_finished', status='complete_with_pending_stages')
    except BaseException as error:
        update('stopped', status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
               failed_phase=state['phase'], error_type=type(error).__name__, error=str(error))
        raise
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--expected-commit')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--wait-hours', type=float, default=48)
    parser.add_argument('--poll-seconds', type=float, default=30)
    args = parser.parse_args()
    if not 0 < args.wait_hours <= 72 or not 1 <= args.poll_seconds <= 60:
        parser.error('Use a bounded wait (up to72h) and a1–60s poll')
    if not args.prepare_only and (not args.expected_commit or len(args.expected_commit) != 40):
        parser.error('--expected-commit is required before execution')
    def interrupt(signum, frame):
        raise KeyboardInterrupt('CPU supervisor interrupted')
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    print(json.dumps(run(args), indent=2))


if __name__ == '__main__':
    main()
