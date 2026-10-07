"""Integrated once-only CPU transport; no model/GPU/install/queue entrypoint.

All remote bodies come from this committed file or the immutable native-A helper.
Before the three actual Git roots exist, the bootstrap copies are trusted captured
bytes tied to local source/code-integration/prelaunch receipts, not Git proof.
The later exact source verifier establishes the actual linked sparse Git roots.
OS/stdlib/Git are trusted; this is not a sandbox or resource authorization.
"""
import argparse
import base64
from dataclasses import asdict
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shlex
import stat
import subprocess
import sys
import time
from types import ModuleType


USER_ROOT = Path('/data/zefan')
REMOTE_BASE = USER_ROOT/'open-jev-v8-runtime-abi-20261003'
BOOTSTRAP = '/home/sigma/miniconda3/envs/llm_env/bin/python3.11'
BOOTSTRAP_SHA = '39b59ede3b21ac9578e12aac4f9372efc7b0dc198379a105e0d64adb52306b58'
VENV = '/data/zefan/open-jev-v8-linux-runtime-20261003/cpu-install-20261003T110248Z-6e0e0877072e2ff7/attempts/install-r1/venv'
CFG_SHA = '5abc75a1267db80e869b4129e41f6da1a7e010f1eae1d9328e96940c5c1837de'
SCIENCE_A = 'd8eeb3d1f8e8d8751476f102ab456170c277e86a'
NATIVE_A = '4b55c6e3f025fd92ec4396d5c61bb4dfe13cbda2'
PLAN_SHA = '984539a92f1aa37b93e58fea7df4511a1635e7e9f284531068bb5a0939ebc8be'
FREEZE_SHA = 'a710f79977ac582cdc9269368e3f442abb88e76e4bbfae89b962116ade213a5f'
NATIVE_DECL_SHA = '53e3cea8adc09fec82aea319775569ad4d487b3b0f88cd1f094653bc70de793d'
LOCK_SHA = 'd1f238a916dfdfbc8b89f3de4c28bb3b7220cdd97ecf609ebb726afab0ca8221'
LOADER_SHA = '6f33f86c9b37bd69612e7d0e79772b23c27540cae7a4191526fc47dbf75e2ede'
INSTALL_RECEIPT_SHA = 'ce1d36beb0ae2a92835e8c8e820b42827208b8af63096ab4449f5a249cbe6dba'
SELF = 'scripts/frontier_v8_runtime_transport.py'
OBSERVER = 'scripts/frontier_v8_runtime_abi.py'
SCOPE = 'frontier_v8_runtime_CPU_transport_only'
SOURCE_SECONDS = 60
SOURCE_CLEANUP_SECONDS = 10
SCRATCH_BUDGET_BYTES = 256 * 1024 * 1024
CAPTURE_REVIEW_SCOPE = 'frontier_v8_CPU_host_capture_prelaunch_only'
LAUNCH_REVIEW_SCOPE = 'frontier_v8_CPU_ABI_launch_prelaunch'
USER_PARENT_LAUNCHER = '"$@"; frontier_transport_status=$?; exit "$frontier_transport_status"'


class TransportError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise TransportError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()


def remote_command(own_source, mode, expected_payload_sha256):
    """Reviewed standard shell parent; construct argv without making an SSH call."""
    require(mode in ('--capture-host', '--launch', '--retrieve')
            and re.fullmatch(r'[0-9a-f]{64}', expected_payload_sha256), 'Declared transport mode/input hash required')
    argv = [BOOTSTRAP, '-B', '-I', '-S', '-c', own_source.decode(), mode,
            '--expected-payload-sha256', expected_payload_sha256]
    # The status/exit commands keep a user shell waiting after Python. Capture
    # still proves its actual kernel UID/ppid relationship rather than assuming it.
    return shlex.join(['/bin/sh', '-c', USER_PARENT_LAUNCHER, 'frontier-v8-user-parent', *argv])


PUBLIC_URL = 'https://github.com/Zefan-Cai/Open-Jev.git'
NATIVE_HELPER_SHA256 = '2d9edb599d48aa2c9e1e5971ce95ae833022622a9de3c8d1a1ca81f0f70debc2'
NONCE_KEY = 'FRONTIER_V8_PROCESS_NONCE'
GIT_OPTIONS = ['-c', 'credential.helper=', '-c', 'core.askPass=/bin/false',
               '-c', 'http.extraHeader=', '-c', 'http.extraHeader=Authorization:',
               '-c', 'http.proxy=',
               '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
               '-c', 'core.untrackedCache=false', '-c', 'protocol.file.allow=never',
               '-c', 'protocol.ext.allow=never']


def _regular_bytes(path):
    require(path.is_absolute() and '..' not in path.parts, 'Actual normalized absolute file required')
    for ancestor in (path, *path.parents):
        if stat.S_ISLNK(ancestor.lstat().st_mode):
            raise ValueError('source file or ancestor symlink refused')
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
            or not 0 <= before.st_size <= MAX_FILE_BYTES):
        raise ValueError('regular same-owner source leaf required')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if identity(os.fstat(descriptor)) != identity(before):
            raise ValueError('source leaf changed before open')
        with os.fdopen(descriptor, 'rb', closefd=False) as handle:
            raw = handle.read()
        if (identity(os.fstat(descriptor)) != identity(before)
                or identity(path.lstat()) != identity(before)):
            raise ValueError('source leaf changed during read')
        return raw
    finally:
        os.close(descriptor)


