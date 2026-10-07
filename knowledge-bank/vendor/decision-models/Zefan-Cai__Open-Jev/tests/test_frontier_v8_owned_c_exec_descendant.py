"""New fixed exec/descendant CPU fixtures; synthetic facts are not observations.

This file is authored by the former design cross-reviewer. It must not be used
as an independent source or actual-result review. No tests/compiler have been
run by this author; the root task owns focused verification and its receipts.
"""

from contextlib import ExitStack
import copy
import errno
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import frontier_v8_owned_c_exec_descendant as observer


ROOT = Path(__file__).resolve().parents[1]
BOOT = '00000000-0000-0000-0000-000000000001'
NONCE = 'a' * 64  # Pure synthetic token; never used as a host request.
SOURCE_HASHES = {name: str(index + 1) * 64 for index, name in enumerate(observer.C_NAMES)}
EXTRA_EXPRESSIONS = {
    'pidfd_send_signal': ('SYS_pidfd_send_signal_expression', '((1 << 8) + 10L)'),
    'pr_set_child_subreaper': ('PR_SET_CHILD_SUBREAPER_expression', '36'),
    'pr_get_child_subreaper': ('PR_GET_CHILD_SUBREAPER_expression', '37'),
    **{name.lower(): (name + '_expression', str(value)) for name, value in (
        ('F_GETFD', 1), ('F_SETFD', 2), ('F_DUPFD_CLOEXEC', 1030), ('FD_CLOEXEC', 1),
        ('O_CLOEXEC', 524288), ('O_NOFOLLOW', 131072), ('O_NONBLOCK', 2048),
        ('F_GETFL', 3), ('F_SETFL', 4), ('EBADF', 9), ('SIGKILL', 9),
        ('SIGPIPE', 13), ('POLLIN', 1), ('POLLNVAL', 32), ('PIPE_BUF', 4096))}}
EXTRA_CPP = ('\n'.join('const long frontier_v8_header_' + marker + ' = ' + value + ';'
                       for marker, (_, value) in EXTRA_EXPRESSIONS.items()) + '\n').encode()
CPP = {'SYS_pidfd_open_expression': '((1 << 8) + 9L)',
       'target_int_bytes': 4, 'target_long_bytes': 8, 'target_pointer_bytes': 8,
       'target_char_bits': 8, 'target_byte_order': 1234,
       **{key: value for key, value in EXTRA_EXPRESSIONS.values()}}
G_PRODUCT = [1, 2, 0o100700, os.getuid(), 128, 6, 7]
E_PRODUCT = [1, 3, 0o100700, os.getuid(), 256, 8, 9]
PAIRS = {'G_E': ('guardian', 'worker'), 'G_D': ('guardian', 'descendant'),
         'E_D': ('worker', 'descendant')}
TIME_NAMES = ('initial preexec_ready exec_sent exec_entered postexec_ready postexec_validated '
              'create_D_sent D_ready all_bound arm_sent all_arm_ack primary finish_sent E_signal '
              'E_terminal E_reaped D_adopted D_signal D_terminal D_reaped FD_complete reset final').split()


def fact(result=None, err=None, value=None, at=None):
    return {'attempted': result is not None, 'result': result, 'errno': err,
            'value': value, 'observed_at_ns': at}


def product_identity(row):
    return dict(zip(('dev', 'ino', 'size', 'mtime_ns', 'ctime_ns'),
                    (row[0], row[1], *row[4:7])))


def identity(role, pid, ppid, product):
    return {'pid': pid, 'ppid': ppid, 'start_ticks': 100 + pid, 'boot_id': BOOT,
            'uid': os.getuid(), 'euid': os.getuid(), 'product_identity': product_identity(product)}


def poll_row(tag, fd=-1, stage='initial_live', result=None, revents=None, at=None):
    owner, target = PAIRS[tag]
    return {'owner': owner, 'target': target, 'handle': tag, 'fd': fd, 'stage': stage,
            'attempts': int(result is not None), 'requested_events': 1, 'result': result,
            'revents': revents, 'errno': 0 if result is not None else None, 'observed_at_ns': at}


def runtime_unknown_payload():
    """Full synthetic early-error shape; no exec, child, FD or reap is observed."""
    headers = {'pidfd_open': 265, 'pidfd_send_signal': 266, 'pr_set_child_subreaper': 36,
        'pr_get_child_subreaper': 37,
        **{name: int(value) for name, value in ((key.removesuffix('_expression'), value)
            for key, value in EXTRA_EXPRESSIONS.values()) if value.isdecimal()},
        **{key: value for key, value in CPP.items() if key.startswith('target_')},
        'pid_t_bytes': 4, 'uid_t_bytes': 4, 'pid_t_signed': True, 'uid_t_signed': False,
        'uint64_bytes': 8, 'int64_bytes': 8, 'pid_representation': 'signed32',
        'uid_representation': 'unsigned32', 'uint64_representation': 'unsigned64',
        'int64_representation': 'signed64', 'pid_max': (1 << 31) - 1, 'uid_max': (1 << 32) - 1,
        'uint64_max': (1 << 64) - 1, 'int64_min': -(1 << 63), 'int64_max': (1 << 63) - 1}
    # First three expression names have a different runtime spelling.
    headers.pop('PR_SET_CHILD_SUBREAPER', None)
    headers.pop('PR_GET_CHILD_SUBREAPER', None)
    t0 = 1000000000
    return {'schema_version': 1, 'scope': observer.SCOPE, 'case': 'normal', 'fault': 'none',
        'nonce': NONCE, 'status': 'failed',
        'error': {'stage': 'initial', 'role': 'guardian', 'operation': 'clock_gettime',
                  'errno': 0, 'result': -1, 'observed_at_ns': t0},
        'headers': headers,
        'products': {'guardian': product_identity(G_PRODUCT), 'leaf': product_identity(E_PRODUCT)},
        'subreaper': {key: fact() for key in ('initial_get', 'set_one', 'get_one', 'reset_zero', 'final_get')},
        'child_subreaper_get': {key: fact() for key in ('preexec_worker', 'worker', 'descendant')},
        'local_sigpipe': {role: {'query': fact(), 'set_ignore': fact()}
                          for role in ('guardian', 'worker', 'descendant')},
        'identities_initial': {'guardian': identity('guardian', 42, 7, G_PRODUCT),
                               'preexec_worker': None, 'worker': None, 'descendant': None},
        'identity_rechecks': dict.fromkeys(('preexec', 'postexec', 'armed_worker', 'armed_descendant',
                                          'presignal_worker', 'presignal_descendant',
                                          'guardian_before_descendant_signal')),
        'exec_protocol': {'attempted': False, 'entered_at_ns': None, 'returned': False,
            'result': None, 'errno': None, 'error_pipe_eof_at_ns': None,
            'startup_closed': {key: {'fd': -1, 'fact': fact()}
                               for key in ('leaf_exec', 'leaf_witness', 'exec_error_write')},
            'startup_private': {key: {'fd': -1, 'fact': fact()}
                                for key in ('command_read', 'report_write')},
            'original_stdio': {role: [{'fd': n, 'fact': fact()} for n in range(3)]
                               for role in ('worker', 'descendant')}},
        'adoptions': [],
        'pidfds': {tag: {'owner': owner, 'target': target, 'fd': -1, 'open': fact(),
            'identity_before': None, 'identity_after': None, 'fdinfo_pid': None,
            'fdinfo_matches': False, 'cloexec': fact(), 'initial_live': poll_row(tag),
            'close': fact(), 'F_GETFD_after_close': fact(), 'owner_death_teardown': False}
            for tag, (owner, target) in PAIRS.items()},
        'polls': [],
        'waits': {tag: {'owner': owner, 'target': target, 'pid': -1, 'attempts': 0,
                       'result': None, 'raw_status': None, 'errno': None, 'observed_at_ns': None}
                  for tag, (owner, target) in PAIRS.items()},
        'signals': {tag: {'owner': owner, 'target': target, 'budget': 0, 'consumed': False,
            'attempts': 0, 'fd': -1, 'signal': 9, 'flags': 0, 'result': None, 'errno': None,
            'observed_at_ns': None, 'presignal_identity': None}
            for tag, (owner, target) in PAIRS.items() if tag != 'E_D'},
        'fd_ledger': [], 'fd_flags': [], 'packets': [], 'command_forwards': [],
        'deadlines': {'t0_ns': t0, **{name: t0 + offset * 1000000000 for name, offset in
            (('work_ns', 5), ('cleanup_ns', 8), ('terminal_ns', 10), ('Gtotal_ns', 12), ('child_expiry_ns', 14))}},
        'times_ns': {**dict.fromkeys(TIME_NAMES), 'initial': t0},
        'controls': {**observer.AUTHORITY, 'fixed_exec_transition_verified': False,
                     'normal_reap_verified': False, 'worker_loss_adoption_verified': False},
        'negative_state': {**{key: [] for key in ('created', 'bound', 'adopted', 'terminal', 'reaped', 'unknown')},
            'descendant_creation_authorized': False, 'descendant_creation_observed': False,
            'negative_cleanup_signal_attempts': 0}}


