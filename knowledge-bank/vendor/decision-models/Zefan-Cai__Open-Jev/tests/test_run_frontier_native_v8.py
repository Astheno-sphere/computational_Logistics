"""Source-integrity fixtures; Git identities are mocked, not live authority."""
from contextlib import ExitStack
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import run_frontier_native_v8 as native


class NativeDeclarationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.native_root, self.science_root = self.root/'native', self.root/'science'
        self.native_root.mkdir(); self.science_root.mkdir()
        self.commit = 'c'*40
        self.blobs, self.dirty, self.heads = {}, {}, {}
        science_files = {}
        for index in range(18):
            name = f'jev/frozen_{index}.py'
            data = f'# scientific fixture {index}\n'.encode()
            p = self.science_root/name; p.parent.mkdir(exist_ok=True)
            p.write_bytes(data); science_files[name] = native.digest(data)
            self.blobs[(self.science_root, name)] = data
        native_files = {}
        for name in native.NATIVE_FILES:
            data = ('# native fixture '+name+'\n').encode()
            p = self.native_root/name; p.parent.mkdir(exist_ok=True)
            p.write_bytes(data); native_files[name] = native.digest(data)
            self.blobs[(self.native_root, name)] = data
        self.heads = {self.native_root: self.commit, self.science_root: native.SCIENCE_COMMIT}
        self.plan = {'implementation_sha256': science_files}
        self.freeze = {'source_commit': native.SCIENCE_COMMIT, 'implementation_sha256': science_files}
        self.plan_path, self.freeze_path, self.declaration_path = [self.root/name for name in
            ('plan.json', 'freeze.json', 'declaration.json')]
        self.plan_path.write_text(json.dumps(self.plan))
        self.plan_sha = native.digest(self.plan_path.read_bytes())
        self.freeze['plan_sha256'] = self.plan_sha
        self.freeze_path.write_text(json.dumps(self.freeze))
        self.freeze_sha = native.digest(self.freeze_path.read_bytes())
        self.declaration = {'schema_version': 1, 'protocol_id': native.PROTOCOL,
            'native_id': 'frontier-v8-native-'+'a'*16, 'status': 'native_CPU_source_preparation_only',
            'scientific_source_commit': native.SCIENCE_COMMIT, 'scientific_plan_sha256': self.plan_sha,
            'scientific_freeze_sha256': self.freeze_sha, 'native_source_commit': self.commit,
            'native_files_sha256': native_files, 'prior_installation_receipt_sha256': native.INSTALL_SHA,
            'prior_installation_review_sha256': native.INSTALL_REVIEW_SHA,
            'execution_available': False, 'resource_authority': False,
            'borrowed_queue_restoration_available': False,
            'gradient_nonzero_groups': {'lora_A': 1, 'lora_B': 1, 'head': 1},
            'gradient_missing_policy': 'report_without_imputation_all_present_finite'}

    def fake_git(self, directory, *args):
        path = Path(directory)
        if args == ('rev-parse', '--show-toplevel'): return str(path).encode()
        if args == ('rev-parse', 'HEAD'): return self.heads[path].encode()
        if args == ('status', '--porcelain', '--untracked-files=all'): return self.dirty.get(path, b'')
        if args[0] == 'show':
            commit, name = args[1].split(':', 1)
            self.assertEqual(commit, self.heads[path])
            return self.blobs[(path, name)]
        raise AssertionError(args)

    def verify(self, declaration=None, expected_sha=None):
        data = self.declaration if declaration is None else declaration
        self.declaration_path.write_text(json.dumps(data))
        with ExitStack() as stack:
            stack.enter_context(patch.object(native, 'PLAN_SHA', self.plan_sha))
            stack.enter_context(patch.object(native, 'FREEZE_SHA', self.freeze_sha))
            stack.enter_context(patch.object(native, '__file__', str(self.native_root/'scripts/run_frontier_native_v8.py')))
            stack.enter_context(patch.object(native, 'git', side_effect=self.fake_git))
            return native.verify_declaration(self.declaration_path, native_root=self.native_root,
                scientific_root=self.science_root, plan=self.plan_path, freeze=self.freeze_path,
                expected_declaration_sha256=expected_sha or native.digest(self.declaration_path.read_bytes()),
                expected_native_commit=self.commit)

    def test_verified_source_retains_unarmed_and_unobserved_result(self):
        result = self.verify()
        self.assertEqual(len(result['native_files_sha256']), 7)
        self.assertEqual(len(result['scientific_files_sha256']), 18)
        for name in ('execution_available', 'resource_authority', 'borrowed_queue_restoration_available',
                     'numerical_settings_applied', 'model_loaded', 'trainable_gradients_observed'):
            self.assertIs(result[name], False)
        self.assertEqual(result['model_calls'], 0)

    def test_ready_flags_extra_keys_and_changed_gradient_policy_cannot_unlock(self):
        for field in ('execution_available', 'resource_authority', 'borrowed_queue_restoration_available',
                      'gradient_missing_policy', 'gradient_nonzero_groups', 'extra_ready'):
            with self.subTest(field=field):
                value = copy.deepcopy(self.declaration)
                value[field] = True if field != 'gradient_nonzero_groups' else {'lora_A': True, 'lora_B': 1, 'head': 1}
                with self.assertRaises(ValueError): self.verify(value)

    def test_hash_inventory_and_published_installation_references_are_bound(self):
        for bad in ('declaration_hash', 'missing_native', 'science_commit', 'prior_install', 'prior_review'):
            with self.subTest(bad=bad):
                value = copy.deepcopy(self.declaration)
                expected = None
                if bad == 'declaration_hash': expected = '0'*64
                elif bad == 'missing_native': value['native_files_sha256'].pop(native.NATIVE_FILES[-1])
                elif bad == 'science_commit': value['scientific_source_commit'] = '0'*40
                elif bad == 'prior_install': value['prior_installation_receipt_sha256'] = '0'*64
                elif bad == 'prior_review': value['prior_installation_review_sha256'] = '0'*64
                with self.assertRaises(ValueError): self.verify(value, expected)

    def test_changed_dirty_or_wrong_source_checkout_is_rejected(self):
        self.dirty[self.science_root] = b' M jev/frozen_0.py\n'
        with self.assertRaisesRegex(ValueError, 'clean'): self.verify()
        self.dirty.clear()
        self.heads[self.science_root] = '0'*40
        with self.assertRaisesRegex(ValueError, 'HEAD/root'): self.verify()
        self.heads[self.science_root] = native.SCIENCE_COMMIT
        p = self.science_root/'jev/frozen_0.py'; p.write_text('# mutated\n')
        with self.assertRaisesRegex(ValueError, 'blob/hash'): self.verify()

    def test_symlink_escape_and_nonrelative_inventory_are_rejected(self):
        p = self.native_root/native.NATIVE_FILES[1]
        p.unlink(); p.symlink_to(self.plan_path)
        with self.assertRaises(ValueError): self.verify()
        p.unlink(); p.write_bytes(self.blobs[(self.native_root, native.NATIVE_FILES[1])])
        with patch.object(native, 'git', side_effect=self.fake_git):
            with self.assertRaisesRegex(ValueError, 'relative'):
                native.check_checkout(self.native_root, self.commit, {'../plan.json': self.plan_sha})

    def test_execute_refuses_before_declared_paths_or_optional_imports(self):
        before = sorted(str(p) for p in self.root.rglob('*'))
        with patch.object(native, 'verify_declaration', side_effect=AssertionError('must not preflight execution')):
            with self.assertRaisesRegex(ValueError, 'Model execution unavailable'):
                native.main(['--execute'])
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob('*')))


if __name__ == '__main__':
    unittest.main()
