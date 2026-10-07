"""Real Git/source imports in fresh standard-library-only interpreters.

Fixture commits are patched only in copied helpers, never production constants.
No training, native model callback, data/weight load, GPU or SSH action runs.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
HELPER = 'scripts/frontier_v8_source_loader.py'
SCIENCE_MODULES = ('jev/__init__.py', 'jev/metrics.py', 'jev/train.py',
    'scripts/run_frontier_training_v8.py', 'scripts/compare_frontier_training_v8.py')
NATIVE_FILES = ('scripts/run_frontier_native_v8.py', 'scripts/frontier_v8_native_model.py',
    'scripts/frontier_v8_owned_process.py', 'docs/frontier-v8-native-runtime.md',
    'tests/test_run_frontier_native_v8.py', 'tests/test_frontier_v8_native_model.py',
    'tests/test_frontier_v8_owned_process.py')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class SourceLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # macOS /var is an alias; production intentionally rejects aliases.
        self.root = Path(self.temp.name).resolve()
        self.roots = {name: self.root/name for name in ('scientific', 'native', 'operational')}
        for root in self.roots.values():
            root.mkdir()
            self.git(root, 'init', '-q')
        for name in SCIENCE_MODULES:
            self.write(self.roots['scientific']/name, (ROOT/name).read_bytes())
        for index in range(18-len(SCIENCE_MODULES)):
            self.write(self.roots['scientific']/f'fixtures/closure_{index}.txt',
                       f'Frozen closure sentinel {index}\n'.encode())
        for name in NATIVE_FILES:
            self.write(self.roots['native']/name, (ROOT/name).read_bytes())
        self.write(self.roots['operational']/HELPER, (ROOT/HELPER).read_bytes())
        self.write(self.roots['operational']/'.gitignore', b'__pycache__/\n*.pyc\n')
        self.refresh()

    @staticmethod
    def write(path, raw):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    @staticmethod
    def git(root, *args):
        environment = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        return subprocess.check_output(['git', '-c', 'user.name=CPU Fixture', '-c',
            'user.email=fixture@example.invalid', '-C', str(root), *args],
            env=environment, stderr=subprocess.DEVNULL)

    def json_file(self, name, value):
        path = self.root/name
        raw = (json.dumps(value, sort_keys=True, indent=2)+'\n').encode()
        path.write_bytes(raw)
        return str(path), digest(raw)

    def refresh(self, *, omit_scientific=()):
        commits, files = {}, {}
        for role, root in self.roots.items():
            self.git(root, 'add', '-A')
            self.git(root, 'commit', '-q', '--no-gpg-sign', '--allow-empty', '-m', 'CPU fixture')
            commits[role] = self.git(root, 'rev-parse', 'HEAD').decode().strip()
            names = self.git(root, 'ls-files', '-z').decode().split('\0')[:-1]
            files[role] = {name: digest((root/name).read_bytes()) for name in names
                          if role != 'scientific' or name not in omit_scientific}
        plan, plan_sha = self.json_file('plan.json', {'implementation_sha256': files['scientific']})
        freeze, freeze_sha = self.json_file('freeze.json', {'source_commit': commits['scientific'],
            'plan_sha256': plan_sha, 'implementation_sha256': files['scientific']})
        native, native_sha = self.json_file('native.json', {
            'native_source_commit': commits['native'], 'native_files_sha256': files['native'],
            'scientific_source_commit': commits['scientific'], 'scientific_plan_sha256': plan_sha,
            'scientific_freeze_sha256': freeze_sha})
        operational, operational_sha = self.json_file('operational.json', {
            'schema_version': 1, 'status': 'three_source_CPU_declaration',
            'source_commit': commits['operational'], 'scientific_source_commit': commits['scientific'],
            'native_source_commit': commits['native'], 'plan_sha256': plan_sha, 'freeze_sha256': freeze_sha,
            'native_declaration_sha256': native_sha, 'files_sha256': files['operational'],
            'execution_available': False, 'resource_authority': False})
        self.context = {role+'_root': str(root) for role, root in self.roots.items()}
        self.context.update(plan=plan, freeze=freeze, native_declaration=native,
            operational_declaration=operational, expected_operational_commit=commits['operational'],
            expected_native_declaration_sha256=native_sha,
            expected_operational_declaration_sha256=operational_sha)
        self.pins = {'SCIENCE_A': commits['scientific'], 'NATIVE_A': commits['native'],
            'PLAN_SHA': plan_sha, 'FREEZE_SHA': freeze_sha, 'NATIVE_DECLARATION_SHA': native_sha}
        self.fixture, _ = self.json_file('fixture.json', {'context': self.context, 'pins': self.pins})

    def child(self, body, *, environment=None, cwd=None):
        preamble = '''
            import importlib.util, json, pathlib, sys, types
            fixture = json.loads(pathlib.Path(sys.argv[1]).read_text())
            context = fixture['context']
            spec = importlib.util.spec_from_file_location('copied_operational_helper',
                str(pathlib.Path(context['operational_root'])/'scripts/frontier_v8_source_loader.py'))
            helper = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(helper)
            for name, value in fixture['pins'].items():
                setattr(helper, name, value)
            def rejected(call, fragment=None):
                try:
                    call()
                except helper.SourceVerificationError as error:
                    assert fragment is None or fragment in str(error), str(error)
                else:
                    raise AssertionError('Verification unexpectedly accepted')
        '''
        program = textwrap.dedent(preamble)+textwrap.dedent(body)
        result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', program, self.fixture],
            cwd=cwd or self.root, env=environment, capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        return result

    def test_actual_clean_repositories_import_real_modules_and_restore_state(self):
        self.child('''
            before = (dict(sys.modules), sys.path, list(sys.path), sys.meta_path, list(sys.meta_path),
                      sys.path_hooks, list(sys.path_hooks), sys.path_importer_cache,
                      dict(sys.path_importer_cache), sys.dont_write_bytecode)
            receipt = helper.verify_three_sources(context)
            assert receipt['model_calls'] == 0 and receipt['resource_authority'] is False
            assert receipt['context'] == context
            with helper.load_cpu_modules(context) as modules:
                assert isinstance(modules.driver, types.ModuleType)
                assert modules.comparator.driver is modules.driver
                assert modules.trainer.__file__ == context['scientific_root']+'/jev/train.py'
                assert callable(modules.trainer.run) and callable(modules.native.make_loader)
                assert modules.comparator.decision(.8) == 'yes'
                assert len(modules.imported_modules) == 7
                assert all(v['loader'] == 'captured_verified_source_bytes'
                           for v in modules.imported_modules.values())
                assert all(p not in sys.modules for p in helper.OPTIONAL)
                assert modules.execution_available is False and modules.resource_authority is False
                assert modules.model_calls == 0
            assert dict(sys.modules) == before[0]
            assert sys.path is before[1] and sys.path == before[2]
            assert sys.meta_path is before[3] and sys.meta_path == before[4]
            assert sys.path_hooks is before[5] and sys.path_hooks == before[6]
            assert sys.path_importer_cache is before[7] and sys.path_importer_cache == before[8]
            assert sys.dont_write_bytecode == before[9]
        ''')
        self.assertFalse(list(self.root.rglob('*.pyc')))

    def test_preloaded_scientific_or_scripts_modules_and_optional_packages_rejected(self):
        self.child('''
            for name in ('jev.metrics', 'scripts', 'scripts.run_frontier_training_v8', 'torch'):
                fake = types.ModuleType(name)
                fake.__file__ = context['scientific_root']+'/jev/metrics.py'
                fake.__spec__ = importlib.util.spec_from_loader(name, loader=None, origin=fake.__file__)
                sys.modules[name] = fake
                rejected(lambda: helper.load_cpu_modules(context).__enter__(), 'Preloaded')
                assert sys.modules[name] is fake
                del sys.modules[name]
        ''')

    def test_hostile_cwd_and_pythonpath_are_not_imported(self):
        shadow = self.root/'shadow'
        self.write(shadow/'jev.py', b"raise AssertionError('hostile jev ran')\n")
        self.write(shadow/'scripts/__init__.py', b"raise AssertionError('hostile scripts ran')\n")
        self.write(shadow/'sitecustomize.py', b"raise AssertionError('site hook ran')\n")
        environment = dict(os.environ, PYTHONPATH=str(shadow), GIT_DIR=str(shadow))
        self.child('''
            with helper.load_cpu_modules(context) as modules:
                assert modules.comparator.driver is modules.driver
        ''', environment=environment, cwd=shadow)

    def test_explicit_foreign_path_and_meta_hook_are_rejected(self):
        self.child('''
            sys.path.insert(0, str(pathlib.Path(context['operational_root']).parent/'shadow'))
            rejected(lambda: helper.load_cpu_modules(context).__enter__(), 'Foreign sys.path')
            sys.path.pop(0)
            class HostileFinder:
                def find_spec(self, *args):
                    raise AssertionError('Foreign hook ran')
            hook = HostileFinder()
            sys.meta_path.insert(0, hook)
            rejected(lambda: helper.load_cpu_modules(context).__enter__(), 'foreign import hooks')
            assert sys.meta_path.pop(0) is hook
        ''')

    def test_caller_path_cache_and_hooks_are_bypassed_then_restored(self):
        self.child('''
            class HostileCache:
                def find_spec(self, *args):
                    raise AssertionError('Foreign cache ran')
            def hostile_hook(*args):
                raise AssertionError('Foreign path hook ran')
            cache = HostileCache()
            standard = helper.sysconfig.get_paths()['stdlib']
            sys.path_importer_cache[standard] = cache
            sys.path_hooks.insert(0, hostile_hook)
            with helper.load_cpu_modules(context) as modules:
                assert modules.comparator.driver is modules.driver
            assert sys.path_importer_cache[standard] is cache
            assert sys.path_hooks[0] is hostile_hook
        ''')

    def test_dirty_untracked_and_ignored_bytecode_are_rejected(self):
        cases = ((self.roots['scientific']/'jev/train.py', b'# changed\n'),
                 (self.roots['native']/'unexpected.txt', b'untracked\n'),
                 (self.roots['operational']/'__pycache__/stale.pyc', b'stale bytecode'))
        for path, raw in cases:
            with self.subTest(path=str(path)):
                old = path.read_bytes() if path.exists() else None
                self.write(path, raw)
                self.child("rejected(lambda: helper.verify_three_sources(context), 'Dirty, untracked or ignored')")
                if old is None:
                    path.unlink()
                    if path.parent.name == '__pycache__':
                        path.parent.rmdir()
                else:
                    path.write_bytes(old)

    def test_symlink_blob_and_alias_root_are_rejected(self):
        path = self.roots['scientific']/'fixtures/closure_0.txt'
        path.unlink()
        path.symlink_to('closure_1.txt')
        self.refresh()
        self.child("rejected(lambda: helper.verify_three_sources(context), 'Symlink')")
        path.unlink()
        path.write_text('Regular closure again\n')
        self.refresh()
        alias = self.root/'alias'
        alias.symlink_to(self.roots['scientific'], target_is_directory=True)
        self.child(f"context['scientific_root'] = {str(alias)!r}\nrejected(lambda: helper.verify_three_sources(context), 'Symlink')")

    def test_nested_roots_wrong_head_inventory_and_loader_origin_are_rejected(self):
        self.child('''
            original = dict(context)
            context['native_root'] = context['scientific_root']+'/jev'
            rejected(lambda: helper.verify_three_sources(context), 'disjoint')
            context.update(original)
            context['expected_operational_commit'] = '0'*40
            rejected(lambda: helper.verify_three_sources(context), 'declaration')
            context.update(original)
            helper.__file__ = context['scientific_root']+'/scripts/frontier_v8_source_loader.py'
            rejected(lambda: helper.verify_three_sources(context), 'Loader must run')
        ''')
        self.child('''
            root = pathlib.Path(context['scientific_root'])
            changed = dict(json.loads(pathlib.Path(context['plan']).read_bytes())['implementation_sha256'])
            changed['jev/train.py'] = '0'*64
            rejected(lambda: helper._checkout(root, helper.SCIENCE_A, changed), 'Source byte/blob/hash differs')
            rejected(lambda: helper._checkout(root, '0'*40, changed), 'Git root/HEAD differs')
        ''')

    def test_external_bytes_and_same_byte_rewrite_between_captures_rejected(self):
        self.child('''
            target = pathlib.Path(context['plan'])
            target.write_bytes(target.read_bytes()+b' ')
            rejected(lambda: helper.verify_three_sources(context), 'External declaration bytes')
        ''')
        self.refresh()
        self.child('''
            capture = helper._capture
            calls = 0
            def changed(value):
                global calls
                result = capture(value)
                calls += 1
                if calls == 1:
                    target = pathlib.Path(context['plan'])
                    target.write_bytes(target.read_bytes())
                return result
            helper._capture = changed
            rejected(lambda: helper.verify_three_sources(context), 'identity changed')
        ''')

    def test_same_bytes_replacement_of_root_between_captures_rejected(self):
        self.child('''
            import shutil
            capture = helper._capture
            calls = 0
            def replaced(value):
                global calls
                result = capture(value)
                calls += 1
                if calls == 1:
                    root = pathlib.Path(context['scientific_root'])
                    moved = root.with_name('old-source')
                    root.rename(moved)
                    shutil.copytree(moved, root)
                return result
            helper._capture = replaced
            rejected(lambda: helper.verify_three_sources(context), 'identity changed')
        ''')

    def test_top_level_optional_import_is_blocked_and_partial_state_restored(self):
        path = self.roots['scientific']/'scripts/compare_frontier_training_v8.py'
        path.write_bytes(path.read_bytes()+b'\nimport torch\n')
        self.refresh()
        self.child('''
            # Initialize lazy standard-library configuration before the state snapshot.
            helper.sysconfig.get_paths()
            before = dict(sys.modules)
            rejected(lambda: helper.load_cpu_modules(context).__enter__(), 'optional module import rejected')
            assert dict(sys.modules) == before and 'torch' not in sys.modules
        ''')

    def test_partial_import_exception_restores_existing_parent_attributes(self):
        path = self.roots['scientific']/'scripts/compare_frontier_training_v8.py'
        path.write_bytes(path.read_bytes()+b"\nimport existing_parent\nexisting_parent.marker = 'changed'\nraise RuntimeError('partial import sentinel')\n")
        self.refresh()
        self.child('''
            helper.sysconfig.get_paths()
            parent = types.ModuleType('existing_parent')
            parent.__path__ = []
            marker = object()
            parent.marker = marker
            sys.modules[parent.__name__] = parent
            before = (dict(sys.modules), list(sys.path), list(sys.meta_path), list(sys.path_hooks),
                      dict(sys.path_importer_cache), sys.dont_write_bytecode)
            try:
                with helper.load_cpu_modules(context):
                    raise AssertionError('Unreachable')
            except RuntimeError as error:
                assert str(error) == 'partial import sentinel'
            else:
                raise AssertionError('Partial import unexpectedly accepted')
            assert parent.marker is marker and sys.modules[parent.__name__] is parent
            assert dict(sys.modules) == before[0] and sys.path == before[1]
            assert sys.meta_path == before[2] and sys.path_hooks == before[3]
            assert sys.path_importer_cache == before[4] and sys.dont_write_bytecode == before[5]
        ''')

    def test_loaded_origin_loader_and_callable_replacements_detected(self):
        for expression in ("modules.trainer.__file__ = '/forged/train.py'",
                           "modules.trainer.__spec__.origin = '/forged/train.py'",
                           'modules.trainer.__loader__ = object()',
                           'modules.trainer.run = lambda *args: None',
                           'modules.trainer.run.__code__ = (lambda *args: None).__code__'):
            with self.subTest(expression=expression):
                self.child(f'''
                    helper.sysconfig.get_paths()
                    before = dict(sys.modules)
                    try:
                        with helper.load_cpu_modules(context) as modules:
                            {expression}
                    except helper.SourceVerificationError:
                        pass
                    else:
                        raise AssertionError('Changed loaded module unexpectedly accepted')
                    assert dict(sys.modules) == before
                ''')

    def test_changes_during_scope_are_detected_and_caller_exception_cleanup_runs(self):
        self.child('''
            helper.sysconfig.get_paths()
            before = dict(sys.modules)
            try:
                with helper.load_cpu_modules(context):
                    target = pathlib.Path(context['freeze'])
                    target.write_bytes(target.read_bytes())
            except helper.SourceVerificationError as error:
                assert 'inside CPU import scope' in str(error)
            else:
                raise AssertionError('Changed declaration unexpectedly accepted')
            assert dict(sys.modules) == before
        ''')
        self.refresh()
        self.child('''
            helper.sysconfig.get_paths()
            before = dict(sys.modules)
            try:
                with helper.load_cpu_modules(context):
                    raise RuntimeError('caller sentinel')
            except RuntimeError as error:
                assert str(error) == 'caller sentinel'
            assert dict(sys.modules) == before
        ''')

    def test_sparse_worktree_actual_git_pointer_is_supported(self):
        base = self.roots['scientific']
        self.write(base/'outside-closure.txt', b'Tracked file outside the declared source closure\n')
        self.refresh(omit_scientific=('outside-closure.txt',))
        sparse = self.root/'sparse-scientific'
        self.git(base, 'worktree', 'add', '--detach', '--no-checkout', str(sparse), self.pins['SCIENCE_A'])
        self.git(sparse, 'sparse-checkout', 'init', '--no-cone')
        names = json.loads(Path(self.context['plan']).read_bytes())['implementation_sha256']
        self.git(sparse, 'sparse-checkout', 'set', '--no-cone', *('/'+name for name in names))
        self.git(sparse, 'read-tree', '-mu', 'HEAD')
        self.assertFalse((sparse/'outside-closure.txt').exists())
        self.child(f'''
            context['scientific_root'] = {str(sparse)!r}
            assert pathlib.Path(context['scientific_root'], '.git').is_file()
            for role in helper.ROLES:
                dirty = helper._git(pathlib.Path(context[role+'_root']), 'status', '--porcelain=v1',
                                    '-z', '--untracked-files=all', '--ignored=matching')
                assert not dirty, (role, repr(dirty))
            helper.verify_three_sources(context)
            with helper.load_cpu_modules(context) as modules:
                assert modules.trainer.__file__.startswith(context['scientific_root'])
        ''')

    def test_execute_and_execute_cli_refuse_before_reading_a_context(self):
        self.child('''
            def never_read(*args, **kwargs):
                raise AssertionError('Context was read')
            helper._bytes = never_read
            rejected(lambda: helper.execute(context), 'execution unavailable')
            rejected(lambda: helper.main(['--execute', '--context', '/missing/context.json']), 'execution unavailable')
        ''')
        result = subprocess.run([sys.executable, '-I', '-S', str(ROOT/HELPER),
            '--execute', '--context', '/missing/context.json'], capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Production model execution unavailable', result.stderr)
        self.assertNotIn('FileNotFoundError', result.stderr)


if __name__ == '__main__':
    unittest.main()
