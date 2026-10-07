"""Verify declared Git source closures and import their CPU-only modules.

Use a fresh ``python -I -S`` process. This checks trusted source provenance,
not a Python sandbox, installed runtime, GPU lease or execution authority.
Scientific/native algorithms and their closed execution entrypoints are unchanged.
"""
import argparse
import _imp
from contextlib import contextmanager
import hashlib
import importlib
from importlib import abc, machinery, util
import json
import marshal
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import sysconfig
import threading
from types import FunctionType, ModuleType, SimpleNamespace
import zipimport


SCIENCE_A = 'd8eeb3d1f8e8d8751476f102ab456170c277e86a'
NATIVE_A = '4b55c6e3f025fd92ec4396d5c61bb4dfe13cbda2'
PLAN_SHA = '984539a92f1aa37b93e58fea7df4511a1635e7e9f284531068bb5a0939ebc8be'
FREEZE_SHA = 'a710f79977ac582cdc9269368e3f442abb88e76e4bbfae89b962116ade213a5f'
NATIVE_DECLARATION_SHA = '53e3cea8adc09fec82aea319775569ad4d487b3b0f88cd1f094653bc70de793d'
CONTEXT_FIELDS = {'scientific_root', 'native_root', 'operational_root', 'plan', 'freeze',
    'native_declaration', 'operational_declaration', 'expected_operational_commit',
    'expected_native_declaration_sha256', 'expected_operational_declaration_sha256'}
ROLES = ('scientific', 'native', 'operational')
EXTERNAL = ('plan', 'freeze', 'native_declaration', 'operational_declaration')
OPTIONAL = ('torch', 'transformers', 'peft', 'triton', 'safetensors', 'accelerate')
STDLIB = sysconfig.get_paths()['stdlib']
NATIVE_FILES = {'scripts/run_frontier_native_v8.py', 'scripts/frontier_v8_native_model.py',
    'scripts/frontier_v8_owned_process.py', 'docs/frontier-v8-native-runtime.md',
    'tests/test_run_frontier_native_v8.py', 'tests/test_frontier_v8_native_model.py',
    'tests/test_frontier_v8_owned_process.py'}


class SourceVerificationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise SourceVerificationError(message)


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _absolute(value):
    require(isinstance(value, str) and value and '\0' not in value, 'Actual absolute path required')
    path = Path(value)
    require(path.is_absolute() and path.as_posix() == value and '..' not in path.parts,
            'Normalized absolute path required')
    for part in (path, *path.parents):
        require(not stat.S_ISLNK(part.lstat().st_mode), 'Symlink path or ancestor rejected')
    return path


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _bytes(path):
    path = _absolute(str(path))
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode), 'Regular file required')
    with path.open('rb') as handle:
        require(_identity(os.fstat(handle.fileno())) == _identity(before), 'Input replaced before read')
        raw = handle.read()
        require(_identity(os.fstat(handle.fileno())) == _identity(before), 'Input changed during read')
    require(_identity(path.lstat()) == _identity(before), 'Input path replaced during read')
    return raw, _identity(before)


def _git(root, *args):
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env['GIT_TERMINAL_PROMPT'] = '0'
    try:
        return subprocess.check_output(['git', '-c', 'core.fsmonitor=false', '-c',
            'core.untrackedCache=false', '-C', str(root), *args], env=env,
            stderr=subprocess.DEVNULL, timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        raise SourceVerificationError('Git source check failed') from error


def _checkout(root, commit, inventory):
    require(stat.S_ISDIR(root.lstat().st_mode), 'Source root must be a directory')
    require(isinstance(commit, str) and re.fullmatch(r'[0-9a-f]{40}', commit), 'Exact commit required')
    require(isinstance(inventory, dict) and inventory, 'Nonempty source inventory required')
    require(_git(root, 'rev-parse', '--show-toplevel').decode().strip() == str(root)
        and _git(root, 'rev-parse', 'HEAD').decode().strip() == commit, 'Actual Git root/HEAD differs')
    require(not _git(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all',
        '--ignored=matching'), 'Dirty, untracked or ignored source files rejected')
    raw_files, identities = {}, {str(root): _identity(root.lstat())}
    for name, digest in inventory.items():
        require(isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9_.\-/]+', name)
            and not Path(name).is_absolute() and Path(name).as_posix() == name
            and '..' not in Path(name).parts and isinstance(digest, str)
            and re.fullmatch(r'[0-9a-f]{64}', digest), 'Regular relative blob inventory required')
        path = _absolute(str(root/name))
        tree = _git(root, 'ls-tree', '-z', commit, '--', ':(literal)'+name)
        require(tree.count(b'\0') == 1, 'Declared Git file missing or ambiguous')
        header, tree_name = tree[:-1].split(b'\t', 1)
        mode, kind, oid = header.split()
        require(mode in (b'100644', b'100755') and kind == b'blob'
            and tree_name.decode() == name, 'Git leaf is not a regular source blob')
        raw, identities[str(path)] = _bytes(path)
        require(raw == _git(root, 'cat-file', 'blob', oid.decode()) and _digest(raw) == digest,
                'Source byte/blob/hash differs: '+name)
        raw_files[name] = raw
        for parent in path.parents:
            info = parent.lstat()
            identities[str(parent)] = (_identity(info) if parent.is_relative_to(root)
                else (info.st_dev, info.st_ino, info.st_mode))
    return raw_files, identities


