"""CPU fixtures; no installed Torch, native ABI, MS host or model observation."""
import base64
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import shlex
import stat
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import frontier_v8_runtime_abi as abi
from scripts import frontier_v8_runtime_transport as transport

ROOT = Path(__file__).resolve().parents[1]


def runtime_fixture(root):
    """76 fake metadata bodies, six fake sources; no installation or imports."""
    root = Path(root).resolve()
    venv = root / 'venv'
    site = venv / 'lib/python3.11/site-packages'
    site.mkdir(parents=True)
    (venv / 'bin').mkdir()
    (venv / 'bin/python').symlink_to(Path(sys.executable).resolve())
    cfg = b'include-system-site-packages = false\nversion = 3.11.15\n'
    (venv / 'pyvenv.cfg').write_bytes(cfg)
    pins = abi.parse_pins((ROOT / 'requirements-linux-py311-cu128-20261002.lock').read_bytes())
    for name, version in pins.items():
        directory = site / (name + '-' + version + '.dist-info')
        directory.mkdir()
        (directory / 'METADATA').write_text('Metadata-Version: 2.1\nName: ' + name + '\nVersion: ' + version + '\n')
    for name in abi.NAMES:
        (site / name).mkdir()
        (site / name / '__init__.py').write_text('fixture_only = True\n')
    spec = {'venv': str(venv), 'interpreter_realpath': str(Path(sys.executable).resolve()),
            'interpreter_sha256': abi.file_sha(Path(sys.executable).resolve()),
            'pyvenv_cfg_sha256': abi.digest(cfg), 'python_version': [3, 11, 15]}
    return venv, site, spec, pins


class FakeTensor:
    def __init__(self, values, dtype, device, requires_grad):
        self.values, self.dtype, self.device, self.requires_grad = values, dtype, device, requires_grad
        self.shape = (len(values), len(values[0]))
        self.grad_fn = None

    def __matmul__(self, other):
        return FakeTensor([[sum(self.values[i][k] * other.values[k][j] for k in range(2))
                            for j in range(2)] for i in range(2)], self.dtype, self.device, False)

    def tolist(self):
        return self.values


def fake_torch(site):
    torch = ModuleType('torch')
    torch.__file__ = str(site / 'torch/__init__.py')
    torch.__version__ = '2.8.0+cu128'
    torch.version = SimpleNamespace(cuda='12.8')
    torch.float32 = 'fixture_float32'
    torch.cuda = SimpleNamespace(is_initialized=Mock(return_value=False))
    torch.set_num_threads = Mock()
    torch.tensor = FakeTensor
    extension = ModuleType('torch._C')
    extension.__file__ = str(site / 'torch/_C.fixture.so')
    Path(extension.__file__).write_bytes(b'explicit opaque fake extension; never loaded')
    extension.__loader__ = abi.machinery.ExtensionFileLoader('torch._C', extension.__file__)
    return torch, extension


