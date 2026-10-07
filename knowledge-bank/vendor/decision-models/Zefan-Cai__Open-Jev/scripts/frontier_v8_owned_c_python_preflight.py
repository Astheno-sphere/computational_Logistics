"""One fixed owned C -> Python readonly CPU metadata boundary; no model route."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from types import ModuleType


SCOPE = 'frontier_v8_owned_C_fixed_Python_readonly_metadata_CPU_fixture'
HELPER_SHA = '1bcda91a4ac9ab50fe051b140fd7ba0fae649c257b45674d1ab15c2bb9a69412'
TOOLCHAIN_SHA = '2175f96e939993db69eb14348fa3115ae583416a1d38307f38f23bd378d003c0'
LINKAGE_SHA = '3374d4ed4ef1bafa38d8f4340ffcc042ee396d966228a682adf890182108b47c'
LOCK_SHA = 'd1f238a916dfdfbc8b89f3de4c28bb3b7220cdd97ecf609ebb726afab0ca8221'
SCIENCE_A = 'd8eeb3d1f8e8d8751476f102ab456170c277e86a'
NATIVE_A = '4b55c6e3f025fd92ec4396d5c61bb4dfe13cbda2'
C_NAMES = ('frontier_v8_owned_c_python_preflight_guardian.c',
           'frontier_v8_owned_c_python_preflight_protocol.h')
WORKER_NAME = 'frontier_v8_python_runtime_preflight.py'
NODES = ('N1-1', 'N1-3', 'N4-1', 'N4-2', 'N4-3', 'N4-4')
AUTHORITY = dict.fromkeys(('functional_containment_verified', 'containment_available',
    'execution_available', 'resource_authority', 'model_runtime_ABI_observed',
    'production_controller_guard_completed', 'GPU_or_foreign_restore'), False)
SUCCESS = ('fixed_Python_exec_transition_observed',
           'fixed_readonly_76_metadata_six_positions_observed',
           'fixed_normal_Python_reap_observed', 'fixed_Python_worker_loss_reap_observed')
FIELDS = {'schema_version', 'scope', 'case', 'nonce', 'input_kind', 'python_version',
          'runtime', 'lock', 'authority', 'host', 'sources', 'attempt_directory',
          'bootstrap', 'source_A', 'scientific_A', 'native_A'}
MAX_SOURCE = 1024 * 1024
MAX_BYTES = 8 * 1024 * 1024
MAX_INTERPRETER = 64 * 1024 * 1024
MAX_DATA = 256 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def parse_python_interpreter(body, linkage):
    """Describe an actual bounded header view; full file binding stays separate."""
    require(type(body) is bytes and 64 <= len(body) <= MAX_INTERPRETER,
            'Bounded complete captured Python ELF required')
    view = body[:MAX_BYTES]
    return {**linkage.parse_elf_product(view), 'captured_bytes': len(body),
            'captured_sha256': digest(body), 'header_view_bytes': len(view),
            'header_view_sha256': digest(view)}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def closed_json(body):
    return json.loads(body, object_pairs_hook=unique_object,
                      parse_constant=lambda value: require(False, 'Nonfinite JSON'))


def hex_sha(value):
    return type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def absolute_path(value):
    require(type(value) is str and all(32 <= ord(char) <= 126 for char in value),
            'Actual single-line path required')
    path = Path(value)
    require(path.is_absolute() and path.as_posix() == value and '..' not in path.parts,
            'Normalized absolute path required')
    require(not any(path.is_relative_to(Path(p)) for p in ('/proc', '/sys', '/dev')),
            'Nonvirtual input/output path required')
    return path


def identity(info):
    return [getattr(info, key) for key in ('st_dev', 'st_ino', 'st_mode', 'st_uid',
            'st_size', 'st_mtime_ns', 'st_ctime_ns')]


def captured_regular(value, limit):
    """No-follow ancestry traversal for the first pure helper's capture."""
    path = absolute_path(str(value))
    parent, fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC), None
    try:
        for part in path.parent.parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                              dir_fd=parent)
            os.close(parent)
            parent = next_fd
        fd = os.open(path.name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
                     dir_fd=parent)
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_size <= limit, 'Bounded regular input')
        chunks, count = [], 0
        while count <= limit:
            chunk = os.read(fd, min(65536, limit + 1 - count))
            if not chunk:
                break
            chunks.append(chunk)
            count += len(chunk)
        require(count <= limit and identity(os.fstat(fd)) == identity(before)
                and identity(os.stat(path.name, dir_fd=parent, follow_symlinks=False)) == identity(before),
                'Captured input changed')
        return b''.join(chunks), identity(before)
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent)


def load_utilities():
    root = absolute_path(__file__).parent
    result = []
    for name, expected, alias in (
        ('frontier_v8_containment_capability.py', HELPER_SHA, 'frontier_python_preflight_identity'),
        ('frontier_v8_c_toolchain.py', TOOLCHAIN_SHA, 'frontier_python_preflight_compiler'),
        ('frontier_v8_owned_c_selfcheck.py', LINKAGE_SHA, 'frontier_python_preflight_linkage')):
        path = root / name
        body, before = captured_regular(path, MAX_SOURCE)
        require(digest(body) == expected and alias not in sys.modules,
                'Pinned pure utility bytes/cache differ')
        module = ModuleType(alias)
        module.__file__, module.__package__ = str(path), None
        exec(compile(body, str(path), 'exec', dont_inherit=True), module.__dict__)
        module._captured_bytes, module._captured_identity = body, tuple(before)
        result.append(module)
    return tuple(result)