def _owned_directory(path, *, owner_start):
    for ancestor in reversed((path, *path.parents)):
        before = ancestor.lstat()
        if not stat.S_ISDIR(before.st_mode):
            raise ValueError('source root or ancestor is not a real directory')
        if ancestor == owner_start or ancestor.is_relative_to(owner_start):
            if before.st_uid != os.getuid():
                raise ValueError('per-user source preparation directory owner differs')
        descriptor = os.open(ancestor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            if identity(os.fstat(descriptor)) != identity(before):
                raise ValueError('source preparation ancestor changed during open')
        finally:
            os.close(descriptor)


def _owned_environment(declaration):
    nonce = os.environ.get(NONCE_KEY)
    if (not isinstance(nonce, str) or not re.fullmatch(r'[0-9a-f]{64}', nonce)
            or declaration['nonce'] != nonce
            or declaration['scope'] != 'fresh_owned_CPU_worker_only'):
        raise ValueError('source preparation must run inside its separately declared owned tree')
    # No inherited credential, proxy, Git, shell or Python configuration.
    # The primitive nonce is preserved for every Git descendant.
    return {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
            'CUDA_VISIBLE_DEVICES': '', 'NVIDIA_VISIBLE_DEVICES': 'none',
            NONCE_KEY: nonce, 'GIT_TERMINAL_PROMPT': '0',
            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_SYSTEM': '/dev/null',
            'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_ASKPASS': '/bin/false',
            'SSH_ASKPASS': '/bin/false', 'GIT_LFS_SKIP_SMUDGE': '1'}


def prepare_source_roots(spec, owned_declaration):
    """Final reviewed launcher calls this from the separately owned worker."""
    if spec['public_url'] != PUBLIC_URL or set(spec['roots']) != {'scientific', 'native', 'operational'}:
        raise ValueError('exact public source contract required')
    root = Path(spec['remote_root'])
    if (not root.is_absolute() or root.as_posix() != spec['remote_root']
            or '..' in root.parts or root.resolve(strict=True) != root):
        raise ValueError('fresh owned non-symlink root required')
    if not root.is_relative_to(USER_ROOT):
        raise ValueError('explicit per-user remote root required')
    _owned_directory(root, owner_start=USER_ROOT)
    preparation_directory = root/'source-preparation/process-r1'
    if spec['source_preparation_directory'] != str(preparation_directory):
        raise ValueError('exact separately owned source preparation directory required')
    _owned_directory(preparation_directory, owner_start=root)
    # The final launcher separately binds this helper's raw native-A bytes and
    # this worker's raw bytes to the prelaunch declaration before any import.
    if spec['native_helper_sha256'] != NATIVE_HELPER_SHA256:
        raise ValueError('immutable native-A helper binding differs')
    env = _owned_environment(owned_declaration)
    objectstore = root/'source-objectstore'
    commands = []

    def log_chunk(stream, start, end):
        path = preparation_directory/('worker.'+stream+'.log')
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(descriptor)
            output_fd = 1 if stream == 'stdout' else 2
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or (info.st_dev, info.st_ino) !=
                    (os.fstat(output_fd).st_dev, os.fstat(output_fd).st_ino)):
                raise ValueError('Git log must be the actual owned worker log')
            os.lseek(descriptor, start, os.SEEK_SET)
            chunks, remaining = [], end-start
            while remaining:
                raw = os.read(descriptor, min(remaining, 1024*1024))
                if not raw:
                    raise ValueError('truncated owned Git log segment')
                chunks.append(raw)
                remaining -= len(raw)
            return b''.join(chunks)
        finally:
            os.close(descriptor)

    def git(where, *args, input_bytes=None):
        argv = ['git', *GIT_OPTIONS, '-C', str(where), *args]
        print(json.dumps({'source_preparation_command_start': argv}), flush=True)
        sys.stderr.flush()
        starts = [os.lseek(fd, 0, os.SEEK_CUR) for fd in (1, 2)]
        # The child's exact bytes are written directly to guard-created logs;
        # partial output survives timeout/controller loss without a PIPE buffer.
        result = subprocess.run(argv, input=input_bytes, stdout=sys.stdout.buffer,
                                stderr=sys.stderr.buffer, env=env, check=False)
        ends = [os.lseek(fd, 0, os.SEEK_CUR) for fd in (1, 2)]
        stdout = log_chunk('stdout', starts[0], ends[0])
        stderr = log_chunk('stderr', starts[1], ends[1])
        commands.append({'argv': argv, 'returncode': result.returncode,
                         'stdout_log_byte_range': [starts[0], ends[0]],
                         'stderr_log_byte_range': [starts[1], ends[1]],
                         'stdout_bytes': len(stdout), 'stderr_bytes': len(stderr),
                         'stdout_sha256': hashlib.sha256(stdout).hexdigest(),
                         'stderr_sha256': hashlib.sha256(stderr).hexdigest()})
        print('\n'+json.dumps({'source_preparation_command': commands[-1]}), flush=True)
        if result.returncode:
            raise ValueError('public Git source preparation failed; request remains consumed')
        return stdout

    objectstore.mkdir(mode=0o700)
    _owned_directory(objectstore, owner_start=root)
    git(objectstore, 'init', '--bare', '--template=')
    # Persist task-specific overrides in the fresh common Git configuration,
    # because the pinned verifier intentionally removes GIT_* environment keys.
    for option, value in [('credential.helper', ''), ('core.askPass', '/bin/false'),
                          ('http.extraHeader', ''), ('http.proxy', ''),
                          ('core.hooksPath', '/dev/null'), ('protocol.file.allow', 'never'),
                          ('protocol.ext.allow', 'never')]:
        git(objectstore, 'config', option, value)
    git(objectstore, 'config', '--add', 'http.extraHeader', 'Authorization:')
    git(objectstore, 'remote', 'add', 'origin', PUBLIC_URL)
    git(objectstore, 'config', 'remote.origin.promisor', 'true')
    git(objectstore, 'config', 'remote.origin.partialCloneFilter', 'blob:none')
    commits = []
    for role in ('scientific', 'native', 'operational'):
        item = spec['roots'][role]
        commit = item['commit']
        if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit):
            raise ValueError('three fixed exact source commits required')
        if not isinstance(item['files_sha256'], dict) or not item['files_sha256']:
            raise ValueError('nonempty final source closure required')
        for name, digest in item['files_sha256'].items():
            relative(name)
            if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
                raise ValueError('exact source SHA256 required')
        commits.append(commit)
    git(objectstore, 'fetch', '--no-tags', '--depth=1', '--filter=blob:none', 'origin', *commits)
    sources = root/'sources'
    sources.mkdir(mode=0o700)
    _owned_directory(sources, owner_start=root)
    for role in ('scientific', 'native', 'operational'):
        item = spec['roots'][role]
        worktree = sources/role
        git(objectstore, 'worktree', 'add', '--no-checkout', '--detach', str(worktree), item['commit'])
        git(worktree, 'sparse-checkout', 'init', '--no-cone')
        patterns = ''.join('/'+name+'\n' for name in sorted(item['files_sha256'])).encode()
        git(worktree, 'sparse-checkout', 'set', '--no-cone', '--stdin', input_bytes=patterns)
        git(worktree, 'checkout', '--detach', item['commit'])
        _owned_directory(worktree, owner_start=root)
        if (git(worktree, 'rev-parse', '--show-toplevel').decode().strip() != str(worktree)
                or git(worktree, 'rev-parse', 'HEAD').decode().strip() != item['commit']
                or git(worktree, 'status', '--porcelain=v1', '-z', '--untracked-files=all',
                       '--ignored=matching')):
            raise ValueError('actual sparse source root/HEAD/clean status differs')
        for name, digest in item['files_sha256'].items():
            path = worktree/name
            raw = _regular_bytes(path)
            if (hashlib.sha256(raw).hexdigest() != digest
                    or git(worktree, 'show', item['commit']+':'+name) != raw):
                raise ValueError('source byte/blob/hash differs')
            _owned_directory(path.parent, owner_start=root)
    _owned_directory(root, owner_start=USER_ROOT)
    # Every declared blob is now local. The verifier's read-only Git calls must
    # fail for missing objects rather than perform a late partial-clone fetch.
    git(objectstore, 'config', 'remote.origin.promisor', 'false')
    return {'schema_version': 1, 'scope': 'separate_owned_public_Git_source_preparation',
            'public_url': PUBLIC_URL, 'roots': spec['roots'], 'commands': commands,
            'final_clean_three_Git_roots_created': True,
            'native_bootstrap_copy_is_final_Git_proof': False,
            'GPU_or_model_or_queue_authority': False}



MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024


def relative(value):
    if (not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.\-/]+', value)
            or Path(value).is_absolute() or Path(value).as_posix() != value
            or any(part in ('.', '..') for part in value.split('/'))):
        raise ValueError('literal normalized allowlisted relative path required')
    return value


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def open_root(value, expected_uid):
    path = Path(value)
    if (not path.is_absolute() or path.as_posix() != value
            or any(part in ('.', '..') for part in path.parts)):
        raise ValueError('normalized absolute artifact root required')
    # Walk from / with O_NOFOLLOW; ancestors need not share the user's owner.
    # The new artifact root and every descendant must have the captured UID.
    current = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in path.parts[1:]:
            before = os.stat(component, dir_fd=current, follow_symlinks=False)
            if not stat.S_ISDIR(before.st_mode):
                raise ValueError('non-directory or symlink root ancestor refused')
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                              dir_fd=current)
            if identity(before) != identity(os.fstat(next_fd)):
                os.close(next_fd)
                raise ValueError('root ancestor changed during open')
            os.close(current)
            current = next_fd
        if os.fstat(current).st_uid != expected_uid:
            raise ValueError('artifact root owner differs from fresh UID')
        return current
    except BaseException:
        os.close(current)
        raise


def read_leaf(root_fd, name, expected_uid):
    parts = relative(name).split('/')
    directories = [os.dup(root_fd)]
    links = []
    leaf_fd = None
    try:
        for component in parts[:-1]:
            before = os.stat(component, dir_fd=directories[-1], follow_symlinks=False)
            if not stat.S_ISDIR(before.st_mode) or before.st_uid != expected_uid:
                raise ValueError('artifact directory symlink/type/owner refused')
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                              dir_fd=directories[-1])
            if identity(before) != identity(os.fstat(next_fd)):
                os.close(next_fd)
                raise ValueError('artifact directory changed during open')
            links.append((directories[-1], component, identity(before)))
            directories.append(next_fd)
        before = os.stat(parts[-1], dir_fd=directories[-1], follow_symlinks=False)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != expected_uid
                or not 0 <= before.st_size <= MAX_FILE_BYTES):
            raise ValueError('regular same-owner bounded artifact required')
        leaf_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                          dir_fd=directories[-1])
        if identity(before) != identity(os.fstat(leaf_fd)):
            raise ValueError('artifact replaced before raw read')
        with os.fdopen(leaf_fd, 'rb', closefd=False) as handle:
            raw = handle.read(MAX_FILE_BYTES + 1)
        if (len(raw) != before.st_size or identity(before) != identity(os.fstat(leaf_fd))
                or identity(before) != identity(os.stat(parts[-1], dir_fd=directories[-1],
                                                       follow_symlinks=False))):
            raise ValueError('artifact changed during raw read')
        for parent_fd, component, original in links:
            if identity(os.stat(component, dir_fd=parent_fd, follow_symlinks=False)) != original:
                raise ValueError('artifact ancestor changed during raw read')
        return raw, {'dev': before.st_dev, 'ino': before.st_ino, 'mode': before.st_mode,
                     'uid': before.st_uid, 'gid': before.st_gid,
                     'bytes': len(raw), 'mtime_ns': before.st_mtime_ns,
                     'ctime_ns': before.st_ctime_ns,
                     'sha256': hashlib.sha256(raw).hexdigest()}
    finally:
        if leaf_fd is not None:
            os.close(leaf_fd)
        for descriptor in reversed(directories):
            os.close(descriptor)


def collect(remote_root, allowlist, fresh_uid):
    """Read only exact fixed candidates, retaining explicit failed-attempt gaps."""
    if (os.getuid() != fresh_uid or os.geteuid() != fresh_uid
            or not isinstance(allowlist, list) or not allowlist
            or len(set(allowlist)) != len(allowlist)):
        raise ValueError('fresh UID and exact unique allowlist required')
    for name in allowlist:
        relative(name)
    root_fd = open_root(remote_root, fresh_uid)
    original_root = identity(os.fstat(root_fd))
    files, missing, refused, total = {}, [], {}, 0
    try:
        for name in allowlist:
            try:
                raw, metadata = read_leaf(root_fd, name, fresh_uid)
                total += len(raw)
                if total > MAX_TOTAL_BYTES:
                    raise ValueError('exact raw retrieval total bound exceeded')
                files[name] = {**metadata, 'base64': base64.b64encode(raw).decode()}
            except FileNotFoundError:
                missing.append(name)
            except (OSError, ValueError) as error:
                refused[name] = {'error_type': type(error).__name__, 'reason': str(error)}
        reopened = open_root(remote_root, fresh_uid)
        try:
            if identity(os.fstat(root_fd)) != original_root or identity(os.fstat(reopened)) != original_root:
                raise ValueError('artifact root identity changed during exact retrieval')
        finally:
            os.close(reopened)
        return {'schema_version': 1, 'scope': 'exact_allowlisted_raw_retrieval_only',
                'remote_root': remote_root, 'fresh_uid': fresh_uid, 'allowlist': allowlist,
                'files': files, 'missing': missing, 'refused': refused,
                'total_raw_bytes': sum(item['bytes'] for item in files.values()),
                'remote_originals_modified': False, 'observer_or_worker_rerun': False,
                'observation_success_claimed': False}
    finally:
        os.close(root_fd)


