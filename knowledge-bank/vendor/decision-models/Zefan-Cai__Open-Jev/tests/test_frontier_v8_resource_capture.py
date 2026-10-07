import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import frontier_v8_resource_capture as capture


BOOT = '11111111-1111-1111-1111-111111111111'


def write_proc(root, pid, ppid=1, state='S', birth=100):
    proc = root/str(pid)
    proc.mkdir(exist_ok=True)
    fields = [state, str(ppid), str(pid), str(pid)] + ['0']*15 + [str(birth)]
    (proc/'stat').write_text(str(pid)+' (fixture) '+' '.join(fields)+'\n')
    (proc/'status').write_text('Uid:\t'+('\t'.join([str(os.getuid())]*4))+'\n')
    (proc/'cmdline').write_bytes(b'/usr/bin/python\0fixture\0')


def gpu_raw(apps=''):
    rows = [f'{i}, GPU-0000000{i}-1111-1111-1111-111111111111, NVIDIA H100, 81559, 0, 0'
            for i in range(8)]
    return '\n'.join(rows)+'\n', apps


class ResourceCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.proc = self.root/'proc'
        (self.proc/'sys/kernel/random').mkdir(parents=True)
        (self.proc/'sys/kernel/random/boot_id').write_text(BOOT+'\n')
        write_proc(self.proc, os.getpid())
        self.request = {'schema_version': 1, 'mode': 'no_borrow',
                        'node_alias': 'ms-n1-1', 'acquisition_id': 'a'*32}

    def observed(self, request=None, raw=None):
        raw = raw or gpu_raw()
        moments = iter([10.0, 10.2])
        return capture.capture_current(request or self.request, proc_root=self.proc,
                                       query=lambda: raw, clock=lambda: next(moments),
                                       sleep=lambda _: None)

    def test_vacancy_requires_both_samples_but_grants_no_authority(self):
        value = self.observed()
        self.assertEqual(len(value['candidate_vacant_gpu_uuids']), 6)
        self.assertFalse(value['execution_available'])
        self.assertFalse(value['resource_authority'])
        self.assertEqual([x['index'] for x in value['protected_gpu_inventory']['gpus']], [0, 1])

    def test_low_util_compute_process_is_occupied(self):
        write_proc(self.proc, 42)
        value = self.observed(raw=gpu_raw('GPU-00000002-1111-1111-1111-111111111111, 42, python\n'))
        self.assertEqual(len(value['candidate_vacant_gpu_uuids']), 5)
        self.assertEqual(value['gpu_samples'][0]['compute_processes'][0]['identity']['start_ticks'], 100)

    def test_missing_protected_card_or_duplicate_uuid_refused(self):
        raw, apps = gpu_raw()
        with self.assertRaises(capture.CaptureError):
            capture.parse_gpu(('\n'.join(raw.splitlines()[1:]), apps), self.proc)
        with self.assertRaises(capture.CaptureError):
            capture.parse_gpu((raw.replace('GPU-00000003', 'GPU-00000002'), apps), self.proc)

    def test_unknown_compute_pid_cannot_be_silently_ignored(self):
        with self.assertRaises(FileNotFoundError):
            self.observed(raw=gpu_raw('GPU-00000002-1111-1111-1111-111111111111, 42, python\n'))

    def test_process_birth_race_refused(self):
        identity = capture.capture_identity(os.getpid(), self.proc)
        changed = capture.capture_identity(os.getpid(), self.proc)
        from dataclasses import replace
        with patch.object(capture, 'capture_identity', side_effect=[identity, replace(changed, start_ticks=101)]):
            with self.assertRaises(capture.CaptureError):
                capture.process_fact(os.getpid(), self.proc)

    def test_special_file_and_symlink_inventory_rejected(self):
        leaf = self.root/'regular'
        leaf.write_bytes(b'unchanged')
        (self.root/'alias').symlink_to(leaf)
        with self.assertRaises(capture.CaptureError):
            capture.fullhash(self.root/'alias')
        fifo = self.root/'fifo'
        os.mkfifo(fifo)
        with self.assertRaises(capture.CaptureError):
            capture.fullhash(fifo)

    def test_tree_inventory_and_required_bytes_reread(self):
        data = self.root/'data'
        data.mkdir()
        leaf = data/'source.py'
        leaf.write_bytes(b'source identity')
        digest = hashlib.sha256(leaf.read_bytes()).hexdigest()
        request = {**self.request, 'immutable_roots': [str(data)],
                   'expected_files_sha256': {str(leaf): digest}}
        self.assertEqual(self.observed(request)['immutable_files'][0]['sha256'], digest)
        leaf.write_bytes(b'changed')
        with self.assertRaises(capture.CaptureError):
            self.observed(request)

    def test_overlapping_roots_and_duplicate_paths_refused(self):
        directory = self.root/'data'
        nested = directory/'nested'
        nested.mkdir(parents=True)
        leaf = directory/'a'
        leaf.write_text('a')
        with self.assertRaises(capture.CaptureError):
            capture.inventory([directory, nested], [])
        with self.assertRaises(capture.CaptureError):
            capture.inventory([directory], [leaf])

    def test_new_file_during_tree_hash_refused(self):
        directory = self.root/'data'
        directory.mkdir()
        leaf = directory/'a'
        leaf.write_text('a')
        real_hash = capture.fullhash
        def modifying(path):
            result = real_hash(path)
            (directory/'new').write_text('new')
            return result
        with patch.object(capture, 'fullhash', side_effect=modifying):
            with self.assertRaises(capture.CaptureError):
                capture.inventory([directory], [])

    def test_directory_scan_error_is_not_silently_treated_as_empty(self):
        directory = self.root/'data'
        directory.mkdir()
        def denied(root, *, followlinks, onerror):
            onerror(PermissionError('fixture scan denied'))
            return iter(())
        with patch.object(capture.os, 'walk', side_effect=denied):
            with self.assertRaisesRegex(capture.CaptureError, 'directory scan failed'):
                capture.inventory([directory], [])

    def test_directory_replaced_with_identical_named_bytes_is_refused(self):
        directory = self.root/'data'
        directory.mkdir()
        leaf = directory/'a'
        leaf.write_text('same bytes')
        real_hash = capture.fullhash
        def replacing(path):
            result = real_hash(path)
            directory.rename(self.root/'old-data')
            directory.mkdir()
            (directory/'a').write_text('same bytes')
            return result
        with patch.object(capture, 'fullhash', side_effect=replacing):
            with self.assertRaises(capture.CaptureError):
                capture.inventory([directory], [])

    def test_excluded_node_and_stale_or_invalid_acquisition_refused(self):
        for key, value in [('node_alias', 'ms-n8-1'), ('node_alias', 'ms-n1-2'),
                           ('acquisition_id', 'old-pid')]:
            with self.assertRaises(capture.CaptureError):
                self.observed({**self.request, key: value})

    def test_progress_must_be_explicit_integer_not_boolean(self):
        progress = self.root/'progress.json'
        progress.write_text(json.dumps({'step': True}))
        with self.assertRaises(capture.CaptureError):
            capture._progress_value({'path': str(progress), 'extractor': 'json_integer',
                                     'key_path': ['step']})

    def test_protected_state_change_refused(self):
        write_proc(self.proc, 42)
        samples = iter([gpu_raw(), gpu_raw('GPU-00000000-1111-1111-1111-111111111111, 42, python\n')])
        moments = iter([1.0, 1.2])
        with self.assertRaises(capture.CaptureError):
            capture.capture_current(self.request, proc_root=self.proc, query=lambda: next(samples),
                                    clock=lambda: next(moments), sleep=lambda _: None)

    def test_second_observation_busy_is_not_free(self):
        first = gpu_raw()
        second = (first[0].replace('2, GPU-00000002-1111-1111-1111-111111111111, NVIDIA H100, 81559, 0, 0',
                                 '2, GPU-00000002-1111-1111-1111-111111111111, NVIDIA H100, 81559, 42, 0'), '')
        moments = iter([1.0, 1.2])
        samples = iter([first, second])
        value = capture.capture_current(self.request, proc_root=self.proc, query=lambda: next(samples),
                                        clock=lambda: next(moments), sleep=lambda _: None)
        self.assertEqual(len(value['candidate_vacant_gpu_uuids']), 5)

    def test_execute_rejects_before_request_read(self):
        with patch.object(Path, 'read_text', side_effect=AssertionError('must not read')):
            with self.assertRaises(capture.CaptureError):
                capture.main(['--execute', '--request', '/does-not-exist'])


if __name__ == '__main__':
    unittest.main()
