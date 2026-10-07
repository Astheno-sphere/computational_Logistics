"""Fixed read-only metadata worker, executed only from captured source bytes.

Importing this module performs no preflight or process action. Package code,
pip, installers and the old runtime ABI routes are never imported or called.
"""
from contextlib import contextmanager
from email.parser import BytesHeaderParser
import errno
import fcntl
import hashlib
from importlib import machinery
import json
import os
from pathlib import Path
import re
import select
import signal
import stat
import sys
import time
from types import FunctionType
import zipimport


SCOPE = 'frontier_v8_owned_C_fixed_Python_readonly_metadata_CPU_fixture'
LOCK_SHA256 = 'd1f238a916dfdfbc8b89f3de4c28bb3b7220cdd97ecf609ebb726afab0ca8221'
NAMES = ('torch', 'transformers', 'peft', 'triton', 'safetensors', 'accelerate')
AUTHORITY = ('functional_containment_verified', 'containment_available',
             'execution_available', 'resource_authority', 'model_runtime_ABI_observed',
             'production_controller_guard_completed', 'GPU_or_foreign_restore')
REQUEST_FIELDS = {'schema_version', 'scope', 'case', 'nonce', 'input_kind',
                  'python_version', 'runtime', 'lock', 'authority', 'host', 'sources',
                  'attempt_directory', 'bootstrap', 'source_A', 'scientific_A', 'native_A'}
RUNTIME_FIELDS = {'venv_root', 'config', 'site', 'alias', 'interpreter',
                  'stdlib', 'lib_dynload', 'stdlib_zip'}
MAX_METADATA = 256 << 10
MAX_METADATA_TOTAL = 16 << 20
MAX_SOURCE = 1 << 20
MAX_SITE_ENTRIES = 8192
MAX_BODY = 256 << 10
RESULT_FIELDS = {'schema_version', 'scope', 'case', 'nonce', 'input_kind', 'identity',
                 'python', 'startup', 'lock', 'snapshots', 'pipcheck_performed',
                 'dependency_consistency_verified', 'authority'}