def _capture(context):
    require(isinstance(context, dict) and set(context) == CONTEXT_FIELDS, 'Exact source context required')
    roots = {role: _absolute(context[role+'_root']) for role in ROLES}
    require(all(not left.is_relative_to(right) and not right.is_relative_to(left)
        for i, left in enumerate(roots.values()) for right in list(roots.values())[i+1:]),
        'Three source roots must be disjoint')
    external = {name: _absolute(context[name]) for name in EXTERNAL}
    require(len(set(external.values())) == 4 and all(not p.is_relative_to(r)
        for p in external.values() for r in roots.values()), 'External declarations overlap source')
    raws, identities = {}, {}
    for name, path in external.items():
        raws[name], identities[str(path)] = _bytes(path)
        for parent in path.parents:
            info = parent.lstat()
            identities[str(parent)] = (info.st_dev, info.st_ino, info.st_mode)
    expected = {'plan': PLAN_SHA, 'freeze': FREEZE_SHA,
        'native_declaration': context['expected_native_declaration_sha256'],
        'operational_declaration': context['expected_operational_declaration_sha256']}
    require(expected['native_declaration'] == NATIVE_DECLARATION_SHA,
            'Pinned native declaration differs')
    require(all(isinstance(v, str) and re.fullmatch(r'[0-9a-f]{64}', v)
        and _digest(raws[k]) == v for k, v in expected.items()), 'External declaration bytes differ')
    plan, freeze, native, operational = (json.loads(raws[k]) for k in EXTERNAL)
    science_files = plan['implementation_sha256']
    require(len(science_files) == 18 and science_files == freeze['implementation_sha256']
        and freeze['source_commit'] == SCIENCE_A and freeze['plan_sha256'] == PLAN_SHA,
        'Frozen scientific closure differs')
    require(native['native_source_commit'] == NATIVE_A
        and set(native['native_files_sha256']) == NATIVE_FILES
        and native['scientific_source_commit'] == SCIENCE_A
        and native['scientific_plan_sha256'] == PLAN_SHA
        and native['scientific_freeze_sha256'] == FREEZE_SHA, 'Frozen native closure differs')
    require(operational['schema_version'] == 1 and operational['status'] == 'three_source_CPU_declaration'
        and operational['source_commit'] == context['expected_operational_commit']
        and operational['source_commit'] not in (SCIENCE_A, NATIVE_A)
        and operational['scientific_source_commit'] == SCIENCE_A
        and operational['native_source_commit'] == NATIVE_A
        and operational['plan_sha256'] == PLAN_SHA and operational['freeze_sha256'] == FREEZE_SHA
        and operational['native_declaration_sha256'] == NATIVE_DECLARATION_SHA
        and operational['execution_available'] is False and operational['resource_authority'] is False,
        'Separate operational CPU declaration required')
    files = {'scientific': science_files, 'native': native['native_files_sha256'],
             'operational': operational['files_sha256']}
    require('scripts/frontier_v8_source_loader.py' in files['operational']
        and Path(__file__) == roots['operational']/'scripts/frontier_v8_source_loader.py',
        'Loader must run from its declared operational source')
    commits = {'scientific': SCIENCE_A, 'native': NATIVE_A,
               'operational': context['expected_operational_commit']}
    sources = {}
    for role in ROLES:
        sources[role], current = _checkout(roots[role], commits[role], files[role])
        identities.update(current)
    receipt = {'schema_version': 1, 'status': 'three_clean_sources_verified_CPU_only',
        'context': dict(context), 'external_files_sha256': expected,
        **{role: {'root': str(roots[role]), 'commit': commits[role], 'files_sha256': files[role]}
            for role in ROLES}, 'scope': 'three_source_CPU_verification_only',
        'execution_available': False, 'resource_authority': False,
        'model_execution_authority': False, 'model_calls': 0}
    return receipt, sources, identities