class RuntimeABITests(unittest.TestCase):
    def test_exact_lock_hash_and_76_unique_versions(self):
        body = (ROOT / 'requirements-linux-py311-cu128-20261002.lock').read_bytes()
        self.assertEqual(len(abi.parse_pins(body)), 76)
        self.assertEqual(abi.normalized('Example._-Name'), 'example-name')
        with self.assertRaisesRegex(abi.RuntimeABIError, 'lock bytes'):
            abi.parse_pins(body + b'\n')

    def test_runtime_binding_preserves_base_prefix_under_S(self):
        with tempfile.TemporaryDirectory() as temp:
            venv, site, spec, _ = runtime_fixture(temp)
            before = (sys.prefix, sys.base_prefix)
            self.assertEqual(abi.runtime_paths(spec), (venv, venv / 'bin/python', site))
            self.assertEqual((sys.prefix, sys.base_prefix), before)
            spec['interpreter_sha256'] = '0' * 64
            with self.assertRaisesRegex(abi.RuntimeABIError, 'interpreter differs'):
                abi.runtime_paths(spec)

    def test_cfg_system_site_and_symlink_ancestor_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            venv, site, spec, _ = runtime_fixture(temp)
            (venv / 'pyvenv.cfg').write_text('include-system-site-packages = true\n')
            spec['pyvenv_cfg_sha256'] = abi.file_sha(venv / 'pyvenv.cfg')
            with self.assertRaisesRegex(abi.RuntimeABIError, 'configuration differs'):
                abi.runtime_paths(spec)
            link = Path(temp) / 'linked'
            link.symlink_to(venv, target_is_directory=True)
            with self.assertRaisesRegex(abi.RuntimeABIError, 'Symlink'):
                abi.regular_path(str(link / 'pyvenv.cfg'))

    def test_metadata76_and_six_positions_before_optional_imports(self):
        with tempfile.TemporaryDirectory() as temp:
            _, site, _, pins = runtime_fixture(temp)
            seen = abi.validate_metadata(abi.metadata_observation(site), pins, site)
            self.assertEqual(len(seen['versions']), 76)
            self.assertEqual(set(seen['package_origins']), set(abi.NAMES))
            self.assertNotIn('torch', sys.modules)
            self.assertTrue(all(Path(p).parent == site for p in seen['metadata_directories'].values()))

    def test_normalized_duplicate_and_extra_metadata_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            _, site, _, pins = runtime_fixture(temp)
            directory = site / 'extra.dist-info'
            directory.mkdir()
            (directory / 'METADATA').write_text('Name: typing_extensions\nVersion: 99\n')
            with self.assertRaisesRegex(abi.RuntimeABIError, 'duplicate'):
                abi.metadata_observation(site)
            (directory / 'METADATA').write_text('Name: extra-fixture\nVersion: 99\n')
            with self.assertRaisesRegex(abi.RuntimeABIError, 'versions differ'):
                abi.validate_metadata(abi.metadata_observation(site), pins, site)

    def test_metadata_version_missing_origin_and_symlink_escape_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            _, site, _, pins = runtime_fixture(temp)
            seen = abi.metadata_observation(site)
            seen['versions']['torch'] = '2.8.0'
            with self.assertRaisesRegex(abi.RuntimeABIError, 'versions differ'):
                abi.validate_metadata(seen, pins, site)
            (site / 'peft/__init__.py').unlink()
            with self.assertRaisesRegex(abi.RuntimeABIError, 'position'):
                abi.metadata_observation(site)
            foreign = Path(temp) / 'outside.py'
            foreign.write_text('raise AssertionError("must not execute")\n')
            (site / 'peft/__init__.py').symlink_to(foreign)
            with self.assertRaisesRegex(abi.RuntimeABIError, 'Symlink'):
                abi.metadata_observation(site)

    def test_manual_site_ignores_pth_customization_and_valid_pyc(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            site = root / 'site'
            site.mkdir()
            sentinel = root / 'ran'
            poison = 'from pathlib import Path; Path(' + repr(str(sentinel)) + ').write_text("bad")\n'
            (site / 'danger.pth').write_text('import sitecustomize\n')
            (site / 'sitecustomize.py').write_text(poison)
            source = site / 'probe.py'
            source.write_text(poison)
            import py_compile
            py_compile.compile(str(source), doraise=True)
            size, stamp = source.stat().st_size, source.stat().st_mtime_ns
            safe = 'value = 17\n'
            source.write_text(safe + '#' * (size - len(safe)))
            os.utime(source, ns=(stamp, stamp))
            code = ('import importlib.util,sys,json; from pathlib import Path; '
                'p=' + repr(str(Path(abi.__file__).resolve())) + '; '
                's=importlib.util.spec_from_file_location("fixture_abi",p); '
                'a=importlib.util.module_from_spec(s); s.loader.exec_module(a); '
                'stdlib=a.clean_startup(); a.select_site(Path(' + repr(str(site)) + '),stdlib); '
                'import probe; print(json.dumps({"value":probe.value,"customized":"sitecustomize" in sys.modules}))')
            result = subprocess.run([sys.executable, '-B', '-I', '-S', '-c', code],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(json.loads(result.stdout), {'value': 17, 'customized': False})
            self.assertFalse(sentinel.exists())

    def test_startup_foreign_path_hook_cache_or_optional_module_rejected(self):
        code = ('import importlib.util; p=' + repr(str(Path(abi.__file__).resolve())) + '; '
            's=importlib.util.spec_from_file_location("fixture_abi",p); '
            'a=importlib.util.module_from_spec(s); s.loader.exec_module(a); a.clean_startup()')
        baseline = subprocess.run([sys.executable, '-B', '-I', '-S', '-c', code],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(baseline.returncode, 0, baseline.stderr.decode())
        for pollution in ('a.sys.path.append("/foreign")', 'a.sys.meta_path.append(object())',
                          'a.sys.modules["torch"]=object()',
                          'a.sys.path_importer_cache["/foreign"]=None'):
            with self.subTest(pollution=pollution):
                child = code.replace('a.clean_startup()', pollution + '; a.clean_startup()')
                result = subprocess.run([sys.executable, '-B', '-I', '-S', '-c', child],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertNotEqual(result.returncode, 0)

    def test_metadata_or_pip_failure_never_imports_Torch(self):
        with tempfile.TemporaryDirectory() as temp:
            _, site, _, pins = runtime_fixture(temp)
            seen = abi.metadata_observation(site)
            torch_import = Mock()
            trace = []
            def pip_failure():
                trace.append('pip')
                raise abi.RuntimeABIError('fixture pipcheck failed')
            with self.assertRaisesRegex(abi.RuntimeABIError, 'fixture pip'):
                abi.checked_CPU_observation(lambda: trace.append('metadata') or seen,
                                            pins, site, pip_failure, torch_import)
            self.assertEqual(trace, ['metadata', 'pip'])
            torch_import.assert_not_called()
            seen['versions']['torch'] = 'wrong'
            pip = Mock()
            with self.assertRaisesRegex(abi.RuntimeABIError, 'versions differ'):
                abi.checked_CPU_observation(lambda: seen, pins, site, pip, torch_import)
            pip.assert_not_called()
            torch_import.assert_not_called()

    def test_allowed_stdlib_cache_key_cannot_point_to_foreign_finder(self):
        with tempfile.TemporaryDirectory() as temp:
            foreign = str(Path(temp).resolve())
            code = ('import importlib.util; p=' + repr(str(Path(abi.__file__).resolve())) + '; '
                's=importlib.util.spec_from_file_location("fixture_abi",p); '
                'a=importlib.util.module_from_spec(s); s.loader.exec_module(a); '
                'key=str(a.Path(a.sysconfig.get_path("stdlib")).resolve()); '
                'a.sys.path_importer_cache[key]=a.machinery.FileFinder(' + repr(foreign) + '); '
                'a.clean_startup()')
            result = subprocess.run([sys.executable, '-B', '-I', '-S', '-c', code],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'Startup FileFinder cache path differs', result.stderr)

    def test_runtime_changes_during_pip_stop_before_Torch(self):
        with tempfile.TemporaryDirectory() as temp:
            _, site, _, pins = runtime_fixture(temp)
            before = abi.metadata_observation(site)
            after = json.loads(json.dumps(before))
            after['metadata_sha256']['torch'] = '0' * 64
            torch_import = Mock()
            with self.assertRaisesRegex(abi.RuntimeABIError, 'changed during pipcheck'):
                abi.checked_CPU_observation(Mock(side_effect=[before, after]), pins, site,
                                            lambda: {'fixture_pipcheck': True}, torch_import)
            torch_import.assert_not_called()

    def test_pip_command_preserves_owned_nonce_and_raw_streams(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            env = abi.cpu_environment(directory, 'a' * 64)
            result = SimpleNamespace(returncode=0, stdout=b'No broken requirements found.\n', stderr=b'')
            def pip_fixture(argv, **kwargs):
                kwargs['stdout'].write(result.stdout)
                kwargs['stderr'].write(result.stderr)
                return result
            with patch.object(abi.subprocess, 'run', side_effect=pip_fixture) as called:
                observed = abi.run_pip_check('/fixture/request.json', 'b' * 64, env, directory)
            argv = called.call_args.args[0]
            self.assertEqual(argv[1:4], ['-B', '-I', '-S'])
            self.assertEqual(called.call_args.kwargs['env'][abi.NONCE_KEY], 'a' * 64)
            self.assertEqual(called.call_args.kwargs['env']['PIP_CONFIG_FILE'], '/dev/null')
            self.assertEqual((directory / 'pip.stdout.log').read_bytes(), result.stdout)
            self.assertEqual(observed['stdout_sha256'], hashlib.sha256(result.stdout).hexdigest())
            self.assertEqual(observed['stdout_bytes'], len(result.stdout))

    def test_environment_discards_credentials_loaders_proxy_and_devices(self):
        with patch.dict(os.environ, {'AWS_SECRET_ACCESS_KEY': 'fixture', 'LD_PRELOAD': '/bad',
                                    'HTTP_PROXY': '/bad', 'PYTHONPATH': '/bad', 'CUDA_VISIBLE_DEVICES': '0'}):
            env = abi.cpu_environment(Path('/fixture/attempt'), 'a' * 64)
        self.assertEqual(env['CUDA_VISIBLE_DEVICES'], '')
        self.assertEqual(env['HF_HUB_OFFLINE'], '1')
        for key in ('AWS_SECRET_ACCESS_KEY', 'LD_PRELOAD', 'HTTP_PROXY', 'PYTHONPATH', 'HOME'):
            self.assertNotIn(key, env)

    def test_pip_failure_preserves_result_code_lengths_hashes_and_raw(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp).resolve()
            outcome = SimpleNamespace(returncode=1, stdout=b'fixture pip output\n', stderr=b'broken requirements\n')
            def pip_fixture(argv, **kwargs):
                kwargs['stdout'].write(outcome.stdout)
                kwargs['stderr'].write(outcome.stderr)
                return outcome
            with patch.object(abi.subprocess, 'run', side_effect=pip_fixture):
                with self.assertRaisesRegex(abi.RuntimeABIError, 'failed before Torch'):
                    abi.run_pip_check('/fixture/request.json', 'b' * 64,
                        abi.cpu_environment(directory, 'a' * 64), directory)
            result = json.loads((directory / 'pip.result.json').read_text())
            self.assertEqual(result['returncode'], 1)
            self.assertEqual(result['stderr_bytes'], len(outcome.stderr))
            self.assertEqual(result['stderr_sha256'], hashlib.sha256(outcome.stderr).hexdigest())
            self.assertEqual((directory / 'pip.stderr.log').read_bytes(), outcome.stderr)

    def test_interrupted_pip_retains_partial_binary_streams_without_result_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp).resolve()
            def interrupted_pip(argv, **kwargs):
                self.assertTrue((directory / 'pip.stdout.log').exists())
                self.assertTrue((directory / 'pip.stderr.log').exists())
                kwargs['stdout'].write(b'partial\x00stdout\n')
                kwargs['stderr'].write(b'partial\xffstderr\n')
                raise RuntimeError('fixture interrupted before return')
            with patch.object(abi.subprocess, 'run', side_effect=interrupted_pip):
                with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                    abi.run_pip_check('/fixture/request.json', 'b' * 64,
                        abi.cpu_environment(directory, 'a' * 64), directory)
            self.assertEqual((directory / 'pip.stdout.log').read_bytes(), b'partial\x00stdout\n')
            self.assertEqual((directory / 'pip.stderr.log').read_bytes(), b'partial\xffstderr\n')
            self.assertFalse((directory / 'pip.result.json').exists())

    def test_fake_CPU_arithmetic_scope_not_real_extension_or_Torch_ABI(self):
        with tempfile.TemporaryDirectory() as temp:
            _, site, _, _ = runtime_fixture(temp)
            torch, extension = fake_torch(site)
            with patch.dict(sys.modules, {'torch': torch, 'torch._C': extension}):
                result = abi.observe_torch(torch, '2.8.0+cu128', site, lambda: [])
            self.assertEqual(result['result'], [[19., 22.], [43., 50.]])
            self.assertFalse(result['requires_grad'])
            self.assertEqual(result['backward_calls'], 0)
            self.assertEqual(torch.cuda.is_initialized.call_count, 2)

    def test_wrong_nonfinite_device_autograd_or_native_origin_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            _, site, _, _ = runtime_fixture(temp)
            for mutation in ('wrong', 'nonfinite', 'device', 'autograd', 'origin'):
                with self.subTest(mutation=mutation):
                    torch, extension = fake_torch(site)
                    if mutation == 'origin':
                        extension.__loader__ = object()
                    else:
                        class ChangedTensor(FakeTensor):
                            def __matmul__(self, other):
                                output = super().__matmul__(other)
                                if mutation == 'wrong': output.values[0][0] = 20.
                                if mutation == 'nonfinite': output.values[0][0] = float('nan')
                                if mutation == 'device': output.device = 'cuda:0'
                                if mutation == 'autograd': output.requires_grad = True
                                return output
                        torch.tensor = ChangedTensor
                    with patch.dict(sys.modules, {'torch': torch, 'torch._C': extension}), self.assertRaises(abi.RuntimeABIError):
                        abi.observe_torch(torch, '2.8.0+cu128', site, lambda: [])

    def test_CUDA_initialized_or_nvidia_fd_is_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            _, site, _, _ = runtime_fixture(temp)
            torch, extension = fake_torch(site)
            torch.cuda.is_initialized.return_value = True
            with patch.dict(sys.modules, {'torch': torch, 'torch._C': extension}), self.assertRaisesRegex(abi.RuntimeABIError, 'CUDA already'):
                abi.observe_torch(torch, '2.8.0+cu128', site, lambda: [])
            fd = Path(temp) / 'fd'
            fd.mkdir()
            (fd / '3').symlink_to('/dev/nvidia0')
            with self.assertRaisesRegex(abi.RuntimeABIError, 'NVIDIA'):
                abi.nvidia_fds(fd)

    def test_request_hash_source_scope_and_budget_rejection(self):
        request = {key: None for key in abi.REQUEST_FIELDS}
        request.update(schema_version=1, scope=abi.SCOPE, nonce='a' * 64,
                       observer_sha256=abi.file_sha(abi.__file__), work_seconds=60, cleanup_seconds=10)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp).resolve() / 'request.json'
            def save(value):
                body = json.dumps(value).encode()
                path.write_bytes(body)
                return abi.digest(body)
            sha = save(request)
            self.assertEqual(abi.read_request(path, sha), request)
            with self.assertRaisesRegex(abi.RuntimeABIError, 'Request bytes'):
                abi.read_request(path, '0' * 64)
            for key, value in [('scope', 'GPU_ready'), ('observer_sha256', '0' * 64),
                               ('nonce', 'old'), ('work_seconds', 61), ('cleanup_seconds', True)]:
                changed = dict(request, **{key: value})
                with self.subTest(key=key), self.assertRaises(abi.RuntimeABIError):
                    abi.read_request(path, save(changed))

    def test_wrong_captured_native_bytes_refused_without_module_execution(self):
        with self.assertRaisesRegex(abi.RuntimeABIError, 'Captured helper'):
            abi.load_captured_module('/fixture/native-copy.py', b'raise AssertionError("never")',
                                     abi.OWNED_SHA, '_fixture_bad_native')
        self.assertNotIn('_fixture_bad_native', sys.modules)

    def test_execute_refuses_before_request_paths_packages_or_attempt(self):
        with (patch.object(abi, 'read_request') as read, patch.object(abi, 'observe_cpu') as observe,
              patch.object(abi, 'package_child') as child):
            with self.assertRaisesRegex(abi.RuntimeABIError, 'Model execution is closed'):
                abi.main(['--execute', '--request', '/missing/old-request'])
            read.assert_not_called()
            observe.assert_not_called()
            child.assert_not_called()

    def test_child_without_fresh_consumed_marker_cannot_import_packages(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            request = {'attempt_directory': str(root), 'nonce': 'a' * 64}
            with self.assertRaises(abi.RuntimeABIError):
                abi.child_authority(request, 'b' * 64)

    def test_consumed_attempt_never_launches_or_imports_native(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            _, _, runtime, _ = runtime_fixture(root)
            attempt = root / 'new-attempt'
            marker = root / 'new-attempt.consumed.json'
            marker.write_text('{}')
            request = {key: None for key in abi.REQUEST_FIELDS}
            request.update(schema_version=1, scope=abi.SCOPE, nonce='a' * 64,
                observer_sha256=abi.file_sha(abi.__file__), work_seconds=60, cleanup_seconds=10,
                bootstrap={'realpath': str(Path(sys.executable).resolve()),
                           'sha256': abi.file_sha(Path(sys.executable).resolve()),
                           'python_version': list(sys.version_info[:3])}, runtime=runtime,
                data_root=str(root / 'data'), attempt_directory=str(attempt),
                source_context={role + '_root': str(root / role) for role in ('scientific', 'native', 'operational')})
            path = root / 'request.json'
            path.write_text(json.dumps(request))
            with (patch.object(abi, 'clean_startup'), patch.object(abi, 'check_host', return_value={}),
                  patch.object(abi, 'load_captured_module') as load):
                with self.assertRaisesRegex(abi.RuntimeABIError, 'Consumed attempt'):
                    abi.observe_cpu(path, abi.file_sha(path))
                load.assert_not_called()
            self.assertFalse(attempt.exists())

    def test_request_mutation_after_worker_stays_consumed_and_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            _, _, runtime, _ = runtime_fixture(root)
            attempt = root / 'new-attempt'
            request = {key: None for key in abi.REQUEST_FIELDS}
            request.update(schema_version=1, scope=abi.SCOPE, nonce='a' * 64,
                observer_sha256=abi.file_sha(abi.__file__), work_seconds=60, cleanup_seconds=10,
                bootstrap={'realpath': str(Path(sys.executable).resolve()),
                           'sha256': abi.file_sha(Path(sys.executable).resolve()),
                           'python_version': list(sys.version_info[:3])}, runtime=runtime,
                data_root=str(root / 'data'), attempt_directory=str(attempt),
                source_context={role + '_root': str(ROOT if role == 'native' else root / role)
                                for role in ('scientific', 'native', 'operational')})
            path = root / 'request.json'
            path.write_text(json.dumps(request))
            expected_request = abi.file_sha(path)
            def fake_owned_worker(argv, *, attempt_directory, **kwargs):
                attempt_directory.mkdir()
                (attempt_directory / 'worker.stdout.log').write_text(json.dumps({
                    'status': 'CPU_runtime_import_arithmetic_observed', 'request_sha256': expected_request,
                    'nonce': request['nonce'], 'process_nonce': 'f' * 64, 'inputs': {}}))
                path.write_text('{}')
                return {'nonce': 'f' * 64, 'scope': 'injected_CPU_lifecycle_fixture_not_process_proof'}
            fake_owned = SimpleNamespace(run_owned_cpu_worker=fake_owned_worker)
            with (patch.object(abi, 'clean_startup'), patch.object(abi, 'check_host', return_value={}),
                  patch.object(abi, 'load_captured_module', return_value=fake_owned),
                  patch.object(abi, 'verify_inputs', return_value=({}, {}))):
                with self.assertRaisesRegex(abi.RuntimeABIError, 'Request bytes differ'):
                    abi.observe_cpu(path, expected_request)
            result = json.loads((attempt / 'receipt.json').read_text())
            self.assertEqual(result['status'], 'CPU_ABI_failed_consumed_no_retry')
            self.assertTrue(attempt.with_name(attempt.name + '.consumed.json').exists())


def captured_fixture(raw):
    return {'base64': base64.b64encode(raw).decode(), 'bytes': len(raw),
            'sha256': transport.sha(raw)}


def gate_fixture(own_source, scope=transport.LAUNCH_REVIEW_SCOPE):
    """Artificial saved receipt inputs, never a live review/CI/integration claim."""
    source, main, tree = 'c' * 40, 'd' * 40, 'e' * 40
    files = {transport.SELF: transport.sha(own_source), transport.OBSERVER: 'b' * 64}
    review = {'schema_version': 1, 'source_commit': source, 'status': 'fixture_review_passed',
              'failed': [], 'files_sha256': files}
    receipts = {'source_review': review, 'prelaunch': dict(review, scope=scope),
        'CI': {'schema_version': 1, 'source_commit': source, 'checks': [
            {'event': event, 'name': 'portable (' + version + ')', 'head_sha': source,
             'status': 'completed', 'conclusion': 'success', 'id': index + 1, 'run_attempt': 1}
            for index, (event, version) in enumerate((event, version)
                for event in ('push', 'pull_request') for version in ('3.10', '3.14'))]},
        'code_integration': {'schema_version': 1, 'source_commit': source, 'main_commit': main,
            'source_tree_sha1': tree, 'main_tree_sha1': tree,
            'source_pushed': True, 'main_integrated': True}}
    return {'source_commit': source, 'main_commit': main, 'source_tree': tree, 'main_tree': tree,
            'transport_sha256': files[transport.SELF], 'observer_sha256': files[transport.OBSERVER],
            'receipts': {name: captured_fixture(transport.json_bytes(body))
                         for name, body in receipts.items()}}


def payload_fixture(own_source):
    """Fake source/data/capture bodies; fixed dummy nonce, no attempt or host run."""
    gates = gate_fixture(own_source)
    capture_gates = gate_fixture(own_source, transport.CAPTURE_REVIEW_SCOPE)
    capture = {'schema_version': 1, 'scope': 'fresh_read_only_host_capture_after_code_integration',
        'gates': capture_gates, 'nonce_generated': False, 'request_consumed': False,
        'host': {'node_alias': 'N1-1', 'hostname': 'fixture-only', 'boot_id': 'fixture-boot', 'uid': os.getuid()},
        'bootstrap': {'realpath': transport.BOOTSTRAP, 'sha256': transport.BOOTSTRAP_SHA,
                      'python_version': [3, 11, 15]},
        'storage': {'path': str(transport.USER_ROOT), 'block_bytes': 4096,
            'available_blocks': 65536, 'available_bytes': 268435456,
            'required_new_scratch_bytes': transport.SCRATCH_BUDGET_BYTES, 'live_disk_reservation': False}}
    data = {f'split-{index}.jsonl': ('fake frozen bytes ' + str(index) + '\n').encode()
            for index in range(13)}
    data['manifest.json'] = b'fake manifest bytes only\n'
    plan = {'data_files_sha256': {name: transport.sha(raw) for name, raw in data.items()
                                 if name.endswith('.jsonl')},
            'data_manifest_sha256': transport.sha(data['manifest.json']),
            'implementation_sha256': {'science.py': '1' * 64}}
    native = {'native_files_sha256': {'native.py': '2' * 64}}
    operational = {'status': 'three_source_CPU_declaration', 'source_commit': gates['source_commit'],
                  'files_sha256': {transport.SELF: transport.sha(own_source),
                                   transport.OBSERVER: gates['observer_sha256']}}
    root = transport.REMOTE_BASE / 'fixture-never-launched'
    context = {role + '_root': str(root / 'sources' / role)
               for role in ('scientific', 'native', 'operational')}
    context.update({key: str(root / name) for key, name in transport.EXTERNAL.items()})
    native_raw, operational_raw = transport.json_bytes(native), transport.json_bytes(operational)
    context.update(expected_operational_commit=gates['source_commit'],
        expected_native_declaration_sha256=transport.sha(native_raw),
        expected_operational_declaration_sha256=transport.sha(operational_raw))
    request = {'schema_version': 1, 'scope': abi.SCOPE, 'nonce': 'a' * 64,
        'source_context': context, 'observer_sha256': gates['observer_sha256'],
        'host': capture['host'], 'bootstrap': capture['bootstrap'],
        'runtime': {'venv': transport.VENV, 'interpreter_realpath': transport.BOOTSTRAP,
            'interpreter_sha256': transport.BOOTSTRAP_SHA, 'pyvenv_cfg_sha256': transport.CFG_SHA,
            'python_version': [3, 11, 15]},
        'data_root': str(root / 'inputs/prepared-data'), 'attempt_directory': str(root / 'attempts/abi-r1'),
        'work_seconds': 60, 'cleanup_seconds': 10}
    bodies = {transport.EXTERNAL['plan']: transport.json_bytes(plan),
        transport.EXTERNAL['freeze']: b'fake frozen external receipt\n',
        transport.EXTERNAL['native_declaration']: native_raw,
        transport.EXTERNAL['operational_declaration']: operational_raw,
        'inputs/external/requirements.lock': b'fake exact lock\n',
        'inputs/external/old-installation-receipt.json': b'fake prior installation receipt\n',
        'helpers/owned-process.py': b'fake immutable helper bytes, never executed\n',
        'inputs/request.json': transport.json_bytes(request),
        'inputs/prepared-data-mapping.json': transport.json_bytes({name: {
            'bytes': len(raw), 'sha256': transport.sha(raw)} for name, raw in data.items()})}
    bodies.update({'inputs/prepared-data/' + name: raw for name, raw in data.items()})
    payload = {'schema_version': 1, 'scope': transport.SCOPE, 'gates': gates,
        'fresh_capture': capture, 'fresh_capture_raw': captured_fixture(transport.json_bytes(capture)),
        'remote_root': str(root), 'nonce': request['nonce'], 'copies': {
            name: captured_fixture(raw) for name, raw in bodies.items()},
        'roots': {'scientific': {'commit': transport.SCIENCE_A, 'files_sha256': plan['implementation_sha256']},
            'native': {'commit': transport.NATIVE_A, 'files_sha256': native['native_files_sha256']},
            'operational': {'commit': gates['source_commit'], 'files_sha256': operational['files_sha256']}}}
    prelaunch = json.loads(transport.decode_copy(gates['receipts']['prelaunch']))
    prelaunch.update(capture_sha256=payload['fresh_capture_raw']['sha256'],
        request_sha256=payload['copies']['inputs/request.json']['sha256'], nonce=payload['nonce'],
        remote_root=str(root), unsigned_payload_sha256=transport.unsigned_payload_sha256(payload))
    gates['receipts']['prelaunch'] = captured_fixture(transport.json_bytes(prelaunch))
    immutable = {key: transport.sha(bodies[name]) for key, name in {
        'PLAN_SHA': transport.EXTERNAL['plan'], 'FREEZE_SHA': transport.EXTERNAL['freeze'],
        'NATIVE_DECL_SHA': transport.EXTERNAL['native_declaration'],
        'LOCK_SHA': 'inputs/external/requirements.lock',
        'INSTALL_RECEIPT_SHA': 'inputs/external/old-installation-receipt.json',
        'NATIVE_HELPER_SHA256': 'helpers/owned-process.py'}.items()}
    return payload, immutable


class RuntimeTransportTests(unittest.TestCase):
    def setUp(self):
        self.source = Path(transport.__file__).read_bytes()

    def test_raw_receipts_reject_stale_CI_head_tree_or_source_despite_valid_hash(self):
        self.assertEqual(set(transport.validate_gates(gate_fixture(self.source), self.source)),
                         set(transport.GATE_RECEIPTS))
        for name, mutation in [('CI', lambda receipt: receipt['checks'][0].update(head_sha='f' * 40)),
            ('source_review', lambda receipt: receipt['files_sha256'].update({transport.OBSERVER: 'f' * 64}))]:
            with self.subTest(name=name):
                gates = gate_fixture(self.source)
                receipt = json.loads(transport.decode_copy(gates['receipts'][name]))
                mutation(receipt)
                gates['receipts'][name] = captured_fixture(transport.json_bytes(receipt))
                with self.assertRaises(transport.TransportError):
                    transport.validate_gates(gates, self.source)
        gates = gate_fixture(self.source)
        gates['main_tree'] = 'f' * 40
        with self.assertRaisesRegex(transport.TransportError, 'tree'):
            transport.validate_gates(gates, self.source)

    def test_capture_only_prelaunch_does_not_authorize_launch(self):
        gates = gate_fixture(self.source, transport.CAPTURE_REVIEW_SCOPE)
        transport.validate_gates(gates, self.source, prelaunch_scope=transport.CAPTURE_REVIEW_SCOPE)
        with self.assertRaisesRegex(transport.TransportError, 'scope'):
            transport.validate_gates(gates, self.source)

    def test_payload_requires_original_capture_and_unchanged_prior_receipts(self):
        payload, immutable = payload_fixture(self.source)
        with patch.multiple(transport, **immutable):
            raw, request = transport.validate_payload(payload, self.source)
            self.assertEqual(len([name for name in raw if name.endswith('.jsonl')]), 13)
            self.assertEqual(request['work_seconds'], 60)
            original = payload['fresh_capture_raw']
            payload['fresh_capture_raw'] = captured_fixture(b'{}')
            with self.assertRaisesRegex(transport.TransportError, 'capture bytes'):
                transport.validate_payload(payload, self.source)
            payload['fresh_capture_raw'] = original
            receipt = transport.decode_copy(payload['gates']['receipts']['source_review'])
            payload['gates']['receipts']['source_review'] = captured_fixture(receipt + b'\n')
            with self.assertRaisesRegex(transport.TransportError, 'may change'):
                transport.validate_payload(payload, self.source)

    def test_final_prelaunch_binds_unsigned_dynamic_payload_and_copied_bytes(self):
        payload, immutable = payload_fixture(self.source)
        with patch.multiple(transport, **immutable):
            receipt = json.loads(transport.decode_copy(payload['gates']['receipts']['prelaunch']))
            receipt['unsigned_payload_sha256'] = '0' * 64
            payload['gates']['receipts']['prelaunch'] = captured_fixture(transport.json_bytes(receipt))
            with self.assertRaisesRegex(transport.TransportError, 'unsigned payload'):
                transport.validate_payload(payload, self.source)
            payload['copies']['inputs/prepared-data/split-0.jsonl'] = captured_fixture(b'changed fake data\n')
            with self.assertRaisesRegex(transport.TransportError, 'copy hash'):
                transport.validate_payload(payload, self.source)

    def test_capture_storage_arithmetic_and_budget_must_match(self):
        payload, immutable = payload_fixture(self.source)
        with patch.multiple(transport, **immutable):
            payload['fresh_capture']['storage']['available_bytes'] -= 1
            payload['fresh_capture_raw'] = captured_fixture(transport.json_bytes(payload['fresh_capture']))
            with self.assertRaisesRegex(transport.TransportError, 'scratch capacity'):
                transport.validate_payload(payload, self.source)

    def test_exact_file_negative_cache_only_and_positive_entry_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp).resolve() / 'transport.py'
            source.write_bytes(self.source)
            key, foreign = str(source), '/fixture-foreign-cache'
            with patch.object(transport, '__file__', key), patch.dict(sys.path_importer_cache, {key: None, foreign: None}):
                proof = transport.normalize_transport_file_cache(self.source)
                self.assertTrue(proof['removed_authenticated_transport_file_negative_cache'])
                self.assertNotIn(key, sys.path_importer_cache)
                self.assertIn(foreign, sys.path_importer_cache)
                sys.path_importer_cache[key] = object()
                with self.assertRaisesRegex(transport.TransportError, 'Positive'):
                    transport.normalize_transport_file_cache(self.source)
            with patch.object(transport, '__file__', key):
                with self.assertRaisesRegex(transport.TransportError, 'source changed'):
                    transport.normalize_transport_file_cache(self.source + b'changed')

    def test_parent_shell_command_preserves_exact_source_as_one_quoted_argument(self):
        raw = b'print("quotes and $HOME and `literal` and \'single\'")\nprint(2)\n'
        command = transport.remote_command(raw, '--capture-host', 'a' * 64)
        args = shlex.split(command)
        self.assertEqual(args[:4], ['/bin/sh', '-c', transport.USER_PARENT_LAUNCHER,
                                    'frontier-v8-user-parent'])
        self.assertEqual(args[4:], [transport.BOOTSTRAP, '-B', '-I', '-S', '-c', raw.decode(),
                                   '--capture-host', '--expected-payload-sha256', 'a' * 64])
        self.assertIn('exit', args[2])
        with self.assertRaises(transport.TransportError):
            transport.remote_command(raw, '--execute', 'a' * 64)

    def test_raw_binary_retrieval_retains_missing_symlink_FIFO_and_directory_refusals(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            raw = b'\x00\xfforiginal binary\r\n'
            (root / 'binary.log').write_bytes(raw)
            (root / 'link.log').symlink_to(root / 'binary.log')
            os.mkfifo(root / 'fifo.log')
            (root / 'directory.log').mkdir()
            names = ['binary.log', 'missing.log', 'link.log', 'fifo.log', 'directory.log']
            packet = transport.collect(str(root), names, os.getuid())
            self.assertEqual(base64.b64decode(packet['files']['binary.log']['base64']), raw)
            self.assertEqual(packet['missing'], ['missing.log'])
            self.assertEqual(set(packet['refused']), {'link.log', 'fifo.log', 'directory.log'})
            self.assertFalse(packet['observer_or_worker_rerun'])
            self.assertFalse(packet['observation_success_claimed'])
            with self.assertRaisesRegex(ValueError, 'owner'):
                transport.read_regular(root, 'binary.log', os.getuid() + 1)

    def test_receive_validates_tampered_hash_owner_and_partition_before_directory_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            remote = root / 'remote'
            remote.mkdir()
            (remote / 'raw.log').write_bytes(b'\x00raw\xff')
            packet = transport.collect(str(remote), ['raw.log'], os.getuid())
            destination = root / 'not-created'
            for mutation in (lambda value: value['files']['raw.log'].update(sha256='0' * 64),
                lambda value: value['files']['raw.log'].update(uid=os.getuid() + 1),
                lambda value: value['missing'].append('raw.log')):
                changed = json.loads(json.dumps(packet))
                mutation(changed)
                with self.assertRaises(ValueError):
                    transport.receive(changed, str(destination), str(remote), ['raw.log'], os.getuid())
                self.assertFalse(destination.exists())

    def test_receive_exclusive_exact_raw_copy_and_context_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            remote = root / 'remote'
            remote.mkdir()
            raw = b'\x00original\xff\n'
            (remote / 'raw.log').write_bytes(raw)
            packet = transport.collect(str(remote), ['raw.log', 'missing.log'], os.getuid())
            destination = root / 'new-local'
            receipt = transport.receive(packet, str(destination), str(remote), packet['allowlist'], os.getuid())
            self.assertEqual((destination / 'raw.log').read_bytes(), raw)
            self.assertEqual(receipt['missing'], ['missing.log'])
            self.assertFalse(receipt['success_observation_claimed'])
            with self.assertRaises(FileExistsError):
                transport.receive(packet, str(destination), str(remote), packet['allowlist'], os.getuid())
            with self.assertRaisesRegex(ValueError, 'context'):
                transport.receive(packet, str(root / 'other'), '/different-root', packet['allowlist'], os.getuid())
            self.assertFalse((root / 'other').exists())

    def test_exact_allowlist_contains_pip_raw_result_and_both_separate_owned_guards(self):
        payload, _ = payload_fixture(self.source)
        names = transport.exact_allowlist(payload)
        self.assertEqual(names, sorted(set(names)))
        for name in ('pip.stdout.log', 'pip.stderr.log', 'pip.result.json'):
            self.assertIn('attempts/abi-r1/' + name, names)
        for prefix in ('source-preparation/process-r1', 'attempts/abi-r1/process-r1'):
            for name in transport.PROCESS_FILES:
                self.assertIn(prefix + '/' + name, names)
        self.assertIn('inputs/fresh-host-capture.json', names)
        self.assertIn('sources/operational/' + transport.SELF, names)
        self.assertNotIn('arbitrary-private-file', names)

    def test_source_preparation_mocked_three_roots_config_hash_refusal_and_raw_failure(self):
        """Direct helper exercise: mocked Git, no clone/network/owned process claim."""
        for outcome in ('success', 'wrong_hash', 'Git_failure'):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as temp:
                root = Path(temp).resolve()
                process = root / 'source-preparation/process-r1'
                process.mkdir(parents=True)
                if outcome == 'success':
                    original_lstat = Path.lstat
                    def foreign_parent_lstat(path):
                        actual = original_lstat(path)
                        if path == root.parent:
                            return SimpleNamespace(st_mode=actual.st_mode,
                                st_uid=0 if os.getuid() else 1)
                        return actual
                    with patch.object(Path, 'lstat', new=foreign_parent_lstat):
                        with self.assertRaisesRegex(ValueError, 'directory owner differs'):
                            transport._owned_directory(root, owner_start=root.parent)
                bodies = {role: ('fake ' + role + ' source\n').encode()
                          for role in ('scientific', 'native', 'operational')}
                roots = {role: {'commit': str(index + 1) * 40,
                    'files_sha256': {'source.py': transport.sha(raw)}}
                    for index, (role, raw) in enumerate(bodies.items())}
                if outcome == 'wrong_hash':
                    roots['scientific']['files_sha256']['source.py'] = '0' * 64
                spec = {'public_url': transport.PUBLIC_URL, 'roots': roots,
                    'remote_root': str(root), 'source_preparation_directory': str(process),
                    'native_helper_sha256': transport.NATIVE_HELPER_SHA256}
                calls = []
                def fake_git(argv, **kwargs):
                    calls.append((argv, kwargs))
                    index = argv.index('-C')
                    where, args = Path(argv[index + 1]), argv[index + 2:]
                    stdout, stderr, code = b'fake Git diagnostic\n', b'', 0
                    if args[:2] == ['worktree', 'add']:
                        destination = Path(args[-2])
                        destination.mkdir(parents=True)
                        (destination / 'source.py').write_bytes(bodies[destination.name])
                    elif args == ['rev-parse', '--show-toplevel']:
                        stdout = (str(where) + '\n').encode()
                    elif args == ['rev-parse', 'HEAD']:
                        stdout = (roots[where.name]['commit'] + '\n').encode()
                    elif args[0] == 'status':
                        stdout = b''
                    elif args[0] == 'show':
                        stdout = bodies[where.name]
                    elif args[0] == 'fetch' and outcome == 'Git_failure':
                        stdout, stderr, code = b'partial fetch\x00\n', b'original failure\xff\n', 128
                    kwargs['stdout'].write(stdout)
                    kwargs['stdout'].flush()
                    kwargs['stderr'].write(stderr)
                    kwargs['stderr'].flush()
                    return SimpleNamespace(returncode=code)
                old_fstat, old_lseek = os.fstat, os.lseek
                with (process / 'worker.stdout.log').open('w+') as out, (process / 'worker.stderr.log').open('w+') as err:
                    descriptors = {1: out.fileno(), 2: err.fileno()}
                    with (patch.object(transport, 'USER_ROOT', root),
                        patch.dict(os.environ, {transport.NONCE_KEY: 'a' * 64, 'SECRET_FIXTURE': 'never inherited'}),
                        patch.object(transport.subprocess, 'run', side_effect=fake_git),
                        patch.object(transport.os, 'fstat', side_effect=lambda fd: old_fstat(descriptors.get(fd, fd))),
                        patch.object(transport.os, 'lseek', side_effect=lambda fd, offset, mode:
                            old_lseek(descriptors.get(fd, fd), offset, mode)),
                        redirect_stdout(out), redirect_stderr(err)):
                        declaration = {'nonce': 'a' * 64, 'scope': 'fresh_owned_CPU_worker_only'}
                        if outcome == 'success':
                            result = transport.prepare_source_roots(spec, declaration)
                        else:
                            with self.assertRaisesRegex(ValueError, 'byte/blob/hash' if outcome == 'wrong_hash' else 'Git source preparation failed'):
                                transport.prepare_source_roots(spec, declaration)
                self.assertTrue(calls)
                self.assertTrue(all(argv[1:len(transport.GIT_OPTIONS) + 1] == transport.GIT_OPTIONS
                                    for argv, _ in calls))
                for _, kwargs in calls:
                    self.assertNotIn('SECRET_FIXTURE', kwargs['env'])
                    self.assertEqual(kwargs['env']['GIT_CONFIG_GLOBAL'], '/dev/null')
                    self.assertEqual(kwargs['env']['CUDA_VISIBLE_DEVICES'], '')
                    self.assertEqual(kwargs['env'][transport.NONCE_KEY], 'a' * 64)
                if outcome == 'success':
                    self.assertTrue(result['final_clean_three_Git_roots_created'])
                    self.assertFalse(result['GPU_or_model_or_queue_authority'])
                    self.assertEqual(set((root / 'sources').iterdir()),
                                     {root / 'sources' / role for role in bodies})
                    self.assertEqual(len([argv for argv, _ in calls if 'sparse-checkout' in argv]), 6)
                    fetch = next(argv for argv, _ in calls if 'fetch' in argv)
                    self.assertIn('--filter=blob:none', fetch)
                    self.assertTrue(any(argv[-3:] == ['config', 'remote.origin.promisor', 'false'] for argv, _ in calls))
                    for command in result['commands']:
                        start, end = command['stdout_log_byte_range']
                        raw = (process / 'worker.stdout.log').read_bytes()[start:end]
                        self.assertEqual(transport.sha(raw), command['stdout_sha256'])
                elif outcome == 'Git_failure':
                    self.assertIn(b'partial fetch\x00\n', (process / 'worker.stdout.log').read_bytes())
                    self.assertEqual((process / 'worker.stderr.log').read_bytes(), b'original failure\xff\n')

    def test_execute_refuses_before_reading_payload_or_launching(self):
        with patch.object(transport, '_regular_bytes') as read, patch.object(transport, 'launch') as launch:
            with self.assertRaisesRegex(transport.TransportError, 'Model execution is closed'):
                transport.main(['--execute', '--payload', '/missing/old-payload'])
            read.assert_not_called()
            launch.assert_not_called()

    def test_matching_source_worker_JSON_nonce_without_live_guard_is_refused(self):
        from dataclasses import make_dataclass
        fields = ('pid', 'ppid', 'uid', 'boot_id', 'start_ticks', 'pgrp', 'session')
        Identity = make_dataclass('FixtureIdentity', fields)
        controller = dict(zip(fields, (100, 50, os.getuid(), 'fixture-boot', 1, 100, 100)))
        worker = Identity(os.getpid(), 200, os.getuid(), 'fixture-boot', 3, os.getpid(), os.getpid())
        guard = Identity(200, 999, os.getuid(), 'fixture-boot', 2, 200, 200)
        identities = {100: Identity(**controller), os.getpid(): worker, 200: guard}
        native = SimpleNamespace(capture_identity=lambda pid: identities[pid])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            helper = root / 'helpers/owned-process.py'
            helper.parent.mkdir()
            helper.write_bytes((ROOT / 'scripts/frontier_v8_owned_process.py').read_bytes())
            helper.chmod(0o400)
            declaration = {'scope': 'fresh_owned_CPU_worker_only', 'nonce': 'a' * 64,
                'source_sha256': transport.NATIVE_HELPER_SHA256, 'cleanup_seconds': 10,
                'deadline_monotonic': 150, 'controller': controller}
            with (patch.dict(os.environ, {transport.NONCE_KEY: 'a' * 64}),
                patch.object(transport.time, 'monotonic', return_value=100),
                patch.object(transport, 'captured_module', return_value=native)):
                with self.assertRaisesRegex(transport.TransportError, 'ancestry differs'):
                    transport.assert_source_child_owned(root, declaration)

    def test_retrieval_uses_reviewed_payload_when_declaration_missing_corrupt_or_boot_changed(self):
        """Injected collection/host facts; no SSH, proc read or actual retrieval run."""
        payload, immutable = payload_fixture(self.source)
        allowlist = transport.exact_allowlist(payload)
        for declaration in (None, {'sha256': '0' * 64}):
            with self.subTest(declaration_present=declaration is not None):
                packet = {'files': {} if declaration is None else {'declaration.json': declaration},
                          'missing': ['declaration.json'] if declaration is None else []}
                wrapper = {'schema_version': 1, 'scope': transport.SCOPE,
                    'transport_payload': captured_fixture(transport.json_bytes(payload)),
                    'expected_declaration_sha256': 'f' * 64}
                raw = transport.json_bytes(wrapper)
                output = io.StringIO()
                flags = SimpleNamespace(flags=SimpleNamespace(isolated=1, no_site=1), dont_write_bytecode=True)
                with (patch.multiple(transport, **immutable), patch.object(transport, 'sys', flags),
                    patch.object(transport, '_regular_bytes', return_value=raw),
                    patch.object(transport, 'own_source_bytes', return_value=self.source),
                    patch.object(transport.platform, 'node', return_value='fixture-only'),
                    patch.object(Path, 'read_text', return_value='different-current-boot\n'),
                    patch.object(transport, 'collect_artifacts', return_value=packet) as collect,
                    redirect_stdout(output)):
                    self.assertEqual(transport.main(['--retrieve', '--payload', '/fixture/input.json',
                        '--expected-payload-sha256', transport.sha(raw)]), 0)
                self.assertEqual(collect.call_args.args, (Path(payload['remote_root']), allowlist, os.getuid()))
                result = json.loads(output.getvalue())
                self.assertFalse(result['launch_boot_unchanged'])
                self.assertEqual(result['declaration_original_hash_matches'], False if declaration else None)
                self.assertEqual(result['original_transport_payload_sha256'],
                                 wrapper['transport_payload']['sha256'])


LIVE_PIDFD = sys.platform == 'linux' and hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal')


@unittest.skipUnless(LIVE_PIDFD, 'fresh Linux pidfd kernel required; portable fixtures remain active')
class RuntimeABILinuxTests(unittest.TestCase):
    def test_live_owned_CPU_fake_metadata_fixture_and_quiescence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            _, site, _, _ = runtime_fixture(root)
            source = (ROOT / 'scripts/frontier_v8_owned_process.py').read_bytes()
            copy = root / 'native-copy.py'
            copy.write_bytes(source)
            copy.chmod(0o400)
            owned = abi.load_captured_module(copy, source, abi.OWNED_SHA, '_fixture_owned_ABI_metadata')
            code = ('import importlib.util,json; from pathlib import Path; p=' + repr(str(Path(abi.__file__).resolve())) + '; '
                's=importlib.util.spec_from_file_location("fixture_abi",p); a=importlib.util.module_from_spec(s); s.loader.exec_module(a); '
                'stdlib=a.clean_startup(); site=Path(' + repr(str(site)) + '); a.select_site(site,stdlib); '
                'pins=a.parse_pins(Path(' + repr(str(ROOT / 'requirements-linux-py311-cu128-20261002.lock')) + ').read_bytes()); '
                'obs=a.validate_metadata(a.metadata_observation(site),pins,site); '
                'print(json.dumps({"scope":"fake76_metadata_owned_CPU_fixture_not_ABI","count":len(obs["versions"]),"Torch_imported":False}))')
            try:
                proof = owned.run_owned_cpu_worker([sys.executable, '-B', '-I', '-S', '-c', code],
                    attempt_directory=root / 'fresh-process', timeout_seconds=10, cleanup_seconds=5)
            finally:
                sys.modules.pop('_fixture_owned_ABI_metadata', None)
            self.assertEqual(json.loads((root / 'fresh-process/worker.stdout.log').read_bytes())['count'], 76)
            self.assertEqual(proof['status'], 'owned_cpu_worker_complete')
            self.assertTrue(proof['quiescence']['members'])
            self.assertTrue(all(x['pidfd_exit_observed'] for x in proof['quiescence']['members']))


if __name__ == '__main__':
    unittest.main()