def runtime_payload(case='normal'):
    """Synthetic complete fixed-case facts; never executes C, a syscall or a PID."""
    row = runtime_unknown_payload()
    row.update(case=case, status='success', error={'stage': 'none', 'role': None,
        'operation': None, 'errno': None, 'result': None, 'observed_at_ns': None})
    ids = row['identities_initial'] = {'guardian': identity('guardian', 42, 7, G_PRODUCT),
        'preexec_worker': identity('preexec_worker', 43, 42, G_PRODUCT),
        'worker': identity('worker', 43, 42, E_PRODUCT),
        'descendant': identity('descendant', 44, 43, E_PRODUCT)}
    t0 = row['deadlines']['t0_ns']
    at = lambda n: t0 + n * 1000000
    times = row['times_ns']
    for key, offset in (('initial', 0), ('preexec_ready', 10), ('exec_sent', 20),
            ('exec_entered', 30), ('postexec_ready', 40), ('postexec_validated', 50),
            ('create_D_sent', 60), ('D_ready', 70), ('all_bound', 80), ('arm_sent', 90),
            ('all_arm_ack', 100), ('primary', 110)):
        times[key] = at(offset)
    offsets = ((('finish_sent', 120), ('D_terminal', 130), ('D_reaped', 140),
        ('E_terminal', 150), ('E_reaped', 160), ('FD_complete', 170), ('reset', 180), ('final', 190))
        if case == 'normal' else (('E_signal', 120), ('E_terminal', 130), ('E_reaped', 140),
        ('D_adopted', 150), ('D_signal', 160), ('D_terminal', 170), ('D_reaped', 180),
        ('FD_complete', 190), ('reset', 200), ('final', 210)))
    for key, offset in offsets:
        times[key] = at(offset)
    row['subreaper'] = {'initial_get': fact(0, 0, 0, at(1)), 'set_one': fact(0, 0, 1, at(2)),
        'get_one': fact(0, 0, 1, at(3)), 'reset_zero': fact(0, 0, 0, times['reset']),
        'final_get': fact(0, 0, 0, times['reset'] + 1)}
    row['child_subreaper_get'] = {role: fact(0, 0, 0, at(offset)) for role, offset in
        (('preexec_worker', 9), ('worker', 39), ('descendant', 69))}
    row['local_sigpipe'] = {role: {'query': fact(0, 0, 1, at(offset)),
        'set_ignore': fact(0, 0, 1, at(offset) + 1)} for role, offset in
        (('guardian', 1), ('worker', 36), ('descendant', 66))}
    checks = row['identity_rechecks']
    checks.update(preexec=copy.deepcopy(ids['preexec_worker']), postexec=copy.deepcopy(ids['worker']),
                  armed_worker=copy.deepcopy(ids['worker']), armed_descendant=copy.deepcopy(ids['descendant']))
    ex = row['exec_protocol']
    ex.update(attempted=True, entered_at_ns=times['exec_entered'], error_pipe_eof_at_ns=at(35))
    for offset, (label, fd) in enumerate((('leaf_exec', 4), ('leaf_witness', 5), ('exec_error_write', 11))):
        ex['startup_closed'][label] = {'fd': fd, 'fact': fact(-1, 9, 0, at(31) + offset)}
    for offset, (label, fd) in enumerate((('command_read', 6), ('report_write', 9))):
        ex['startup_private'][label] = {'fd': fd, 'fact': fact(0, 0, 0, at(34 + offset))}
    for tag, fd, offset in (('G_E', 12, 11), ('G_D', 13, 74), ('E_D', 4, 72)):
        target = ids['preexec_worker' if tag == 'G_E' else 'descendant']
        h = row['pidfds'][tag]
        h.update(fd=fd, open=fact(fd, 0, 0, at(offset)), identity_before=copy.deepcopy(target),
                 identity_after=copy.deepcopy(target), fdinfo_pid=target['pid'], fdinfo_matches=True,
                 cloexec=fact(1, 0, 0, at(offset) + 1),
                 initial_live=poll_row(tag, fd, result=0, revents=0, at=at(offset) + 2))
        if tag == 'E_D' and case == 'worker_loss':
            h['owner_death_teardown'] = True
        else:
            end = times['D_reaped'] if tag == 'E_D' else times['FD_complete'] - 10
            h.update(close=fact(0, 0, 0, end + 1), F_GETFD_after_close=fact(-1, 9, 0, end + 2))
    row['polls'] = [poll_row('G_E', 12, 'postexec_live', 0, 0, at(45)),
                    poll_row('G_E', 12, 'armed_live', 0, 0, at(105)),
                    poll_row('G_D', 13, 'armed_live', 0, 0, at(105)),
                    poll_row('G_E', 12, 'terminal', 1, 1, times['E_terminal'])]
    if case == 'normal':
        row['polls'].append(poll_row('E_D', 4, 'terminal', 1, 1, times['D_terminal']))
        row['polls'].append(poll_row('G_D', 13, 'terminal', 1, 1, at(165)))
    else:
        row['polls'].append(poll_row('G_D', 13, 'terminal', 1, 1, times['D_terminal']))
    for tag, target, key in (('G_E', 'worker', 'E_reaped'),
                            ('E_D' if case == 'normal' else 'G_D', 'descendant', 'D_reaped')):
        row['waits'][tag].update(pid=ids[target]['pid'], attempts=3, result=ids[target]['pid'],
            raw_status=0 if case == 'normal' else 9, errno=0, observed_at_ns=times[key])
    for tag, signal in row['signals'].items():
        signal.update(budget=int(case == 'worker_loss'), fd=row['pidfds'][tag]['fd'])
    if case == 'worker_loss':
        adopted = {**copy.deepcopy(ids['descendant']), 'ppid': ids['guardian']['pid']}
        checks.update(presignal_worker=copy.deepcopy(ids['worker']), presignal_descendant=adopted,
                      guardian_before_descendant_signal=copy.deepcopy(ids['guardian']))
        row['adoptions'] = [{'target': 'descendant', 'old_parent': 43, 'new_parent': 42,
            'identity': copy.deepcopy(adopted), 'guardian_identity': copy.deepcopy(ids['guardian']),
            'observed_at_ns': times['D_adopted']}]
        for tag, target, key in (('G_E', ids['worker'], 'E_signal'), ('G_D', adopted, 'D_signal')):
            row['signals'][tag].update(consumed=True, attempts=1, result=0, errno=0,
                observed_at_ns=times[key], presignal_identity=copy.deepcopy(target))
            row['polls'].append(poll_row(tag, row['pidfds'][tag]['fd'], 'presignal_live',
                                        0, 0, times[key] - 1))

    ledger = row['fd_ledger']
    def close(owner, label, epoch, fd, offset, evidence='explicit_once_close'):
        item = {'owner': owner, 'label': label, 'epoch': epoch, 'fd': fd, 'evidence': evidence,
                'close': fact(), 'F_GETFD_after_close': fact()}
        if evidence == 'explicit_once_close':
            item.update(close=fact(0, 0, 0, at(offset)), F_GETFD_after_close=fact(-1, 9, 0, at(offset) + 1))
        ledger.append(item)
        return item

    for role in ('preexec_worker', 'worker', 'descendant'):
        for index, label in enumerate(('original_stdin', 'original_stdout', 'original_stderr')):
            close(role, label, 'original_stdio', index if role == 'preexec_worker' else -1, 5,
                  'explicit_once_close' if role == 'preexec_worker' else 'original_absent')
    for label, item in ex['startup_closed'].items():
        closed = close('worker', label, 'exec_entry', item['fd'], 0, 'exec_entry_closed')
        closed['F_GETFD_after_close'] = copy.deepcopy(item['fact'])
    for label, fd in (('command_read', 6), ('report_write', 9), ('exec_error_write', 11)):
        close('guardian', label, 'preexec', fd, 7)
    for label, fd in (('guardian_product', 3), ('command_write', 7), ('report_read', 8),
                      ('exec_error_read', 10)):
        close('preexec_worker', label, 'preexec', fd, 6)
    for label, fd in (('leaf_exec', 4), ('leaf_witness', 5)):
        close('guardian', label, 'preexec', fd, 51)
    for role, label, epoch, fd in (('worker', 'child_command_read', 'child_generation', 0),
            ('worker', 'child_report_write', 'child_generation', 3),
            ('descendant', 'command_read', 'preexec', 6), ('descendant', 'report_write', 'preexec', 9),
            ('descendant', 'child_command_write', 'child_generation', 1),
            ('descendant', 'child_report_read', 'child_generation', 2)):
        close(role, label, epoch, fd, 65)
    for tag in ('G_E', 'G_D'):
        h = row['pidfds'][tag]
        item = close('guardian', tag, 'preexec' if tag == 'G_E' else 'child_generation', h['fd'], 0)
        item['close'], item['F_GETFD_after_close'] = copy.deepcopy(h['close']), copy.deepcopy(h['F_GETFD_after_close'])
    for label, fd in (('guardian_product', 3), ('command_write', 7), ('report_read', 8), ('exec_error_read', 10)):
        close('guardian', label, 'preexec', fd, 169 if case == 'normal' else 189)
    if case == 'normal':
        for role, label, epoch, fd in (('worker', 'command_read', 'preexec', 6),
                ('worker', 'child_command_write', 'child_generation', 1),
                ('worker', 'child_report_read', 'child_generation', 2)):
            close(role, label, epoch, fd, 143)
        h = row['pidfds']['E_D']
        item = close('worker', 'E_D', 'child_generation', 4, 0)
        item['close'], item['F_GETFD_after_close'] = copy.deepcopy(h['close']), copy.deepcopy(h['F_GETFD_after_close'])
        close('descendant', 'child_command_read', 'child_generation', 0, 125)
        close('descendant', 'child_report_write', 'child_generation', 3, 0, 'parent_report_EOF')
        close('worker', 'report_write', 'preexec', 9, 0, 'parent_report_EOF')
    else:
        for label, epoch, fd in (('command_read', 'preexec', 6), ('report_write', 'preexec', 9),
                ('child_command_write', 'child_generation', 1), ('child_report_read', 'child_generation', 2),
                ('E_D', 'child_generation', 4)):
            close('worker', label, epoch, fd, 0, 'owner_death')
        for label, fd in (('child_command_read', 0), ('child_report_write', 3)):
            close('descendant', label, 'child_generation', fd, 0, 'unreturned_loss_close')
    flags = row['fd_flags']
    for index, label in enumerate(('original_stdin', 'original_stdout', 'original_stderr')):
        flags.append({'owner': 'guardian', 'label': label, 'epoch': 'original_stdio', 'fd': index,
            'F_GETFD_before': fact(0, 0, 0, at(1) + index + 2), 'F_SETFD': fact(),
            'F_GETFD_after': fact(), 'F_GETFL': fact()})
    for label, fd in (('guardian_product', 3), ('leaf_exec', 4), ('leaf_witness', 5),
            ('command_read', 6), ('command_write', 7), ('report_read', 8), ('report_write', 9),
            ('exec_error_read', 10), ('exec_error_write', 11)):
        flags.append({'owner': 'guardian', 'label': label, 'epoch': 'preexec', 'fd': fd,
            'F_GETFD_before': fact(1, 0, 0, at(1) + 10), 'F_SETFD': fact(), 'F_GETFD_after': fact(),
            'F_GETFL': fact(0 if label in ('guardian_product', 'leaf_exec', 'leaf_witness')
                           else 2049 if label.endswith('write') else 2048, 0, 0, at(1) + 11)})
    for label, fd in (('child_command_read', 0), ('child_command_write', 1),
                      ('child_report_read', 2), ('child_report_write', 3)):
        flags.append({'owner': 'worker', 'label': label, 'epoch': 'child_generation', 'fd': fd,
            'F_GETFD_before': fact(1, 0, 0, at(60) + 10), 'F_SETFD': fact(), 'F_GETFD_after': fact(),
            'F_GETFL': fact(2049 if label.endswith('write') else 2048, 0, 0, at(60) + 11)})
    for label, item in {**ex['startup_closed'], **ex['startup_private']}.items():
        retain = label in ex['startup_private']
        flags.append({'owner': 'preexec_worker', 'label': label, 'epoch': 'preexec', 'fd': item['fd'],
            'F_GETFD_before': fact(1, 0, 0, at(8)), 'F_SETFD': fact(0, 0, 0, at(8) + 1) if retain else fact(),
            'F_GETFD_after': fact(0, 0, 0, at(8) + 2) if retain else fact(),
            'F_GETFL': fact((2049 if label.endswith('write') else 2048)
                           if label not in ('leaf_exec', 'leaf_witness') else 0, 0, 0, at(8) + 3)})
    for role, label, epoch, fd in (('worker', 'command_read', 'preexec', 6),
            ('worker', 'report_write', 'preexec', 9),
            ('descendant', 'child_command_read', 'child_generation', 0),
            ('descendant', 'child_report_write', 'child_generation', 3)):
        retain = role == 'worker'
        flags.append({'owner': role, 'label': label, 'epoch': epoch, 'fd': fd,
            'F_GETFD_before': fact(0 if retain else 1, 0, 0, at(37 if retain else 66)),
            'F_SETFD': fact(0, 0, 0, at(37) + 1) if retain else fact(),
            'F_GETFD_after': fact(0, 0, 0, at(37) + 2) if retain else fact(),
            'F_GETFL': fact(2049 if label.endswith('write') else 2048, 0, 0, at(37 if retain else 66) + 3)})
    seq = {}
    def packet(source, kind, offset, aux=0, edge='G_E'):
        key = source, edge
        seq[key] = seq.get(key, 0) + 1
        row['packets'].append({'source': source, 'transport': 'worker' if source == 'descendant' else source,
            'edge': edge, 'direction': 'command' if source == 'guardian' else 'report', 'kind': kind,
            'sequence': seq[key], 'aux': aux, 'sent_at_ns': at(offset), 'observed_at_ns': at(offset),
            'shared_t0_ns': t0, 'bytes': 512, 'PIPE_BUF_bound': 4096,
            'forwarded_original': source == 'descendant'})
    packet('preexec_worker', 'PRODUCT_CHECK', 9, aux=1)
    packet('preexec_worker', 'PRODUCT_CHECK', 9, aux=2)
    packet('preexec_worker', 'PRE_EXEC_READY', 10)
    packet('guardian', 'EXEC', 20)
    packet('preexec_worker', 'EXEC_ENTER', 30)
    packet('worker', 'POST_EXEC_READY', 40)
    packet('guardian', 'CREATE_D', 60)
    packet('worker', 'D_CREATED', 61)
    packet('descendant', 'D_READY', 70, edge='E_D')
    packet('worker', 'HANDLE_FACT', 73, aux=2)
    packet('guardian', 'ARM', 90)
    packet('worker', 'COMMAND_FORWARDED', 91, aux=9)
    packet('descendant', 'ARM_ACK', 95, aux=3, edge='E_D')
    packet('worker', 'ALL_ARM_ACK', 100, aux=3)
    row['command_forwards'] = [{'owner': 'worker', 'kind': 'ARM', 'original_sequence': 3,
                               'observed_at_ns': at(90) + 1}]
    if case == 'normal':
        packet('guardian', 'FINISH', 120)
        packet('worker', 'COMMAND_FORWARDED', 121, aux=12)
        packet('descendant', 'D_FINISH_ACK', 126, aux=4, edge='E_D')
        packet('worker', 'E_FINISH_ACK', 145, aux=4)
        row['command_forwards'].append({'owner': 'worker', 'kind': 'FINISH',
                                       'original_sequence': 4, 'observed_at_ns': at(120) + 1})
    row['controls'].update(fixed_exec_transition_verified=True, normal_reap_verified=case == 'normal',
                           worker_loss_adoption_verified=case == 'worker_loss')
    row['negative_state'].update(created=['worker', 'descendant'], bound=['worker', 'descendant'],
        adopted=[] if case == 'normal' else ['descendant'], terminal=['worker', 'descendant'],
        reaped=['worker', 'descendant'], unknown=[], descendant_creation_authorized=True,
        descendant_creation_observed=True)
    return row