def _verified(context):
    first = _capture(context)
    second = _capture(context)
    require(first == second, 'Source/declaration or directory identity changed during verification')
    return first


def verify_three_sources(context):
    """Actual declared inventories, including sparse Git worktrees; no authority."""
    return _verified(context)[0]


class _CapturedLoader(abc.Loader):
    def __init__(self, path, raw, package=False):
        self.path, self.raw, self.package = path, raw, package
        self.code = compile(raw, path or '<verified-science-scripts>', 'exec', dont_inherit=True)
        self.module = None
        self.functions = {}

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        self.module = module
        if self.path:
            module.__file__ = self.path
        exec(self.code, module.__dict__)
        self.functions = {name: (value, value.__code__) for name, value in module.__dict__.items()
            if isinstance(value, FunctionType) and value.__module__ == module.__name__}


class _Finder(abc.MetaPathFinder):
    def __init__(self, loaders):
        self.loaders = loaders

    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.loaders:
            loader = self.loaders[fullname]
            return util.spec_from_loader(fullname, loader, origin=loader.path,
                                         is_package=loader.package)
        require(fullname.split('.')[0] in sys.stdlib_module_names,
                'Undeclared or optional module import rejected: '+fullname)
        return None


def _audit(loaders):
    result = {}
    for name, loader in loaders.items():
        module = sys.modules.get(name)
        require(module is loader.module and module is not None and module.__loader__ is loader
            and module.__spec__.loader is loader and module.__spec__.origin == loader.path,
            'Loaded module/loader/origin identity differs: '+name)
        require(loader.path is None or module.__file__ == loader.path, 'Loaded module path differs')
        require(all(module.__dict__.get(key) is function and function.__code__ is code
            for key, (function, code) in loader.functions.items()), 'Loaded callable identity differs: '+name)
        result[name] = {'path': loader.path, 'source_sha256': _digest(loader.raw),
            'compiled_code_sha256': _digest(marshal.dumps(loader.code)),
            'loader': 'captured_verified_source_bytes', 'synthetic_namespace': loader.path is None}
    require(all(not any(n == p or n.startswith(p+'.') for n in sys.modules) for p in OPTIONAL),
            'Optional model modules appeared during CPU imports')
    return result