def receive(packet, destination, expected_remote_root, expected_allowlist, fresh_remote_uid):
    """Decode and validate all bytes before exclusively creating a new local root."""
    if (packet['schema_version'] != 1 or packet['scope'] != 'exact_allowlisted_raw_retrieval_only'
            or packet['remote_root'] != expected_remote_root
            or packet['fresh_uid'] != fresh_remote_uid
            or packet['allowlist'] != expected_allowlist
            or packet['remote_originals_modified'] is not False
            or packet['observer_or_worker_rerun'] is not False):
        raise ValueError('exact retrieval context differs')
    files, missing, refused = packet['files'], packet['missing'], packet['refused']
    if (not isinstance(expected_allowlist, list)
            or len(set(expected_allowlist)) != len(expected_allowlist)
            or not isinstance(missing, list) or len(set(missing)) != len(missing)):
        raise ValueError('unique exact allowlist and missing path list required')
    sets = (set(files), set(missing), set(refused))
    if (any(left & right for i, left in enumerate(sets) for right in sets[i + 1:])
            or set().union(*sets) != set(expected_allowlist)):
        raise ValueError('retrieval categories must partition the exact allowlist')
    decoded, total = {}, 0
    for name, item in files.items():
        relative(name)
        if item['uid'] != fresh_remote_uid or not stat.S_ISREG(item['mode']):
            raise ValueError('remote artifact type/owner differs')
        raw = base64.b64decode(item['base64'], validate=True)
        total += len(raw)
        if (len(raw) != item['bytes'] or len(raw) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES
                or hashlib.sha256(raw).hexdigest() != item['sha256']):
            raise ValueError('decoded raw artifact hash/size differs')
        decoded[name] = raw
    if total != packet['total_raw_bytes']:
        raise ValueError('packet total raw byte count differs')
    path = Path(destination)
    if (not path.is_absolute() or path.as_posix() != destination
            or any(part in ('.', '..') for part in path.parts)):
        raise ValueError('fresh normalized absolute local output root required')
    parent_fd = open_root(str(path.parent), os.getuid())
    try:
        os.mkdir(path.name, mode=0o700, dir_fd=parent_fd)
    finally:
        os.close(parent_fd)
    root_fd = open_root(destination, os.getuid())
    try:
        for name, raw in decoded.items():
            parts = name.split('/')
            directory_fd = os.dup(root_fd)
            try:
                for component in parts[:-1]:
                    try:
                        os.mkdir(component, mode=0o700, dir_fd=directory_fd)
                    except FileExistsError:
                        pass
                    next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                      dir_fd=directory_fd)
                    if os.fstat(next_fd).st_uid != os.getuid():
                        os.close(next_fd)
                        raise ValueError('local output ancestor owner differs')
                    os.close(directory_fd)
                    directory_fd = next_fd
                descriptor = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                     0o600, dir_fd=directory_fd)
                with os.fdopen(descriptor, 'wb') as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        os.fsync(root_fd)
    finally:
        os.close(root_fd)
    return {'schema_version': 1, 'scope': 'local_exact_raw_artifact_binding',
            'remote_root': expected_remote_root, 'local_root': destination,
            'files': {name: {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                      for name, raw in decoded.items()},
            'missing': missing, 'refused': refused,
            'success_observation_claimed': False, 'observer_or_worker_rerun': False}


GATE_FIELDS = {'source_commit', 'main_commit', 'source_tree', 'main_tree',
    'transport_sha256', 'observer_sha256', 'receipts'}
GATE_RECEIPTS = ('source_review', 'CI', 'code_integration', 'prelaunch')
EXTERNAL = {'plan': 'inputs/external/plan.json', 'freeze': 'inputs/external/freeze.json',
    'native_declaration': 'inputs/external/native-declaration.json',
    'operational_declaration': 'inputs/external/operational-declaration.json'}
PROCESS_FILES = ('declaration.json', 'watchdog-receipt.json', 'worker.stdout.log',
                 'worker.stderr.log', 'watchdog.stderr.log')


def captured_module(path, raw, expected, alias):
    require(sha(raw) == expected and alias not in sys.modules, 'Captured bootstrap bytes differ')
    module = ModuleType(alias)
    module.__file__, module.__package__ = str(path), ''
    sys.modules[alias] = module
    try:
        exec(compile(raw, str(path), 'exec', dont_inherit=True), module.__dict__)
    except BaseException:
        sys.modules.pop(alias, None)
        raise
    return module


def own_source_bytes():
    if '__file__' in globals():
        return _regular_bytes(Path(__file__).absolute())
    require('-c' in sys.orig_argv, 'Exact committed source body required')
    return sys.orig_argv[sys.orig_argv.index('-c') + 1].encode()


def validate_gates(gates, own_source, *, prelaunch_scope=LAUNCH_REVIEW_SCOPE):
    require(isinstance(gates, dict) and set(gates) == GATE_FIELDS, 'Exact reviewed code gates required')
    for key in ('source_commit', 'main_commit', 'source_tree', 'main_tree'):
        require(isinstance(gates[key], str) and re.fullmatch(r'[0-9a-f]{40}', gates[key]),
                'Exact source/main Git identities required')
    require(gates['source_tree'] == gates['main_tree']
            and gates['transport_sha256'] == sha(own_source)
            and re.fullmatch(r'[0-9a-f]{64}', gates['observer_sha256']),
            'Source/main tree or captured transport identity differs')
    require(isinstance(gates['receipts'], dict) and set(gates['receipts']) == set(GATE_RECEIPTS),
            'Actual raw review/CI/integration/prelaunch receipts required')
    receipts = {name: json.loads(decode_copy(item)) for name, item in gates['receipts'].items()}
    expected_files = {SELF: gates['transport_sha256'], OBSERVER: gates['observer_sha256']}
    for name in ('source_review', 'prelaunch'):
        receipt = receipts[name]
        require(receipt['schema_version'] == 1 and receipt['source_commit'] == gates['source_commit']
                and receipt['status'].endswith('_review_passed') and receipt['failed'] == []
                and all(receipt['files_sha256'][path] == value for path, value in expected_files.items()),
                'Raw source/prelaunch review source bindings differ')
    require(prelaunch_scope in (CAPTURE_REVIEW_SCOPE, LAUNCH_REVIEW_SCOPE)
            and receipts['prelaunch']['scope'] == prelaunch_scope,
            'Separate capture-only or exact CPU launch prelaunch scope required')
    ci = receipts['CI']
    require(ci['schema_version'] == 1 and ci['source_commit'] == gates['source_commit']
            and isinstance(ci['checks'], list) and len(ci['checks']) == 4,
            'Actual exact-head required CI receipt differs')
    expected = {(event, 'portable ('+version+')') for event in ('push', 'pull_request')
                for version in ('3.10', '3.14')}
    require({(check['event'], check['name']) for check in ci['checks']} == expected
            and all(check['head_sha'] == gates['source_commit'] and check['status'] == 'completed'
                    and check['conclusion'] == 'success' and type(check['id']) is int
                    and check['id'] > 0 and type(check['run_attempt']) is int
                    and check['run_attempt'] > 0 for check in ci['checks']),
            'Required exact-source CI matrix did not pass')
    integrated = receipts['code_integration']
    require(integrated['schema_version'] == 1
            and integrated['source_commit'] == gates['source_commit']
            and integrated['main_commit'] == gates['main_commit']
            and integrated['source_tree_sha1'] == gates['source_tree']
            and integrated['main_tree_sha1'] == gates['main_tree']
            and integrated['source_pushed'] is True and integrated['main_integrated'] is True,
            'Actual pushed source/main integration receipt differs')
    # Validate these saved raw receipt identities/fields. The caller and its
    # independent local reviews remain trusted: this is no live GitHub status
    # query, proof of receipt authorship, model/resource authority or sandbox.
    return {name: decode_copy(item) for name, item in gates['receipts'].items()}


def decode_copy(item):
    require(isinstance(item, dict) and set(item) == {'base64', 'bytes', 'sha256'}
            and type(item['bytes']) is int and 0 <= item['bytes'] <= MAX_FILE_BYTES
            and isinstance(item['sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', item['sha256']),
            'Exact bounded captured-file binding required')
    raw = base64.b64decode(item['base64'], validate=True)
    require(len(raw) == item['bytes'] and sha(raw) == item['sha256'], 'Captured-file hash/size differs')
    return raw


def host_fact(native_raw):
    require(sys.platform == 'linux' and platform.machine() == 'x86_64'
            and sys.version_info[:2] == (3, 11) and os.getuid() == os.geteuid()
            and sys.flags.isolated == sys.flags.no_site == 1 and sys.dont_write_bytecode,
            'Fresh Linux x86_64 Python 3.11 -B -I -S required')
    actual = Path(sys.executable).resolve(strict=True)
    require(str(actual) == BOOTSTRAP and sha(_regular_bytes(actual)) == BOOTSTRAP_SHA,
            'Recorded resolved bootstrap identity differs')
    native = captured_module('<captured-native-A-host-reader>', native_raw,
                             NATIVE_HELPER_SHA256, '_transport_capture_native')
    try:
        controller = asdict(native.capture_identity(os.getpid()))
        parent = asdict(native.capture_identity(os.getppid()))
    finally:
        sys.modules.pop('_transport_capture_native', None)
    require(controller['ppid'] == parent['pid'] and controller['uid'] == parent['uid']
            and controller['boot_id'] == parent['boot_id']
            and controller['start_ticks'] >= parent['start_ticks'], 'Fresh capture ancestry differs')
    require(platform.node() == 'kwade5342000001', 'Declared N1-1 route hostname differs')
    _owned_directory(USER_ROOT, owner_start=USER_ROOT)
    storage = os.statvfs(USER_ROOT)
    available = storage.f_bavail * storage.f_frsize
    require(storage.f_frsize > 0 and available >= SCRATCH_BUDGET_BYTES,
            'Fresh per-user disk capacity is below the declared CPU scratch budget')
    return {'schema_version': 1, 'scope': 'fresh_read_only_host_capture_after_code_integration',
        'observed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'canonical_node_alias': 'ms-n1-1',
        'host': {'node_alias': 'N1-1', 'hostname': platform.node(),
                 'boot_id': controller['boot_id'], 'uid': os.getuid()},
        'controller': controller, 'parent': parent,
        'bootstrap': {'realpath': str(actual), 'sha256': BOOTSTRAP_SHA,
                      'python_version': list(sys.version_info[:3])},
        'startup': {'prefix': sys.prefix, 'base_prefix': sys.base_prefix,
                    'sys_path': list(sys.path), 'isolated': sys.flags.isolated,
                    'no_site': sys.flags.no_site, 'dont_write_bytecode': sys.dont_write_bytecode},
        'storage': {'path': str(USER_ROOT), 'block_bytes': storage.f_frsize,
                    'available_blocks': storage.f_bavail, 'available_bytes': available,
                    'required_new_scratch_bytes': SCRATCH_BUDGET_BYTES,
                    'live_disk_reservation': False},
        'copied_native_anchor_is_Git_proof': False,
        'historical_host_identity_used_as_current': False,
        'nonce_generated': False, 'request_consumed': False, 'resource_authority': False}


def capture_host(gates, own_source, native_raw):
    validate_gates(gates, own_source, prelaunch_scope=CAPTURE_REVIEW_SCOPE)
    return {**host_fact(native_raw), 'gates': gates}


def unsigned_payload_sha256(payload):
    """Bind final dynamic inputs without a self-referential review digest."""
    unsigned = json.loads(json_bytes(payload))
    unsigned['gates']['receipts'].pop('prelaunch')
    return sha(json_bytes(unsigned))


def validate_payload(payload, own_source):
    require(isinstance(payload, dict) and set(payload) == {'schema_version', 'scope', 'gates',
        'fresh_capture', 'fresh_capture_raw', 'remote_root', 'nonce', 'roots', 'copies'}
        and payload['schema_version'] == 1 and payload['scope'] == SCOPE,
        'Exact once-only CPU transport payload required')
    validate_gates(payload['gates'], own_source)
    root = Path(payload['remote_root'])
    require(root.is_absolute() and root.as_posix() == payload['remote_root']
            and root.parent == REMOTE_BASE and re.fullmatch(r'[A-Za-z0-9_.-]{1,127}', root.name)
            and root.name not in ('.', '..') and re.fullmatch(r'[0-9a-f]{64}', payload['nonce']),
            'Fresh per-user root and new declared nonce required')
    capture = payload['fresh_capture']
    captured_raw = decode_copy(payload['fresh_capture_raw'])
    require(json.loads(captured_raw) == capture, 'Original unchanged fresh capture bytes differ')
    validate_gates(capture['gates'], own_source, prelaunch_scope=CAPTURE_REVIEW_SCOPE)
    previous = {key: value for key, value in capture['gates'].items() if key != 'receipts'}
    latest = {key: value for key, value in payload['gates'].items() if key != 'receipts'}
    require(previous == latest and all(capture['gates']['receipts'][name] ==
            payload['gates']['receipts'][name] for name in GATE_RECEIPTS if name != 'prelaunch'),
            'Only the separately scoped prelaunch receipt may change after fresh capture')
    require(capture['schema_version'] == 1
            and capture['scope'] == 'fresh_read_only_host_capture_after_code_integration'
            and capture['nonce_generated'] is False
            and capture['request_consumed'] is False, 'Separate fresh post-integration capture required')
    storage = capture['storage']
    require(storage['path'] == str(USER_ROOT) and type(storage['block_bytes']) is int
            and type(storage['available_blocks']) is int and storage['block_bytes'] > 0
            and storage['available_bytes'] == storage['block_bytes'] * storage['available_blocks']
            and storage['available_bytes'] >= SCRATCH_BUDGET_BYTES
            and storage['required_new_scratch_bytes'] == SCRATCH_BUDGET_BYTES
            and storage['live_disk_reservation'] is False, 'Fresh captured CPU scratch capacity binding differs')
    require(isinstance(payload['copies'], dict), 'Exact copied input map required')
    names = {relative(name) for name in payload['copies']}
    fixed = {*EXTERNAL.values(), 'inputs/external/requirements.lock',
             'inputs/external/old-installation-receipt.json', 'inputs/prepared-data-mapping.json',
             'inputs/request.json', 'helpers/owned-process.py'}
    require(fixed <= names, 'Required external/copy/request input missing')
    raw = {name: decode_copy(payload['copies'][name]) for name in fixed}
    require(sha(raw[EXTERNAL['plan']]) == PLAN_SHA and sha(raw[EXTERNAL['freeze']]) == FREEZE_SHA
            and sha(raw[EXTERNAL['native_declaration']]) == NATIVE_DECL_SHA
            and sha(raw['inputs/external/requirements.lock']) == LOCK_SHA
            and sha(raw['inputs/external/old-installation-receipt.json']) == INSTALL_RECEIPT_SHA
            and sha(raw['helpers/owned-process.py']) == NATIVE_HELPER_SHA256,
            'Pinned immutable plan/freeze/native/lock/owned bytes differ')
    plan = json.loads(raw[EXTERNAL['plan']])
    native = json.loads(raw[EXTERNAL['native_declaration']])
    operational = json.loads(raw[EXTERNAL['operational_declaration']])
    files = {**plan['data_files_sha256'], 'manifest.json': plan['data_manifest_sha256']}
    require(len(files) == 14 and sum(name.endswith('.jsonl') for name in files) == 13,
            'Exact 13 prepared JSONL and manifest mapping required')
    data_names = {'inputs/prepared-data/'+relative(name) for name in files}
    require(names == fixed | data_names, 'Undeclared copied inputs rejected before reading them')
    raw.update({name: decode_copy(payload['copies'][name]) for name in data_names})
    mapping = {}
    for name, expected in files.items():
        body = raw['inputs/prepared-data/'+name]
        require(sha(body) == expected, 'Frozen prepared copy hash differs')
        mapping[name] = {'bytes': len(body), 'sha256': expected}
    require(json.loads(raw['inputs/prepared-data-mapping.json']) == mapping,
            'Separate prepared-data exact copy mapping differs')
    roots = payload['roots']
    require(set(roots) == {'scientific', 'native', 'operational'}
            and roots['scientific'] == {'commit': SCIENCE_A, 'files_sha256': plan['implementation_sha256']}
            and roots['native'] == {'commit': NATIVE_A, 'files_sha256': native['native_files_sha256']}
            and roots['operational'] == {'commit': payload['gates']['source_commit'],
                                        'files_sha256': operational['files_sha256']}
            and operational['source_commit'] == payload['gates']['source_commit']
            and operational['status'] == 'three_source_CPU_declaration'
            and operational['files_sha256'][SELF] == sha(own_source)
            and operational['files_sha256'][OBSERVER] == payload['gates']['observer_sha256'],
            'Three separately declared exact source closures differ')
    for entry in roots.values():
        require(entry['files_sha256'], 'Nonempty source closure required')
        for name, expected in entry['files_sha256'].items():
            relative(name)
            require(re.fullmatch(r'[0-9a-f]{64}', expected), 'Exact source leaf hash required')
    request = json.loads(raw['inputs/request.json'])
    require(set(request) == {'schema_version', 'scope', 'nonce', 'source_context', 'observer_sha256',
        'host', 'bootstrap', 'runtime', 'data_root', 'attempt_directory', 'work_seconds', 'cleanup_seconds'},
        'Exact separate observer request fields required')
    for key, maximum in (('work_seconds', 60), ('cleanup_seconds', 10)):
        require(type(request[key]) in (int, float) and math.isfinite(request[key])
                and 0 < request[key] <= maximum, 'Bounded observer worker/cleanup budget required')
    context = {role+'_root': str(root/'sources'/role) for role in roots}
    context.update({key: str(root/name) for key, name in EXTERNAL.items()})
    context.update(expected_operational_commit=payload['gates']['source_commit'],
        expected_native_declaration_sha256=NATIVE_DECL_SHA,
        expected_operational_declaration_sha256=sha(raw[EXTERNAL['operational_declaration']]))
    require(request['schema_version'] == 1 and request['scope'] == 'frontier_v8_runtime_CPU_ABI_only'
            and request['nonce'] == payload['nonce'] and request['source_context'] == context
            and request['observer_sha256'] == payload['gates']['observer_sha256']
            and request['host'] == capture['host'] and request['bootstrap'] == capture['bootstrap']
            and request['data_root'] == str(root/'inputs/prepared-data')
            and request['attempt_directory'] == str(root/'attempts/abi-r1')
            and request['runtime'] == {'venv': VENV, 'interpreter_realpath': BOOTSTRAP,
                'interpreter_sha256': BOOTSTRAP_SHA, 'pyvenv_cfg_sha256': CFG_SHA,
                'python_version': capture['bootstrap']['python_version']},
            'Fresh observer request/path/runtime binding differs')
    require(sum(map(len, raw.values())) <= MAX_TOTAL_BYTES, 'Transport captured input total too large')
    prelaunch = json.loads(decode_copy(payload['gates']['receipts']['prelaunch']))
    require(prelaunch['capture_sha256'] == sha(captured_raw)
            and prelaunch['request_sha256'] == sha(raw['inputs/request.json'])
            and prelaunch['nonce'] == payload['nonce'] and prelaunch['remote_root'] == str(root)
            and prelaunch['unsigned_payload_sha256'] == unsigned_payload_sha256(payload),
            'Final prelaunch review must bind the exact fresh capture/request/nonce/root/unsigned payload')
    return raw, request


def write_regular(root, name, raw, mode=0o400):
    parts = relative(name).split('/')
    directory = open_root(str(root), os.getuid())
    try:
        for component in parts[:-1]:
            try:
                os.mkdir(component, mode=0o700, dir_fd=directory)
            except FileExistsError:
                pass
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            require(os.fstat(next_fd).st_uid == os.getuid(), 'New output ancestor owner differs')
            os.close(directory)
            directory = next_fd
        descriptor = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             mode, dir_fd=directory)
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), mode)
        os.fsync(directory)
    finally:
        os.close(directory)