def flag_fault_payload(clock_error=False):
    """Synthetic failed preexec witness mutation, before any fexecve attempt."""
    row = runtime_unknown_payload()
    row['fault'] = 'witness_cloexec_cleared'
    row['error'] = {'stage': 'exec', 'role': 'preexec_worker',
        'operation': 'clock_gettime' if clock_error else 'fcntl',
        'errno': errno.EIO if clock_error else errno.EINTR,
        'result': -1, 'observed_at_ns': 1025000001}
    x = row['identities_initial']['preexec_worker'] = identity('preexec_worker', 43, 42, G_PRODUCT)
    row['identity_rechecks']['preexec'] = copy.deepcopy(x)
    row['subreaper'].update(initial_get=fact(0, 0, 0, 1001000000), set_one=fact(0, 0, 1, 1002000000),
                           get_one=fact(0, 0, 1, 1003000000))
    row['child_subreaper_get']['preexec_worker'] = fact(0, 0, 0, 1009000000)
    row['times_ns'].update(preexec_ready=1010000000, exec_sent=1020000000,
                           E_terminal=1040000000, E_reaped=1050000000, final=1060000000)
    h = row['pidfds']['G_E']
    h.update(fd=12, open=fact(12, 0, 0, 1011000000), identity_before=copy.deepcopy(x),
        identity_after=copy.deepcopy(x), fdinfo_pid=43, fdinfo_matches=True,
        cloexec=fact(1, 0, 0, 1011000001), initial_live=poll_row('G_E', 12, result=0, revents=0, at=1011000002),
        close=fact(0, 0, 0, 1051000000), F_GETFD_after_close=fact(-1, 9, 0, 1051000001))
    row['signals']['G_E']['fd'] = 12
    row['polls'] = [poll_row('G_E', 12, 'terminal', 1, 1, 1040000000)]
    row['waits']['G_E'].update(pid=43, attempts=2, result=43, raw_status=71 << 8, errno=0,
                             observed_at_ns=1050000000)
    row['fd_flags'] = [
        {'owner': 'preexec_worker', 'label': 'leaf_witness', 'epoch': 'preexec', 'fd': 5,
         'F_GETFD_before': fact(1, 0, 0, 1008000000), 'F_SETFD': fact(), 'F_GETFD_after': fact(),
         'F_GETFL': fact(0, 0, 0, 1008000001)},
        {'owner': 'preexec_worker', 'label': 'leaf_witness', 'epoch': 'preexec', 'fd': 5,
         'F_GETFD_before': fact(1, 0, 0, 1025000000),
         'F_SETFD': fact() if clock_error else fact(-1, errno.EINTR, 0, 1025000001),
         'F_GETFD_after': fact() if clock_error else fact(1, 0, 0, 1025000002),
         'F_GETFL': fact() if clock_error else fact(0, 0, 0, 1025000003)}]
    row['packets'] = [{'source': source, 'transport': source, 'edge': 'G_E',
        'direction': 'command' if source == 'guardian' else 'report', 'kind': kind,
        'sequence': sequence, 'aux': 0, 'sent_at_ns': sent, 'observed_at_ns': received,
        'shared_t0_ns': 1000000000, 'bytes': 512, 'PIPE_BUF_bound': 4096, 'forwarded_original': False}
        for source, kind, sequence, sent, received in (
            ('preexec_worker', 'PRE_EXEC_READY', 1, 1010000000, 1010000000),
            ('guardian', 'EXEC', 1, 1020000000, 1020000000),
            ('preexec_worker', 'ERROR', 2, 1025000001, 1026000000))]
    row['negative_state'].update(created=['worker'], bound=['worker'], terminal=['worker'], reaped=['worker'])
    return row


