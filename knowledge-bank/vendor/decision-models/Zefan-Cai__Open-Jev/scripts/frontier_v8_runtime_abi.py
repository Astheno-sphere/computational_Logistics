"""One separately declared, owned Linux CPU runtime observation; no model CLI.

The existing venv is read-only input. Metadata, positions and pipcheck precede
Torch. Explicit CPU arithmetic and endpoint observations do not prove CUDA ABI,
absence of transient native device access, a sandbox or resource authority.
"""
import argparse
from contextlib import contextmanager
import hashlib
from importlib import machinery, metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import stat
import subprocess
import sys
import sysconfig
import time
from types import FunctionType, ModuleType
import zipimport


LOCK_SHA = 'd1f238a916dfdfbc8b89f3de4c28bb3b7220cdd97ecf609ebb726afab0ca8221'
LOADER_SHA = '6f33f86c9b37bd69612e7d0e79772b23c27540cae7a4191526fc47dbf75e2ede'
OWNED_SHA = '2d9edb599d48aa2c9e1e5971ce95ae833022622a9de3c8d1a1ca81f0f70debc2'
SCOPE = 'frontier_v8_runtime_CPU_ABI_only'
NONCE_KEY = 'FRONTIER_V8_PROCESS_NONCE'
NAMES = ('torch', 'transformers', 'peft', 'triton', 'safetensors', 'accelerate')
NODES = ('N1-1', 'N1-3', 'N4-1', 'N4-2', 'N4-3', 'N4-4')
REQUEST_FIELDS = {'schema_version', 'scope', 'nonce', 'source_context', 'observer_sha256',
    'host', 'bootstrap', 'runtime', 'data_root', 'attempt_directory', 'work_seconds', 'cleanup_seconds'}
SOURCE_PREFLIGHT_SECONDS = 30


