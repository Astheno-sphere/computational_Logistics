"""Verify separate v8 native preparation source; model execution stays unavailable.

This CPU source check neither imports a model nor consumes a GPU attempt.
The native model callback and owned CPU watchdog are not a GPU lease or a
restoration implementation for somebody else's training queue.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


PROTOCOL = 'frontier-v8-native-cpu-20261003-r1'
SCIENCE_COMMIT = 'd8eeb3d1f8e8d8751476f102ab456170c277e86a'
PLAN_SHA = '984539a92f1aa37b93e58fea7df4511a1635e7e9f284531068bb5a0939ebc8be'
FREEZE_SHA = 'a710f79977ac582cdc9269368e3f442abb88e76e4bbfae89b962116ade213a5f'
INSTALL_SHA = 'ce1d36beb0ae2a92835e8c8e820b42827208b8af63096ab4449f5a249cbe6dba'
INSTALL_REVIEW_SHA = '7ede82a8d759836b11b66957169a0c6ae89df1d54636332072c6c4fb25f81fd9'
NATIVE_FILES = (
    'scripts/run_frontier_native_v8.py', 'scripts/frontier_v8_native_model.py',
    'scripts/frontier_v8_owned_process.py', 'docs/frontier-v8-native-runtime.md',
    'tests/test_run_frontier_native_v8.py', 'tests/test_frontier_v8_native_model.py',
    'tests/test_frontier_v8_owned_process.py',
)
FIELDS = {'schema_version', 'protocol_id', 'native_id', 'status',
          'scientific_source_commit', 'scientific_plan_sha256', 'scientific_freeze_sha256',
          'native_source_commit', 'native_files_sha256', 'prior_installation_receipt_sha256',
          'prior_installation_review_sha256', 'execution_available', 'resource_authority',
          'borrowed_queue_restoration_available', 'gradient_nonzero_groups',
          'gradient_missing_policy'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def raw_file(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'Regular input file required')
    return path.read_bytes()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(directory, *arguments):
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env['GIT_TERMINAL_PROMPT'] = '0'
    return subprocess.check_output(['git', '-C', str(directory), *arguments],
                                   env=env, stderr=subprocess.DEVNULL)


def check_checkout(directory, commit, files):
    root = Path(directory)
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(),
            'Actual regular absolute source checkout required')
    require(re.fullmatch(r'[0-9a-f]{40}', commit) is not None,
            'Pinned source commit required')
    require(Path(git(root, 'rev-parse', '--show-toplevel').decode().strip()).resolve() == root.resolve()
            and git(root, 'rev-parse', 'HEAD').decode().strip() == commit,
            'Source checkout HEAD/root differs')
    require(not git(root, 'status', '--porcelain', '--untracked-files=all'),
            'Source checkout must be clean')
    for name, checksum in files.items():
        path = Path(name)
        require(isinstance(name, str) and path.as_posix() == name and bool(path.parts)
                and not path.is_absolute() and '..' not in path.parts
                and re.fullmatch(r'[0-9a-f]{64}', checksum) is not None,
                'Exact regular relative source inventory required')
        require((root/path).resolve().is_relative_to(root.resolve()), 'Source escapes checkout')
        blob = git(root, 'show', commit+':'+name)
        require(raw_file(root/path) == blob and digest(blob) == checksum,
                'Source blob/hash differs: '+name)
    return dict(files)


def verify_declaration(declaration, *, native_root, scientific_root, plan, freeze,
                       expected_declaration_sha256, expected_native_commit):
    """Check immutable source bytes only; no stage/resource/model attestation."""
    declaration_raw, plan_raw, freeze_raw = map(raw_file, (declaration, plan, freeze))
    require(digest(declaration_raw) == expected_declaration_sha256,
            'Native declaration bytes differ')
    require(digest(plan_raw) == PLAN_SHA and digest(freeze_raw) == FREEZE_SHA,
            'Frozen scientific plan/receipt bytes differ')
    declared, scientific, frozen = map(json.loads, (declaration_raw, plan_raw, freeze_raw))
    require(set(declared) == FIELDS and type(declared['schema_version']) is int
            and declared['schema_version'] == 1 and declared['protocol_id'] == PROTOCOL
            and re.fullmatch(r'frontier-v8-native-[0-9a-f]{16,64}', declared['native_id']) is not None
            and declared['status'] == 'native_CPU_source_preparation_only',
            'Separate CPU native declaration required')
    require(declared['scientific_source_commit'] == frozen['source_commit'] == SCIENCE_COMMIT
            and declared['scientific_plan_sha256'] == frozen['plan_sha256'] == PLAN_SHA
            and declared['scientific_freeze_sha256'] == FREEZE_SHA,
            'Scientific source/plan/freeze binding differs')
    require(declared['native_source_commit'] == expected_native_commit
            and expected_native_commit != SCIENCE_COMMIT
            and set(declared['native_files_sha256']) == set(NATIVE_FILES),
            'Complete separate native source inventory required')
    require(all(declared[key] is False for key in ('execution_available', 'resource_authority',
                                                  'borrowed_queue_restoration_available'))
            and declared['gradient_nonzero_groups'] == {'lora_A': 1, 'lora_B': 1, 'head': 1}
            and all(type(v) is int for v in declared['gradient_nonzero_groups'].values())
            and declared['gradient_missing_policy'] == 'report_without_imputation_all_present_finite',
            'CPU declarations cannot enable execution or change gradient criteria')
    require(declared['prior_installation_receipt_sha256'] == INSTALL_SHA
            and declared['prior_installation_review_sha256'] == INSTALL_REVIEW_SHA,
            'Prior completed installation reference differs')
    native, science = Path(native_root), Path(scientific_root)
    require(Path(__file__).resolve() == (native/'scripts/run_frontier_native_v8.py').resolve(),
            'Verifier must run from its declared native checkout')
    require(not native.resolve().is_relative_to(science.resolve())
            and not science.resolve().is_relative_to(native.resolve()),
            'Native and scientific source trees must be separate')
    for path in (declaration, plan, freeze):
        require(not Path(path).resolve().is_relative_to(science.resolve())
                and not Path(path).resolve().is_relative_to(native.resolve()),
                'External declaration/plan/freeze cannot dirty either source checkout')
    scientific_hashes = scientific['implementation_sha256']
    require(len(scientific_hashes) == 18 and scientific_hashes == frozen['implementation_sha256'],
            'Frozen scientific closure differs')
    native_hashes = check_checkout(native, expected_native_commit, declared['native_files_sha256'])
    source_hashes = check_checkout(science, SCIENCE_COMMIT, scientific_hashes)
    return {'schema_version': 1, 'status': 'native_CPU_source_declaration_verified',
        'protocol_id': PROTOCOL, 'native_id': declared['native_id'],
        'native_source_commit': expected_native_commit, 'native_files_sha256': native_hashes,
        'scientific_source_commit': SCIENCE_COMMIT, 'scientific_files_sha256': source_hashes,
        'plan_sha256': PLAN_SHA, 'freeze_sha256': FREEZE_SHA,
        'declaration_sha256': digest(declaration_raw), 'execution_available': False,
        'resource_authority': False, 'borrowed_queue_restoration_available': False,
        'numerical_settings_applied': False, 'model_loaded': False,
        'trainable_gradients_observed': False, 'model_calls': 0, 'GPU_actions': 0,
        'limits': ['Source integrity only. Prior installation is not a fresh host stage.',
                   'Injected CPU model fixtures do not load real tensors or prove CUDA/ABI behavior.',
                   'The process-only watchdog contains its own CPU tree; no foreign queue restoration is implemented.',
                   'Fresh staged data/weights/runtime and live GPU lease/restoration remain required.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--verify-declaration', action='store_true')
    mode.add_argument('--execute', action='store_true')
    for name in ('declaration', 'native-root', 'scientific-root', 'plan', 'freeze',
                 'expected-declaration-sha256', 'expected-native-commit'):
        parser.add_argument('--'+name)
    args = parser.parse_args(argv)
    if args.execute:
        raise ValueError('Model execution unavailable: fresh GPU lease and original-queue restoration protocol required')
    require(all(getattr(args, name.replace('-', '_')) for name in
                ('declaration', 'native-root', 'scientific-root', 'plan', 'freeze',
                 'expected-declaration-sha256', 'expected-native-commit')), 'Complete source-check arguments required')
    result = verify_declaration(args.declaration, native_root=args.native_root,
        scientific_root=args.scientific_root, plan=args.plan, freeze=args.freeze,
        expected_declaration_sha256=args.expected_declaration_sha256,
        expected_native_commit=args.expected_native_commit)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