def parse_request(body, expected_hash, source_hashes):
    require(type(body) is bytes and len(body) <= 65536 and hex_sha(expected_hash)
            and digest(body) == expected_hash, 'Exact bounded fresh request required')
    row = closed_json(body)
    require(type(row) is dict and set(row) == FIELDS and type(row['schema_version']) is int
            and row['schema_version'] == 1 and row['scope'] == SCOPE
            and row['input_kind'] == 'real_readonly_runtime', 'Exact live readonly scope; fixture route refused')
    require(type(row['case']) is str and row['case'] in ('normal', 'worker_loss')
            and hex_sha(row['nonce']), 'Closed fresh case/nonce required')
    require(type(row['authority']) is dict and set(row['authority']) == set(AUTHORITY)
            and all(value is False for value in row['authority'].values()), 'Broad authority must stay false')
    require(type(row['sources']) is dict and set(row['sources']) == {
                'observer_sha256', 'worker_sha256', 'c_sources_sha256',
                'identity_helper_sha256', 'toolchain_sha256', 'linkage_sha256'}
            and row['sources'] == source_hashes
            and row['sources']['identity_helper_sha256'] == HELPER_SHA
            and row['sources']['toolchain_sha256'] == TOOLCHAIN_SHA
            and row['sources']['linkage_sha256'] == LINKAGE_SHA
            and type(row['sources']['c_sources_sha256']) is dict
            and set(row['sources']['c_sources_sha256']) == set(C_NAMES)
            and all(hex_sha(v) for v in row['sources']['c_sources_sha256'].values())
            and hex_sha(row['sources']['observer_sha256']) and hex_sha(row['sources']['worker_sha256']),
            'Exact new source and selected pure utility hashes required')
    require(row['scientific_A'] == SCIENCE_A and row['native_A'] == NATIVE_A
            and type(row['source_A']) is str and re.fullmatch(r'[0-9a-f]{40}', row['source_A']),
            'Distinct frozen scientific/native pins and operational source declaration required')
    version = row['python_version']
    require(type(version) is list and len(version) == 3 and all(type(v) is int and 0 <= v <= 65535 for v in version)
            and version[:2] == [3, 11], 'Declared exact Python3.11 runtime required')
    runtime = row['runtime']
    require(type(runtime) is dict and set(runtime) == {'venv_root', 'config', 'site', 'alias',
            'interpreter', 'stdlib', 'lib_dynload', 'stdlib_zip'}, 'Closed readonly runtime inputs')
    venv = absolute_path(runtime['venv_root'])
    require(str(venv).startswith('/data/zefan/open-jev-v8-linux-runtime-20261003/'),
            'Only existing PR27 readonly venv input')
    require(type(runtime['config']) is dict and set(runtime['config']) == {'path', 'sha256'}
            and runtime['config']['path'] == str(venv / 'pyvenv.cfg')
            and hex_sha(runtime['config']['sha256']), 'Exact readonly config binding')
    require(type(runtime['interpreter']) is dict and set(runtime['interpreter']) == {'path', 'sha256'}
            and hex_sha(runtime['interpreter']['sha256']), 'Exact canonical ELF binding')
    absolute_path(runtime['interpreter']['path'])
    require(runtime['site'] == str(venv / 'lib/python3.11/site-packages')
            and runtime['alias'] == str(venv / 'bin/python'), 'Exact separate site and alias positions')
    for field in ('stdlib', 'lib_dynload', 'stdlib_zip'):
        absolute_path(runtime[field])
    require(type(row['lock']) is dict and set(row['lock']) == {'path', 'sha256'}
            and row['lock']['sha256'] == LOCK_SHA, 'Frozen76 lock binding required')
    absolute_path(row['lock']['path'])
    host = row['host']
    require(type(host) is dict and set(host) == {'node_alias', 'hostname', 'boot_id', 'uid'}
            and host['node_alias'] in NODES and type(host['hostname']) is str and host['hostname']
            and type(host['uid']) is int and host['uid'] >= 0
            and type(host['boot_id']) is str and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', host['boot_id']),
            'Exact approved host identity required')
    bootstrap = row['bootstrap']
    require(type(bootstrap) is dict and set(bootstrap) == {'path', 'sha256', 'python_version'}
            and hex_sha(bootstrap['sha256']) and type(bootstrap['python_version']) is list
            and len(bootstrap['python_version']) == 3
            and all(type(v) is int and 0 <= v <= 65535 for v in bootstrap['python_version']),
            'Exact observer bootstrap identity required')
    absolute_path(bootstrap['path'])
    attempt = absolute_path(row['attempt_directory'])
    prefix = 'open-jev-v8-owned-python-preflight-bridge-' + row['case'] + '-'
    require(attempt.name == 'attempt-r1' and attempt.parent.parent == Path('/data/zefan')
            and attempt.parent.name.startswith(prefix) and attempt.parent.name.endswith('-' + row['nonce'][:16]),
            'Fresh separate once-only output namespace required')
    return row


def build_product(source, header, backend, utility, linkage, record):
    """Compile captured CPP and link one fresh guardian; never an old product."""
    record.update({'status': 'failed', 'link_attempts': 0})
    build = record['compile_leg'] = utility.run_toolchain(source, backend)
    require(build['status'] == 'success' and str(header) in build['headers'],
            'Fresh C compile and exact new protocol header required')
    cpp, _ = backend.read_output('preprocess.stdout', MAX_BYTES)
    build['cpp_facts']['extra_header_expressions'] = parse_extra_cpp(cpp)
    compiler, obj = build['compiler'], backend.root / 'probe.o'
    product = backend.root / 'python-preflight-guardian'
    record['link_attempts'] = 1
    link = record['link'] = backend.run('link', [compiler['path'], str(obj),
        '-Wl,-Map,' + str(backend.root / 'link.map'), '-o', str(product)])
    require(link['status'] == 'success', 'Fresh fixed guardian link failed')
    raw, map_row = backend.read_output('link.map', MAX_BYTES)
    links, total = {}, 0
    for path in linkage.parse_link_map(raw, obj):
        item = links[path] = backend.snapshot(os.path.realpath(path), utility.MAX_DRIVER)
        total += item['bytes']
        require(total <= utility.MAX_HEADERS_TOTAL, 'Postlink input inventory limit')
    raw, product_row = backend.read_output(product.name, MAX_BYTES)
    require(product_row['identity'][2] & 0o111, 'Executable new guardian mode required')
    record['product'] = {**product_row, **linkage.parse_elf_product(raw)}
    require(all(record['product'][key] == build['object'][key]
                for key in ('elf_class', 'data_encoding', 'machine')), 'Object/product descriptor drift')
    interpreter_path = record['product']['interpreter']
    interpreter = record['interpreter'] = backend.snapshot(os.path.realpath(interpreter_path), utility.MAX_DRIVER)
    record['postlink_inputs'] = links
    bindings = record['output_bindings'] = {**build['output_bindings'], 'link.map': map_row,
        product.name: product_row, 'link.stdout': link['stdout'], 'link.stderr': link['stderr']}

    def recheck():
        for path, item in {**build['headers'], **links}.items():
            require(os.path.realpath(path) == item['path']
                    and backend.snapshot(item['path'], utility.MAX_DRIVER) == item,
                    'Source/header/postlink input snapshot drift')
        require(os.path.realpath(compiler['role_path']) == compiler['path']
                and all(backend.snapshot(compiler['path'], utility.MAX_DRIVER)[key] == compiler[key]
                        for key in ('path', 'sha256', 'identity', 'bytes')),
                'Controlled compiler role drift')
        require(os.path.realpath(interpreter_path) == interpreter['path']
                and backend.snapshot(interpreter['path'], utility.MAX_DRIVER) == interpreter,
                'New guardian ELF interpreter drift')
        for name, item in bindings.items():
            require(backend.read_output(name, MAX_BYTES)[1] == item, 'Captured build output drift')
    recheck()
    record['status'] = 'success'
    return recheck


def run_runtime(backend, argv):
    """New40s direct-G observation. Does not guarantee descendant cleanup."""
    result = {'label': 'runtime', 'argv': argv, 'status': 'failed', 'returncode': None,
              'timed_out': False, 'direct_child_pid': None, 'kill_attempted': False,
              'reap_completed': False, 'kill_error': None, 'reap_error': None,
              'descendant_cleanup_verified': False}
    streams = []
    try:
        for suffix in ('stdout', 'stderr'):
            fd = os.open('runtime.' + suffix, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                         | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=backend.root_fd)
            streams.append(os.fdopen(fd, 'wb'))
        env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
               'CUDA_VISIBLE_DEVICES': '', 'NVIDIA_VISIBLE_DEVICES': 'none',
               'PIP_CONFIG_FILE': '/dev/null'}
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=streams[0],
            stderr=streams[1], cwd=str(backend.root), env=env, close_fds=True)
        result['direct_child_pid'] = child.pid
        try:
            result['returncode'] = child.wait(timeout=40)
            result['reap_completed'] = True
        except subprocess.TimeoutExpired:
            result['timed_out'], result['kill_attempted'] = True, True
            try:
                child.kill()
            except Exception as error:
                result['kill_error'] = {'type': type(error).__name__, 'message': str(error)}
            try:
                result['returncode'] = child.wait(timeout=2)
                result['reap_completed'] = True
            except Exception as error:
                result['reap_error'] = {'type': type(error).__name__, 'message': str(error)}
        if not result['timed_out'] and result['returncode'] == 0:
            result['status'] = 'success'
    except Exception as error:
        result['error'] = {'type': type(error).__name__, 'message': str(error)}
    finally:
        for stream in streams:
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
    for suffix in ('stdout', 'stderr'):
        result[suffix] = backend.read_output('runtime.' + suffix, MAX_BYTES)[1]
    backend.helper.write_json_at(backend.root_fd, 'runtime.json', result)
    return result


EXTRA_HEADERS = ('pidfd_send_signal', 'f_getfd', 'f_setfd', 'fd_cloexec', 'o_cloexec',
    'o_nofollow', 'o_nonblock', 'f_getfl', 'ebadf', 'eagain', 'eintr', 'esrch',
    'sigkill', 'sigpipe', 'pollin', 'pollnval', 'pipe_buf', 'rlimit_core', 'rlimit_cpu')