class RuntimeABIError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise RuntimeABIError(message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def _identity_tuple(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def regular_path(value, *, directory=False):
    require(isinstance(value, str) and '\0' not in value, 'Actual path required')
    path = Path(value)
    require(path.is_absolute() and path.as_posix() == value and '..' not in path.parts,
            'Normalized absolute path required')
    for part in (path, *path.parents):
        require(not part.is_symlink(), 'Symlink input or ancestor rejected')
    require(path.is_dir() if directory else path.is_file(), 'Regular input required')
    return path


def captured_bytes(value):
    path = regular_path(str(value))
    before = _identity_tuple(path.stat())
    with path.open('rb') as handle:
        require(_identity_tuple(os.fstat(handle.fileno())) == before, 'Input replaced before read')
        body = handle.read()
        require(_identity_tuple(os.fstat(handle.fileno())) == before, 'Input changed during read')
    require(_identity_tuple(path.stat()) == before, 'Input replaced after read')
    return body, before


def file_sha(path):
    return digest(captured_bytes(path)[0])


def write_once(path, value):
    with Path(path).open('x') as handle:
        handle.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def normalized(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def parse_pins(body):
    require(digest(body) == LOCK_SHA, 'Frozen 76-version lock bytes differ')
    result = {}
    for line in body.decode().splitlines():
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([^\s;]+)', line)
        require(match is not None and normalized(match[1]) not in result, 'Exact unique pins required')
        result[normalized(match[1])] = match[2]
    require(len(result) == 76 and result['torch'] == '2.8.0+cu128', 'Frozen 76-version set required')
    return result


def clean_startup():
    require(sys.flags.isolated == sys.flags.no_site == 1 and sys.dont_write_bytecode,
            'Fresh observer and package children require -B -I -S')
    stdlib = Path(sysconfig.get_path('stdlib')).resolve()
    paths = {str(stdlib), str(stdlib / 'lib-dynload'),
             str(stdlib.parent / ('python%d%d.zip' % sys.version_info[:2]))}
    require(all(type(path) is str and path in paths for path in sys.path), 'Foreign startup sys.path')
    require(not any(name in ('sitecustomize', 'usercustomize')
                    or name.split('.')[0] in (*NAMES, 'numpy', 'pip') for name in sys.modules),
            'Preloaded optional package or customization rejected')
    require(sys.meta_path == [machinery.BuiltinImporter, machinery.FrozenImporter, machinery.PathFinder],
            'Foreign startup meta finder')
    require(len(sys.path_hooks) == 2 and sys.path_hooks[0] is zipimport.zipimporter,
            'Foreign startup path hook')
    hook = sys.path_hooks[1]
    require(isinstance(hook, FunctionType) and hook.__code__ is machinery.FileFinder.path_hook().__code__
            and hook.__closure__ is not None and len(hook.__closure__) == 2
            and hook.__closure__[0].cell_contents is machinery.FileFinder, 'Foreign startup path hook')
    details = hook.__closure__[1].cell_contents
    allowed = {machinery.SourceFileLoader: machinery.SOURCE_SUFFIXES,
               machinery.SourcelessFileLoader: machinery.BYTECODE_SUFFIXES,
               machinery.ExtensionFileLoader: machinery.EXTENSION_SUFFIXES}
    require(len(details) == 3 and {loader for loader, _ in details} == set(allowed)
            and all(suffixes == allowed[loader] for loader, suffixes in details), 'Foreign startup hook loader')
    for path, finder in sys.path_importer_cache.items():
        if path == str(Path(__file__).resolve()) and finder is None:
            continue  # CPython file entry's negative cache, never a package path.
        require(path in paths or Path(path).is_relative_to(stdlib), 'Foreign startup importer cache')
        require(finder is None or type(finder) in (machinery.FileFinder, zipimport.zipimporter),
                'Foreign startup cache object')
        if type(finder) is machinery.FileFinder:
            require(finder.path == path, 'Startup FileFinder cache path differs')
            expected_loaders = {(suffix, loader) for loader, suffixes in allowed.items() for suffix in suffixes}
            require(type(finder._loaders) is list and len(finder._loaders) == len(expected_loaders)
                    and set(finder._loaders) == expected_loaders, 'Foreign startup cache loader')
        elif type(finder) is zipimport.zipimporter:
            require(finder.archive in paths and not Path(finder.prefix).is_absolute()
                    and '..' not in Path(finder.prefix).parts
                    and str(Path(finder.archive) / finder.prefix) == path,
                    'Startup zip archive/prefix cache binding differs')
    return stdlib


def load_captured_module(path, body, expected, alias):
    require(digest(body) == expected and alias not in sys.modules, 'Captured helper identity differs')
    module = ModuleType(alias)
    module.__file__ = str(path)
    module.__package__ = ''
    sys.modules[alias] = module  # dataclasses resolves its executing module.
    try:
        exec(compile(body, str(path), 'exec', dont_inherit=True), module.__dict__)
    except BaseException:
        sys.modules.pop(alias, None)
        raise
    return module


def read_request(path, expected):
    require(re.fullmatch(r'[0-9a-f]{64}', expected or '') is not None, 'Explicit request hash required')
    body, _ = captured_bytes(path)
    require(digest(body) == expected, 'Request bytes differ')
    request = json.loads(body)
    require(isinstance(request, dict) and set(request) == REQUEST_FIELDS
            and request['schema_version'] == 1 and request['scope'] == SCOPE,
            'Exact separate CPU ABI declaration required')
    require(re.fullmatch(r'[0-9a-f]{64}', request['nonce']) is not None, 'Fresh declaration nonce required')
    require(request['observer_sha256'] == file_sha(__file__), 'Observer source differs from request')
    for field, maximum in (('work_seconds', 60), ('cleanup_seconds', 10)):
        value = request[field]
        require(not isinstance(value, bool) and isinstance(value, (float, int))
                and math.isfinite(value) and 0 < value <= maximum, 'CPU budget differs')
    return request


def runtime_paths(spec):
    require(set(spec) == {'venv', 'interpreter_realpath', 'interpreter_sha256',
                         'pyvenv_cfg_sha256', 'python_version'}, 'Exact runtime binding required')
    venv = regular_path(spec['venv'], directory=True)
    require(venv.stat().st_uid == os.getuid(), 'Runtime owner differs')
    cfg = captured_bytes(venv / 'pyvenv.cfg')[0]
    require(digest(cfg) == spec['pyvenv_cfg_sha256']
            and re.search(rb'^include-system-site-packages\s*=\s*false\s*$', cfg, re.M),
            'Declared isolated venv configuration differs')
    python = venv / 'bin/python'
    require(python.parent.is_dir() and not python.parent.is_symlink()
            and str(python.resolve()) == spec['interpreter_realpath']
            and file_sha(python.resolve()) == spec['interpreter_sha256'], 'Runtime interpreter differs')
    require(type(spec['python_version']) is list and len(spec['python_version']) == 3
            and spec['python_version'][:2] == [3, 11], 'Declared Linux runtime is Python 3.11')
    site = regular_path(str(venv / 'lib/python3.11/site-packages'), directory=True)
    return venv, python, site


def process_identity(pid):
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    require(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', boot) is not None, 'Kernel boot identity invalid')
    stat_row = Path('/proc/%d/stat' % pid).read_text()
    opening, closing = stat_row.find('('), stat_row.rfind(')')
    require(opening > 0 and int(stat_row[:opening]) == pid and closing > opening, 'Kernel PID identity invalid')
    fields = stat_row[closing + 1:].split()
    require(len(fields) >= 20, 'Kernel process identity truncated')
    uid_rows = [x for x in Path('/proc/%d/status' % pid).read_text().splitlines() if x.startswith('Uid:')]
    require(len(uid_rows) == 1, 'Kernel UID missing')
    uids = [int(x) for x in uid_rows[0].split()[1:]]
    require(len(uids) == 4 and len(set(uids)) == 1, 'Changed process privileges')
    return {'boot_id': boot, 'pid': pid, 'uid': uids[0], 'start_ticks': int(fields[19]),
            'ppid': int(fields[1]), 'pgrp': int(fields[2]), 'session': int(fields[3])}


def check_host(request):
    require(sys.platform == 'linux' and platform.machine() == 'x86_64', 'Linux x86_64 observer required')
    identity = process_identity(os.getpid())
    host = request['host']
    require(set(host) == {'node_alias', 'hostname', 'boot_id', 'uid'} and host['node_alias'] in NODES
            and host['hostname'] == platform.node() and host['boot_id'] == identity['boot_id']
            and type(host['uid']) is int and host['uid'] == identity['uid'] == os.getuid() == os.geteuid(),
            'Fresh declared host identity differs')
    return identity


def verify_inputs(request):
    context = request['source_context']
    root = regular_path(context['operational_root'], directory=True)
    loader_path = root / 'scripts/frontier_v8_source_loader.py'
    body = captured_bytes(loader_path)[0]
    loader = load_captured_module(loader_path, body, LOADER_SHA, '_frontier_abi_source_verifier')
    try:
        source_receipt, sources, _ = loader._verified(context)
    finally:
        sys.modules.pop('_frontier_abi_source_verifier', None)
    require(root / 'scripts/frontier_v8_runtime_abi.py' == Path(__file__).resolve()
            and sources['operational']['scripts/frontier_v8_runtime_abi.py'] == captured_bytes(__file__)[0],
            'Observer is outside its verified operational closure')
    plan = json.loads(captured_bytes(context['plan'])[0])
    lock = sources['scientific']['requirements-linux-py311-cu128-20261002.lock']
    pins = parse_pins(lock)
    data_root = regular_path(request['data_root'], directory=True)
    expected = {**plan['data_files_sha256'], 'manifest.json': plan['data_manifest_sha256']}
    seen = {}
    for name, expected_sha in expected.items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'Unsafe frozen data filename')
        seen[name] = file_sha(data_root / name)
        require(seen[name] == expected_sha, 'Frozen prepared data bytes differ: ' + name)
    return {'three_source_verification': source_receipt, 'data_sha256': seen,
            'lock_sha256': digest(lock)}, pins


class CapturedSourceLoader(machinery.SourceFileLoader):
    """Always compile current captured source; never read a timestamp/hash pyc."""
    def get_code(self, fullname):
        body, _ = captured_bytes(self.path)
        return compile(body, self.path, 'exec', dont_inherit=True)


def select_site(site, stdlib):
    # FileFinder hooks replace SourceFileLoader for all newly imported .py files.
    # Existing interpreter/stdlib/builtin modules remain trusted inputs.
    sys.path[:] = [str(stdlib), str(stdlib / 'lib-dynload'), str(site)]
    sys.path_hooks[:] = [machinery.FileFinder.path_hook(
        (CapturedSourceLoader, machinery.SOURCE_SUFFIXES),
        (machinery.ExtensionFileLoader, machinery.EXTENSION_SUFFIXES))]
    sys.path_importer_cache.clear()


def metadata_observation(site):
    versions, roots, directories, metadata_hashes = {}, {}, {}, {}
    for distribution in metadata.distributions(path=[str(site)]):
        name = normalized(distribution.metadata['Name'])
        require(name not in versions, 'Normalized duplicate distribution')
        directory = regular_path(str(Path(distribution._path)), directory=True)
        require(directory.parent == site and directory.name.endswith('.dist-info'), 'Distribution metadata escaped site')
        location = Path(distribution.locate_file('')).resolve()
        require(location == site, 'Distribution package root escaped site')
        versions[name], roots[name], directories[name] = distribution.version, str(location), str(directory)
        metadata_hashes[name] = file_sha(directory / 'METADATA')
    origins = {}
    for name in NAMES:
        spec = machinery.PathFinder.find_spec(name, [str(site)])
        require(spec is not None and spec.origin is not None, 'Missing top-level package position')
        origin = regular_path(spec.origin)
        require(origin.is_relative_to(site), 'Package position escaped validated site')
        origins[name] = {'path': str(origin), 'sha256': file_sha(origin)}
    require(not any(name == 'torch' or name.startswith('torch.') for name in sys.modules),
            'Torch imported before metadata validation')
    return {'versions': versions, 'distribution_roots': roots, 'metadata_directories': directories,
            'metadata_sha256': metadata_hashes, 'package_origins': origins}


def validate_metadata(observation, expected, site):
    require(observation['versions'] == expected and set(observation['distribution_roots']) == set(expected)
            and set(observation['metadata_directories']) == set(expected), 'Exact 76 runtime versions differ')
    require(set(observation['package_origins']) == set(NAMES), 'Six package origins required')
    for value in observation['distribution_roots'].values():
        require(Path(value) == site, 'Distribution root escaped validated site')
    for value in observation['metadata_directories'].values():
        require(regular_path(value, directory=True).parent == site, 'Metadata directory escaped validated site')
    for value in observation['package_origins'].values():
        path = regular_path(value['path'])
        require(path.is_relative_to(site) and file_sha(path) == value['sha256'], 'Module position changed or escaped')
    return observation


def cpu_environment(attempt, nonce):
    require(re.fullmatch(r'[0-9a-f]{64}', nonce or '') is not None, 'Owned process nonce absent')
    cache = str(attempt / 'cache')
    return {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
        NONCE_KEY: nonce, 'CUDA_VISIBLE_DEVICES': '', 'NVIDIA_VISIBLE_DEVICES': 'none',
        'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'HF_HOME': cache,
        'HF_HUB_CACHE': cache, 'TORCH_HOME': cache, 'XDG_CACHE_HOME': cache,
        'PIP_CONFIG_FILE': '/dev/null', 'PIP_NO_INPUT': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1',
        'NETRC': str(attempt / 'no-netrc')}


def child_authority(request, expected_request):
    attempt = regular_path(request['attempt_directory'], directory=True)
    marker = json.loads(captured_bytes(attempt.with_name(attempt.name + '.consumed.json'))[0])
    declaration = json.loads(captured_bytes(attempt / 'process-r1/declaration.json')[0])
    require(marker['request_sha256'] == expected_request and marker['nonce'] == request['nonce']
            and declaration['nonce'] == os.environ.get(NONCE_KEY), 'Fresh consumed request/process binding differs')
    controller = declaration['controller']
    require(process_identity(controller['pid']) == controller, 'Original current controller identity lost')
    current = process_identity(os.getpid())
    ancestry = [current]
    while ancestry[-1]['ppid'] != controller['pid']:
        require(len(ancestry) < 8, 'CPU child is outside declared owned ancestry')
        parent = process_identity(ancestry[-1]['ppid'])
        require(parent['boot_id'] == current['boot_id'] and parent['uid'] == current['uid']
                and parent['start_ticks'] <= ancestry[-1]['start_ticks'], 'CPU ancestry identity differs')
        ancestry.append(parent)
    require(len(ancestry) >= 2, 'Only watchdog-owned worker/descendants may observe')
    guard_argv = Path('/proc/%d/cmdline' % ancestry[-1]['pid']).read_bytes().split(b'\0')
    require(str(attempt / 'native-owned-process.py').encode() in guard_argv
            and str(attempt / 'process-r1/declaration.json').encode() in guard_argv,
            'Owned watchdog execution-copy origin differs')
    require(file_sha(attempt / 'native-owned-process.py') == OWNED_SHA, 'Owned execution-copy bytes changed')
    return attempt, current, ancestry


def nvidia_fds(proc_fd=Path('/proc/self/fd')):
    found = []
    for entry in proc_fd.iterdir():
        try:
            target = os.readlink(entry)
        except FileNotFoundError:
            continue  # FD closed between directory enumeration and readlink.
        if target.startswith('/dev/nvidia'):
            found.append({'fd': entry.name, 'target': target})
    require(not found, 'NVIDIA device descriptor observed')
    return found


def observe_torch(torch, expected_version, site, fd_probe=nvidia_fds):
    require(str(torch.__version__) == expected_version and torch.version.cuda == '12.8', 'Torch build metadata differs')
    origins = {}
    for name, module in list(sys.modules.items()):
        if name == 'torch' or name.startswith('torch.'):
            require(isinstance(module, ModuleType), 'Unexpected Torch module object')
            value = vars(module).get('__file__')
            if value is not None:
                path = regular_path(value)
                require(path.is_relative_to(site), 'Loaded Torch origin escaped validated site')
                origins[name] = str(path)
    for name in ('torch', 'torch._C'):
        require(name in origins, 'Actual Torch Python/native module origin absent')
    require(isinstance(vars(sys.modules['torch._C']).get('__loader__'), machinery.ExtensionFileLoader),
            'Torch _C is not a loaded native extension')
    initialized_before = torch.cuda.is_initialized()
    require(initialized_before is False, 'CUDA already initialized')
    before_fds = fd_probe()
    torch.set_num_threads(1)
    left = torch.tensor([[1., 2.], [3., 4.]], dtype=torch.float32, device='cpu', requires_grad=False)
    right = torch.tensor([[5., 6.], [7., 8.]], dtype=torch.float32, device='cpu', requires_grad=False)
    result = left @ right
    values = result.tolist()
    require(str(left.device) == str(right.device) == str(result.device) == 'cpu'
            and left.dtype == right.dtype == result.dtype == torch.float32
            and tuple(result.shape) == (2, 2) and values == [[19., 22.], [43., 50.]]
            and all(math.isfinite(x) for row in values for x in row)
            and not left.requires_grad and not right.requires_grad and not result.requires_grad
            and result.grad_fn is None, 'Explicit CPU FP32 arithmetic differs')
    initialized_after = torch.cuda.is_initialized()
    require(initialized_after is False, 'CUDA initialized during CPU observation')
    after_fds = fd_probe()
    return {'torch_version': str(torch.__version__), 'compiled_CUDA_metadata': torch.version.cuda,
            'loaded_torch_origins': origins, 'torch_C_sha256': file_sha(origins['torch._C']),
            'cuda_is_initialized_before': initialized_before, 'cuda_is_initialized_after': initialized_after,
            'nvidia_fds_before': before_fds, 'nvidia_fds_after': after_fds,
            'CPU_tensor_device': 'cpu', 'dtype': 'torch.float32', 'shape': [2, 2],
            'operands': [[[1., 2.], [3., 4.]], [[5., 6.], [7., 8.]]], 'result': values,
            'requires_grad': False, 'backward_calls': 0, 'model_calls': 0}


def run_pip_check(request_path, expected_request, env, output_directory):
    argv = [sys.executable, '-B', '-I', '-S', str(Path(__file__).resolve()), '--pip-child',
            '--request', str(request_path), '--expected-request-sha256', expected_request]
    stdout_path, stderr_path = (Path(output_directory) / name for name in ('pip.stdout.log', 'pip.stderr.log'))
    with stdout_path.open('xb') as stdout_file, stderr_path.open('xb') as stderr_file:
        result = subprocess.run(argv, env=env, stdin=subprocess.DEVNULL, stdout=stdout_file,
                                stderr=stderr_file, check=False)
    stdout, stderr = stdout_path.read_bytes(), stderr_path.read_bytes()
    observation = {'argv': argv, 'returncode': result.returncode,
            'stdout': stdout.decode(errors='replace'), 'stderr': stderr.decode(errors='replace'),
            'stdout_sha256': digest(stdout), 'stderr_sha256': digest(stderr),
            'stdout_bytes': len(stdout), 'stderr_bytes': len(stderr)}
    write_once(Path(output_directory) / 'pip.result.json', observation)
    require(result.returncode == 0, 'Isolated pipcheck failed before Torch: ' + stderr.decode(errors='replace'))
    return observation


def checked_CPU_observation(metadata_probe, expected, site, pipcheck, torch_import):
    observations = validate_metadata(metadata_probe(), expected, site)
    pip = pipcheck()
    require(validate_metadata(metadata_probe(), expected, site) == observations,
            'Runtime metadata/positions changed during pipcheck')
    require(not any(name == 'torch' or name.startswith('torch.') for name in sys.modules),
            'Torch imported before validated metadata/pipcheck')
    before_import_fds = nvidia_fds()
    torch = torch_import()
    return observations, pip, before_import_fds, observe_torch(torch, expected['torch'], site)


def package_child(request, request_path, expected_request, *, pip_only=False):
    stdlib = clean_startup()
    identity = check_host(request)
    attempt, _, ancestry = child_authority(request, expected_request)
    env = cpu_environment(attempt, os.environ.get(NONCE_KEY))
    os.environ.clear()
    os.environ.update(env)
    os.chdir(attempt)
    venv, python, site = runtime_paths(request['runtime'])
    require(str(Path(sys.executable)) == str(python)
            and list(sys.version_info[:3]) == request['runtime']['python_version'], 'Runtime child executable/version differs')
    inputs, pins = verify_inputs(request)
    select_site(site, stdlib)
    if pip_only:
        # -S's true base prefix is retained. No --require-virtualenv predicate,
        # install command, site.addsitedir or inherited pip configuration is used.
        import runpy
        validate_metadata(metadata_observation(site), pins, site)
        sys.argv = ['pip', '--isolated', '--disable-pip-version-check', '--no-input', 'check']
        runpy.run_module('pip', run_name='__main__')
        return None
    def import_torch():
        import torch
        return torch
    observations, pipcheck, before_import_fds, observation = checked_CPU_observation(
        lambda: metadata_observation(site), pins, site,
        lambda: run_pip_check(request_path, expected_request, env, attempt), import_torch)
    return {'schema_version': 1, 'status': 'CPU_runtime_import_arithmetic_observed', 'scope': SCOPE,
            'nonce': request['nonce'], 'process_nonce': env[NONCE_KEY], 'request_sha256': expected_request,
            'identity': identity, 'ancestry': ancestry, 'inputs': inputs, 'metadata': observations,
            'pipcheck': pipcheck, 'before_Torch_import_nvidia_fds': before_import_fds,
            'runtime': {'declared_venv': str(venv), 'lexical_executable': sys.executable,
                        'real_executable': str(Path(sys.executable).resolve()),
                        'actual_prefix': sys.prefix, 'actual_base_prefix': sys.base_prefix,
                        'site_selected_manually': str(site), 'sys_path': list(sys.path),
                        'Python_flags': {'isolated': sys.flags.isolated, 'no_site': sys.flags.no_site,
                                         'dont_write_bytecode': sys.dont_write_bytecode}},
            'observation': observation, 'execution_available': False, 'resource_authority': False,
            'limitations': ['CPU import/arithmetic only; compiled CUDA metadata is not CUDA ABI or device evidence.',
                'Metadata/positions/pipcheck are not independent wheel or installed-file payload attestation.',
                'FD and is_initialized endpoints cannot exclude transient native device access; no syscall sandbox.',
                'Existing OS/CPython/stdlib/opaque extension internals are trusted inputs; retained Python references are not revoked.',
                'No model, LoRA/head/base tensor, gradient, training, GPU lease or queue-restoration observation.']}


@contextmanager
def controller_preflight_budget():
    require(hasattr(signal, 'setitimer') and signal.getitimer(signal.ITIMER_REAL)[0] == 0,
            'Fresh bounded controller preflight required')
    previous = signal.getsignal(signal.SIGALRM)
    def expired(number, frame):
        raise RuntimeABIError('Separate 30-second controller preflight expired')
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, SOURCE_PREFLIGHT_SECONDS)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def observe_cpu(request_path, expected_request):
    clean_startup()
    with controller_preflight_budget():
        request = read_request(request_path, expected_request)
        controller = check_host(request)
        bootstrap = request['bootstrap']
        require(set(bootstrap) == {'realpath', 'sha256', 'python_version'}
                and bootstrap['realpath'] == str(Path(sys.executable).resolve())
                and bootstrap['sha256'] == file_sha(Path(sys.executable).resolve())
                and bootstrap['python_version'] == list(sys.version_info[:3]), 'Declared bootstrap interpreter differs')
        venv, python, _ = runtime_paths(request['runtime'])
        attempt = Path(request['attempt_directory'])
        require(attempt.is_absolute() and attempt.as_posix() == str(attempt.resolve())
                and not attempt.exists() and not attempt.is_symlink(), 'Fresh non-symlink attempt required')
        parent = regular_path(str(attempt.parent), directory=True)
        require(parent.stat().st_uid == os.getuid(), 'Owned attempt parent required')
        protected = [venv, Path(request['data_root']),
                     *[Path(request['source_context'][role + '_root']) for role in ('scientific', 'native', 'operational')]]
        require(all(not attempt.is_relative_to(p) and not p.is_relative_to(attempt) for p in protected),
                'Attempt overlaps immutable source/data/runtime')
        marker = attempt.with_name(attempt.name + '.consumed.json')
        require(not marker.exists() and not marker.is_symlink(), 'Consumed attempt cannot retry')
        original = Path(request['source_context']['native_root']) / 'scripts/frontier_v8_owned_process.py'
        native_bytes, native_identity = captured_bytes(original)
        require(digest(native_bytes) == OWNED_SHA, 'Pinned native primitive bytes differ')
    write_once(marker, {'schema_version': 1, 'status': 'CPU_ABI_attempt_consumed_no_retry',
        'scope': SCOPE, 'nonce': request['nonce'], 'request_sha256': expected_request, 'controller': controller})
    attempt.mkdir(mode=0o700)
    copy = attempt / 'native-owned-process.py'
    with copy.open('xb') as handle:
        handle.write(native_bytes)
    copy.chmod(0o400)
    copy_identity = _identity_tuple(copy.stat())
    owned = load_captured_module(copy, native_bytes, OWNED_SHA, '_frontier_abi_owned_process')
    started = time.monotonic()
    result = {'schema_version': 1, 'status': 'CPU_ABI_failed_consumed_no_retry', 'scope': SCOPE,
        'nonce': request['nonce'], 'request_sha256': expected_request, 'controller': controller,
        'native_primitive': {'original_path': str(original), 'original_sha256': OWNED_SHA,
            'execution_copy_path': str(copy), 'copy_sha256': OWNED_SHA, 'copy_mode': '0400'},
        'execution_available': False, 'resource_authority': False,
        'source_preflight_budget_seconds': SOURCE_PREFLIGHT_SECONDS,
        'source_postflight_budget_seconds': SOURCE_PREFLIGHT_SECONDS,
        'worker_budget_seconds': request['work_seconds'], 'cleanup_budget_seconds': request['cleanup_seconds'],
        'whole_transport_episode_budget_claimed': False,
        'guard_interpreter_flags_limit': 'Immutable guard re-execs -I -S without -B; observer/pip/Torch child argv includes -B -I -S.',
        'model_calls': 0, 'training_runs': 0, 'installations': 0, 'GPU_actions': 0, 'queue_actions': 0}
    try:
        argv = [str(python), '-B', '-I', '-S', str(Path(__file__).resolve()), '--cpu-child',
                '--request', str(request_path), '--expected-request-sha256', expected_request]
        proof = owned.run_owned_cpu_worker(argv, attempt_directory=attempt / 'process-r1',
            timeout_seconds=request['work_seconds'], cleanup_seconds=request['cleanup_seconds'])
        raw = (attempt / 'process-r1/worker.stdout.log').read_bytes()
        observation = json.loads(raw)
        require(observation['status'] == 'CPU_runtime_import_arithmetic_observed'
                and observation['request_sha256'] == expected_request and observation['nonce'] == request['nonce']
                and observation['process_nonce'] == proof['nonce'], 'CPU observation and process proof binding differs')
        require(captured_bytes(original) == (native_bytes, native_identity)
                and file_sha(copy) == OWNED_SHA and _identity_tuple(copy.stat()) == copy_identity,
                'Native original or execution copy changed')
        require(request['observer_sha256'] == file_sha(__file__), 'Observer source changed during attempt')
        with controller_preflight_budget():
            inputs_after, _ = verify_inputs(request)
            require(inputs_after == observation['inputs'], 'Source/plan/data changed during CPU observation')
            require(read_request(request_path, expected_request) == request,
                    'Exact request changed during CPU observation')
        result.update(status='CPU_runtime_ABI_observation_complete', process_proof=proof,
                      observation=observation, worker_stdout_sha256=digest(raw),
                      source_plan_data_postflight_equal=True)
    except BaseException as error:
        result['error'] = str(error)
        if getattr(error, 'receipt', None) is not None:
            result['process_proof'] = error.receipt
        raise
    finally:
        result['controller_observation_elapsed_seconds'] = time.monotonic() - started
        write_once(attempt / 'receipt.json', result)
        sys.modules.pop('_frontier_abi_owned_process', None)
    return result


def execute(*args, **kwargs):
    raise RuntimeABIError('Model execution is closed; CPU ABI observation grants no model/resource authority')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--observe-cpu', action='store_true')
    mode.add_argument('--cpu-child', action='store_true')
    mode.add_argument('--pip-child', action='store_true')
    mode.add_argument('--execute', action='store_true')
    parser.add_argument('--request')
    parser.add_argument('--expected-request-sha256')
    args = parser.parse_args(argv)
    if args.execute:
        execute()  # Refuse before any request/path/runtime/package handling.
    require(args.request is not None, 'External reviewed request required')
    if args.observe_cpu:
        result = observe_cpu(args.request, args.expected_request_sha256)
    else:
        clean_startup()
        request = read_request(args.request, args.expected_request_sha256)
        result = package_child(request, args.request, args.expected_request_sha256, pip_only=args.pip_child)
    if result is not None:
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
