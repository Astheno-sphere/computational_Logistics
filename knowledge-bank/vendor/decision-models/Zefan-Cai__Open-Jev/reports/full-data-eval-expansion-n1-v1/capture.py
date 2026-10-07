"""Explicit read-only SSH capture of completed final 27B expansion evidence."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

import expansion_contract as c

SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o",
       "StrictHostKeyChecking=yes", "-o", "LogLevel=ERROR", "sigma@192.0.2.1"]

# Executed with stdlib only on the source host; never writes or imports project code.
PROBE = r'''
import hashlib, json, math, socket, stat, subprocess
from pathlib import Path

def snapshot(config):
    assert socket.gethostname() == config['hostname'], 'Wrong source host'
    root, run, data = (Path(config[key]) for key in ('root', 'run', 'data'))
    def read(path):
        return json.loads(path.read_bytes())
    def file_info(path):
        assert not path.is_symlink() and stat.S_ISREG(path.stat().st_mode), 'Nonregular source file'
        digest, size = hashlib.sha256(), 0
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1048576), b''):
                digest.update(block)
                size += len(block)
        assert size == path.stat().st_size
        return {'sha256': digest.hexdigest(), 'bytes': size}
    def files(directory):
        assert directory.is_dir() and not directory.is_symlink()
        result = set()
        for path in directory.rglob('*'):
            assert not path.is_symlink(), 'Symlinked source entry'
            if not path.is_dir():
                assert stat.S_ISREG(path.stat().st_mode), 'Nonregular source entry'
                result.add(path.relative_to(directory).as_posix())
        return result
    required = [root/'manifest.json', root/'27b/summary.json', run/'summary.json']
    if not all(path.is_file() for path in required):
        return {'status': 'not_ready', 'reason': 'Final evaluation/training completion artifacts absent'}
    assert root.is_dir() and not root.is_symlink()
    for path in required:
        file_info(path)
    manifest_raw = (root/'manifest.json').read_text()
    manifest, summary, trained = json.loads(manifest_raw), read(root/'27b/summary.json'), read(run/'summary.json')
    state = manifest.get('models', {}).get('27b', {})
    if (manifest.get('status') != 'complete' or manifest.get('gpus_free_after_cleanup') is not True
            or state.get('status') != 'complete' or state.get('exit_codes') != [0]*4
            or summary.get('status') != 'complete' or trained.get('status') != 'complete'):
        return {'status': 'not_ready', 'reason': 'Completed training/evaluation and controller cleanup required',
                'controller_status': manifest.get('status'), 'model_status': state.get('status')}
    directory, checkpoint = root/'27b', run/'checkpoint'
    plan, metadata = read(directory/'plan.json'), read(run/'run.json')
    assert manifest['model_order'] == ['27b'] and manifest['phase'] == 'parallel_data_eval'
    assert all(item['dataset_profile'] == config['profile'] for item in (manifest, plan, summary))
    assert all(item['partition'] == 'concatenated_test_ood' for item in (manifest, plan, summary))
    assert summary['total_rows'] == 40281 and summary['data_identity']['counts'] == {'test':14902, 'ood':25379}
    assert metadata['steps'] == trained['steps'] == 27581 and trained['trained_rows_consumed'] == 110324
    assert metadata['commit'] == config['training_commit'] and metadata['identity_sha256'] == config['run_identity']
    assert metadata['model'] == trained['model'] == config['model'] and metadata['revision'] == config['revision']
    assert metadata['seed'] == 20260920 and metadata['training_rows_consumed'] == 110324
    distribution = metadata['distribution']
    assert distribution == trained['distribution'] and distribution['world_size'] == distribution['global_batch_size'] == 4
    assert distribution['local_rows_per_step'] == 1 and distribution['backend'] == 'nccl' and distribution['device_type'] == 'cuda'
    saved_temperature = read(checkpoint/'temperature.json')
    ids = metadata['calibration_ids']
    assert len(ids) == len(set(ids)) == metadata['calibration_rows'] == saved_temperature['n'] == 512
    assert hashlib.sha256(json.dumps(ids).encode()).hexdigest() == saved_temperature['ids_sha256'] == config['calibration_ids_sha256']
    assert saved_temperature['split'] == 'calibration' and saved_temperature == plan['checkpoint']['calibration']
    value = saved_temperature['temperature']
    assert type(value) in (int,float) and math.isfinite(value) and value > 0 and value == trained['temperature']
    error = trained['checkpoint_reload_max_error']
    assert type(error) in (int,float) and math.isfinite(error) and 0 <= error <= .05
    assert plan['tag'] == '27b' and Path(plan['data']) == data and Path(plan['checkpoint_path']) == checkpoint
    assert plan['checkpoint'] == summary['checkpoint']
    assert files(directory) == set(config['evaluation_files'])
    assert all(read(directory/f'shard-{rank}.json')['status'] == 'complete' for rank in range(4))
    names = files(checkpoint)
    assert set(config['weight_files']) <= names <= set(config['weight_files']) | {'adapter/README.md'}
    assert not run.is_symlink() and not data.is_symlink()
    assert not (run/'resume.json').exists(), 'Resume snapshot is not a final run'
    checkout = Path(plan['policy_path']).parents[2]
    commit = subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'], text=True).strip()
    assert commit == config['commit']
    implementation = {name:file_info(checkout/name)['sha256'] for name in config['source_files']}
    assert implementation == plan['implementation_sha256'] == manifest['implementation_sha256']
    training_names = set(config['run_files']) | {'checkpoint/'+name for name in names}
    captured = {'evaluation/'+name:file_info(directory/name) for name in config['evaluation_files']}
    captured.update({'training/'+name:file_info(run/name) for name in sorted(training_names)})
    digest = hashlib.sha256()
    for name in sorted(names):
        digest.update(name.encode()+b'\0')
        with (checkpoint/name).open('rb') as stream:
            for block in iter(lambda:stream.read(1048576), b''):
                digest.update(block)
    assert digest.hexdigest() == plan['checkpoint']['checkpoint_sha256']
    completion = plan['checkpoint']['training_completion']
    for key, name in (('run_sha256','run.json'), ('summary_sha256','summary.json'),
                      ('training_log_sha256','training.jsonl'), ('calibration_predictions_sha256','calibration.jsonl')):
        assert completion[key] == captured['training/'+name]['sha256']
    data_files = {name:file_info(data/name) for name in ['manifest.json']+[s+'.jsonl' for s in config['hashes']]}
    assert data_files['manifest.json']['sha256'] == config['manifest_sha256']
    assert all(data_files[s+'.jsonl']['sha256'] == value for s,value in config['hashes'].items())
    return {'status':'ready', 'hostname':socket.gethostname(), 'tag':'27b', 'source_root':str(root),
            'source_run':str(run), 'source_data':str(data), 'source_commit':commit, 'source_checkout':str(checkout),
            'implementation_sha256':implementation, 'policy_sha256':file_info(Path(plan['policy_path']))['sha256'],
            'files':captured, 'data_files':data_files, 'checkpoint_sha256':digest.hexdigest(),
            'controller_manifest_raw':manifest_raw}
'''


def config():
    return {"hostname": c.HOSTNAME, "root": c.REMOTE, "run": c.REMOTE_RUN, "data": c.REMOTE_DATA,
            "profile": c.PROFILE, "commit": c.COMMIT, "source_files": c.SOURCE_FILES,
            "training_commit": c.TRAINING_COMMIT, "run_identity": c.RUN_IDENTITY,
            "model": c.MODEL, "revision": c.REVISION, "calibration_ids_sha256": c.CALIBRATION_IDS_SHA,
            "evaluation_files": sorted(c.EVAL_FILES), "weight_files": sorted(c.WEIGHT_FILES),
            "run_files": sorted(c.RUN_FILES), "hashes": c.HASHES, "manifest_sha256": c.MANIFEST_SHA}


def probe():
    code = PROBE + "\nprint(json.dumps(snapshot(" + repr(config()) + ")))\n"
    result = subprocess.run([*SSH, "python3", "-"], input=code, text=True,
                            capture_output=True, check=True, timeout=180)
    return c.decode(result.stdout)


def unpack(archive, destination, names):
    with tarfile.open(archive) as bundle:
        members = bundle.getmembers()
        c.require(sorted(m.name for m in members) == sorted(names) and all(m.isfile() for m in members),
                  "Unexpected archive members; partial evidence retained")
        # Names are a prevalidated fixed set; reject links, duplicate entries and traversal.
        for member in members:
            c.require(member.name in names and not Path(member.name).is_absolute()
                      and ".." not in Path(member.name).parts, "Unsafe archive member")
        bundle.extractall(destination, filter="data")


def capture(destination):
    destination = Path(destination)
    c.require(not destination.exists() and not destination.is_symlink(), "Preserve existing evidence destination")
    before = probe()
    if before["status"] != "ready":
        return before
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=destination.name+".partial-", dir=destination.parent))
    for label, source in (("evaluation", c.REMOTE+"/27b"), ("training", c.REMOTE_RUN)):
        names = sorted(name.removeprefix(label+"/") for name in before["files"] if name.startswith(label+"/"))
        expected = c.EVAL_FILES if label == "evaluation" else c.RUN_FILES | {"checkpoint/"+name for name in c.WEIGHT_FILES}
        c.require(set(names) == expected or (label == "training" and set(names) == expected | {"checkpoint/adapter/README.md"}),
                  "Unexpected capture file set")
        archive = staging/(label+".tar")
        with archive.open("xb") as stream:
            subprocess.run([*SSH, "tar", "-C", source, "-cf", "-", *names], stdout=stream, check=True, timeout=300)
        (staging/label).mkdir()
        unpack(archive, staging/label, names)
        archive.unlink()
    after = probe()
    c.require(before == after, "Source changed while copying; partial evidence retained")
    for name, expected in before["files"].items():
        c.require(c.info(c.safe_file(staging, name)) == expected, "Copied bytes differ: "+name)
    raw = before.pop("controller_manifest_raw")
    after.pop("controller_manifest_raw")
    for label in ("before", "after"):
        (staging/f"controller-manifest-{label}.json").write_text(raw)
    result = {"schema_version": 1, "status": "copied_completed_expansion",
              "captured_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "source_before": before, "source_after": after,
              "controller_manifests": {label:c.info(staging/f"controller-manifest-{label}.json") for label in ("before", "after")},
              "read_only_remote": True, "model_inference_performed": False}
    (staging/"capture.json").write_text(json.dumps(result, indent=2)+"\n")
    c.require(not destination.exists() and not destination.is_symlink(), "Destination appeared during capture")
    staging.rename(destination)
    return {"status": result["status"], "destination": str(destination), "source_files": len(before["files"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("runs/full-data-eval-expansion-n1-v1/27b"))
    args = parser.parse_args()
    result = capture(args.output)
    print(json.dumps(result, indent=2))
    if result["status"] == "not_ready":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