def synthetic_self():
    return {'boot_id': BOOT, 'pid': 42, 'ppid': 7, 'pgrp': 42, 'session': 42,
            'start_ticks': 100, 'state': 'R', 'uid': os.getuid(), 'euid': os.getuid(),
            'proc_uids': [os.getuid()] * 4, 'parent_identity_verified': False,
            'ancestry_verified': False}


def request_row():
    return {'schema_version': 1, 'scope': observer.SCOPE, 'nonce': NONCE,
            'observer_sha256': 'f' * 64, 'c_sources_sha256': SOURCE_HASHES.copy(),
            'identity_helper_sha256': observer.HELPER_SHA,
            'toolchain_sha256': observer.TOOLCHAIN_SHA, 'linkage_sha256': observer.LINKAGE_SHA,
            'case': 'normal', 'attempt_directory': '/fixture/new-attempt',
            'host': {'node_alias': 'N1-1', 'hostname': 'fixture-host', 'boot_id': BOOT,
                     'uid': os.getuid()},
            'bootstrap': {'executable': '/fixture/bootstrap', 'sha256': 'b' * 64,
                          'version': [3, 11, 15]}, 'authority': observer.AUTHORITY.copy()}


class ObserverFixture:
    """Owned local files and injected fixture results; no C or host activity."""
    def __enter__(self):
        self.stack = ExitStack()
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.source = self.directory / 'observer.py'
        self.source.write_bytes(b'# Injected new exec/descendant observer binding.\n')
        self.sources = {}
        for name in observer.C_NAMES:
            path = self.directory / name
            path.write_bytes((ROOT / 'scripts' / name).read_bytes())
            self.sources[name] = path
        for name, attribute in (('frontier_v8_containment_capability.py', 'helper_path'),
                ('frontier_v8_c_toolchain.py', 'utility_path'),
                ('frontier_v8_owned_c_selfcheck.py', 'linkage_path')):
            path = self.directory / name
            path.write_bytes((ROOT / 'scripts' / name).read_bytes())
            setattr(self, attribute, path)
        self.bootstrap = self.directory / 'bootstrap'
        self.bootstrap.write_bytes(b'injected bootstrap bytes')
        with patch.object(observer, '__file__', str(self.source)):
            self.helper, self.utility, self.linkage = observer.load_utilities()
        self.attempt, self.request_path = self.directory / 'attempt', self.directory / 'request.json'
        self.request = request_row()
        self.request.update({'nonce': secrets.token_hex(32),
            'observer_sha256': observer.digest(self.source.read_bytes()),
            'c_sources_sha256': {name: observer.digest(path.read_bytes())
                                for name, path in self.sources.items()},
            'attempt_directory': str(self.attempt),
            'bootstrap': {'executable': str(self.bootstrap),
                'sha256': observer.digest(self.bootstrap.read_bytes()),
                'version': list(sys.version_info[:3])}})
        self.write_request()
        self.pipeline = Mock(return_value={**observer.AUTHORITY,
            **dict.fromkeys(observer.SUCCESS, False), observer.SUCCESS[0]: True,
            observer.SUCCESS[1]: True, 'status': 'success'})
        for target, attribute, value in (
                (observer, '__file__', str(self.source)),
                (observer, 'load_utilities', Mock(return_value=(self.helper, self.utility, self.linkage))),
                (observer, 'run_fixture', self.pipeline),
                (self.utility, 'CompilerBackend', Mock()),
                (observer.sys, 'flags', SimpleNamespace(isolated=1, no_site=1)),
                (observer.sys, 'dont_write_bytecode', True),
                (observer.sys, 'platform', 'linux'),
                (observer.sys, 'executable', str(self.bootstrap)),
                (observer.os, 'uname', Mock(return_value=SimpleNamespace(nodename='fixture-host'))),
                (self.helper, 'capture_self_identity', Mock(side_effect=lambda: synthetic_self()))):
            self.stack.enter_context(patch.object(target, attribute, value))
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def write_request(self):
        body = json.dumps(self.request, sort_keys=True).encode()
        self.request_path.write_bytes(body)
        self.request_sha = observer.digest(body)

    def observe(self):
        return observer.observe(str(self.request_path), self.request_sha)

    @property
    def marker(self):
        return self.attempt.with_name(self.attempt.name + '.consumed.json')


class PipelineFixture:
    """Injected two-product pipeline, without a compiler or runtime process."""
    def __enter__(self):
        self.stack = ExitStack()
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        self.stack.callback(os.close, self.fd)
        self.sources = {name: self.root / name for name in observer.C_NAMES}
        self.utility = SimpleNamespace(CompilerBackend=Mock(side_effect=lambda helper, root, fd:
                                       SimpleNamespace(root=root, root_fd=fd)))
        self.command = {'status': 'success', 'returncode': 0, 'timed_out': False, 'kill_attempted': False,
                        'direct_child_pid': 42, 'reap_completed': True,
                        'stdout': {'sha256': observer.digest(b'{}'), 'bytes': 2},
                        'stderr': {'sha256': observer.digest(b''), 'bytes': 0}}
        def run(label, argv):
            self.command['argv'] = argv.copy()
            return self.command
        def read_output(name, limit):
            return ((b'{}', self.command['stdout']) if name == 'runtime.stdout'
                    else (b'', self.command['stderr']))
        self.backend = SimpleNamespace(root=self.root, root_fd=self.fd, helper=object(),
            run=Mock(side_effect=run), read_output=Mock(side_effect=read_output))
        self.built = []
        self.rechecks = []

        def build(source, header, backend, utility, linkage, name, record):
            self.built.append((name, source, header))
            record.update({'status': 'success', 'compile_leg': {
                'cpp_facts': {'fixture': 'opaque'}, 'headers': {str(header): {'fixture': 'stable'}}},
                'product': {'path': str(backend.root / name),
                    'identity': [1, 2 if name == 'guardian' else 3, 0o100700, os.getuid(), 128, 6, 7]}})
            recheck = Mock()
            self.rechecks.append(recheck)
            return recheck

        self.build = self.stack.enter_context(patch.object(observer, 'build_product', side_effect=build))
        self.parse = self.stack.enter_context(patch.object(observer, 'parse_runtime',
                                                        return_value={'status': 'success'}))
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def run(self, case='normal', nonce=NONCE, callback=None, fault='none', sources=None):
        return observer.run_fixture(self.sources if sources is None else sources, self.backend,
            self.utility, object(), case, nonce, 7, os.getuid(), BOOT, callback, fault)