@contextmanager
def load_cpu_modules(context):
    """Import actual frozen CPU modules, then restore caller import state.

    Returned real modules remain trusted Python callables, not a sandbox. This
    method calls no trainer/native/model function and provides no GPU authority.
    """
    require(threading.current_thread() is threading.main_thread(), 'Main-thread import scope required')
    require(all(f in (machinery.BuiltinImporter, machinery.FrozenImporter, machinery.PathFinder)
        for f in sys.meta_path), 'Use fresh python -I -S; foreign import hooks rejected')
    require(not any(n == 'jev' or n.startswith('jev.') or n == 'scripts'
        or (n.startswith('scripts.') and n != __name__) for n in sys.modules),
        'Preloaded scientific/scripts namespace rejected; use a fresh process')
    require(not any(n == p or n.startswith(p+'.') for n in sys.modules for p in OPTIONAL),
        'Preloaded optional modules rejected')
    stdlib = STDLIB
    stdlib_paths = {stdlib, str(Path(stdlib)/'lib-dynload'),
        str(Path(stdlib).parent/('python'+str(sys.version_info.major)+str(sys.version_info.minor)+'.zip'))}
    require(all(isinstance(p, str) and p in stdlib_paths for p in sys.path),
            'Foreign sys.path entry rejected; use fresh python -I -S')
    receipt, sources, identities = _verified(context)
    native_name = '_openjev_native_'+context['expected_operational_commit']
    require(native_name not in sys.modules, 'Preloaded native alias rejected')
    mapping = {'jev': ('scientific', 'jev/__init__.py', True),
        'jev.metrics': ('scientific', 'jev/metrics.py', False),
        'jev.train': ('scientific', 'jev/train.py', False),
        'scripts.run_frontier_training_v8': ('scientific', 'scripts/run_frontier_training_v8.py', False),
        'scripts.compare_frontier_training_v8': ('scientific', 'scripts/compare_frontier_training_v8.py', False),
        native_name: ('native', 'scripts/frontier_v8_native_model.py', False)}
    loaders = {'scripts': _CapturedLoader(None, b'', True)}
    for name, (role, relative, package) in mapping.items():
        require(relative in sources[role], 'Imported source missing from declared closure')
        loaders[name] = _CapturedLoader(str(Path(receipt[role]['root'])/relative),
                                        sources[role][relative], package)
    original_modules, original_path = sys.modules, sys.path
    before_modules, before_path = dict(sys.modules), list(sys.path)
    parents = {n: dict(m.__dict__) for n, m in sys.modules.items()
               if isinstance(m, ModuleType) and hasattr(m, '__path__')}
    original_meta, original_hooks, original_cache = sys.meta_path, sys.path_hooks, sys.path_importer_cache
    before_meta, before_hooks, before_cache = list(sys.meta_path), list(sys.path_hooks), dict(sys.path_importer_cache)
    bytecode = sys.dont_write_bytecode
    _imp.acquire_lock()
    try:
        sys.path = [stdlib, str(Path(stdlib)/'lib-dynload')]
        sys.meta_path = [_Finder(loaders), machinery.BuiltinImporter, machinery.FrozenImporter, machinery.PathFinder]
        sys.path_hooks = [zipimport.zipimporter, machinery.FileFinder.path_hook(
            (machinery.SourceFileLoader, machinery.SOURCE_SUFFIXES),
            (machinery.ExtensionFileLoader, machinery.EXTENSION_SUFFIXES))]
        sys.path_importer_cache = {}
        sys.dont_write_bytecode = True
        driver = importlib.import_module('scripts.run_frontier_training_v8')
        comparator = importlib.import_module('scripts.compare_frontier_training_v8')
        trainer = importlib.import_module('jev.train')
        native = importlib.import_module(native_name)
        audit = _audit(loaders)
        require(_capture(context) == (receipt, sources, identities), 'Sources changed during module loading')
        yield SimpleNamespace(driver=driver, comparator=comparator, trainer=trainer, native=native,
            source_receipt=receipt, imported_modules=audit, execution_available=False,
            resource_authority=False, model_calls=0)
        _audit(loaders)
        require(_capture(context) == (receipt, sources, identities), 'Sources changed inside CPU import scope')
    finally:
        sys.modules = original_modules
        for name in set(sys.modules)-set(before_modules):
            del sys.modules[name]
        sys.modules.update(before_modules)
        for name, attributes in parents.items():
            before_modules[name].__dict__.clear()
            before_modules[name].__dict__.update(attributes)
        sys.path, sys.meta_path, sys.path_hooks, sys.path_importer_cache = original_path, original_meta, original_hooks, original_cache
        sys.path[:] = before_path
        sys.meta_path[:] = before_meta
        sys.path_hooks[:] = before_hooks
        sys.path_importer_cache.clear()
        sys.path_importer_cache.update(before_cache)
        sys.dont_write_bytecode = bytecode
        _imp.release_lock()


def execute(*args, **kwargs):
    raise SourceVerificationError('Production model execution unavailable; source imports grant no GPU authority')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--verify-only', action='store_true')
    mode.add_argument('--import-cpu', action='store_true')
    mode.add_argument('--execute', action='store_true')
    parser.add_argument('--context')
    args = parser.parse_args(argv)
    if args.execute:
        execute()
    raw, identity = _bytes(_absolute(args.context))
    context = json.loads(raw)
    require(all(not Path(args.context).is_relative_to(Path(context[role+'_root'])) for role in ROLES),
            'Context must remain outside all source checkouts')
    if args.import_cpu:
        with load_cpu_modules(context) as bundle:
            result = {'source_receipt': bundle.source_receipt, 'imported_modules': bundle.imported_modules,
                'execution_available': False, 'resource_authority': False, 'model_calls': 0,
                'optional_modules_absent': list(OPTIONAL)}
    else:
        result = verify_three_sources(context)
    require(_bytes(Path(args.context)) == (raw, identity), 'Context changed during verification')
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