NATIVE_FIELDS = {'schema_version', 'scope', 'case', 'nonce', 'input_kind', 'fault',
    'native_success', 'error', 't0_ns', 'deadlines', 'runtime_argv', 'python_exec_argv',
    'kernel_python_argv', 'expected_hashes', 'products', 'identities', 'exec', 'handle',
    'signal', 'wait', 'polls', 'fd_ledger', 'fd_flags', 'protocol', 'python_body', 'times', 'native_facts'}
TIME_NAMES = ('pre_ready_ns', 'exec_go_ns', 'ready_ns', 'data_complete_ns', 'arm_ns',
              'ack_ns', 'primary_ns', 'terminal_ns', 'reap_ns', 'fd_complete_ns', 'final_ns')
OFFSETS = {'work_ns': 20, 'cleanup_ns': 25, 'terminal_ns': 28, 'total_ns': 30, 'expiry_ns': 35}


def parse_extra_cpp(body):
    """Preserve fresh C expressions; never evaluate C arithmetic in Python."""
    text = body.decode('ascii')
    result = {}
    token = r'(?:0[xX][0-9a-fA-F]+|[0-9]+)[uUlL]*|<<|>>|[()+\-*/%~&|^]'
    for name in EXTRA_HEADERS:
        marker = 'frontier_v8_header_' + name
        require(len(re.findall(r'\b' + marker + r'\b', text)) == 1, 'Unique fresh header declaration required')
        match = re.search(r'\bconst\s+long\s+' + marker + r'\s*=\s*([^;]+);', text)
        require(match is not None and 0 < len(match[1]) <= 1024, 'Closed expanded header expression required')
        expression = match[1].strip()
        enum = {'rlimit_core': 'RLIMIT_CORE', 'rlimit_cpu': 'RLIMIT_CPU'}.get(name)
        require(expression == enum or re.fullmatch(r'(?:\s*(?:' + token + r'))+\s*', expression),
                'Unsupported expanded header expression')
        result[name] = expression
    return result


def shape(row, fields, message):
    require(type(row) is dict and set(row) == set(fields), message)


def integer(value, low=0, high=(1 << 63) - 1, *, optional=False):
    require((optional and value is None) or type(value) is int and low <= value <= high,
            'Closed machine integer or explicit unknown required')


def call_fact(row):
    shape(row, ('attempted', 'result', 'errno', 'at_ns'), 'Closed C call fact required')
    require(type(row['attempted']) is bool, 'Actual attempted flag required')
    if row['attempted']:
        integer(row['result'], -(1 << 31), (1 << 31) - 1)
        integer(row['errno'], 0, (1 << 31) - 1)
        integer(row['at_ns'], 1, optional=True)  # X close packet does not return individual clocks.
    else:
        require(all(row[key] is None for key in ('result', 'errno', 'at_ns')), 'Unattempted call cannot invent results')


def stat6(value, *, optional=False):
    if optional and value is None:
        return
    require(type(value) is list and len(value) == 6, 'Actual stat tuple required')
    for index, item in enumerate(value):
        integer(item, 0, (1 << 64) - 1 if index < 4 else (1 << 63) - 1)
    require(stat.S_ISREG(value[2]) and value[3] > 0, 'Regular nonempty product/source required')


def product_tuple(info):
    require(type(info) in (list, tuple) and len(info) == 7, 'Selected helper stat identity required')
    return [info[index] for index in (0, 1, 2, 4, 5, 6)]


def validate_protocol(row):
    packets = row['protocol']
    require(type(packets) is list and len(packets) <= 64, 'Bounded actual packet ledger required')
    counters = {'G': 0, 'child': 0}
    previous = row['t0_ns']
    for packet in packets:
        shape(packet, ('role', 'direction', 'seq', 'kind', 'at_ns', 'observed_ns', 'length', 'sha256', 'payload'),
              'Closed actual protocol record required')
        require(packet['role'] in ('G', 'X', 'P') and packet['direction'] ==
                ('sent' if packet['role'] == 'G' else 'received'), 'Exact private direction/role required')
        group = 'G' if packet['role'] == 'G' else 'child'
        counters[group] += 1
        require(type(packet['seq']) is int and packet['seq'] == counters[group], 'Original writer sequence cannot reset/retransmit')
        integer(packet['at_ns'], row['t0_ns'], row['deadlines']['expiry_ns'])
        integer(packet['observed_ns'], row['t0_ns'], row['deadlines']['expiry_ns'])
        require(packet['at_ns'] <= packet['observed_ns'] and previous <= packet['observed_ns'], 'Packet causal clocks differ')
        previous = packet['observed_ns']
        require(type(packet['kind']) is str and packet['kind'] in
                ('PRE_READY', 'GO', 'EXEC_ENTER', 'READY', 'CHECK', 'DATA', 'ARM', 'ARM_ACK', 'ACK', 'FINISH', 'FINISH_ACK', 'ERROR')
                and type(packet['payload']) is str and packet['payload'].isascii(), 'Closed ASCII control record required')
        wire = 'PP1 %s %s %d %s %d%s\n' % (packet['role'], row['nonce'], packet['seq'], packet['kind'],
            packet['at_ns'], ' ' + packet['payload'] if packet['payload'] else '')
        require(len(wire.encode()) <= min(512, row['native_facts']['observed_pipe_buf'], row['native_facts']['PIPE_BUF']),
                'Fixed control exceeds actual/header PIPE_BUF')
        if packet['kind'] == 'DATA':
            integer(packet['length'], 1, MAX_DATA)
            require(hex_sha(packet['sha256']) and packet['payload'] == str(packet['length']) + ' ' + packet['sha256'],
                    'Exact DATA length/hash framing required')
        else:
            require(packet['length'] is packet['sha256'] is None, 'Control cannot invent DATA facts')
    if row['native_success']:
        expected = [('X', 'PRE_READY'), ('G', 'GO'), ('X', 'EXEC_ENTER'), ('P', 'READY'),
            ('G', 'CHECK'), ('P', 'DATA'), ('P', 'ARM'), ('G', 'ARM_ACK'), ('P', 'ACK')]
        if row['case'] == 'normal':
            expected += [('G', 'FINISH'), ('P', 'FINISH_ACK')]
        require([(p['role'], p['kind']) for p in packets] == expected, 'Complete fixed handshake/action order required')
        require(all(not p['payload'] for p in packets if p['kind'] not in ('PRE_READY', 'READY', 'DATA')),
                'Fixed empty control payload required')
    return packets