class ExecDescendantTests(unittest.TestCase):
    def assert_no_authority(self, row):
        for key in observer.AUTHORITY:
            self.assertIs(row[key], False, key)

    def parse_request(self, body, expected=None):
        helper, _, _ = observer.load_utilities()
        return observer.parse_request(body, expected or observer.digest(body), 'f' * 64,
                                      SOURCE_HASHES, helper)

    def parse_runtime(self, row, command=None):
        body = json.dumps(row).encode() if type(row) is dict else row
        positive = type(row) is dict and row['status'] == 'success'
        cmd = {'direct_child_pid': 42, 'status': 'success' if positive else 'failed', 'returncode': 0 if positive else 1,
               'timed_out': False, 'kill_attempted': False, 'reap_completed': True,
               'argv': ['/fixture/guardian', row.get('case', 'normal') if type(row) is dict else 'normal',
                        NONCE, '/fixture/leaf', row.get('fault', 'none') if type(row) is dict else 'none']}
        if command is not None:
            cmd = command
        return observer.parse_runtime(body, cmd, CPP, 7, os.getuid(), BOOT, row.get('case', 'normal')
            if type(row) is dict else 'normal', NONCE, G_PRODUCT, E_PRODUCT,
            row.get('fault', 'none') if type(row) is dict else 'none')

    def test_runtime_early_error_preserves_unknown_unattempted_operations_without_reset_or_authority(self):
        row = runtime_unknown_payload()
        parsed = self.parse_runtime(row)
        self.assertEqual(parsed, row)
        self.assertEqual(parsed['error'], row['error'])
        self.assert_no_authority(parsed['controls'])
        self.assertTrue(all(not value['attempted'] for value in parsed['subreaper'].values()))
        self.assertIsNone(parsed['identities_initial']['descendant'])
        self.assertEqual(sum(value['attempts'] for value in parsed['signals'].values()), 0)

    def test_runtime_partial_duplicate_nonfinite_extra_and_boolean_machine_values_are_refused(self):
        row = runtime_unknown_payload()
        raw = json.dumps(row).encode()
        for body in (raw[:-1], b'{"schema_version":1,' + raw[1:],
                     raw.replace(b'"schema_version": 1', b'"schema_version": NaN')):
            with self.subTest(body=body[:50]), self.assertRaises(ValueError):
                self.parse_runtime(body)
        for key, value in (('schema_version', True), ('extra', None), ('nonce', 'wrong'),
                           ('scope', 'old-scope')):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse_runtime({**row, key: value})
        for key, value in (('pid', True), ('pid', 1 << 31), ('uid', 1 << 32),
                           ('start_ticks', 1 << 64), ('euid', -1)):
            changed = copy.deepcopy(row)
            changed['identities_initial']['guardian'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.parse_runtime(changed)

    def test_runtime_header_representation_product_binding_and_operation_integer_bounds_are_required(self):
        row = runtime_unknown_payload()
        for key, value in (('target_long_bytes', 16), ('pid_t_signed', 1),
                ('uid_t_signed', True), ('uid_max', 1 << 32), ('int64_min', -(1 << 63) + 1),
                ('PIPE_BUF', 128), ('SIGKILL', 15), ('pidfd_open', 1 << 63)):
            changed = copy.deepcopy(row)
            changed['headers'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse_runtime(changed)
        changed = copy.deepcopy(row)
        changed['products']['leaf']['ino'] += 1
        with self.assertRaises(ValueError):
            self.parse_runtime(changed)
        for bad in (fact(1 << 31, 0, at=1000000000),
                    fact(0, 1 << 31, at=1000000000),
                    {'attempted': False, 'result': 0, 'errno': 0, 'value': 0, 'observed_at_ns': 1}):
            changed = copy.deepcopy(row)
            changed['subreaper']['initial_get'] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.parse_runtime(changed)

    def test_runtime_unknown_cannot_invent_close_reap_signal_or_subreaper_reset(self):
        row = runtime_unknown_payload()
        changes = []
        changed = copy.deepcopy(row)
        changed['pidfds']['G_E']['close'] = {'attempted': False, 'result': 0, 'errno': 0,
                                            'value': None, 'observed_at_ns': 1000000000}
        changes.append(changed)
        changed = copy.deepcopy(row)
        changed['waits']['G_E']['result'] = 43
        changes.append(changed)
        changed = copy.deepcopy(row)
        changed['signals']['G_E']['consumed'] = True
        changes.append(changed)
        changed = copy.deepcopy(row)
        changed['subreaper']['reset_zero'] = fact(0, 0, 0, 1000000001)
        changes.append(changed)
        for index, changed in enumerate(changes):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.parse_runtime(changed)

    def test_runtime_FD_provenance_duplicates_and_original_absent_with_invented_EBADF_are_refused(self):
        row = runtime_unknown_payload()
        item = {'owner': 'descendant', 'label': 'original_stdin', 'epoch': 'original_stdio', 'fd': -1,
                'evidence': 'original_absent', 'close': fact(), 'F_GETFD_after_close': fact()}
        for items in ([item, copy.deepcopy(item)],
                      [{**item, 'F_GETFD_after_close': fact(-1, errno.EBADF, at=1000000001)}],
                      [{**item, 'close': fact(0, 0, at=1000000001)}]):
            changed = copy.deepcopy(row)
            changed['fd_ledger'] = items
            with self.subTest(items=items), self.assertRaises(ValueError):
                self.parse_runtime(changed)

    def test_witness_fault_two_flag_operations_share_one_handle_and_preserve_failed_or_uncalled_set(self):
        for clock_error in (False, True):
            with self.subTest(clock_error=clock_error):
                row = flag_fault_payload(clock_error)
                parsed = self.parse_runtime(row)
                self.assertEqual(parsed, row)
                self.assertEqual(parsed['fd_flags'][0]['fd'], parsed['fd_flags'][1]['fd'])
                self.assertFalse(parsed['exec_protocol']['attempted'])
                self.assertFalse(parsed['exec_protocol']['returned'])
                self.assertIsNone(parsed['identities_initial']['descendant'])
                self.assertEqual(sum(value['attempts'] for value in parsed['signals'].values()), 0)
                if clock_error:
                    self.assertFalse(parsed['fd_flags'][1]['F_SETFD']['attempted'])
                else:
                    self.assertEqual(parsed['fd_flags'][1]['F_SETFD']['result'], -1)
                    self.assertEqual(parsed['fd_flags'][1]['F_SETFD']['errno'], errno.EINTR)
        for problem in ('third', 'different_fd', 'other_owner', 'other_label', 'other_fault', 'success'):
            row = flag_fault_payload()
            if problem == 'third':
                row['fd_flags'].append(copy.deepcopy(row['fd_flags'][1]))
            elif problem == 'different_fd':
                row['fd_flags'][1]['fd'] += 1
            elif problem in ('other_owner', 'other_label'):
                key, value = ('owner', 'worker') if problem == 'other_owner' else ('label', 'command_read')
                for item in row['fd_flags']:
                    item[key] = value
            elif problem == 'other_fault':
                row['fault'] = 'exec_fd_closed'
            else:
                row['status'] = 'success'
            with self.subTest(problem=problem), self.assertRaises(ValueError):
                self.parse_runtime(row)

    def test_runtime_absolute_budget_packet_bounds_and_broad_control_unlock_are_refused(self):
        row = runtime_unknown_payload()
        for change in ('deadline', 'reverse', 'broad', 'narrow'):
            changed = copy.deepcopy(row)
            if change == 'deadline':
                changed['deadlines']['work_ns'] += 1
            elif change == 'reverse':
                changed['times_ns']['initial'] -= 1
            elif change == 'broad':
                changed['controls']['execution_available'] = True
            else:
                changed['controls']['fixed_exec_transition_verified'] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.parse_runtime(changed)
        packet = {'source': 'guardian', 'transport': 'guardian', 'edge': 'G_E', 'direction': 'command',
                  'kind': 'EXEC', 'sequence': 1, 'aux': 0, 'sent_at_ns': 1000000002,
                  'observed_at_ns': 1000000001, 'shared_t0_ns': 1000000000, 'bytes': 128,
                  'PIPE_BUF_bound': 4096, 'forwarded_original': False}
        changed = copy.deepcopy(row)
        changed['packets'] = [packet]
        with self.assertRaises(ValueError):
            self.parse_runtime(changed)

    def test_complete_synthetic_normal_and_loss_recompute_distinct_owned_wait_chains(self):
        for case in ('normal', 'worker_loss'):
            with self.subTest(case=case):
                row = runtime_payload(case)
                self.assertEqual(self.parse_runtime(row), row)
                self.assert_no_authority(row['controls'])
                self.assertEqual(row['waits']['G_E']['raw_status'], 0 if case == 'normal' else 9)
                self.assertEqual(row['signals']['G_E']['attempts'], int(case == 'worker_loss'))
                self.assertEqual(row['signals']['G_D']['attempts'], int(case == 'worker_loss'))

    def test_exec_EOF_requires_same_PID_birth_boot_parent_product_and_five_startup_FD_facts(self):
        baseline = runtime_payload()
        for problem in ('EOF', 'PID', 'birth', 'boot', 'parent', 'product', 'witness', 'private_CLOEXEC'):
            row = copy.deepcopy(baseline)
            if problem == 'EOF':
                row['exec_protocol']['error_pipe_eof_at_ns'] = None
            elif problem == 'witness':
                row['exec_protocol']['startup_closed']['leaf_witness']['fact'] = fact(0, 0, 0, 1031000001)
            elif problem == 'private_CLOEXEC':
                row['exec_protocol']['startup_private']['command_read']['fact']['result'] = 1
            else:
                changes = {'PID': ('pid', 45), 'birth': ('start_ticks', 999), 'boot': ('boot_id', BOOT[:-1] + '2'),
                           'parent': ('ppid', 7), 'product': ('product_identity', product_identity(G_PRODUCT))}
                key, value = changes[problem]
                row['identities_initial']['worker'][key] = value
            with self.subTest(problem=problem), self.assertRaises(ValueError):
                self.parse_runtime(row)

    def test_packet_release_order_missing_ARM_ACK_origin_sequence_or_forwarded_role_cannot_succeed(self):
        baseline = runtime_payload()
        for problem in ('CREATE_before_postexec', 'missing_CREATE', 'missing_ACK', 'sequence', 'source', 'forwarded',
                        'missing_product', 'duplicate_product_aux', 'late_product'):
            row = copy.deepcopy(baseline)
            if problem == 'CREATE_before_postexec':
                row['times_ns']['create_D_sent'] = row['times_ns']['postexec_ready'] - 1
            elif problem in ('missing_CREATE', 'missing_ACK'):
                kind = 'CREATE_D' if problem == 'missing_CREATE' else 'ARM_ACK'
                row['packets'] = [item for item in row['packets'] if item['kind'] != kind]
            elif problem in ('missing_product', 'duplicate_product_aux', 'late_product'):
                packet = next(item for item in row['packets'] if item['kind'] == 'PRODUCT_CHECK' and item['aux'] == 2)
                if problem == 'missing_product':
                    row['packets'].remove(packet)
                elif problem == 'duplicate_product_aux':
                    packet['aux'] = 1
                else:
                    row['packets'].remove(packet)
                    packet['sent_at_ns'] = packet['observed_at_ns'] = row['times_ns']['preexec_ready'] + 1
                    position = next(index for index, item in enumerate(row['packets']) if item['kind'] == 'PRE_EXEC_READY')
                    row['packets'].insert(position + 1, packet)
            else:
                packet = next(item for item in row['packets'] if item['kind'] == 'ARM_ACK')
                if problem == 'sequence':
                    packet['sequence'] += 1
                elif problem == 'source':
                    packet['source'] = 'worker'
                else:
                    packet['forwarded_original'] = False
            if problem != 'sequence':
                sequences = {}
                for packet in row['packets']:
                    key = packet['source'], packet['edge']
                    sequences[key] = sequences.get(key, 0) + 1
                    packet['sequence'] = sequences[key]
            with self.subTest(problem=problem), self.assertRaises(ValueError):
                self.parse_runtime(row)

    def test_wrong_reap_owner_raw_wait_parent_or_adoption_identity_is_refused(self):
        for problem in ('normal_owner', 'normal_raw', 'normal_G_D_wait', 'loss_parent', 'loss_birth', 'loss_guardian'):
            row = runtime_payload('normal' if problem.startswith('normal') else 'worker_loss')
            if problem == 'normal_owner':
                row['waits']['E_D']['owner'] = 'guardian'
            elif problem == 'normal_raw':
                row['waits']['E_D']['raw_status'] = 9
            elif problem == 'normal_G_D_wait':
                row['waits']['G_D'].update(attempts=1, result=44, raw_status=0, errno=0, observed_at_ns=1140000000)
            else:
                if problem == 'loss_parent':
                    row['adoptions'][0]['new_parent'] = 7
                elif problem == 'loss_birth':
                    row['adoptions'][0]['identity']['start_ticks'] += 1
                else:
                    row['adoptions'][0]['guardian_identity']['pid'] = 7
            with self.subTest(problem=problem), self.assertRaises(ValueError):
                self.parse_runtime(row)

    def test_descendant_child_pipe_reuses_FD_zero_with_absent_original_stdio_and_no_budget_reset(self):
        row = runtime_payload()
        self.assertEqual(self.parse_runtime(row), row)
        item = next(item for item in row['fd_flags'] if item['owner'] == 'descendant'
                    and item['label'] == 'child_command_read')
        self.assertEqual(item['fd'], 0)
        stdio = next(item for item in row['fd_ledger'] if item['owner'] == 'descendant'
                     and item['label'] == 'original_stdin')
        self.assertEqual(stdio['fd'], -1)
        self.assertFalse(stdio['close']['attempted'])
        for problem in ('stdio_closes_retained_pipe', 'duplicate_generation'):
            changed = copy.deepcopy(row)
            if problem == 'stdio_closes_retained_pipe':
                item = next(item for item in changed['fd_ledger'] if item['owner'] == 'descendant'
                            and item['label'] == 'original_stdin')
                item.update(fd=0, evidence='explicit_once_close', close=fact(0, 0, 0, 1065000000),
                            F_GETFD_after_close=fact(-1, 9, 0, 1065000001))
            else:
                item = next(item for item in changed['fd_ledger'] if item['owner'] == 'descendant'
                            and item['label'] == 'child_command_read')
                changed['fd_ledger'].append(copy.deepcopy(item))
            with self.subTest(problem=problem), self.assertRaises(ValueError):
                self.parse_runtime(changed)

    def test_original_signal_budgets_wrong_handle_twice_signal_and_E_D_owner_death_fact_are_refused(self):
        for problem in ('normal_budget', 'normal_signal', 'loss_twice', 'loss_handle', 'loss_E_D_close'):
            row = runtime_payload('normal' if problem.startswith('normal') else 'worker_loss')
            if problem == 'normal_budget':
                row['signals']['G_E']['budget'] = 1
            elif problem == 'normal_signal':
                row['signals']['G_E'].update(attempts=1, consumed=True, result=0, errno=0,
                    observed_at_ns=1110000000, presignal_identity=copy.deepcopy(row['identities_initial']['worker']))
            elif problem == 'loss_twice':
                row['signals']['G_E']['attempts'] = 2
            elif problem == 'loss_handle':
                row['signals']['G_D']['fd'] = row['pidfds']['G_E']['fd']
            else:
                row['pidfds']['E_D'].update(close=fact(0, 0, 0, 1140000000),
                                           F_GETFD_after_close=fact(-1, 9, 0, 1140000001))
            with self.subTest(problem=problem), self.assertRaises(ValueError):
                self.parse_runtime(row)

    def test_failed_planned_E_signal_preserves_consumed_budget_and_permanently_disables_D_signal(self):
        row = runtime_payload('worker_loss')
        row['status'] = 'failed'
        row['error'] = {'stage': 'worker_loss', 'role': 'guardian', 'operation': 'pidfd_send_signal',
                        'errno': errno.EINTR, 'result': -1, 'observed_at_ns': row['times_ns']['E_signal']}
        row['controls'].update(fixed_exec_transition_verified=False, normal_reap_verified=False,
                               worker_loss_adoption_verified=False)
        row['signals']['G_E'].update(result=-1, errno=errno.EINTR)
        row['signals']['G_D'].update(consumed=False, attempts=0, result=None, errno=None,
                                    observed_at_ns=None, presignal_identity=None)
        row['adoptions'] = []
        row['identity_rechecks'].update(presignal_descendant=None, guardian_before_descendant_signal=None)
        row['pidfds']['E_D']['owner_death_teardown'] = False
        row['subreaper'].update(reset_zero=fact(), final_get=fact())
        for key in ('E_terminal', 'E_reaped', 'D_adopted', 'D_signal', 'D_terminal', 'D_reaped', 'FD_complete', 'reset', 'final'):
            row['times_ns'][key] = None
        for tag in ('G_E', 'G_D'):
            row['waits'][tag].update(pid=-1, attempts=0, result=None, raw_status=None, errno=None, observed_at_ns=None)
        row['polls'] = [value for value in row['polls'] if value['stage'] != 'terminal'
                        and not (value['handle'] == 'G_D' and value['stage'] == 'presignal_live')]
        row['fd_ledger'] = [item for item in row['fd_ledger'] if item['evidence'] not in
                            ('owner_death', 'unreturned_loss_close')]
        row['negative_state'].update(adopted=[], terminal=[], reaped=[], unknown=['worker', 'descendant'])
        parsed = self.parse_runtime(row)
        self.assertEqual(parsed['error'], row['error'])
        self.assertTrue(parsed['signals']['G_E']['consumed'])
        self.assertEqual(parsed['signals']['G_E']['attempts'], 1)
        for problem in ('D_signal', 'reset_budget'):
            changed = copy.deepcopy(row)
            if problem == 'D_signal':
                changed['signals']['G_D'].update(consumed=True, attempts=1, result=0, errno=0,
                    observed_at_ns=row['error']['observed_at_ns'] + 1,
                    presignal_identity=copy.deepcopy(row['identities_initial']['descendant']))
            else:
                changed['signals']['G_E']['consumed'] = False
            with self.subTest(problem=problem), self.assertRaises(ValueError):
                self.parse_runtime(changed)

    def test_fresh_signal_work_cleanup_clocks_and_missing_terminal_reset_cannot_succeed(self):
        for problem in ('E_expired', 'D_expired', 'reverse', 'nonfinite', 'missing_FD_complete', 'missing_reset', 'missing_final'):
            row = runtime_payload('worker_loss')
            if problem == 'E_expired':
                row['times_ns']['E_signal'] = row['signals']['G_E']['observed_at_ns'] = row['deadlines']['work_ns']
            elif problem == 'D_expired':
                row['times_ns']['D_signal'] = row['signals']['G_D']['observed_at_ns'] = row['deadlines']['cleanup_ns']
            elif problem == 'reverse':
                row['times_ns']['all_arm_ack'] = row['times_ns']['arm_sent'] - 1
            elif problem == 'nonfinite':
                row['times_ns']['final'] = float('inf')
            elif problem == 'missing_FD_complete':
                row['times_ns']['FD_complete'] = None
            elif problem == 'missing_reset':
                row['subreaper']['reset_zero'] = fact()
            else:
                row['times_ns']['final'] = None
            with self.subTest(problem=problem), self.assertRaises(ValueError):
                self.parse_runtime(row)

    def test_partial_post_reap_reset_failure_retains_actual_attempt_without_success(self):
        row = runtime_payload()
        row.update(status='failed', error={'stage': 'terminal', 'role': 'guardian', 'operation': 'prctl',
            'errno': errno.EIO, 'result': -1, 'observed_at_ns': row['times_ns']['reset'] + 1})
        row['controls'].update(fixed_exec_transition_verified=False, normal_reap_verified=False,
                               worker_loss_adoption_verified=False)
        row['subreaper']['final_get'] = fact(-1, errno.EIO, -1, row['error']['observed_at_ns'])
        row['times_ns']['final'] = None
        parsed = self.parse_runtime(row)
        self.assertEqual(parsed, row)
        self.assertTrue(parsed['subreaper']['reset_zero']['attempted'])
        self.assertEqual(parsed['subreaper']['final_get']['result'], -1)
        self.assertFalse(parsed['controls']['normal_reap_verified'])

    def test_request_binds_three_C_sources_three_utilities_case_and_exact_raw_hash(self):
        row = request_row()
        body = json.dumps(row).encode()
        self.assertEqual(self.parse_request(body), row)
        for key, value in (('schema_version', True), ('scope', 'old-scope'), ('case', 'controller_loss'),
                ('nonce', 'short'), ('observer_sha256', '0' * 64), ('identity_helper_sha256', '0' * 64),
                ('toolchain_sha256', '0' * 64), ('linkage_sha256', '0' * 64), ('extra', False)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse_request(json.dumps({**row, key: value}).encode())
        with self.assertRaises(ValueError):
            self.parse_request(body + b' ', observer.digest(body))
        for sources in ({}, {**SOURCE_HASHES, 'other.c': '4' * 64},
                        {**SOURCE_HASHES, observer.C_NAMES[0]: '0' * 64}):
            with self.subTest(sources=sources), self.assertRaises(ValueError):
                self.parse_request(json.dumps({**row, 'c_sources_sha256': sources}).encode())

    def test_request_rejects_boolean_and_out_of_machine_bounds_UID_and_false_authority_drift(self):
        row = request_row()
        for uid in (True, -1, 1 << 32):
            with self.subTest(uid=uid), self.assertRaises(ValueError):
                self.parse_request(json.dumps({**row, 'host': {**row['host'], 'uid': uid}}).encode())
        for key in observer.AUTHORITY:
            for value in (True, 0, None):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.parse_request(json.dumps({**row, 'authority': {**observer.AUTHORITY, key: value}}).encode())
        for host in ({**row['host'], 'node_alias': 'N1-2'}, {**row['host'], 'boot_id': 'other'},
                     {**row['host'], 'hostname': ''}):
            with self.subTest(host=host), self.assertRaises(ValueError):
                self.parse_request(json.dumps({**row, 'host': host}).encode())

    def test_request_duplicate_nonfinite_partial_and_virtual_paths_are_refused(self):
        body = json.dumps(request_row()).encode()
        for raw in (b'{"schema_version":1,' + body[1:], body[:-1],
                    body.replace(b'"schema_version": 1', b'"schema_version": NaN')):
            with self.subTest(raw=raw[:64]), self.assertRaises(ValueError):
                self.parse_request(raw)
        for key, path in (('attempt_directory', '/proc/self/fd/0'),
                          ('attempt_directory', '/fixture/../old'), ('attempt_directory', 'relative')):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.parse_request(json.dumps({**request_row(), key: path}).encode())

    def test_CPP_has_eighteen_closed_opaque_expressions_without_python_evaluation(self):
        facts = observer.parse_exec_cpp_markers(EXTRA_CPP)
        self.assertEqual(facts, {key: value for key, value in EXTRA_EXPRESSIONS.values()})
        self.assertEqual(facts['SYS_pidfd_send_signal_expression'], '((1 << 8) + 10L)')
        for raw in (EXTRA_CPP + EXTRA_CPP, EXTRA_CPP.replace(b'36;', b'PR_SET_CHILD_SUBREAPER;'),
                    EXTRA_CPP.replace(b'36;', b'unknown_call();'), EXTRA_CPP[:-80]):
            with self.subTest(raw=raw[:40]), self.assertRaises(ValueError):
                observer.parse_exec_cpp_markers(raw)

    def test_prevalidation_drift_never_consumes_new_case_or_enters_C_fixture(self):
        for change in ('source', 'C', 'helper_path', 'utility_path', 'linkage_path', 'bootstrap'):
            with self.subTest(change=change), ObserverFixture() as f:
                path = f.sources[observer.C_NAMES[0]] if change == 'C' else getattr(f, change)
                path.write_bytes(path.read_bytes() + b' changed')
                with self.assertRaises((ValueError, OSError)):
                    f.observe()
                f.pipeline.assert_not_called()
                self.assertFalse(f.marker.exists())
                self.assertFalse(f.attempt.exists())

    def test_success_consumes_once_retains_bound_receipt_and_only_case_flags(self):
        with ObserverFixture() as f:
            row = f.observe()
            self.assertEqual(row['status'], 'fixed_owned_C_exec_descendant_observed', row)
            self.assert_no_authority(row)
            self.assertIs(row[observer.SUCCESS[0]], True)
            self.assertIs(row[observer.SUCCESS[1]], True)
            self.assertIs(row[observer.SUCCESS[2]], False)
            self.assertEqual(json.loads((f.attempt / 'receipt.json').read_bytes()), row)
            marker = f.marker.read_bytes()
            with self.assertRaises((ValueError, OSError)):
                f.observe()
            self.assertEqual(f.pipeline.call_count, 1)
            self.assertEqual(f.marker.read_bytes(), marker)

    def test_postvalidation_drift_or_failed_fixture_stays_consumed_with_all_narrow_flags_false(self):
        for failure in ('fixture', 'source', 'marker', 'self'):
            with self.subTest(failure=failure), ObserverFixture() as f:
                success = f.pipeline.return_value
                if failure == 'fixture':
                    f.pipeline.return_value = {**observer.AUTHORITY,
                        **dict.fromkeys(observer.SUCCESS, False), 'status': 'failed'}
                elif failure == 'self':
                    f.helper.capture_self_identity.side_effect = [synthetic_self(),
                        {**synthetic_self(), 'start_ticks': 101}]
                else:
                    def pipeline(*args):
                        path = f.source if failure == 'source' else f.marker
                        path.write_bytes(path.read_bytes() + b' changed')
                        return success
                    f.pipeline.side_effect = pipeline
                row = f.observe()
                self.assertEqual(row['status'], 'failed', row)
                self.assert_no_authority(row)
                self.assertTrue(f.marker.exists())
                self.assertFalse(any(row[key] for key in observer.SUCCESS))

    def test_captured_utility_cache_and_changed_pinned_linkage_body_are_refused(self):
        original = observer.load_utilities
        for name in ('frontier_v8_exec_descendant_identity_helper',
                     'frontier_v8_exec_descendant_build_utility',
                     'frontier_v8_exec_descendant_linkage_utility'):
            with self.subTest(name=name), patch.dict(sys.modules, {name: object()}), \
                    self.assertRaises(ValueError):
                original()
        with ObserverFixture() as f:
            f.linkage_path.write_bytes(b'changed pinned pure linkage utility')
            with patch.object(observer, 'load_utilities', original), self.assertRaises((ValueError, OSError)):
                f.observe()

    def test_execute_refuses_before_argument_parser_utilities_request_or_C_fixture(self):
        with patch.object(observer, 'load_utilities') as utilities, \
                patch.object(observer, 'observe') as observe, \
                patch.object(observer, 'run_fixture') as fixture, \
                patch.object(observer.argparse, 'ArgumentParser') as parser:
            for argv in (['--execute'], ['--request', '/missing', '--execute=true']):
                with self.assertRaises(ValueError):
                    observer.main(argv)
            for mocked in (utilities, observe, fixture, parser):
                mocked.assert_not_called()

    def test_pipeline_builds_two_distinct_products_then_invokes_only_fixed_guardian_argv_once(self):
        for case in ('normal', 'worker_loss'):
            with self.subTest(case=case), PipelineFixture() as f:
                row = f.run(case)
                self.assertEqual(row['status'], 'success', row)
                self.assert_no_authority(row)
                self.assertEqual([x[0] for x in f.built], ['leaf', 'guardian'])
                self.assertEqual([x[1] for x in f.built],
                                 [f.sources[observer.C_NAMES[1]], f.sources[observer.C_NAMES[0]]])
                self.assertTrue(all(x[2] == f.sources[observer.C_NAMES[2]] for x in f.built))
                f.backend.run.assert_called_once_with('runtime',
                    [str(f.root / 'guardian' / 'guardian'), case, NONCE,
                     str(f.root / 'leaf' / 'leaf'), 'none'])
                self.assertEqual(row['runtime_attempts'], 1)
                self.assertTrue(row['runtime_returned_complete_facts'])
                self.assertFalse(row['complete_mapped_code_authenticated'])
                self.assertIs(row[observer.SUCCESS[0]], True)
                self.assertIs(row[observer.SUCCESS[1]], case == 'normal')
                self.assertIs(row[observer.SUCCESS[2]], case == 'worker_loss')
                self.assertTrue(all(x.call_count == 2 for x in f.rechecks))

    def test_pipeline_closed_case_nonce_fault_and_three_C_inputs_block_before_any_build(self):
        changes = ({'case': 'foreign'}, {'nonce': 'short'}, {'fault': 'other'},
                   {'sources': {}}, {'sources': {**{n: Path('/fixture') for n in observer.C_NAMES},
                                                    'foreign.c': Path('/foreign')}})
        for changes in changes:
            with self.subTest(changes=changes), PipelineFixture() as f:
                row = f.run(**changes)
                self.assertEqual(row['status'], 'failed', row)
                self.assert_no_authority(row)
                f.build.assert_not_called()
                f.backend.run.assert_not_called()
                self.assertEqual(row['runtime_attempts'], 0)

    def test_pipeline_input_boundary_failure_blocks_build_or_first_runtime(self):
        for before_build in (True, False):
            with self.subTest(before_build=before_build), PipelineFixture() as f:
                callback = Mock(side_effect=([ValueError('input drift')] if before_build else
                                             [None, ValueError('input drift')]))
                row = f.run(callback=callback)
                self.assertEqual(row['status'], 'failed', row)
                self.assertEqual(f.build.call_count, 0 if before_build else 2)
                f.backend.run.assert_not_called()
                self.assertEqual(row['runtime_attempts'], 0)

    def test_pipeline_link_failure_or_cross_product_header_drift_blocks_runtime(self):
        for problem in ('link', 'header'):
            with self.subTest(problem=problem), PipelineFixture() as f:
                original = f.build.side_effect
                def build(*args):
                    if problem == 'link':
                        raise ValueError('new product link failed')
                    recheck = original(*args)
                    if args[-2] == 'guardian':
                        args[-1]['compile_leg']['headers'][str(f.sources[observer.C_NAMES[2]])] = {'fixture': 'drift'}
                    return recheck
                f.build.side_effect = build
                row = f.run()
                self.assertEqual(row['status'], 'failed', row)
                f.backend.run.assert_not_called()
                self.assertEqual(row['runtime_attempts'], 0)

    def test_pipeline_failed_or_incomplete_runtime_is_once_consumed_with_no_narrow_flag(self):
        for failure in ('negative', 'partial', 'timeout'):
            with self.subTest(failure=failure), PipelineFixture() as f:
                if failure == 'partial':
                    f.parse.side_effect = ValueError('partial runtime facts')
                else:
                    f.parse.return_value = {'status': 'failed', 'unknown': ['descendant']}
                    f.command.update(status='failed', returncode=1)
                    if failure == 'timeout':
                        f.command.update(timed_out=True, returncode=None, reap_completed=False)
                        f.parse.side_effect = ValueError('incomplete timeout')
                row = f.run()
                self.assertEqual(row['status'], 'failed', row)
                self.assert_no_authority(row)
                self.assertFalse(any(row[key] for key in observer.SUCCESS))
                self.assertEqual(row['runtime_attempts'], 1)
                f.backend.run.assert_called_once()
                if failure == 'negative':
                    self.assertTrue(row['runtime_returned_complete_facts'])
                    self.assertEqual(row['runtime_report'], f.parse.return_value)
                else:
                    self.assertFalse(row['runtime_returned_complete_facts'])

    def test_pipeline_runtime_argv_stream_binding_stderr_and_postparser_drift_block_narrow_success(self):
        for problem in ('argv', 'stdout_binding', 'stderr', 'postparser'):
            with self.subTest(problem=problem), PipelineFixture() as f:
                if problem == 'argv':
                    def run(label, argv):
                        f.command['argv'] = ['/foreign/command']
                        return f.command
                    f.backend.run.side_effect = run
                else:
                    original = f.backend.read_output.side_effect
                    reads = {'runtime.stdout': 0}
                    if problem == 'stderr':
                        f.command['stderr'] = {'sha256': observer.digest(b'error'), 'bytes': 5}
                    def read_output(name, limit):
                        raw, binding = original(name, limit)
                        if problem == 'stdout_binding' and name == 'runtime.stdout':
                            return raw, {**binding, 'sha256': '0' * 64}
                        if problem == 'stderr' and name == 'runtime.stderr':
                            return b'error', binding
                        if problem == 'postparser' and name == 'runtime.stdout':
                            reads[name] += 1
                            if reads[name] > 1:
                                return b'{} ', {**binding, 'bytes': 3, 'sha256': observer.digest(b'{} ')}
                        return raw, binding
                    f.backend.read_output.side_effect = read_output
                row = f.run()
                self.assertEqual(row['status'], 'failed', row)
                self.assertEqual(row['runtime_attempts'], 1)
                f.backend.run.assert_called_once()
                self.assert_no_authority(row)
                self.assertFalse(any(row[key] for key in observer.SUCCESS))
                if problem == 'postparser':
                    f.parse.assert_called_once()
                    self.assertTrue(row['runtime_returned_complete_facts'])
                else:
                    f.parse.assert_not_called()
                    self.assertFalse(row['runtime_returned_complete_facts'])

    @unittest.skipUnless(sys.platform == 'linux', 'Actual fixed normal exec fixture requires Linux')
    def test_real_linux_normal_exec_descendant_case(self):
        self.real_case('normal')

    @unittest.skipUnless(sys.platform == 'linux', 'Actual fixed worker-loss exec fixture requires Linux')
    def test_real_linux_worker_loss_exec_adoption_reap_case(self):
        self.real_case('worker_loss')

    @unittest.skipUnless(sys.platform == 'linux', 'Actual owned exec descriptor EBADF fixture requires Linux')
    def test_real_linux_once_exec_fd_closed_failure_creates_no_descendant(self):
        self.real_case('normal', 'exec_fd_closed')

    @unittest.skipUnless(sys.platform == 'linux', 'Actual owned witness startup failure requires Linux')
    def test_real_linux_once_witness_leak_exits_immediately_without_descendant(self):
        self.real_case('normal', 'witness_cloexec_cleared')

    def real_case(self, case, fault='none'):
        helper, utility, linkage = observer.load_utilities()
        boot = helper.capture_self_identity()['boot_id']
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            (directory / 'tmp').mkdir()
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                row = observer.run_fixture({name: ROOT / 'scripts' / name for name in observer.C_NAMES},
                    utility.CompilerBackend(helper, directory, fd), utility, linkage, case,
                    secrets.token_hex(32), os.getpid(), os.getuid(), boot, fault=fault)
                self.assert_no_authority(row)
                self.assertEqual(row['runtime_attempts'], 1, row)
                self.assertTrue(row['runtime_returned_complete_facts'], row)
                facts = row['runtime_report']
                if fault == 'none':
                    self.assertEqual(row['status'], 'success', row)
                    self.assertEqual(facts['status'], 'success')
                    self.assertEqual(facts['waits']['G_E']['raw_status'], 0 if case == 'normal' else 9)
                    if case == 'normal':
                        self.assertEqual(facts['waits']['E_D']['raw_status'], 0)
                        self.assertEqual(facts['waits']['G_D']['result'], None)
                    else:
                        self.assertEqual(facts['waits']['G_D']['raw_status'], 9)
                        self.assertEqual(len(facts['adoptions']), 1)
                        self.assertEqual(facts['adoptions'][0]['new_parent'], facts['identities_initial']['guardian']['pid'])
                    self.assertEqual(sum(x['attempts'] for x in facts['signals'].values()),
                                     0 if case == 'normal' else 2)
                    self.assertIs(row[observer.SUCCESS[0]], True)
                    self.assertIs(row[observer.SUCCESS[1]], case == 'normal')
                    self.assertIs(row[observer.SUCCESS[2]], case == 'worker_loss')
                else:
                    self.assertEqual(row['status'], 'failed', row)
                    self.assertEqual(facts['status'], 'failed')
                    self.assertFalse(any(row[key] for key in observer.SUCCESS))
                    self.assertIsNone(facts['identities_initial']['descendant'])
                    self.assertEqual(sum(x['attempts'] for x in facts['signals'].values()), 0)
                    self.assertEqual(facts['waits']['G_E']['raw_status'], 71 << 8 if fault == 'exec_fd_closed' else 70 << 8)
                    self.assertEqual(facts['error']['errno'], errno.EBADF if fault == 'exec_fd_closed' else 0)
                    self.assertFalse(facts['negative_state']['descendant_creation_authorized'])
                    self.assertFalse(facts['negative_state']['descendant_creation_observed'])
                    self.assertIsNone(facts['times_ns']['reset'])
            finally:
                os.close(fd)

    # Actual focused/compiler verification belongs to the root task's receipts.


if __name__ == '__main__':
    unittest.main()