def read_regular(root, name, uid):
    descriptor = open_root(str(root), uid)
    try:
        return read_leaf(descriptor, name, uid)
    finally:
        os.close(descriptor)


def exact_allowlist(payload):
    names = set(payload['copies']) | {'inputs/gates/'+name+'.json' for name in GATE_RECEIPTS} | {'declaration.json', 'transport-request-consumed.json',
        'transport-completion-or-failure.json', 'source-context.json', 'inputs/transport-payload.json',
        'inputs/fresh-host-capture.json',
        'helpers/runtime-transport.py', 'source-preparation/result.json', 'source-verification.json',
        'attempts/abi-r1.consumed.json', 'attempts/abi-r1/receipt.json',
        'attempts/abi-r1/native-owned-process.py', 'attempts/abi-r1/pip.stdout.log',
        'attempts/abi-r1/pip.stderr.log', 'attempts/abi-r1/pip.result.json',
        'exact-artifact-manifest.json'}
    names.update(prefix+'/'+name for prefix in ('source-preparation/process-r1', 'attempts/abi-r1/process-r1')
                 for name in PROCESS_FILES)
    names.update('sources/'+role+'/'+relative(name) for role, entry in payload['roots'].items()
                 for name in entry['files_sha256'])
    return sorted(names)


def collect_artifacts(root, allowlist, uid):
    return collect(str(root), allowlist, uid)