def parse_runtime(body, command, cpp, request, bindings, worker, fault='none'):
    require(type(body) is bytes and 0 < len(body) <= MAX_BYTES, 'Bounded actual native body required')
    row = closed_json(body)
    shape(row, NATIVE_FIELDS, 'Closed native JSON required')
    require(type(row['schema_version']) is int and row['schema_version'] == 1 and row['scope'] == SCOPE
            and row['case'] == request['case'] and row['nonce'] == request['nonce']
            and row['input_kind'] == request['input_kind'] and row['fault'] == fault
            and type(row['native_success']) is bool, 'Fixed request/runtime binding required')
    integer(row['t0_ns'], 1, (1 << 63) - 1 - 35 * 1000000000)
    shape(row['deadlines'], OFFSETS, 'Exact shared deadlines required')
    require(all(type(row['deadlines'][key]) is int and row['deadlines'][key] == row['t0_ns'] + value * 1000000000
                for key, value in OFFSETS.items()), 'Exact absolute offsets required')
    require(row['runtime_argv'] == command['argv'] and len(row['runtime_argv']) == 12
            and row['runtime_argv'][1:] == [request['case'], request['nonce'], request['runtime']['interpreter']['path'],
                bindings['worker_path'], bindings['request_path'], request['runtime']['interpreter']['sha256'],
                request['sources']['worker_sha256'], bindings['request_sha256'],
                '.'.join(str(v) for v in request['python_version']), request['input_kind'], fault], 'Exact new native argv required')
    shape(row['expected_hashes'], ('interpreter', 'worker', 'request'), 'Expected hashes must be declared separately')
    require(row['expected_hashes'] == {'interpreter': request['runtime']['interpreter']['sha256'],
        'worker': request['sources']['worker_sha256'], 'request': bindings['request_sha256']}, 'Expected source/input hashes differ')
    nf = row['native_facts']
    numeric = ('SYS_pidfd_open', 'SYS_pidfd_send_signal', 'F_GETFD', 'F_SETFD', 'FD_CLOEXEC',
        'O_CLOEXEC', 'O_NOFOLLOW', 'O_NONBLOCK', 'F_GETFL', 'EBADF', 'EAGAIN', 'EINTR', 'ESRCH',
        'SIGKILL', 'SIGPIPE', 'POLLIN', 'POLLNVAL', 'PIPE_BUF', 'RLIMIT_CORE', 'RLIMIT_CPU',
        'int_bytes', 'long_bytes', 'pointer_bytes', 'char_bits', 'byte_order', 'pid_t_bytes',
        'pid_t_signed', 'uid_t_bytes', 'uid_t_signed', 'dev_t_bytes', 'ino_t_bytes', 'rlim_t_bytes', 'observed_pipe_buf')
    shape(nf, (*numeric, 'rlimits', 'sigpipe'), 'Closed freshly compiled header/scalar facts required')
    for name in numeric:
        integer(nf[name], 0, (1 << 63) - 1)
    require(nf['pid_t_bytes'] == nf['uid_t_bytes'] == nf['int_bytes'] == 4
            and nf['pid_t_signed'] == 1 and nf['uid_t_signed'] == 0 and nf['char_bits'] == 8
            and 0 < nf['dev_t_bytes'] <= 8 and 0 < nf['ino_t_bytes'] <= 8 and 0 < nf['rlim_t_bytes'] <= 8,
            'Declared supported scalar representations required')
    for native, compiled in (('int_bytes', 'target_int_bytes'), ('long_bytes', 'target_long_bytes'),
        ('pointer_bytes', 'target_pointer_bytes'), ('char_bits', 'target_char_bits'), ('byte_order', 'target_byte_order')):
        require(nf[native] == cpp[compiled], 'Fresh CPP/runtime target observations differ')
    require(type(cpp['extra_header_expressions']) is dict and set(cpp['extra_header_expressions']) == set(EXTRA_HEADERS),
            'Fresh symbolic header expressions required; no numeric substitution')
    shape(nf['rlimits'], ('reported', 'core_requested', 'core_result', 'core_errno', 'cpu_requested', 'cpu_result', 'cpu_errno'),
          'Actual child rlimit result shape required')
    shape(nf['sigpipe'], ('set', 'get', 'ignored'), 'Local SIGPIPE facts required')
    call_fact(nf['sigpipe']['set']); call_fact(nf['sigpipe']['get'])
    require(nf['sigpipe']['ignored'] is None or type(nf['sigpipe']['ignored']) is bool, 'Observed local handler or unknown required')
    shape(row['products'], ('guardian', 'interpreter'), 'Actual product observations required')
    for value in row['products'].values():
        stat6(value, optional=True)
    shape(row['identities'], ('G', 'X', 'P_transition', 'P_pre_action'), 'Exact native identity roles required')
    for info in row['identities'].values():
        if info is None:
            continue
        shape(info, ('pid', 'ppid', 'uid', 'euid', 'birth', 'boot_id', 'state', 'product'), 'Actual kernel identity required')
        integer(info['pid'], 1, (1 << 31) - 1); integer(info['ppid'], 1, (1 << 31) - 1)
        integer(info['uid'], 0, (1 << 32) - 1); integer(info['euid'], 0, (1 << 32) - 1)
        integer(info['birth'], 1, (1 << 64) - 1)
        require(info['boot_id'] == bindings['boot_id'] and info['uid'] == info['euid'] == bindings['uid']
                and type(info['state']) is str and len(info['state']) == 1, 'Fresh boot/UID/live-state facts required')
        stat6(info['product'])
    shape(row['exec'], ('attempted', 'returned', 'result', 'errno', 'enter_ns', 'error_eof_ns', 'error_pipe_result'),
          'Prospective entry and actual exec outcome must remain separate')
    require((row['exec']['attempted'] is None or type(row['exec']['attempted']) is bool)
            and (row['exec']['returned'] is None or type(row['exec']['returned']) is bool), 'Explicit exec attempt/return state required')
    for key in ('enter_ns', 'error_eof_ns'):
        integer(row['exec'][key], row['t0_ns'], optional=True)
    if row['exec']['returned'] is True:
        require(row['exec']['attempted'] is True and row['exec']['result'] == -1
                and type(row['exec']['errno']) is int and row['exec']['errno'] > 0
                and row['exec']['error_pipe_result'] == {'result': -1, 'errno': row['exec']['errno']},
                'Actual returned exec error record required')
    else:
        require(row['exec']['result'] is row['exec']['errno'] is row['exec']['error_pipe_result'] is None,
                'Unknown/nonreturned exec cannot invent syscall return facts')
    shape(row['handle'], ('fd', 'open', 'flags', 'fdinfo_pid', 'live_poll', 'close', 'badfd'), 'Original G_P facts required')
    for key in ('open', 'flags', 'close', 'badfd'):
        call_fact(row['handle'][key])
    integer(row['handle']['fd'], 0, (1 << 31) - 1, optional=True)
    integer(row['handle']['fdinfo_pid'], 1, (1 << 31) - 1, optional=True)
    shape(row['signal'], ('budget_consumed', 'attempts', 'fd', 'flags', 'result', 'errno', 'at_ns'), 'One original signal ledger required')
    signal = row['signal']
    require(type(signal['budget_consumed']) is bool and type(signal['attempts']) is int and signal['attempts'] in (0, 1)
            and signal['budget_consumed'] is (signal['attempts'] == 1) and type(signal['flags']) is int and signal['flags'] == 0,
            'Original signal budget cannot reset or invent attempts')
    if not signal['attempts']:
        require(signal['result'] is signal['errno'] is signal['at_ns'] is None, 'Uncalled signal cannot invent return facts')
    else:
        require(request['case'] == 'worker_loss' and fault == 'none' and signal['fd'] == row['handle']['fd'],
                'Only declared loss original handle may receive one signal')
        integer(signal['result'], -1, (1 << 31) - 1); integer(signal['errno'], 0, (1 << 31) - 1)
        integer(signal['at_ns'], row['t0_ns'], row['deadlines']['work_ns'] - 1)
    shape(row['wait'], ('attempts', 'result_pid', 'raw_status', 'errno', 'at_ns'), 'Exact G wait/reap result required')
    wait = row['wait']; integer(wait['attempts'], 0, (1 << 31) - 1)
    for key in ('result_pid', 'raw_status', 'errno', 'at_ns'):
        integer(wait[key], -1 if key == 'result_pid' else 0, optional=True)
    shape(row['times'], TIME_NAMES, 'Shared causal clocks required')
    for value in row['times'].values():
        integer(value, row['t0_ns'], optional=True)
    require(type(row['polls']) is list and len(row['polls']) <= 64, 'Bounded actual poll ledger required')
    for poll in row['polls'] + ([row['handle']['live_poll']] if row['handle']['live_poll'] is not None else []):
        shape(poll, ('fd', 'result', 'revents', 'errno', 'at_ns', 'purpose'), 'Closed poll fact required')
        integer(poll['fd'], 0, (1 << 31) - 1); integer(poll['result'], -1, (1 << 31) - 1)
        integer(poll['revents'], 0, 65535); integer(poll['errno'], 0, (1 << 31) - 1)
        integer(poll['at_ns'], row['t0_ns']); require(type(poll['purpose']) is str, 'Actual poll purpose required')
    require(type(row['fd_ledger']) is list and len(row['fd_ledger']) <= 64
            and type(row['fd_flags']) is list and len(row['fd_flags']) <= 64, 'Bounded semantic FD ledgers required')
    seen = set()
    for item in row['fd_ledger']:
        shape(item, ('owner', 'label', 'generation', 'fd', 'evidence', 'close', 'badfd'), 'Closed semantic FD row required')
        key = (item['owner'], item['label'], item['generation'])
        require(key not in seen and item['owner'] in ('G', 'X', 'P') and type(item['label']) is str,
                'Duplicate semantic handle/budget is forbidden')
        seen.add(key); integer(item['generation'], 0, 1); integer(item['fd'], -1, (1 << 31) - 1)
        call_fact(item['close']); call_fact(item['badfd'])
        if item['evidence'] == 'explicit_once_close':
            require(item['fd'] >= 0 and item['close']['attempted'] is item['badfd']['attempted'] is True,
                    'Actual explicit close and subsequent check attempts required')
            if row['native_success']:
                require(item['close']['result'] == item['close']['errno'] == 0
                    and item['badfd']['result'] == -1 and item['badfd']['errno'] == nf['EBADF'], 'Actual once-close/immediate EBADF required')
        else:
            require(item['evidence'] in ('original_absent', 'exec_cloexec', 'parent_report_eof', 'owner_death', 'unknown')
                    and not item['close']['attempted'] and not item['badfd']['attempted'], 'Non-returned close cannot be fabricated as syscall facts')
    for item in row['fd_flags']:
        shape(item, ('owner', 'label', 'generation', 'fd', 'before', 'set', 'after', 'getfl'), 'Closed original flag provenance required')
        require(item['owner'] == 'G' and type(item['label']) is str and type(item['generation']) is int and item['generation'] == 1,
                'Flags cannot relabel owner/generation')
        integer(item['fd'], 0, (1 << 31) - 1)
        for key in ('before', 'set', 'after', 'getfl'):
            call_fact(item[key])
    pb = row['python_body']
    shape(pb, ('complete', 'declared_length', 'declared_sha256', 'length', 'raw_hex'), 'Exact returned body bytes required')
    require(type(pb['complete']) is bool and type(pb['raw_hex']) is str
            and re.fullmatch(r'(?:[0-9a-f]{2})*', pb['raw_hex']) is not None, 'Actual lowercase byte encoding required')
    integer(pb['length'], 0, MAX_DATA); integer(pb['declared_length'], 1, MAX_DATA, optional=True)
    raw = bytes.fromhex(pb['raw_hex']); require(len(raw) == pb['length'], 'Returned body length differs')
    packets = validate_protocol(row)
    if not row['native_success']:
        require(row['error'] is not None, 'Negative native result needs actual error')
        shape(row['error'], ('stage', 'operation', 'errno', 'result_known', 'result', 'at_ns'), 'Actual first native error required')
        require(type(row['error']['result_known']) is bool and type(row['error']['stage']) is type(row['error']['operation']) is str,
                'Actual error classification required')
        integer(row['error']['errno'], 0, (1 << 31) - 1)
        integer(row['error']['at_ns'], row['t0_ns'])
        if row['error']['result_known']:
            integer(row['error']['result'], -(1 << 31), (1 << 31) - 1)
        else:
            require(row['error']['result'] is None, 'Unknown first-error result must stay null')
        return row  # No narrow flag comes from this partial/negative body.
    require(fault == 'none' and command['status'] == 'success' and command['returncode'] == 0
            and command['reap_completed'] is True and command['timed_out'] is command['kill_attempted'] is False
            and row['error'] is None, 'Successful direct-G observation without outer timeout/kill required')
    g, x, p, live = (row['identities'][key] for key in ('G', 'X', 'P_transition', 'P_pre_action'))
    require(all(info is not None for info in (g, x, p, live)) and g['pid'] == command['direct_child_pid']
            and g['ppid'] == bindings['parent_pid'] and x['ppid'] == p['ppid'] == live['ppid'] == g['pid'], 'Actual owned parent chain required')
    same = ('pid', 'ppid', 'uid', 'euid', 'birth', 'boot_id')
    require(all(x[key] == p[key] == live[key] for key in same) and p['state'] not in ('Z', 'X') and live['state'] not in ('Z', 'X'),
            'Same live PID/birth/boot/UID/parent across exec required')
    guardian = product_tuple(bindings['guardian_identity']); interpreter = product_tuple(bindings['interpreter_identity'])
    require(row['products'] == {'guardian': guardian, 'interpreter': interpreter}
            and g['product'] == x['product'] == guardian and p['product'] == live['product'] == interpreter
            and guardian != interpreter, 'Actual distinct guardian->interpreter transition required')
    ex = row['exec']
    require(ex['attempted'] is True and ex['returned'] is False and ex['result'] is ex['errno'] is ex['error_pipe_result'] is None
            and type(ex['enter_ns']) is type(ex['error_eof_ns']) is int
            and row['times']['exec_go_ns'] <= ex['enter_ns'] <= ex['error_eof_ns'] <= row['times']['ready_ns'],
            'Joint exec-error EOF/readiness/identity evidence required; no returned success')
    argv = row['python_exec_argv']
    require(type(argv) is list and len(argv) == 18 and argv[:5] == [request['runtime']['interpreter']['path'], '-B', '-I', '-S', '-c']
            and argv[5] == bindings['bootstrap_literal'] and argv[6] == 'PP_BOOT1'
            and argv[11:] == [request['sources']['worker_sha256'], bindings['request_sha256'], request['nonce'], request['case'],
                              str(row['t0_ns']), request['input_kind'], '.'.join(str(v) for v in request['python_version'])]
            and row['kernel_python_argv'] == argv, 'Actual fixed Python bootstrap argv/kernel argv required')
    require(pb['complete'] is True and pb['length'] == pb['declared_length'] and hex_sha(pb['declared_sha256'])
            and digest(raw) == pb['declared_sha256'], 'Actual DATA bytes/hash independently recomputed by outer parser')
    packet_by_kind = {packet['kind']: packet for packet in packets}
    require(packet_by_kind['DATA']['length'] == pb['declared_length']
            and packet_by_kind['DATA']['sha256'] == pb['declared_sha256'], 'DATA header and returned body bindings differ')
    data = closed_json(raw.decode('utf-8'))
    worker.validate_result(data, request, bindings['lock_pins'])
    startup = data['startup']
    require(startup['t0_ns'] == row['t0_ns'] and startup['deadlines'] == row['deadlines']
            and startup['initial_argv'] == ['-c', *argv[6:]] and startup['orig_argv'] == argv
            and startup['bootstrap_sha256'] == digest(argv[5].encode()), 'Actual versus logical startup argv/literal binding required')
    for name, index in (('worker', 7), ('request', 8)):
        record = startup['captured'][name]
        require(record['fd'] == int(argv[index]) and record['before'] == record['after'] == product_tuple(bindings[name + '_identity'])
                and record['badfd_result'] is None and record['badfd_exception'] == 'OSError' and record['badfd_errno'] == nf['EBADF'],
                'Captured original FD bytes/identity and actual Python exception semantics required')
    require(startup['command_fd'] == int(argv[9]) and startup['report_fd'] == int(argv[10]), 'Original private P edge binding required')
    identity = data['identity']
    require(all(identity[key] == p[key] for key in ('pid', 'ppid', 'uid', 'euid', 'birth', 'boot_id'))
            and identity['proc_exe']['identity'] == interpreter, 'Actual Python/kernel native identity match required')
    times = row['times']
    require(all(type(times[key]) is int for key in TIME_NAMES) and list(times.values()) != []
            and all(times[a] <= times[b] for a, b in zip(TIME_NAMES, TIME_NAMES[1:]))
            and times['primary_ns'] < row['deadlines']['work_ns'] and times['terminal_ns'] < row['deadlines']['cleanup_ns']
            and times['reap_ns'] <= times['fd_complete_ns'] < row['deadlines']['terminal_ns']
            and times['final_ns'] < row['deadlines']['total_ns'], 'Actual finite causal work/terminal/FD/final clocks required')
    handle = row['handle']; require(handle['fdinfo_pid'] == p['pid'] and handle['open']['attempted'] is True
        and handle['open']['result'] == handle['fd'] and handle['open']['errno'] == 0
        and handle['flags']['attempted'] is True and handle['flags']['result'] & nf['FD_CLOEXEC']
        and handle['close']['attempted'] is handle['badfd']['attempted'] is True
        and handle['close']['result'] == handle['close']['errno'] == 0
        and handle['badfd']['result'] == -1 and handle['badfd']['errno'] == nf['EBADF'], 'Original retained pidfd open/once-close chain required')
    require(wait['attempts'] > 0 and wait['result_pid'] == p['pid'] and wait['errno'] == 0
            and wait['raw_status'] == (0 if request['case'] == 'normal' else nf['SIGKILL']), 'G exclusively owns exact P reap/raw wait')
    if request['case'] == 'normal':
        require(signal['attempts'] == 0, 'Normal directed signals must be zero')
    else:
        require(signal['attempts'] == 1 and signal['result'] == signal['errno'] == 0
                and times['ack_ns'] <= signal['at_ns'] == times['primary_ns'] < row['deadlines']['work_ns'], 'Once original loss signal needs ready/ACK/fresh deadline')
    expected_g = {'interpreter', 'worker_script', 'request', 'command_read', 'command_write',
                  'report_read', 'report_write', 'exec_error_read', 'exec_error_write', 'G_P'}
    require({item['label'] for item in row['fd_ledger'] if item['owner'] == 'G'} == expected_g
            and all(item['generation'] == 1 and item['evidence'] == 'explicit_once_close'
                    for item in row['fd_ledger'] if item['owner'] == 'G'), 'All original G private/pidfd once-close facts required')
    require(len(row['fd_ledger']) == 20 and len(row['fd_flags']) == 9, 'Fixed semantic FD inventory required')
    ledger = {(item['owner'], item['label']): item for item in row['fd_ledger']}
    require(len(ledger) == 20 and all(item['generation'] == 1 for item in ledger.values()),
            'One original generation per semantic handle required')
    expected_x = {'command_write', 'report_read', 'exec_error_read', 'original_stdin', 'original_stdout', 'original_stderr',
                  'interpreter', 'exec_error_write'}
    require({item['label'] for item in row['fd_ledger'] if item['owner'] == 'X'} == expected_x
            and {item['label'] for item in row['fd_ledger'] if item['owner'] == 'P'} == {'command_read', 'report_write'},
            'Exact X/P private inventory required')
    original_fds = {name: ledger['G', name]['fd'] for name in expected_g}
    require(len(set(original_fds.values())) == 10 and min(original_fds.values()) > 2
            and original_fds['G_P'] == handle['fd'], 'Original managed handles cannot alias stdio/each other')
    for (owner, label), item in ledger.items():
        expected_fd = {'original_stdin': 0, 'original_stdout': 1, 'original_stderr': 2}.get(label, original_fds.get(label))
        require(item['fd'] == expected_fd, 'Original semantic FD correspondence differs')
        if owner == 'G':
            require(type(item['close']['at_ns']) is type(item['badfd']['at_ns']) is int
                    and row['t0_ns'] <= item['close']['at_ns'] <= item['badfd']['at_ns'] <= times['fd_complete_ns'],
                    'Actual G close/immediate badfd clocks required')
        elif owner == 'X' and label in ('interpreter', 'exec_error_write'):
            require(item['evidence'] == 'exec_cloexec', 'Joint transition CLOEXEC evidence required')
        elif owner == 'X':
            require(item['evidence'] == 'explicit_once_close'
                    and item['close']['at_ns'] is item['badfd']['at_ns'] is None, 'Returned X close results without invented syscall clocks required')
        else:
            require(item['evidence'] == ('parent_report_eof' if label == 'report_write' else
                    'unknown' if request['case'] == 'normal' else 'owner_death'), 'P last-writer/command close evidence differs')
    require(ledger['G', 'G_P']['close'] == handle['close'] and ledger['G', 'G_P']['badfd'] == handle['badfd'],
            'Original pidfd close facts must bind ledger')
    flags = {item['label']: item for item in row['fd_flags']}
    require(len(flags) == 9 and set(flags) == expected_g - {'G_P'}, 'Exact nine original acquisition flags required')
    inherited = {'worker_script', 'request', 'command_read', 'report_write'}
    for label, item in flags.items():
        require(item['fd'] == original_fds[label] and all(item[key]['attempted'] is True
                and item[key]['errno'] == 0 and type(item[key]['at_ns']) is int
                for key in ('before', 'set', 'after', 'getfl'))
                and item['set']['result'] == 0 and item['before']['result'] >= 0
                and item['after']['result'] == (item['before']['result'] & ~nf['FD_CLOEXEC'] if label in inherited
                    else item['before']['result'] | nf['FD_CLOEXEC'])
                and row['t0_ns'] <= item['before']['at_ns'] <= item['set']['at_ns'] <= item['after']['at_ns']
                    <= item['getfl']['at_ns'] <= times['pre_ready_ns'], 'Actual preexec inheritance provenance required')
        if label.startswith(('command_', 'report_', 'exec_error_')):
            require(item['getfl']['result'] & nf['O_NONBLOCK'], 'Private pipes must be nonblocking')
    child_labels = ('command_write', 'report_read', 'exec_error_read', 'original_stdin', 'original_stdout', 'original_stderr')
    pre = ' '.join('%d 0 0 0 -1 %d' % (ledger['X', label]['fd'], nf['EBADF']) for label in child_labels) + ' 0 0 0 0'
    require(packet_by_kind['PRE_READY']['payload'] == pre, 'Exact six close and four rlimit tokens required')
    ready = ' '.join(map(str, [p[key] for key in ('pid', 'ppid', 'uid', 'euid', 'birth')]
        + request['python_version'] + [1, 1, 1] + [request['sources']['worker_sha256'], bindings['request_sha256']]))
    require(packet_by_kind['READY']['payload'] == ready, 'Exact P identity/version/flags/captured hash READY required')
    for kind, clock in (('PRE_READY', 'pre_ready_ns'), ('GO', 'exec_go_ns'), ('READY', 'ready_ns'), ('ARM', 'arm_ns'), ('ACK', 'ack_ns')):
        require(packet_by_kind[kind]['observed_ns'] <= times[clock]
                and (kind == 'READY' or packet_by_kind[kind]['observed_ns'] == times[clock]),
                'Actual handshake/summary clock binding differs')
    require(packet_by_kind['EXEC_ENTER']['at_ns'] == ex['enter_ns']
            and packet_by_kind['DATA']['observed_ns'] <= times['data_complete_ns'] <= packet_by_kind['ARM']['observed_ns']
            and times['primary_ns'] <= wait['at_ns'] <= times['reap_ns'], 'Actual entry/DATA/reap timing binding differs')
    if request['case'] == 'normal':
        require(times['primary_ns'] <= packet_by_kind['FINISH']['at_ns']
                and packet_by_kind['FINISH_ACK']['observed_ns'] <= times['terminal_ns'], 'FINISH/ACK must precede terminal observation')
    initial = handle['live_poll']
    require(initial is not None and initial in row['polls'] and initial['purpose'] == 'initial_live'
            and initial['fd'] == handle['fd'] and initial['result'] == initial['revents'] == initial['errno'] == 0
            and handle['open']['at_ns'] <= handle['flags']['at_ns'] <= initial['at_ns'] <= times['exec_go_ns'],
            'Original preexec live pidfd observation required')
    pre_action = [poll for poll in row['polls'] if poll['purpose'] == 'pre_action_live']
    terminal = [poll for poll in row['polls'] if poll['purpose'] == 'terminal' and poll['result'] > 0
                and poll['revents'] & nf['POLLIN'] and not poll['revents'] & nf['POLLNVAL']]
    require(len(pre_action) == 1 and pre_action[0]['fd'] == handle['fd']
            and pre_action[0]['result'] == pre_action[0]['revents'] == pre_action[0]['errno'] == 0
            and times['ack_ns'] <= pre_action[0]['at_ns'] <= times['primary_ns']
            and terminal and all(poll['fd'] == handle['fd'] and poll['errno'] == 0
                and times['primary_ns'] <= poll['at_ns'] <= times['terminal_ns'] for poll in terminal),
            'Fresh action live and terminal POLLIN facts required')
    rlimits = nf['rlimits']
    require(rlimits == {'reported': True, 'core_requested': [0, 0], 'core_result': 0, 'core_errno': 0,
                       'cpu_requested': [20, 21], 'cpu_result': 0, 'cpu_errno': 0}
            and nf['sigpipe']['ignored'] is True, 'Actual fixed child limits/local SIGPIPE evidence required')
    return row