class PreflightError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PreflightError(message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def normalized(name):
    require(type(name) is str and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', name),
            'Invalid distribution name')
    return re.sub(r'[-_.]+', '-', name).lower()


def identity_tuple(info):
    return [info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns]


def absolute_path(value):
    require(type(value) is str and 0 < len(value) <= 4096 and '\0' not in value,
            'Bounded path required')
    path = Path(value)
    require(path.is_absolute() and path.as_posix() == value and '..' not in path.parts,
            'Canonical absolute path required')
    return path


@contextmanager
def opened_path(value, *, directory=False):
    """Traverse canonical parents using actual no-follow directory handles."""
    path = absolute_path(value)
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    fd = os.open('/', flags | os.O_DIRECTORY)
    try:
        for index, part in enumerate(path.parts[1:]):
            is_directory = index < len(path.parts) - 2 or directory
            child = os.open(part, flags | (os.O_DIRECTORY if is_directory else 0), dir_fd=fd)
            old, fd = fd, child
            os.close(old)
        require(stat.S_ISDIR(os.fstat(fd).st_mode) if directory
                else stat.S_ISREG(os.fstat(fd).st_mode), 'Wrong input file type')
        yield fd
    finally:
        os.close(fd)


def capture_regular(value, limit):
    require(type(limit) is int and limit > 0, 'Positive capture limit required')
    with opened_path(value) as fd:
        before = identity_tuple(os.fstat(fd))
        require(before[3] <= limit, 'Input exceeds capture limit')
        chunks, length = [], 0
        while True:
            chunk = os.read(fd, min(65536, limit + 1 - length))
            if not chunk:
                break
            chunks.append(chunk)
            length += len(chunk)
            require(length <= limit, 'Input grew beyond capture limit')
        after = identity_tuple(os.fstat(fd))
        require(before == after and length == before[3], 'Input changed during capture')
    with opened_path(value) as fd:
        require(identity_tuple(os.fstat(fd)) == before, 'Input pathname changed after capture')
    body = b''.join(chunks)
    return body, {'path': value, 'sha256': digest(body), 'identity': before, 'bytes': length}


def directory_observation(value):
    with opened_path(value, directory=True) as fd:
        return {'path': value, 'identity': identity_tuple(os.fstat(fd))}


def parse_lock(body):
    require(type(body) is bytes and len(body) <= 65536 and digest(body) == LOCK_SHA256,
            'Frozen lock bytes differ')
    pins = {}
    for line in body.decode('ascii').splitlines():
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([^\s;]+)', line)
        require(match is not None, 'Exact runtime pin required')
        name = normalized(match[1])
        require(name not in pins, 'Duplicate runtime pin')
        pins[name] = match[2]
    require(len(pins) == 76 and pins.get('torch') == '2.8.0+cu128'
            and pins.get('pip') == '24.0' and pins.get('setuptools') == '79.0.1',
            'Fixed 76-package lock required')
    return pins


def parse_metadata(body):
    require(type(body) is bytes and 0 < len(body) <= MAX_METADATA, 'Bounded METADATA required')
    message = BytesHeaderParser().parsebytes(body)
    names, versions = message.get_all('Name', []), message.get_all('Version', [])
    require(len(names) == len(versions) == 1, 'Single Name and Version required')
    name, version = str(names[0]), str(versions[0])
    require(type(version) is str and 0 < len(version) <= 256
            and re.fullmatch(r'[^\s;]+', version), 'Bounded exact version required')
    return normalized(name), version


def duplicate_free_json(body):
    def pairs(values):
        row = {}
        for key, value in values:
            require(key not in row, 'Duplicate JSON key')
            row[key] = value
        return row
    def constant(value):
        raise PreflightError('Nonfinite JSON value')
    return json.loads(body, object_pairs_hook=pairs, parse_constant=constant)


def hash_value(value, length=64):
    return type(value) is str and re.fullmatch(r'[0-9a-f]{%d}' % length, value) is not None


def version_value(value):
    return type(value) is list and len(value) == 3 and all(
        type(part) is int and 0 <= part <= 65535 for part in value)


def validate_request(request):
    require(type(request) is dict and set(request) == REQUEST_FIELDS
            and type(request['schema_version']) is int and request['schema_version'] == 1
            and request['scope'] == SCOPE, 'Closed fixed request required')
    require(request['case'] in ('normal', 'worker_loss') and hash_value(request['nonce'])
            and request['input_kind'] in ('real_readonly_runtime', 'synthetic_CI_fixture')
            and version_value(request['python_version']), 'Request case/version differs')
    if request['input_kind'] == 'real_readonly_runtime':
        require(request['python_version'][:2] == [3, 11], 'Real runtime requires Python 3.11')
    require(type(request['authority']) is dict and set(request['authority']) == set(AUTHORITY)
            and all(value is False for value in request['authority'].values()), 'Authority must stay false')
    runtime = request['runtime']
    require(type(runtime) is dict and set(runtime) == RUNTIME_FIELDS, 'Closed runtime inputs required')
    for name in ('venv_root', 'site', 'alias', 'stdlib', 'lib_dynload', 'stdlib_zip'):
        absolute_path(runtime[name])
    for name in ('config', 'interpreter'):
        require(type(runtime[name]) is dict and set(runtime[name]) == {'path', 'sha256'}
                and hash_value(runtime[name]['sha256']), 'Bound runtime file required')
        absolute_path(runtime[name]['path'])
    venv = absolute_path(runtime['venv_root'])
    require(runtime['config']['path'] == str(venv / 'pyvenv.cfg')
            and runtime['alias'] == str(venv / 'bin/python')
            and runtime['site'] == str(venv / ('lib/python%d.%d/site-packages' % tuple(request['python_version'][:2])))
            and runtime['lib_dynload'] == str(Path(runtime['stdlib']) / 'lib-dynload')
            and runtime['stdlib_zip'] == str(Path(runtime['stdlib']).parent /
                ('python%d%d.zip' % tuple(request['python_version'][:2]))), 'Runtime path relation differs')
    require(type(request['lock']) is dict and set(request['lock']) == {'path', 'sha256'}
            and request['lock']['sha256'] == LOCK_SHA256, 'Bound frozen lock required')
    absolute_path(request['lock']['path'])
    absolute_path(request['attempt_directory'])
    require(type(request['host']) is dict and set(request['host']) == {'node_alias', 'hostname', 'boot_id', 'uid'}
            and type(request['host']['uid']) is int and request['host']['uid'] >= 0
            and all(type(request['host'][key]) is str and 0 < len(request['host'][key]) <= 256
                    for key in ('node_alias', 'hostname'))
            and type(request['host']['boot_id']) is str
            and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', request['host']['boot_id']),
            'Bound host fields required')
    require(type(request['bootstrap']) is dict and set(request['bootstrap']) == {'path', 'sha256', 'python_version'}
            and hash_value(request['bootstrap']['sha256']) and version_value(request['bootstrap']['python_version']),
            'Bound bootstrap required')
    absolute_path(request['bootstrap']['path'])
    sources = request['sources']
    require(type(sources) is dict and set(sources) == {'observer_sha256', 'worker_sha256',
            'c_sources_sha256', 'identity_helper_sha256', 'toolchain_sha256', 'linkage_sha256'}
            and all(hash_value(value) for key, value in sources.items() if key != 'c_sources_sha256')
            and type(sources['c_sources_sha256']) is dict and set(sources['c_sources_sha256']) == {
                'frontier_v8_owned_c_python_preflight_guardian.c', 'frontier_v8_owned_c_python_preflight_protocol.h'}
            and all(hash_value(value) for value in sources['c_sources_sha256'].values()), 'Fixed source hashes required')
    require(all(hash_value(request[key], 40) for key in ('source_A', 'scientific_A', 'native_A')),
            'Source/scientific metadata differs')
    return request


def parse_request(body):
    require(type(body) is bytes and len(body) <= 65536, 'Bounded captured request required')
    return validate_request(duplicate_free_json(body))


def alias_observation(alias, expected):
    current, links = absolute_path(alias), []
    for _ in range(8):
        with opened_path(str(current.parent), directory=True) as fd:
            before = os.stat(current.name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISLNK(before.st_mode):
                target = os.readlink(current.name, dir_fd=fd)
                require(0 < len(target) <= 4096, 'Bounded alias target required')
                after = os.stat(current.name, dir_fd=fd, follow_symlinks=False)
                require(identity_tuple(before) == identity_tuple(after), 'Alias changed during observation')
                links.append({'path': str(current), 'target': target, 'identity': identity_tuple(before)})
            else:
                require(stat.S_ISREG(before.st_mode) and str(current) == expected and links,
                        'Declared venv alias backing differs')
                return {'path': alias, 'links': links, 'target': expected, 'identity': identity_tuple(before)}
        current = absolute_path(os.path.normpath(target if target.startswith('/') else str(current.parent / target)))
    raise PreflightError('Alias chain exceeds bound')


def runtime_observation(runtime):
    config, cfg_fact = capture_regular(runtime['config']['path'], 65536)
    require(cfg_fact['sha256'] == runtime['config']['sha256']
            and len(re.findall(rb'^include-system-site-packages\s*=\s*false\s*$', config, re.M)) == 1
            and len(re.findall(rb'^include-system-site-packages\s*=', config, re.M)) == 1,
            'Read-only venv config differs')
    return {'venv': directory_observation(runtime['venv_root']),
            'site': directory_observation(runtime['site']), 'config': cfg_fact,
            'alias': alias_observation(runtime['alias'], runtime['interpreter']['path'])}


def source_origins(site):
    finder = machinery.FileFinder(site, (machinery.SourceFileLoader, machinery.SOURCE_SUFFIXES))
    result = {}
    for name in NAMES:
        spec = finder.find_spec(name)
        expected = str(Path(site) / name / '__init__.py')
        require(spec is not None and type(spec.loader) is machinery.SourceFileLoader
                and spec.origin == expected and list(spec.submodule_search_locations or []) == [str(Path(site) / name)],
                'Fixed source entry position differs')
        _, result[name] = capture_regular(expected, MAX_SOURCE)
    return result


def metadata_snapshot(site, pins):
    absolute_path(site)
    names, entries = [], 0
    with opened_path(site, directory=True) as fd:
        with os.scandir(fd) as iterator:
            for entry in iterator:
                entries += 1
                require(entries <= MAX_SITE_ENTRIES, 'Explicit site enumeration exceeds bound')
                require(not entry.name.endswith('.egg-info'), 'Legacy metadata rejected')
                if entry.name.endswith('.dist-info'):
                    require(not entry.is_symlink() and entry.is_dir(follow_symlinks=False),
                            'Regular metadata directory required')
                    names.append(entry.name)
                    require(len(names) <= 76, 'Extra distribution metadata')
    require(len(names) == 76, 'Exactly 76 metadata directories required')
    versions, roots, directories, hashes, identities, total = {}, {}, {}, {}, {}, 0
    for dirname in sorted(names):
        directory = str(Path(site) / dirname)
        directory_observation(directory)
        body, fact = capture_regular(str(Path(directory) / 'METADATA'), MAX_METADATA)
        total += len(body)
        require(total <= MAX_METADATA_TOTAL, 'Total metadata bytes exceed bound')
        name, version = parse_metadata(body)
        require(name not in versions, 'Normalized duplicate distribution')
        versions[name], roots[name], directories[name] = version, site, directory
        hashes[name], identities[name] = fact['sha256'], fact['identity']
    require(versions == pins, 'Exact 76 runtime versions differ')
    return {'versions': versions, 'distribution_roots': roots, 'metadata_directories': directories,
            'metadata_sha256': hashes, 'metadata_identity': identities,
            'explicit_scan': {'passes': 1, 'entries': entries, 'metadata_bytes': total}}


def readonly_snapshot(runtime, pins):
    return {'runtime_inputs': runtime_observation(runtime),
            'metadata': metadata_snapshot(runtime['site'], pins),
            'package_origins': source_origins(runtime['site'])}


def compare_snapshots(before, after):
    require(before == after, 'Selected runtime metadata/origins/config/alias changed')
    return True


def startup_observation(runtime):
    roots = {runtime[name] for name in ('stdlib', 'lib_dynload', 'stdlib_zip')}
    require(list(sys.meta_path) == [machinery.BuiltinImporter, machinery.FrozenImporter, machinery.PathFinder],
            'Foreign startup meta finder')
    require(len(sys.path_hooks) == 2 and sys.path_hooks[0] is zipimport.zipimporter,
            'Standard zip/path hooks required')
    hook = sys.path_hooks[1]
    require(isinstance(hook, FunctionType) and hook.__code__ is machinery.FileFinder.path_hook().__code__
            and hook.__closure__ is not None and len(hook.__closure__) == 2
            and hook.__closure__[0].cell_contents is machinery.FileFinder, 'Foreign startup FileFinder hook')
    details = hook.__closure__[1].cell_contents
    loaders = {machinery.SourceFileLoader: machinery.SOURCE_SUFFIXES,
               machinery.SourcelessFileLoader: machinery.BYTECODE_SUFFIXES,
               machinery.ExtensionFileLoader: machinery.EXTENSION_SUFFIXES}
    require(len(details) == 3 and {loader for loader, _ in details} == set(loaders)
            and all(suffixes == loaders[loader] for loader, suffixes in details), 'Foreign startup hook loaders')
    cache = []
    for path, finder in sys.path_importer_cache.items():
        require(type(path) is str and (path in roots or Path(path).is_relative_to(Path(runtime['stdlib']))),
                'Foreign startup importer-cache path')
        require(finder is None or type(finder) in (machinery.FileFinder, zipimport.zipimporter),
                'Foreign startup cache finder')
        row = {'path': path, 'kind': 'absent' if finder is None else type(finder).__name__}
        if type(finder) is machinery.FileFinder:
            require(finder.path == path, 'Startup finder path differs')
            expected = {(suffix, loader) for loader, suffixes in loaders.items() for suffix in suffixes}
            require(type(finder._loaders) is list and len(finder._loaders) == len(expected)
                    and set(finder._loaders) == expected, 'Foreign startup cache loader')
        elif type(finder) is zipimport.zipimporter:
            require(finder.archive in roots and not Path(finder.prefix).is_absolute()
                    and '..' not in Path(finder.prefix).parts
                    and str(Path(finder.archive) / finder.prefix) == path, 'Foreign startup zip archive/prefix')
            row.update({'archive': finder.archive, 'prefix': finder.prefix})
        cache.append(row)
    forbidden = (*NAMES, 'numpy', 'pip', 'site', 'sitecustomize', 'usercustomize')
    require(not any(name.split('.')[0] in forbidden for name in sys.modules), 'Runtime/site package already loaded')
    origins = {}
    for name in ('os', 'sys', 'hashlib', 'json', 're', 'select', 'signal', 'stat', 'time',
                 'fcntl', 'pathlib', 'email.parser', 'importlib.machinery', 'types', 'zipimport'):
        module = sys.modules[name]
        origin = getattr(getattr(module, '__spec__', None), 'origin', None)
        kind = 'builtin' if origin == 'built-in' else 'frozen' if origin == 'frozen' else 'stdlib_file'
        if kind == 'stdlib_file':
            require(type(origin) is str and Path(origin).is_relative_to(Path(runtime['stdlib'])),
                    'Fixed stdlib origin escaped trusted root')
        origins[name] = {'classification': kind, 'origin': origin}
    observation = {'python_version': list(sys.version_info[:3]), 'sys_executable': sys.executable,
        'sys_prefix': sys.prefix, 'sys_base_prefix': sys.base_prefix, 'sys_path': list(sys.path),
        'flags': {'isolated': sys.flags.isolated, 'no_site': sys.flags.no_site,
                  'dont_write_bytecode': sys.dont_write_bytecode},
        'stdlib_origins': origins, 'importer_cache': sorted(cache, key=lambda row: row['path']),
        'stdlib_zip_present': os.path.isfile(runtime['stdlib_zip'])}
    return observation


def validate_startup(observation, runtime, expected_version, input_kind):
    keys = {'python_version', 'sys_executable', 'sys_prefix', 'sys_base_prefix', 'sys_path',
            'flags', 'stdlib_origins', 'importer_cache', 'stdlib_zip_present'}
    require(type(observation) is dict and set(observation) == keys
            and version_value(observation['python_version']) and observation['python_version'] == expected_version and
            (input_kind == 'synthetic_CI_fixture' or expected_version[:2] == [3, 11]), 'Startup Python version differs')
    flags = observation['flags']
    require(type(flags) is dict and set(flags) == {'isolated', 'no_site', 'dont_write_bytecode'}
            and type(flags['isolated']) is type(flags['no_site']) is int
            and flags['isolated'] == flags['no_site'] == 1 and flags['dont_write_bytecode'] is True,
            'Fresh Python requires -B -I -S')
    roots = {runtime[name] for name in ('stdlib', 'lib_dynload', 'stdlib_zip')}
    require(type(observation['sys_path']) is list and all(type(path) is str and path in roots for path in observation['sys_path'])
            and set(observation['sys_path']) == roots
            and len(set(observation['sys_path'])) == len(observation['sys_path'])
            and runtime['site'] not in observation['sys_path'], 'Foreign startup sys.path')
    require(all(type(observation[key]) is str for key in ('sys_executable', 'sys_prefix', 'sys_base_prefix'))
            and type(observation['stdlib_zip_present']) is bool, 'Preserved Python descriptions required')
    origins = observation['stdlib_origins']
    names = {'os', 'sys', 'hashlib', 'json', 're', 'select', 'signal', 'stat', 'time',
             'fcntl', 'pathlib', 'email.parser', 'importlib.machinery', 'types', 'zipimport'}
    require(type(origins) is dict and set(origins) == names, 'Fixed stdlib origin facts required')
    for row in origins.values():
        require(type(row) is dict and set(row) == {'classification', 'origin'}, 'Closed stdlib origin fact required')
        kind, origin = row['classification'], row['origin']
        require((kind == 'builtin' and origin == 'built-in') or (kind == 'frozen' and origin == 'frozen')
                or (kind == 'stdlib_file' and type(origin) is str
                    and absolute_path(origin).is_relative_to(Path(runtime['stdlib']))), 'Stdlib classification/origin differs')
    require(type(observation['importer_cache']) is list and len(observation['importer_cache']) <= 512,
            'Bounded startup importer cache required')
    seen = set()
    for row in observation['importer_cache']:
        require(type(row) is dict and row.get('kind') in ('absent', 'FileFinder', 'zipimporter')
                and set(row) == ({'path', 'kind', 'archive', 'prefix'} if row['kind'] == 'zipimporter' else {'path', 'kind'}),
                'Closed standard cache facts required')
        path = absolute_path(row['path'])
        require(row['path'] not in seen and (row['path'] in roots or path.is_relative_to(Path(runtime['stdlib']))),
                'Foreign or duplicate importer-cache path')
        seen.add(row['path'])
        if row['kind'] == 'zipimporter':
            require(row['archive'] in roots and type(row['prefix']) is str
                    and not Path(row['prefix']).is_absolute() and '..' not in Path(row['prefix']).parts
                    and str(Path(row['archive']) / row['prefix']) == row['path'], 'Unbound zip cache archive/prefix')
    return observation


def validate_bootstrap(startup, request):
    keys = {'schema_version', 'nonce', 'case', 'input_kind', 'python_version_expected',
            'command_fd', 'report_fd', 't0_ns', 'deadlines', 'captured', 'initial_argv',
            'orig_argv', 'bootstrap_sha256', 'logical_file', 'logical_arguments'}
    require(type(startup) is dict and set(startup) == keys
            and type(startup['schema_version']) is int and startup['schema_version'] == 1,
            'Closed captured startup required')
    require(all(startup[key] == request[key] for key in ('nonce', 'case', 'input_kind'))
            and version_value(startup['python_version_expected'])
            and startup['python_version_expected'] == request['python_version'], 'Bootstrap request binding differs')
    require(type(startup['t0_ns']) is int and startup['t0_ns'] > 0, 'Original monotonic t0 required')
    offsets = {'work_ns': 20, 'cleanup_ns': 25, 'terminal_ns': 28, 'total_ns': 30, 'expiry_ns': 35}
    require(type(startup['deadlines']) is dict and set(startup['deadlines']) == set(offsets)
            and all(type(startup['deadlines'][key]) is int
                    and startup['deadlines'][key] == startup['t0_ns'] + seconds * 1000000000
                    for key, seconds in offsets.items()), 'Fixed absolute deadlines differ')
    require(type(startup['captured']) is dict and set(startup['captured']) == {'worker', 'request'},
            'Original capture records required')
    handles = [startup['command_fd'], startup['report_fd']]
    capture_keys = {'fd', 'sha256', 'length', 'before', 'after', 'close_return',
                    'badfd_result', 'badfd_exception', 'badfd_errno'}
    for name, maximum in (('worker', MAX_SOURCE), ('request', 65536)):
        row = startup['captured'][name]
        require(type(row) is dict and set(row) == capture_keys and hash_value(row['sha256'])
                and type(row['length']) is int and 0 <= row['length'] <= maximum
                and type(row['before']) is list and len(row['before']) == 6
                and all(type(value) is int and value >= 0 for value in row['before'])
                and type(row['after']) is list and all(type(value) is int for value in row['after'])
                and row['before'] == row['after'] and row['length'] == row['before'][3]
                and stat.S_ISREG(row['before'][2]) and row['close_return'] is None
                and row['badfd_result'] is None and row['badfd_exception'] == 'OSError'
                and type(row['badfd_errno']) is int and row['badfd_errno'] == errno.EBADF,
                'Captured bytes or Python once-close observations differ')
        handles.append(row['fd'])
    require(all(type(fd) is int and fd > 2 for fd in handles) and len(set(handles)) == 4,
            'Distinct original inherited handles required')
    require(startup['captured']['worker']['sha256'] == request['sources']['worker_sha256'],
            'Captured worker hash differs')
    require(startup['logical_file'] == 'frontier_v8_python_runtime_preflight.py'
            and startup['logical_arguments'] == [startup['logical_file'], request['case'],
                                                request['nonce'], request['input_kind']], 'Logical payload labels differ')
    initial = ['-c', 'PP_BOOT1', str(handles[2]), str(handles[3]), str(handles[0]), str(handles[1]),
               startup['captured']['worker']['sha256'], startup['captured']['request']['sha256'],
               request['nonce'], request['case'], str(startup['t0_ns']), request['input_kind'],
               '.'.join(str(value) for value in request['python_version'])]
    require(startup['initial_argv'] == initial, 'Actual initial -c argv differs')
    original = startup['orig_argv']
    if original is None:
        require(startup['bootstrap_sha256'] is None, 'Unavailable argv cannot authenticate bootstrap literal')
    else:
        require(type(original) is list and len(original) == 18
                and all(type(value) is str and len(value) <= 65536 for value in original)
                and original[0] == request['runtime']['interpreter']['path']
                and original[1:5] == ['-B', '-I', '-S', '-c'] and original[6:] == initial[1:]
                and digest(original[5].encode('utf-8')) == startup['bootstrap_sha256'], 'Actual original exec argv differs')
    return startup


def _kernel_bytes(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        data = b''
        while True:
            chunk = os.read(fd, min(4096, limit + 1 - len(data)))
            if not chunk:
                return data
            data += chunk
            require(len(data) <= limit, 'Kernel observation exceeds bound')
    finally:
        os.close(fd)


def process_observation():
    pid = os.getpid()
    raw = _kernel_bytes('/proc/%d/stat' % pid, 65536).decode('ascii')
    closing = raw.rfind(')')
    require(raw.startswith(str(pid) + ' (') and closing > 0, 'Current kernel PID differs')
    fields = raw[closing + 1:].split()
    require(len(fields) >= 20, 'Kernel birth observation incomplete')
    boot = _kernel_bytes('/proc/sys/kernel/random/boot_id', 128).decode('ascii').strip()
    require(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', boot), 'Kernel boot identity differs')
    path = '/proc/%d/exe' % pid
    return {'pid': pid, 'ppid': int(fields[1]), 'uid': os.getuid(), 'euid': os.geteuid(),
            'birth': int(fields[19]), 'boot_id': boot,
            'proc_exe': {'path': os.readlink(path), 'identity': identity_tuple(os.stat(path))}}


def validate_identity(observation, request):
    require(type(observation) is dict and set(observation) == {'pid', 'ppid', 'uid', 'euid', 'birth', 'boot_id', 'proc_exe'}
            and all(type(observation[key]) is int and observation[key] > 0 for key in ('pid', 'ppid', 'birth'))
            and observation['uid'] == observation['euid'] == request['host']['uid']
            and observation['boot_id'] == request['host']['boot_id']
            and type(observation['uid']) is type(observation['euid']) is int
            and type(observation['proc_exe']) is dict and set(observation['proc_exe']) == {'path', 'identity'}
            and observation['proc_exe']['path'] == request['runtime']['interpreter']['path']
            and _stat_fact(observation['proc_exe']['identity'], regular=True),
            'Current owned Python identity differs')
    return observation


def _stat_fact(info, *, regular):
    return (type(info) is list and len(info) == 6 and all(type(value) is int and value >= 0 for value in info)
            and (stat.S_ISREG(info[2]) if regular else stat.S_ISDIR(info[2])))


def _capture_fact(row, path, limit):
    require(type(row) is dict and set(row) == {'path', 'sha256', 'identity', 'bytes'}
            and row['path'] == path and hash_value(row['sha256']) and _stat_fact(row['identity'], regular=True)
            and type(row['bytes']) is int and 0 <= row['bytes'] == row['identity'][3] <= limit,
            'Closed bounded file capture fact differs')


def validate_runtime_observation(observation, runtime):
    require(type(observation) is dict and set(observation) == {'venv', 'site', 'config', 'alias'},
            'Closed runtime input observations required')
    for name, path in (('venv', runtime['venv_root']), ('site', runtime['site'])):
        row = observation[name]
        require(type(row) is dict and set(row) == {'path', 'identity'} and row['path'] == path
                and _stat_fact(row['identity'], regular=False), 'Runtime directory identity differs')
    _capture_fact(observation['config'], runtime['config']['path'], 65536)
    require(observation['config']['sha256'] == runtime['config']['sha256'], 'Observed config hash differs')
    alias = observation['alias']
    require(type(alias) is dict and set(alias) == {'path', 'links', 'target', 'identity'}
            and alias['path'] == runtime['alias'] and alias['target'] == runtime['interpreter']['path']
            and _stat_fact(alias['identity'], regular=True) and type(alias['links']) is list
            and 0 < len(alias['links']) <= 8, 'Observed interpreter alias differs')
    current = alias['path']
    for link in alias['links']:
        require(type(link) is dict and set(link) == {'path', 'target', 'identity'} and link['path'] == current
                and type(link['target']) is str and 0 < len(link['target']) <= 4096
                and type(link['identity']) is list and len(link['identity']) == 6
                and all(type(value) is int and value >= 0 for value in link['identity'])
                and stat.S_ISLNK(link['identity'][2]), 'Closed alias link observation differs')
        current = str(absolute_path(os.path.normpath(link['target'] if link['target'].startswith('/')
                      else str(Path(current).parent / link['target']))))
    require(current == alias['target'], 'Alias chain target differs')
    return observation


def validate_snapshot(snapshot, pins, site):
    require(type(snapshot) is dict and set(snapshot) == {'runtime_inputs', 'metadata', 'package_origins'},
            'Closed read-only snapshot required')
    metadata = snapshot['metadata']
    require(type(metadata) is dict and set(metadata) == {'versions', 'distribution_roots',
            'metadata_directories', 'metadata_sha256', 'metadata_identity', 'explicit_scan'}
            and metadata['versions'] == pins and all(set(metadata[key]) == set(pins) for key in
                ('distribution_roots', 'metadata_directories', 'metadata_sha256', 'metadata_identity')),
            'Complete exact metadata inventory required')
    for name in pins:
        require(metadata['distribution_roots'][name] == site
                and type(metadata['metadata_directories'][name]) is str
                and absolute_path(metadata['metadata_directories'][name]).parent == Path(site)
                and Path(metadata['metadata_directories'][name]).name.endswith('.dist-info')
                and hash_value(metadata['metadata_sha256'][name]), 'Metadata position or hash differs')
        info = metadata['metadata_identity'][name]
        require(type(info) is list and len(info) == 6 and all(type(value) is int and value >= 0 for value in info)
                and stat.S_ISREG(info[2]) and 0 < info[3] <= MAX_METADATA, 'Metadata file identity differs')
    scan = metadata['explicit_scan']
    require(type(scan) is dict and set(scan) == {'passes', 'entries', 'metadata_bytes'}
            and type(scan['passes']) is int and scan['passes'] == 1
            and type(scan['entries']) is int and 76 <= scan['entries'] <= MAX_SITE_ENTRIES
            and type(scan['metadata_bytes']) is int
            and scan['metadata_bytes'] == sum(info[3] for info in metadata['metadata_identity'].values())
            and scan['metadata_bytes'] <= MAX_METADATA_TOTAL, 'Explicit metadata scan facts differ')
    require(type(snapshot['package_origins']) is dict and set(snapshot['package_origins']) == set(NAMES),
            'Exactly six source entry positions required')
    for name, row in snapshot['package_origins'].items():
        require(type(row) is dict and set(row) == {'path', 'sha256', 'identity', 'bytes'}
                and row['path'] == str(Path(site) / name / '__init__.py') and hash_value(row['sha256'])
                and type(row['identity']) is list and len(row['identity']) == 6
                and all(type(value) is int and value >= 0 for value in row['identity'])
                and stat.S_ISREG(row['identity'][2]) and type(row['bytes']) is int
                and 0 <= row['bytes'] == row['identity'][3] <= MAX_SOURCE, 'Source entry fact differs')
    return snapshot


def validate_result(row, request, pins):
    validate_request(request)
    require(type(row) is dict and set(row) == RESULT_FIELDS and type(row['schema_version']) is int
            and row['schema_version'] == 1 and row['scope'] == SCOPE
            and all(row[key] == request[key] for key in ('case', 'nonce', 'input_kind')),
            'Closed fixed DATA result required')
    validate_identity(row['identity'], request)
    validate_startup(row['python'], request['runtime'], request['python_version'], request['input_kind'])
    validate_bootstrap(row['startup'], request)
    require(type(row['lock']) is dict and set(row['lock']) == {'path', 'sha256', 'identity', 'bytes', 'pins'}
            and row['lock']['path'] == request['lock']['path'] and row['lock']['sha256'] == LOCK_SHA256
            and row['lock']['pins'] == pins, 'Captured lock result differs')
    _capture_fact({key: value for key, value in row['lock'].items() if key != 'pins'}, request['lock']['path'], 65536)
    require(type(row['snapshots']) is dict and set(row['snapshots']) == {'before', 'after'},
            'Both read-only snapshots required')
    for snapshot in row['snapshots'].values():
        validate_snapshot(snapshot, pins, request['runtime']['site'])
        validate_runtime_observation(snapshot['runtime_inputs'], request['runtime'])
        require(snapshot['runtime_inputs']['alias']['identity'] == row['identity']['proc_exe']['identity'],
                'Alias backing and current Python product differ')
    compare_snapshots(row['snapshots']['before'], row['snapshots']['after'])
    require(type(row['pipcheck_performed']) is int and row['pipcheck_performed'] == 0
            and row['dependency_consistency_verified'] is False and row['authority'] == request['authority']
            and all(value is False for value in row['authority'].values()), 'No dependency/authority grant allowed')
    return row


def _now(state, deadline):
    now = time.monotonic_ns()
    require(type(now) is int and now >= state['last'] and now < deadline, 'Worker absolute deadline/clock failed')
    state['last'] = now
    return now


def _poll(state, fd, events, deadline):
    now = _now(state, deadline)
    poller = select.poll()
    poller.register(fd, events)
    rows = poller.poll(min(100, max(1, (deadline - now + 999999) // 1000000)))
    _now(state, deadline)
    require(all(key == fd and not flags & (select.POLLERR | select.POLLNVAL) for key, flags in rows),
            'Private pipe poll error')


def _control(state, kind, payload, deadline):
    at = _now(state, deadline)
    sequence = state['sequence']
    state['sequence'] += 1
    message = ('PP1 P %s %d %s %d%s\n' %
               (state['nonce'], sequence, kind, at, (' ' + payload) if payload else '')).encode('ascii')
    require(len(message) <= 512 and len(message) <= state['pipe_buf'], 'Atomic control exceeds bound')
    while True:
        _now(state, deadline)
        try:
            count = os.write(state['report_fd'], message)
        except BlockingIOError as error:
            require(error.errno == errno.EAGAIN, 'Unexpected control write failure')
            _poll(state, state['report_fd'], select.POLLOUT, deadline)
            continue
        require(count == len(message), 'Partial control write is permanent negative')
        return


def _data(state, body, deadline):
    require(type(body) is bytes and len(body) <= MAX_BODY, 'Bounded DATA bytes required')
    _control(state, 'DATA', '%d %s' % (len(body), digest(body)), deadline)
    cursor = 0
    while cursor < len(body):
        _now(state, deadline)
        try:
            count = os.write(state['report_fd'], body[cursor:])
        except BlockingIOError as error:
            require(error.errno == errno.EAGAIN, 'Unexpected DATA write failure')
            _poll(state, state['report_fd'], select.POLLOUT, deadline)
            continue
        require(type(count) is int and 0 < count <= len(body) - cursor, 'Invalid DATA progress')
        cursor += count


def _command(state, sequence, kind, deadline):
    message = b''
    while b'\n' not in message:
        _now(state, deadline)
        try:
            chunk = os.read(state['command_fd'], 513 - len(message))
        except BlockingIOError as error:
            require(error.errno == errno.EAGAIN, 'Unexpected command read failure')
            _poll(state, state['command_fd'], select.POLLIN, deadline)
            continue
        require(chunk, 'Private command EOF is negative')
        message += chunk
        require(len(message) <= 512, 'Private command exceeds bound')
    match = re.fullmatch(rb'PP1 G ([0-9a-f]{64}) ([1-9][0-9]*) ([A-Z_]+) ([1-9][0-9]*)\n', message)
    require(match is not None and match[1].decode('ascii') == state['nonce']
            and int(match[2]) == sequence and match[3].decode('ascii') == kind
            and state.get('last_command_at', state['t0_ns']) <= int(match[4]) <= _now(state, deadline),
            'Exact private command order differs')
    state['last_command_at'] = int(match[4])


def bridge_entry(REQUEST, STARTUP):
    """Only fixed bootstrap invokes this entry with captured request/startup."""
    state, result = None, 70
    try:
        request = validate_request(REQUEST)
        startup = validate_bootstrap(STARTUP, request)
        work, terminal, expiry = (startup['deadlines'][key] for key in ('work_ns', 'terminal_ns', 'expiry_ns'))
        state = {'nonce': request['nonce'], 'sequence': 3, 'last': startup['t0_ns'], 't0_ns': startup['t0_ns'],
                 'command_fd': startup['command_fd'], 'report_fd': startup['report_fd'], 'pipe_buf': 0}
        _now(state, work)
        for fd in (state['command_fd'], state['report_fd']):
            require(not fcntl.fcntl(fd, fcntl.F_GETFD) & fcntl.FD_CLOEXEC
                    and fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_NONBLOCK, 'Retained private FD flags differ')
        state['pipe_buf'] = os.fpathconf(state['report_fd'], 'PC_PIPE_BUF')
        require(state['pipe_buf'] >= 512, 'Runtime PIPE_BUF too small')
        signal.signal(signal.SIGPIPE, signal.SIG_IGN)
        require(signal.getsignal(signal.SIGPIPE) == signal.SIG_IGN, 'Local SIGPIPE ignore failed')
        python = validate_startup(startup_observation(request['runtime']), request['runtime'],
                                  request['python_version'], request['input_kind'])
        identity = validate_identity(process_observation(), request)
        require(os.uname().nodename == request['host']['hostname'], 'Current hostname differs')
        ready = [identity[key] for key in ('pid', 'ppid', 'uid', 'euid', 'birth')]
        ready += python['python_version'] + [1, 1, 1]
        ready += [startup['captured'][key]['sha256'] for key in ('worker', 'request')]
        _control(state, 'READY', ' '.join(str(value) for value in ready), work)
        _command(state, 2, 'CHECK', work)
        lock_body, lock = capture_regular(request['lock']['path'], 65536)
        pins = parse_lock(lock_body)
        lock['pins'] = pins
        before = readonly_snapshot(request['runtime'], pins)
        _now(state, work)
        after = readonly_snapshot(request['runtime'], pins)
        _now(state, work)
        compare_snapshots(before, after)
        validate_startup(startup_observation(request['runtime']), request['runtime'],
                         request['python_version'], request['input_kind'])
        row = {'schema_version': 1, 'scope': SCOPE, 'case': request['case'], 'nonce': request['nonce'],
               'input_kind': request['input_kind'], 'identity': identity, 'python': python, 'startup': startup,
               'lock': lock, 'snapshots': {'before': before, 'after': after}, 'pipcheck_performed': 0,
               'dependency_consistency_verified': False, 'authority': {key: False for key in AUTHORITY}}
        validate_result(row, request, pins)
        body = json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8')
        _data(state, body, work)
        _control(state, 'ARM', '', work)
        _command(state, 3, 'ARM_ACK', work)
        _control(state, 'ACK', '', work)
        _command(state, 4, 'FINISH', expiry)
        require(request['case'] == 'normal', 'Loss case cannot accept FINISH')
        _control(state, 'FINISH_ACK', '', terminal)
        result = 0
    except BaseException as error:
        if state is not None:
            code = 'worker_capture' if isinstance(error, OSError) else 'worker_validation'
            if isinstance(error, PreflightError) and 'deadline/clock' in str(error):
                code = 'worker_deadline'
            try:
                _control(state, 'ERROR', code, STARTUP['deadlines']['expiry_ns'])
            except BaseException:
                pass  # A failed/expired original report edge is retained as unknown.
        result = 70
    finally:
        if state is not None:
            # These later closes cannot be self-reported in the earlier DATA body.
            for key in ('command_fd', 'report_fd'):
                try:
                    os.close(state[key])
                except OSError:
                    result = 70
    return result