def assert_source_child_owned(root, declaration):
    """The hidden CLI permits only this direct native-watchdog worker."""
    nonce = os.environ.get(NONCE_KEY)
    require(declaration['scope'] == 'fresh_owned_CPU_worker_only'
            and declaration['nonce'] == nonce and re.fullmatch(r'[0-9a-f]{64}', nonce or '')
            and declaration['source_sha256'] == NATIVE_HELPER_SHA256
            and declaration['cleanup_seconds'] == SOURCE_CLEANUP_SECONDS
            and type(declaration['deadline_monotonic']) in (int, float)
            and math.isfinite(declaration['deadline_monotonic'])
            and time.monotonic() < declaration['deadline_monotonic'] <= time.monotonic() + SOURCE_SECONDS,
            'Live bounded source worker declaration differs')
    helper = root/'helpers/owned-process.py'
    helper_raw, helper_info = read_regular(root, 'helpers/owned-process.py', os.getuid())
    require(stat.S_IMODE(helper_info['mode']) == 0o400, 'Readonly owned bootstrap copy required')
    native = captured_module(helper, helper_raw, NATIVE_HELPER_SHA256, '_transport_source_owned_check')
    try:
        controller = asdict(native.capture_identity(declaration['controller']['pid']))
        worker = asdict(native.capture_identity(os.getpid()))
        guard = asdict(native.capture_identity(worker['ppid']))
        require(controller == declaration['controller']
                and worker['ppid'] == guard['pid'] and guard['ppid'] == controller['pid']
                and controller['uid'] == guard['uid'] == worker['uid'] == os.getuid() == os.geteuid()
                and controller['boot_id'] == guard['boot_id'] == worker['boot_id']
                and controller['start_ticks'] <= guard['start_ticks'] <= worker['start_ticks']
                and guard['pgrp'] == guard['session'] == guard['pid']
                and worker['pgrp'] == worker['session'] == worker['pid'],
                'Actual source controller/guard/direct worker ancestry differs')
        argv = Path('/proc/%d/cmdline' % guard['pid']).read_bytes().split(b'\0')[:-1]
        expected = [BOOTSTRAP.encode(), b'-I', b'-S', str(helper).encode(), b'--watchdog',
                    str(root/'source-preparation/process-r1/declaration.json').encode(), b'--channel-fd']
        require(len(argv) == 8 and argv[:7] == expected and argv[7].isdigit(),
                'Actual native source guard argv/execution-copy origin differs')
        require(asdict(native.capture_identity(controller['pid'])) == controller
                and asdict(native.capture_identity(guard['pid'])) == guard
                and asdict(native.capture_identity(worker['pid'])) == worker
                and read_regular(root, 'helpers/owned-process.py', os.getuid())[0] == helper_raw,
                'Source ownership or bootstrap bytes changed during checks')
        return {'controller': controller, 'guard': guard, 'worker': worker,
                'source_guard_copy_sha256': NATIVE_HELPER_SHA256,
                'direct_native_watchdog_worker_verified': True}
    finally:
        sys.modules.pop('_transport_source_owned_check', None)


