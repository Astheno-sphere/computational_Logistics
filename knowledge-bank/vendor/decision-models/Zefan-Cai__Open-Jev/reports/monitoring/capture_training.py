"""Read-only observation of the currently owned, pinned N1 four-rank run."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


REMOTE = r'''
import datetime, hashlib, json, math, pathlib, socket, subprocess
root = pathlib.Path('/mnt/localssd/open-jev')
run = pathlib.Path('/data/zefan/open-jev/runs/browser-drone-expansion-v1-27b-ddp-n1-v1')
queue = pathlib.Path('/data/zefan/open-jev/queues/n1-four-gpu-handoff-v1')
assert socket.gethostname() == 'kwade5342000001'
status = json.loads((queue / 'status.json').read_bytes())
assert status['status'] == 'running' and status['phase'] == 'four_gpu_fresh_27b_training'
assert status['supervisor_pid'] == 1239866 and status['child_pid'] == 2872894
run_raw = (run / 'run.json').read_bytes()
metadata = json.loads(run_raw)
assert hashlib.sha256(run_raw).hexdigest() == 'ecc34d76c1bd670cb3e2e8a80c32fa1424df3f4c6acc24d23d547ea832a2ec49'
assert metadata['identity_sha256'] == '24c861e3a7937db09c8ba68b240600cb33c743d200e91375246b724a062b5bdb'
commits = {}
for directory, expected in (
    ('repo', '99e881108c6cacadafd364088505e84975ca43fc'),
    ('eval-repo', '74ee5f8c9fd0b8af43edbc46f0359df3676a2a45'),
    ('four-gpu-repo', '99c5361d83edd5f9dbd11cb3f4bd9f9c54b5973e')):
    commits[directory] = subprocess.check_output(['git', '-C', str(root / directory), 'rev-parse', 'HEAD'], text=True).strip()
    assert commits[directory] == expected
workers = [2873893, 2873894, 2873895, 2873896]
uuids = ['GPU-fc42ba52-5802-1120-aef6-87fb880ddb8e', 'GPU-00cda577-7982-b822-3c12-f6dc8b8db809',
         'GPU-2f1ea441-6f3c-76fa-5184-5049fb2450d2', 'GPU-9ab08bcc-ce17-0461-aaf2-5d57ddcb4775']
processes = []
for pid, ticks in [(pid, 936168439) for pid in workers] + [(2872894, 936168297), (1239866, 935343424)]:
    proc = pathlib.Path('/proc') / str(pid)
    stat = proc.joinpath('stat').read_text().rsplit(')', 1)[1].split()
    assert stat[0] != 'Z' and int(stat[19]) == ticks
    cwd = str(proc.joinpath('cwd').resolve())
    assert cwd == str(root / 'four-gpu-repo')
    environment = dict(item.split('=', 1) for item in proc.joinpath('environ').read_bytes().decode().split('\0') if '=' in item)
    selected = {k: environment[k] for k in ('CUDA_VISIBLE_DEVICES', 'LOCAL_RANK', 'RANK', 'WORLD_SIZE') if k in environment}
    assert selected['CUDA_VISIBLE_DEVICES'] == ('' if pid == 1239866 else ','.join(uuids))
    if pid in workers:
        assert selected['LOCAL_RANK'] == selected['RANK'] == str(workers.index(pid))
        assert selected['WORLD_SIZE'] == '4'
    processes.append({'pid': pid, 'start_ticks': ticks, 'cwd': cwd, 'selected_environment': selected})
raw = (run / 'training.jsonl').read_bytes()
complete = raw[:raw.rfind(b'\n') + 1]
logs = [json.loads(line) for line in complete.splitlines()]
assert [row['step'] for row in logs] == list(range(1, len(logs) + 1))
assert 0 < len(logs) <= 27581
assert all(row['world_size'] == row['global_batch_size'] == 4 for row in logs)
assert all(type(row[k]) in (float, int) and math.isfinite(row[k]) and row[k] >= 0
           for row in logs for k in ('loss', 'gradient_norm', 'elapsed_seconds', 'peak_memory_gib'))
assert all(b['elapsed_seconds'] > a['elapsed_seconds'] for a, b in zip(logs, logs[1:]))
gpu = subprocess.check_output(['nvidia-smi', '-i', '0,1,2,3', '--query-gpu=index,uuid,memory.used,utilization.gpu', '--format=csv,noheader'], text=True)
compute = subprocess.check_output(['nvidia-smi', '-i', '0,1,2,3', '--query-compute-apps=gpu_uuid,pid,used_memory', '--format=csv,noheader'], text=True)
assert [(int(line.split(',')[0]), line.split(',')[1].strip()) for line in gpu.splitlines()] == list(enumerate(uuids))
assert {(line.split(',')[0].strip(), int(line.split(',')[1])) for line in compute.splitlines()} == set(zip(uuids, workers))
print(json.dumps({'hostname': socket.gethostname(), 'status': status,
    'run_sha256': hashlib.sha256(run_raw).hexdigest(), 'run_identity_sha256': metadata['identity_sha256'],
    'processes': processes, 'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'phase': status['phase'], 'checkout_commits': commits, 'completed_steps': len(logs),
    'scheduled_rows_by_cursor': len(logs) * 4, 'total_steps': 27581, 'total_train_rows': 110324,
    'latest_log': logs[-1], 'recent_window': [logs[max(0, len(logs)-101)], logs[-1]],
    'finite_contiguous_log': True, 'ignored_partial_trailing_log_bytes': len(raw) - len(complete),
    'snapshots': sorted(p.name for p in (run / 'training-checkpoints').glob('step-*') if (p / 'resume.json').is_file()),
    'gpu_0_3': gpu, 'gpu_0_3_compute_processes': compute,
    'scope': 'Read-only owned process/run identities, finite contiguous training logs, pinned checkouts and physical GPU0-3 telemetry; no tensors loaded, GPU allocations, other-card/node inspection or process changes.'}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error('Preserve prior evidence; output must be new')
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
                             'sigma@192.0.2.1', '/usr/bin/python3 -B -S -'],
                            input=REMOTE, text=True, capture_output=True, check=True, timeout=60)
    report = json.loads(result.stdout)
    report['capture_script_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'output': str(args.output), 'step': report['completed_steps'],
                      'observed_at': report['observed_at'], 'latest_snapshot': report['snapshots'][-1]}))


if __name__ == '__main__':
    main()
