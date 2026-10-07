"""Read-only capture of one completed N1 release-v2 evaluation; no model calls."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile


REMOTE = "/data/zefan/open-jev/evals/fullpass-2b-9b-four-gpu-data-v1"
FILES = ["plan.json", "summary.json", "merged-test.jsonl", "merged-ood.jsonl"] + [
    f"shard-{rank}.{suffix}" for rank in range(4) for suffix in ("json", "jsonl", "log")]
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o",
       "StrictHostKeyChecking=accept-new", "-o", "LogLevel=ERROR", "sigma@192.0.2.1"]

# Sent through stdin; writes nothing on N1 and imports no project/model modules.
PROBE = r'''
import hashlib, json, socket, subprocess, sys
from pathlib import Path
tag = sys.argv[1]
assert tag in ('2b', '9b') and socket.gethostname() == 'kwade5342000001'
root = Path('/data/zefan/open-jev/evals/fullpass-2b-9b-four-gpu-data-v1')
directory = root/tag
def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()
def read(path):
    return json.loads(path.read_text())
manifest_raw = (root/'manifest.json').read_text()
manifest = json.loads(manifest_raw)
model_state = manifest.get('models', {}).get(tag, {})
if (model_state.get('status') != 'complete' or model_state.get('exit_codes') != [0]*4
        or not (directory/'summary.json').is_file()):
    print(json.dumps({'status': 'not_ready', 'tag': tag, 'model_state': model_state,
                      'controller_status': manifest.get('status')}))
    sys.exit(0)
summary, plan = read(directory/'summary.json'), read(directory/'plan.json')
assert summary['status'] == 'complete' and plan['tag'] == tag
names = ['plan.json', 'summary.json', 'merged-test.jsonl', 'merged-ood.jsonl'] + [
    f'shard-{rank}.{suffix}' for rank in range(4) for suffix in ('json', 'jsonl', 'log')]
assert sorted(p.name for p in directory.iterdir()) == sorted(names)
assert all((directory/name).is_file() and not (directory/name).is_symlink() for name in names)
assert all(read(directory/f'shard-{rank}.json')['status'] == 'complete' for rank in range(4))
checkout = Path(plan['policy_path']).parents[2]
commit = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
assert commit == '99c5361d83edd5f9dbd11cb3f4bd9f9c54b5973e'
implementation = {name: sha(checkout/name) for name in plan['implementation_sha256']}
assert implementation == plan['implementation_sha256'] == manifest['implementation_sha256']
data = Path(plan['data'])
data_files = {name: sha(data/name) for name in ['manifest.json'] + [
    split+'.jsonl' for split in ('train', 'calibration', 'validation', 'test', 'ood')]}
checkpoint = Path(plan['checkpoint_path'])
digest = hashlib.sha256()
for path in sorted(checkpoint.rglob('*')):
    if path.is_file():
        digest.update(str(path.relative_to(checkpoint)).encode()+b'\0')
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1048576), b''):
                digest.update(block)
checkpoint_state = {'checkpoint_sha256': digest.hexdigest(),
    'run_sha256': sha(checkpoint.parent/'run.json'), 'summary_sha256': sha(checkpoint.parent/'summary.json')}
checkpoint_files = {str(path.relative_to(checkpoint)): {'sha256': sha(path), 'bytes': path.stat().st_size}
                    for path in sorted(checkpoint.rglob('*')) if path.is_file()}
print(json.dumps({'status': 'ready', 'tag': tag, 'hostname': socket.gethostname(),
    'source_root': str(root), 'source_commit': commit, 'source_checkout': str(checkout),
    'controller_manifest_raw': manifest_raw,
    'files': {name: {'sha256': sha(directory/name), 'bytes': (directory/name).stat().st_size} for name in names},
    'implementation_sha256': implementation, 'policy_sha256': sha(Path(plan['policy_path'])),
    'data_files_sha256': data_files, 'checkpoint_state': checkpoint_state,
    'checkpoint_files': checkpoint_files}))
'''


def probe(tag):
    result = subprocess.run([*SSH, "python3", "-", tag], input=PROBE, text=True,
                            capture_output=True, check=True, timeout=120)
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("2b", "9b"), required=True)
    parser.add_argument("--output-root", type=Path, default=Path("runs/full-data-eval-n1-v1"))
    args = parser.parse_args()
    destination = args.output_root/args.model
    if destination.exists():
        raise FileExistsError(f"Preserve existing evidence; destination already exists: {destination}")
    before = probe(args.model)
    if before["status"] != "ready":
        print(json.dumps(before, indent=2))
        raise SystemExit(2)
    args.output_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=args.model+".partial-", dir=args.output_root))
    archive = staging/"source.tar"
    with archive.open("wb") as stream:
        subprocess.run([*SSH, "tar", "-C", REMOTE+"/"+args.model, "-cf", "-", *FILES],
                       stdout=stream, check=True, timeout=180)
    with tarfile.open(archive) as bundle:
        members = bundle.getmembers()
        if sorted(m.name for m in members) != sorted(FILES) or not all(m.isfile() for m in members):
            raise ValueError("Unexpected archive members; partial evidence retained")
        bundle.extractall(staging, filter="data")
    archive.unlink()
    after = probe(args.model)
    for key in ("status", "tag", "hostname", "source_root", "source_commit", "source_checkout",
                "files", "implementation_sha256", "policy_sha256", "data_files_sha256", "checkpoint_state", "checkpoint_files"):
        if before[key] != after.get(key):
            raise ValueError(f"Source changed while copying: {key}; partial evidence retained")
    for name, metadata in before["files"].items():
        raw = (staging/name).read_bytes()
        if len(raw) != metadata["bytes"] or hashlib.sha256(raw).hexdigest() != metadata["sha256"]:
            raise ValueError(f"Local copied bytes mismatch: {name}; partial evidence retained")
    controller_manifests = {}
    for label, snapshot in (("before", before), ("after", after)):
        raw = snapshot.pop("controller_manifest_raw").encode()
        (staging/f"controller-manifest-{label}.json").write_bytes(raw)
        controller_manifests[label] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    capture = {"schema_version": 1, "status": "copied_completed_model",
               "captured_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "source_before": before, "source_after": after, "controller_manifests": controller_manifests,
               "read_only_remote": True, "model_inference_performed": False,
               "scope": "This model completed; controller state may still be running its next model."}
    (staging/"capture.json").write_text(json.dumps(capture, indent=2)+"\n")
    staging.rename(destination)
    print(json.dumps({"status": "copied_completed_model", "destination": str(destination),
                      "source_files": len(FILES)}, indent=2))


if __name__ == "__main__":
    main()