def normalize_transport_file_cache(own_source):
    """Remove only this authenticated file entry's CPython negative cache."""
    if '__file__' not in globals():
        return {'removed_authenticated_transport_file_negative_cache': False,
                'path': None, 'before_present': False, 'after_present': False}
    path = str(Path(__file__).absolute())
    require(_regular_bytes(Path(path)) == own_source, 'Transport entry source changed before observer')
    removed = path in sys.path_importer_cache
    if removed:
        require(sys.path_importer_cache[path] is None, 'Positive transport-entry importer cache refused')
        del sys.path_importer_cache[path]
    return {'removed_authenticated_transport_file_negative_cache': removed,
            'path': path, 'before_present': removed, 'after_present': path in sys.path_importer_cache}


def launch(payload, own_source, *, payload_raw=None):
    raw, request = validate_payload(payload, own_source)
    if payload_raw is None:
        payload_raw = json_bytes(payload)
    require(isinstance(payload_raw, bytes) and len(payload_raw) <= MAX_TOTAL_BYTES
            and json.loads(payload_raw) == payload, 'Original transport payload bytes differ')
    current = host_fact(raw['helpers/owned-process.py'])
    require(current['host'] == payload['fresh_capture']['host']
            and current['bootstrap'] == payload['fresh_capture']['bootstrap'],
            'Fresh captured host continuity lost before new request')
    _owned_directory(USER_ROOT, owner_start=USER_ROOT)
    try:
        REMOTE_BASE.mkdir(mode=0o700)
    except FileExistsError:
        pass
    _owned_directory(REMOTE_BASE, owner_start=USER_ROOT)
    root = Path(payload['remote_root'])
    root.mkdir(mode=0o700)  # An existing root or symlink is permanently refused.
    allowlist = exact_allowlist(payload)
    declaration = {'schema_version': 1, 'scope': SCOPE, 'remote_root': str(root),
        'nonce': payload['nonce'], 'gates': payload['gates'], 'fresh_host': current,
        'payload_sha256': sha(payload_raw), 'request_sha256': sha(raw['inputs/request.json']),
        'allowlist': allowlist, 'allowlist_sha256': sha(json_bytes(allowlist)),
        'native_bootstrap_copy_is_actual_Git_proof': False,
        'capture_sha256': sha(decode_copy(payload['fresh_capture_raw'])),
        'fresh_scratch_storage': current['storage'],
        'source_preparation_seconds': SOURCE_SECONDS, 'source_preparation_cleanup_seconds': SOURCE_CLEANUP_SECONDS,
        'source_verifier_seconds': 30, 'observer_preflight_seconds': 30,
        'observer_postflight_seconds': 30, 'ABI_worker_maximum_seconds': 60,
        'ABI_cleanup_maximum_seconds': 10, 'outer_transport_SSH_seconds': 360,
        'outer_transport_deadline_is_remote_cleanup_proof': False, 'resource_authority': False}
    result = {'schema_version': 1, 'scope': SCOPE, 'status': 'transport_failed_consumed_no_retry',
              'nonce': payload['nonce'], 'remote_root': str(root),
              'model_calls': 0, 'GPU_actions': 0, 'installations': 0, 'queue_actions': 0,
              'execution_available': False, 'resource_authority': False}
    write_regular(root, 'transport-request-consumed.json', json_bytes({
        'schema_version': 1, 'status': 'one_transport_request_consumed_no_retry',
        'nonce': payload['nonce'], 'payload_sha256': sha(payload_raw), 'gates': payload['gates']}))
    print(json.dumps({'transport_retrieval_binding': {
        'remote_root': str(root), 'declaration_sha256': sha(json_bytes(declaration)),
        'allowlist_sha256': declaration['allowlist_sha256'], 'payload_sha256': sha(payload_raw)}},
        sort_keys=True, allow_nan=False), flush=True)
    try:
        write_regular(root, 'declaration.json', json_bytes(declaration))
        write_regular(root, 'inputs/transport-payload.json', payload_raw)
        write_regular(root, 'inputs/fresh-host-capture.json', decode_copy(payload['fresh_capture_raw']))
        write_regular(root, 'helpers/runtime-transport.py', own_source)
        for name, body in raw.items():
            write_regular(root, name, body)
        for name, item in payload['gates']['receipts'].items():
            write_regular(root, 'inputs/gates/'+name+'.json', decode_copy(item))
        write_regular(root, 'source-context.json', json_bytes(request['source_context']))
        (root/'source-preparation').mkdir(mode=0o700)
        (root/'attempts').mkdir(mode=0o700)
        helper = root/'helpers/owned-process.py'
        native = captured_module(helper, raw['helpers/owned-process.py'], NATIVE_HELPER_SHA256, '_transport_native')
        try:
            proof = native.run_owned_cpu_worker([BOOTSTRAP, '-B', '-I', '-S',
                str(root/'helpers/runtime-transport.py'), '--source-child',
                '--payload', str(root/'inputs/transport-payload.json'), '--expected-payload-sha256', sha(payload_raw)],
                attempt_directory=root/'source-preparation/process-r1',
                timeout_seconds=SOURCE_SECONDS, cleanup_seconds=SOURCE_CLEANUP_SECONDS)
            write_regular(root, 'source-preparation/result.json', json_bytes(proof))
        finally:
            sys.modules.pop('_transport_native', None)
        require(read_regular(root, 'helpers/runtime-transport.py', os.getuid())[0] == own_source
                and read_regular(root, 'sources/operational/'+SELF, os.getuid())[0] == own_source,
                'Copied and actual Git transport source identities differ')
        observer_raw = read_regular(root, 'sources/operational/'+OBSERVER, os.getuid())[0]
        observer_path = root/'sources/operational'/OBSERVER
        observer = captured_module(observer_path, observer_raw, payload['gates']['observer_sha256'],
                                   '_transport_observer')
        try:
            loader_raw = read_regular(root, 'sources/operational/scripts/frontier_v8_source_loader.py', os.getuid())[0]
            loader = captured_module(root/'sources/operational/scripts/frontier_v8_source_loader.py',
                                     loader_raw, LOADER_SHA, '_transport_source_verifier')
            try:
                with observer.controller_preflight_budget():
                    verified = loader.verify_three_sources(request['source_context'])
                write_regular(root, 'source-verification.json', json_bytes(verified))
            finally:
                sys.modules.pop('_transport_source_verifier', None)
            result['startup_cache_normalization'] = normalize_transport_file_cache(own_source)
            observation = observer.observe_cpu(str(root/'inputs/request.json'), sha(raw['inputs/request.json']))
            require(observation['status'] == 'CPU_runtime_ABI_observation_complete', 'CPU observer did not complete')
            result.update(status='CPU_transport_observation_complete', source_process_proof=proof,
                          observer_receipt_sha256=sha(read_regular(root, 'attempts/abi-r1/receipt.json', os.getuid())[0]))
        finally:
            sys.modules.pop('_transport_observer', None)
    except BaseException as error:
        result['error'] = str(error)
        if getattr(error, 'receipt', None) is not None:
            result['process_proof'] = error.receipt
        raise
    finally:
        write_regular(root, 'transport-completion-or-failure.json', json_bytes(result))
        packet = collect_artifacts(root, [name for name in allowlist if name != 'exact-artifact-manifest.json'], os.getuid())
        manifest = {key: value for key, value in packet.items() if key != 'files'}
        manifest['files'] = {name: {key: value for key, value in item.items() if key != 'base64'}
                             for name, item in packet['files'].items()}
        write_regular(root, 'exact-artifact-manifest.json', json_bytes(manifest))
    return {'result': result, 'declaration_sha256': sha(json_bytes(declaration)),
            'allowlist_sha256': declaration['allowlist_sha256']}