def bootstrap_literal(body):
    text = body.decode('ascii')
    match = re.search(r'static const char pp_bootstrap\[\] =\s*((?:"(?:[^"\\]|\\.)*"\s*)+);', text)
    require(match is not None, 'One fixed captured bootstrap literal required')
    pieces = re.findall(r'"(?:[^"\\]|\\.)*"', match[1])
    # The reviewed C literal uses only JSON-compatible escapes, decoded as data.
    return ''.join(json.loads(piece) for piece in pieces)


def captured_worker(path, body):
    module = ModuleType('frontier_v8_captured_readonly_worker')
    module.__file__, module.__package__ = str(path), None
    exec(compile(body, str(path), 'exec', dont_inherit=True), module.__dict__)
    return module


def run_fixture(request_path, expected_sha256, backend, utility, linkage,
                expected_parent_pid, expected_uid, expected_boot_id, fault='none',
                pre_runtime_check=None):
    """One fresh build/run; synthetic input is confined to this fixture API."""
    result = {**AUTHORITY, **dict.fromkeys(SUCCESS, False), 'status': 'failed',
        'runtime_attempts': 0, 'runtime_returned_complete_facts': False,
        'complete_mapped_code_authenticated': False, 'fault': fault}
    try:
        require(fault in ('none', 'closed_exec', 'script_hash'), 'Closed fixture fault required')
        helper = backend.helper
        source = absolute_path(__file__)
        paths = [source, *(source.with_name(name) for name in C_NAMES),
            source.with_name(WORKER_NAME), Path(helper.__file__), Path(utility.__file__),
            Path(linkage.__file__)]
        captures = [(path, *helper.read_regular(str(path), MAX_SOURCE)) for path in paths]
        raw, request_identity = helper.read_regular(str(absolute_path(str(request_path))), 65536, owner=expected_uid)
        require(hex_sha(expected_sha256) and digest(raw) == expected_sha256, 'Fresh request bytes differ')
        worker = captured_worker(paths[3], captures[3][1])
        request = worker.parse_request(raw)
        hashes = {'observer_sha256': digest(captures[0][1]), 'worker_sha256': digest(captures[3][1]),
            'c_sources_sha256': {name: digest(captures[index + 1][1]) for index, name in enumerate(C_NAMES)},
            'identity_helper_sha256': digest(captures[4][1]), 'toolchain_sha256': digest(captures[5][1]),
            'linkage_sha256': digest(captures[6][1])}
        require(request['sources'] == hashes and hashes['identity_helper_sha256'] == HELPER_SHA
                and hashes['toolchain_sha256'] == TOOLCHAIN_SHA and hashes['linkage_sha256'] == LINKAGE_SHA,
                'Exact new sources and pinned utilities required')
        for index, module in ((4, helper), (5, utility), (6, linkage)):
            require(captures[index][1:] == (module._captured_bytes, module._captured_identity),
                    'Captured utility bytes/identity drift')
        if request['input_kind'] == 'real_readonly_runtime':
            parse_request(raw, expected_sha256, hashes)
            require(fault == 'none', 'Real input cannot take a synthetic fault route')
        require(request['host']['uid'] == expected_uid and request['host']['boot_id'] == expected_boot_id
                and request['attempt_directory'] == str(backend.root), 'Exact fixture host/output binding required')
        interpreter_path = absolute_path(request['runtime']['interpreter']['path'])
        interpreter, interpreter_identity = helper.read_regular(str(interpreter_path), MAX_INTERPRETER)
        require(digest(interpreter) == request['runtime']['interpreter']['sha256']
                and interpreter_identity[2] & 0o111, 'Exact executable Python ELF required')
        result['python_interpreter'] = parse_python_interpreter(interpreter, linkage)
        require(result['python_interpreter']['captured_sha256'] == request['runtime']['interpreter']['sha256'],
                'Full captured Python ELF descriptor hash differs')
        lock_path = absolute_path(request['lock']['path'])
        lock_body, lock_identity = helper.read_regular(str(lock_path), 65536)
        require(digest(lock_body) == LOCK_SHA, 'Frozen lock bytes differ')
        pins = worker.parse_lock(lock_body)
        literal = bootstrap_literal(captures[1][1])
        captures += [(absolute_path(str(request_path)), raw, request_identity),
                     (interpreter_path, interpreter, interpreter_identity),
                     (lock_path, lock_body, lock_identity)]

        def validate_inputs():
            for path, body, info in captures:
                require(helper.read_regular(str(path), max(len(body), 1)) == (body, info),
                        'Captured source/request/interpreter/lock drift')
            if pre_runtime_check is not None:
                pre_runtime_check()

        validate_inputs()
        record = result['build'] = {}
        recheck = build_product(paths[1], paths[2], backend, utility, linkage, record)
        validate_inputs(); recheck()
        argv = [record['product']['path'], request['case'], request['nonce'], str(interpreter_path),
            str(paths[3]), str(request_path), request['runtime']['interpreter']['sha256'],
            hashes['worker_sha256'], expected_sha256, '.'.join(map(str, request['python_version'])),
            request['input_kind'], fault]
        result['runtime_attempts'] = 1
        command = result['runtime_command'] = run_runtime(backend, argv)
        stdout, stdout_row = backend.read_output('runtime.stdout', MAX_BYTES)
        stderr, stderr_row = backend.read_output('runtime.stderr', MAX_BYTES)
        require(stdout_row == command['stdout'] and stderr_row == command['stderr'] and not stderr,
                'Captured runtime streams differ or stderr is nonempty')
        bindings = {'worker_path': str(paths[3]), 'request_path': str(request_path),
            'request_sha256': expected_sha256, 'parent_pid': expected_parent_pid,
            'uid': expected_uid, 'boot_id': expected_boot_id,
            'guardian_identity': record['product']['identity'], 'interpreter_identity': interpreter_identity,
            'worker_identity': captures[3][2], 'request_identity': request_identity,
            'bootstrap_literal': literal, 'lock_pins': pins}
        facts = result['runtime_report'] = parse_runtime(stdout, command,
            record['compile_leg']['cpp_facts'], request, bindings, worker, fault)
        result['runtime_returned_complete_facts'] = True
        validate_inputs(); recheck()
        require(backend.read_output('runtime.stdout', MAX_BYTES) == (stdout, stdout_row)
                and backend.read_output('runtime.stderr', MAX_BYTES) == (stderr, stderr_row),
                'Runtime stream drift after validation')
        result['runtime_output_bindings'] = {'stdout': stdout_row, 'stderr': stderr_row}
        require(facts['native_success'] is True and fault == 'none', 'Fixed Python preflight returned a negative result')
        result[SUCCESS[0]] = result[SUCCESS[1]] = True
        result[SUCCESS[2 if request['case'] == 'normal' else 3]] = True
        result['status'] = 'success'
    except Exception as error:
        result['error'] = {'type': type(error).__name__, 'message': str(error)}
    return result


