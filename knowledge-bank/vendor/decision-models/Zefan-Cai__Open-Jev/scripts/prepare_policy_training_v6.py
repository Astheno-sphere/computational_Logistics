"""Freeze only original Train rows for one released-2B adaptation; no model calls."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from jev.data import SPLITS, _write_dataset, validate_records
from jev.train import _file_sha256, _json_sha256, source_checkout_commit

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = {'v4':'frontier-controls-v4', 'v5':'temporal-windows-v5',
            'v6':'original-policy-controls-v6-candidate'}
COUNTS = {'v4':(2400,240,240,240,240), 'v5':(128,32,32,32,32), 'v6':(240,36,36,36,36)}
LOCKS = {'v4':(ROOT/'reports/frontier-controls-v4/continued-2b-20261002/run.lock.json','selection'),
         'v5':(ROOT/'reports/temporal-windows-v5-20261002/ms-2b-fixed-pilot/pilot/pilot.lock.json','v5_selection')}
RELEASE = ROOT/'reports/efficiency-20261002/h200-2b-package-provenance.json'
V6_LOCK = ROOT/'reports/openjev-hf-data-20261002/original-candidate/candidate-manifest.json'
V6_LOCK_SHA256 = '35bb2d6b408e7832d36cf8bbdb77839fda39b9cd99a90e7c9d388776705dcc9f'


def committed_source():
    commit = source_checkout_commit(__file__)
    files = ('scripts/prepare_policy_training_v6.py','jev/train.py','jev/data.py',
             'jev/frontier_controls_v4.py','jev/temporal_windows_v5.py','jev/policy_controls_v6.py',
             V6_LOCK.relative_to(ROOT).as_posix())
    for name in files:
        try:
            frozen = subprocess.check_output(['git','-C',str(ROOT),'show',commit+':'+name],stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as error:
            raise ValueError('Commit preparation/training/generators before freezing the candidate') from error
        if frozen != (ROOT/name).read_bytes():
            raise ValueError('Uncommitted preparation/training/generator bytes: '+name)
    return commit


def read_source(name, directory):
    directory = Path(directory)
    manifest = json.loads((directory/'manifest.json').read_text())
    if name == 'v6':
        lock = json.loads(V6_LOCK.read_text())
        if (_file_sha256(V6_LOCK) != V6_LOCK_SHA256
                or _file_sha256(directory/'manifest.json') != lock['dataset_manifest_sha256']
                or manifest['files_sha256'] != lock['split_sha256']):
            raise ValueError('V6 differs from the public frozen candidate manifest/split hashes')
    if manifest['configuration']['generator_version'] != VERSIONS[name]:
        raise ValueError('Wrong original source version: '+name)
    if set(manifest['files_sha256']) != {split+'.jsonl' for split in SPLITS}:
        raise ValueError('Each source must retain all five frozen splits')
    splits = {}
    for split, count in zip(SPLITS,COUNTS[name]):
        path = directory/(split+'.jsonl')
        if _file_sha256(path) != manifest['files_sha256'][path.name]:
            raise ValueError('Source file hash changed: '+str(path))
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        if len(rows) != count or any(r['split'] != split or r['source'] != VERSIONS[name]
                or r['metadata']['provenance']['type'] != 'synthetic' for r in rows):
            raise ValueError('Source count/split/provenance differs: '+name+'/'+split)
        splits[split] = rows
    all_rows = [r for rows in splits.values() for r in rows]
    validate_records(all_rows)
    groups = {}
    for row in all_rows:
        groups.setdefault(row['group_id'],[]).append(row)
    if any(len(rows) != 4 or {r['metadata']['provenance']['variant'] for r in rows} != {0,1,2,3}
           for rows in groups.values()):
        raise ValueError('Every source group must retain all four variants')
    return splits, {'manifest_sha256':_file_sha256(directory/'manifest.json'),
        'split_sha256':manifest['files_sha256'], 'rows_sha256':{s:_json_sha256(r) for s,r in splits.items()},
        'rows':{s:len(r) for s,r in splits.items()},
        **({'frozen_candidate_sha256':V6_LOCK_SHA256} if name == 'v6' else {})}


def write_rows(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n' for r in rows))


def prepare(v4, v5, v6, output, initial_checkpoint, training_output):
    output = Path(output)
    if output.exists():
        raise FileExistsError('Choose a fresh immutable preparation directory')
    commit = committed_source()
    directories = {'v4':Path(v4),'v5':Path(v5),'v6':Path(v6)}
    sources, identities = {}, {}
    for name,directory in directories.items():
        sources[name],identities[name] = read_source(name,directory)
    validate_records([r for splits in sources.values() for rows in splits.values() for r in rows])
    regression, locks = {}, {}
    for name,(path,key) in LOCKS.items():
        selection = json.loads(path.read_text())[key]
        if selection['manifest_sha256'] != identities[name]['manifest_sha256']:
            raise ValueError('Observed regression lock is for another source: '+name)
        regression[name] = {}
        for split in ('test','ood'):
            lookup = {r['id']:r for r in sources[name][split]}
            rows = [lookup[identity] for identity in selection['selected_ids'][split]]
            if _json_sha256(rows) != selection['selected_sha256'][split]:
                raise ValueError('Observed regression selection changed: '+name+'/'+split)
            regression[name][split] = rows
        locks[name] = {'file_sha256':_file_sha256(path),'selected_rows_sha256':selection['selected_sha256']}
    mixed = [r for name in sources for split in ('train','calibration','validation') for r in sources[name][split]]
    mixed += sources['v6']['test'] + sources['v6']['ood']
    manifest = _write_dataset(mixed,output,{'type':'synthetic','status':'candidate_not_trained',
        'generator_version':'policy-training-v6-mixture','seed':20261002,'source_commit':commit,
        'preparation_sha256':_file_sha256(__file__), 'sources':identities,
        'train_policy':'All original Train rows only; no Test/OOD/Calibration/Validation promotion'})
    heldout_hashes = {}
    for name,directory in directories.items():
        for split in ('calibration','validation'):
            destination = output/'heldout'/name/(split+'.jsonl')
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(directory/(split+'.jsonl'),destination)
            heldout_hashes[destination.relative_to(output).as_posix()] = _file_sha256(destination)
    for name,splits in regression.items():
        for split,rows in splits.items():
            destination = output/'observed-regression'/name/(split+'.jsonl')
            write_rows(destination,rows)
            heldout_hashes[destination.relative_to(output).as_posix()] = _file_sha256(destination)
    count = manifest['summary']['splits']['train']
    settings = dict(steps=count//4,accumulation=4,train_rows=count,
        calibration_rows=manifest['summary']['splits']['calibration'],eval_rows=len(sources['v6']['test']),
        max_length=4096,lora_rank=8,lr=2e-5,head_lr=5e-5,brier_weight=.1,
        seed=20261002,training_sampling='shuffled',checkpoint_every=0)
    release = json.loads(RELEASE.read_text())
    command = ['python','-m','jev.train','--model',release['base_model'],'--revision',release['base_revision'],
        '--data',str(output),'--output',str(training_output),'--initial-checkpoint',str(initial_checkpoint)]
    for name,value in settings.items():
        command += ['--'+name.replace('_','-'),str(value)]
    plan = {'schema_version':1,'status':'predeclared_candidate_not_trained','source_commit':commit,
        'data_manifest_sha256':_file_sha256(output/'manifest.json'),'settings':settings,'training_argv':command,
        'released_package_proof_sha256':_file_sha256(RELEASE),
        'expected_initial_checkpoint':{'model_repo':release['model_repository'],
            'model_revision':release['model_repository_revision'],'directory_sha256':release['checkpoint_sha256'],
            'files_sha256':{n.removeprefix('checkpoint/'):v['sha256'] for n,v in release['files'].items()}},
        'checkpoint_staging':'The checkpoint argument names its future training-host path; preparation never loads weights. Verify its exact released file hashes before executing.',
        'heldout_files_sha256':heldout_hashes,'observed_regression_locks':locks,
        'required_future_comparison':{'status':'not_run_not_automatically_provided_by_jev.train',
            'reference':'Exact released 2B and fixed final adapted weights, recomputed in the same runtime',
            'ablation':'Saved released/adapted logits at released temperature and newly trained calibration-only temperature',
            'primary':'v6 Test/OOD36 each; per family, cents equality/one-cent, authority scope/latest/revocation and untrusted-text invariance',
            'regression':'Preserved observed v4/v5 Test/OOD; report aggregate, exclusion-boundary and state-tracking regressions',
            'metrics':'Argmax, Brier/NLL/ECE and inclusive Noul0.2/0.8 accuracy/coverage/accepted errors'},
        'stop_policy':'One fixed full Train pass, fixed final checkpoint. Initial-checkpoint mode has checkpoint_every=0 and cannot resume; interruption requires a separately declared future attempt. No test/OOD retuning or automatic release promotion. Validation remains separate and is not consumed by jev.train.',
        'limitations':'Original synthetic candidate only; not trained, GPU-verified, a natural-request or official JevBench result. V5 diagnostic weights are not the initialization.'}
    (output/'comparison-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    return manifest,plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('v4','v5','v6','output','initial-checkpoint','training-output'):
        parser.add_argument('--'+name,required=True)
    args = parser.parse_args()
    manifest,plan = prepare(args.v4,args.v5,args.v6,args.output,args.initial_checkpoint,args.training_output)
    print(json.dumps({'status':plan['status'],'source_commit':plan['source_commit'],
                      'rows':manifest['summary']['splits'],'steps':plan['settings']['steps']},indent=2))


if __name__ == '__main__':
    main()