def execute(*args, **kwargs):
    raise TransportError('Model execution is closed; CPU transport grants no model/resource authority')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for name in ('capture-host', 'launch', 'source-child', 'retrieve', 'execute'):
        modes.add_argument('--'+name, action='store_true')
    parser.add_argument('--payload')
    parser.add_argument('--expected-payload-sha256')
    args = parser.parse_args(argv)
    if args.execute:
        execute()  # Closed before stdin/path/package/runtime handling.
    require(sys.flags.isolated == sys.flags.no_site == 1 and sys.dont_write_bytecode,
            'Fresh transport -B -I -S required')
    require(re.fullmatch(r'[0-9a-f]{64}', args.expected_payload_sha256 or ''), 'Exact input hash required')
    body = _regular_bytes(Path(args.payload)) if args.payload else sys.stdin.buffer.read(MAX_TOTAL_BYTES+1)
    require(len(body) <= MAX_TOTAL_BYTES and sha(body) == args.expected_payload_sha256, 'Exact bounded input bytes differ')
    payload = json.loads(body)
    own_source = own_source_bytes()
    if args.capture_host:
        require(set(payload) == {'schema_version', 'scope', 'gates', 'native_helper'}
                and payload['schema_version'] == 1 and payload['scope'] == SCOPE, 'Exact capture input required')
        result = capture_host(payload['gates'], own_source, decode_copy(payload['native_helper']))
    elif args.launch:
        result = launch(payload, own_source, payload_raw=body)
    elif args.source_child:
        validate_payload(payload, own_source)
        root = Path(payload['remote_root'])
        declaration = json.loads(read_regular(root, 'source-preparation/process-r1/declaration.json', os.getuid())[0])
        require(declaration['argv'] == [BOOTSTRAP, '-B', '-I', '-S', str(root/'helpers/runtime-transport.py'),
                '--source-child', '--payload', str(root/'inputs/transport-payload.json'),
                '--expected-payload-sha256', args.expected_payload_sha256]
                and declaration['source_sha256'] == NATIVE_HELPER_SHA256,
                'Separate native-owned source preparation declaration differs')
        ownership = assert_source_child_owned(root, declaration)
        result = prepare_source_roots({'public_url': PUBLIC_URL, 'remote_root': str(root),
            'roots': payload['roots'], 'native_helper_sha256': NATIVE_HELPER_SHA256,
            'source_preparation_directory': str(root/'source-preparation/process-r1')}, declaration)
        result['actual_source_child_ownership'] = ownership
    else:
        require(set(payload) == {'schema_version', 'scope', 'transport_payload', 'expected_declaration_sha256'}
                and payload['schema_version'] == 1 and payload['scope'] == SCOPE, 'Exact retrieval input required')
        original_raw = decode_copy(payload['transport_payload'])
        original = json.loads(original_raw)
        validate_payload(original, own_source)
        root = Path(original['remote_root'])
        previous = original['fresh_capture']['host']
        require(previous['uid'] == os.getuid() == os.geteuid() and previous['hostname'] == platform.node(),
                'Exact retrieval user/host differs')
        expected = payload['expected_declaration_sha256']
        require(expected is None or re.fullmatch(r'[0-9a-f]{64}', expected), 'Declared original receipt hash required')
        # Derive candidates from the already reviewed original launch payload,
        # never a partially written/corrupt remote declaration or directory walk.
        result = collect_artifacts(root, exact_allowlist(original), os.getuid())
        declaration = result['files'].get('declaration.json')
        current_boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        result['retrieval_host'] = {'hostname': platform.node(), 'uid': os.getuid(), 'boot_id': current_boot}
        result['launch_boot_unchanged'] = current_boot == previous['boot_id']
        result['expected_declaration_sha256'] = expected
        result['declaration_original_hash_matches'] = (declaration['sha256'] == expected
            if declaration is not None and expected is not None else None)
        result['original_transport_payload_sha256'] = sha(original_raw)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