def observe(request_path, expected_sha256):
    require(sys.platform == 'linux' and sys.flags.isolated == sys.flags.no_site == 1
            and sys.dont_write_bytecode and os.getuid() == os.geteuid(),
            'Fresh equal-UID Linux -B -I -S file entry required')
    helper, utility, linkage = load_utilities()
    source = absolute_path(__file__)
    paths = [source, *(source.with_name(name) for name in C_NAMES), source.with_name(WORKER_NAME),
             Path(helper.__file__), Path(utility.__file__), Path(linkage.__file__)]
    inputs = [(path, *helper.read_regular(str(path), MAX_SOURCE)) for path in paths]
    request_file = absolute_path(request_path)
    raw, info = helper.read_regular(str(request_file), 65536, owner=os.getuid())
    inputs.append((request_file, raw, info))
    hashes = {'observer_sha256': digest(inputs[0][1]), 'worker_sha256': digest(inputs[3][1]),
        'c_sources_sha256': {name: digest(inputs[index + 1][1]) for index, name in enumerate(C_NAMES)},
        'identity_helper_sha256': digest(inputs[4][1]), 'toolchain_sha256': digest(inputs[5][1]),
        'linkage_sha256': digest(inputs[6][1])}
    request = parse_request(raw, expected_sha256, hashes)
    bootstrap = absolute_path(request['bootstrap']['path'])
    lexical_executable = sys.executable
    require(os.path.realpath(lexical_executable) == str(bootstrap)
            and list(sys.version_info[:3]) == request['bootstrap']['python_version'], 'Observer bootstrap differs')
    body, info = helper.read_regular(str(bootstrap), MAX_INTERPRETER)
    require(digest(body) == request['bootstrap']['sha256'], 'Observer bootstrap bytes differ')
    inputs.append((bootstrap, body, info))
    own = helper.capture_self_identity()
    require(own['uid'] == own['euid'] == request['host']['uid'] == os.getuid()
            and own['boot_id'] == request['host']['boot_id']
            and os.uname().nodename == request['host']['hostname'], 'Current host/self identity differs')
    root = absolute_path(request['attempt_directory']); marker = root.with_name(root.name + '.consumed.json')
    for output in (root, marker):
        for path in [row[0] for row in inputs] + [absolute_path(request['lock']['path']),
                absolute_path(request['runtime']['venv_root']), absolute_path(request['runtime']['interpreter']['path'])]:
            require(output != path and not output.is_relative_to(path) and not path.is_relative_to(output),
                    'Fresh output overlaps readonly input')
    parent, root_fd = helper.open_parent(root), None
    try:
        boundary = os.fstat(parent); uid = os.getuid()
        require(boundary.st_uid == uid, 'Owned fresh output parent required')
        helper._absent(parent, root.name); helper._absent(parent, marker.name)
        helper.write_json_at(parent, marker.name, {**AUTHORITY, 'schema_version': 1, 'status': 'consumed',
            'scope': SCOPE, 'case': request['case'], 'nonce': request['nonce'], 'request_sha256': expected_sha256,
            'sources': hashes, 'products_and_PIDs_not_yet_created': True})
        os.fsync(parent)
        marker_body, marker_info = helper.read_regular(str(marker), 65536, owner=uid)
        receipt = {**AUTHORITY, **dict.fromkeys(SUCCESS, False), 'schema_version': 1, 'scope': SCOPE,
            'status': 'failed', 'case': request['case'], 'nonce': request['nonce'], 'request_sha256': expected_sha256,
            'host': request['host'], 'self_identity': own, 'attempt_directory': str(root),
            'node_alias_authenticated': False, 'input_and_self_identity_postvalidation_passed': False,
            'native_guard_executed_or_modified': False, 'os_api_shim_installed': False,
            'pipcheck_performed': 0, 'dependency_consistency_verified': False,
            'captured_utilities': {'old_observe_or_CLI_called': False, 'hashes': hashes},
            'trusted_baseline': 'CPython/stdlib/compiler/linker/loader/libc/filesystem; not full mapped-code auth'}
        try:
            os.mkdir(root.name, 0o700, dir_fd=parent)
            root_fd = os.open(root.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
            root_info = os.fstat(root_fd)
            require(root_info.st_uid == uid, 'Output owner differs')
            os.mkdir('tmp', 0o700, dir_fd=root_fd)

            def validate_inputs():
                for path, body, info in inputs:
                    require(helper.read_regular(str(path), max(len(body), 1)) == (body, info), 'Observer input drift')
                require(helper.read_regular(str(marker), 65536, owner=uid) == (marker_body, marker_info), 'Consumed marker drift')
                after = helper.capture_self_identity()
                require(all(after[key] == own[key] for key in ('boot_id', 'pid', 'ppid', 'start_ticks', 'uid', 'euid', 'proc_uids'))
                        and sys.executable == lexical_executable and os.path.realpath(sys.executable) == str(bootstrap)
                        and list(sys.version_info[:3]) == request['bootstrap']['python_version']
                        and os.uname().nodename == request['host']['hostname'], 'Self/bootstrap/host drift')
                check = helper.open_parent(root)
                try:
                    latest = os.fstat(check)
                    require((latest.st_dev, latest.st_ino, latest.st_uid) == (boundary.st_dev, boundary.st_ino, uid), 'Output parent drift')
                    latest = os.stat(root.name, dir_fd=check, follow_symlinks=False)
                    require(stat.S_ISDIR(latest.st_mode) and (latest.st_dev, latest.st_ino, latest.st_uid) ==
                            (root_info.st_dev, root_info.st_ino, uid), 'Output directory drift')
                finally:
                    os.close(check)

            receipt['fixture'] = run_fixture(request_file, expected_sha256,
                utility.CompilerBackend(helper, root, root_fd), utility, linkage,
                own['pid'], uid, own['boot_id'], pre_runtime_check=validate_inputs)
            validate_inputs()
            receipt['input_and_self_identity_postvalidation_passed'] = True
            if receipt['fixture']['status'] == 'success':
                receipt['status'] = 'success'
                for key in SUCCESS:
                    receipt[key] = receipt['fixture'][key]
        except Exception as error:
            receipt['error'] = {'type': type(error).__name__, 'message': str(error)}
        if root_fd is not None:
            helper.write_json_at(root_fd, 'receipt.json', receipt); os.fsync(root_fd)
        else:
            helper.write_json_at(parent, root.name + '.failed-receipt.json', receipt)
        os.fsync(parent)
        return receipt
    finally:
        if root_fd is not None:
            os.close(root_fd)
        os.close(parent)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if '--execute' in argv:
        raise ValueError('Production/model execution unavailable')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True)
    parser.add_argument('--expected-request-sha256', required=True)
    args = parser.parse_args(argv)
    return observe(args.request, args.expected_request_sha256)


if __name__ == '__main__':
    try:
        value = main()
        print(json.dumps(value, sort_keys=True, allow_nan=False))
        sys.exit(0 if value['status'] == 'success' else 1)
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error': {'type': type(error).__name__,
              'message': str(error)}, **AUTHORITY, **dict.fromkeys(SUCCESS, False)}, sort_keys=True))
        sys.exit(1)
