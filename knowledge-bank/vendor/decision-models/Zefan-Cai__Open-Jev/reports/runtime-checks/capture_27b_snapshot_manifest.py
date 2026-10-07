"""Read-only N1 snapshot hash/log audit; no tensors, model imports or GPU work."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


REMOTE = r'''
import datetime, hashlib, json, math, pathlib, socket

def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()

assert socket.gethostname() == 'kwade5342000001'
run_path = pathlib.Path('/data/zefan/open-jev/runs/browser-drone-expansion-v1-27b-ddp-n1-v1')
snapshot = run_path / 'training-checkpoints' / f'step-{STEP:08d}'
assert not snapshot.is_symlink() and snapshot.is_dir()
assert snapshot.resolve().parent == (run_path / 'training-checkpoints').resolve()
for name in ('resume.json', 'training_state.pt', 'training.jsonl',
             'baseline_test.jsonl', 'baseline_ood.jsonl', 'baseline_calibration.jsonl'):
    path = snapshot / name
    assert not path.is_symlink() and path.is_file() and path.resolve().parent == snapshot.resolve()
resume_raw = (snapshot / 'resume.json').read_bytes()
info = json.loads(resume_raw)
run_raw = (run_path / 'run.json').read_bytes()
run = json.loads(run_raw)
assert (info['schema_version'], info['kind'], info['complete'], info['inference_ready']) == (
    2, 'distributed_training_resume_only', True, False)
assert type(info['completed_step']) is int and info['completed_step'] == STEP
assert 0 < STEP <= 27581
identity = hashlib.sha256(json.dumps({'training': info['identity'], 'distribution': info['distribution']},
    sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
assert identity == run['identity_sha256'] == '24c861e3a7937db09c8ba68b240600cb33c743d200e91375246b724a062b5bdb'
assert run['commit'] == '99c5361d83edd5f9dbd11cb3f4bd9f9c54b5973e'
for key in ('identity_sha256', 'commit', 'distribution', 'original_baseline_sha256'):
    assert info['run_metadata'][key] == run[key]
baselines = {'baseline_test.jsonl', 'baseline_ood.jsonl', 'baseline_calibration.jsonl'}
files = {'training_state.pt', 'training.jsonl'} | baselines
assert set(info['files_sha256']) == files
assert {p.name for p in snapshot.iterdir()} == files | {'resume.json'}
hashes = {name: sha(snapshot / name) for name in sorted(files)}
assert hashes == info['files_sha256']
log_raw = (snapshot / 'training.jsonl').read_bytes()
assert hashlib.sha256(log_raw).hexdigest() == hashes['training.jsonl']
logs = [json.loads(line) for line in log_raw.splitlines()]
assert [row['step'] for row in logs] == list(range(1, STEP + 1))
assert all(row['world_size'] == row['global_batch_size'] == 4 for row in logs)
assert all(type(row[key]) in (int, float) and math.isfinite(row[key]) and row[key] >= 0
    for row in logs for key in ('loss', 'gradient_norm', 'elapsed_seconds', 'peak_memory_gib'))
assert all(b['elapsed_seconds'] > a['elapsed_seconds'] for a, b in zip(logs, logs[1:]))
with (run_path / 'training.jsonl').open('rb') as stream:
    assert stream.read(len(log_raw)) == log_raw
assert all(sha(run_path / name) == hashes[name] == run['original_baseline_sha256'][name] for name in baselines)
assert (snapshot / 'resume.json').read_bytes() == resume_raw
assert (run_path / 'run.json').read_bytes() == run_raw
assert {name: sha(snapshot / name) for name in sorted(files)} == hashes
print(json.dumps({
    'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'snapshot': str(snapshot), 'status': 'passed', 'completed_step': STEP,
    'rows_by_global_cursor': STEP * 4, 'run_identity_sha256': identity,
    'run_sha256': hashlib.sha256(run_raw).hexdigest(),
    'resume_sha256': hashlib.sha256(resume_raw).hexdigest(), 'files_sha256': hashes,
    'log_prefix_matches_parent': True, 'baselines_match_parent': True,
    'all_logged_numeric_fields_finite': True, 'log_elapsed_time_strictly_increasing': True,
    'snapshot_payload_hashes_unchanged_through_audit': True,
    'snapshot_run_metadata_matches_parent_identity': True,
    'snapshot_files_regular_without_symlinks': True,
    'full_tensor_payload_loaded': False, 'gpu_used': False,
    'scope': 'Immutable snapshot metadata, identity, manifest byte hashes and finite log prefix; no tensor semantics or actual resume exercised.'
}, indent=2))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--step', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 0 < args.step <= 27581:
        parser.error('step must be between 1 and 27581')
    if args.output.exists():
        parser.error('output already exists; preserve previous evidence')
    result = subprocess.run([
        'ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
        'sigma@192.0.2.1', '/usr/bin/python3 -B -S -',
    ], input=f'STEP = {args.step}\n' + REMOTE, text=True, capture_output=True, check=True, timeout=120)
    report = json.loads(result.stdout)
    report['capture_script_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'report': str(args.output), 'status': report['status'], 'completed_step': report['completed_step']}))


if __name__ == '__main__':
    main()
