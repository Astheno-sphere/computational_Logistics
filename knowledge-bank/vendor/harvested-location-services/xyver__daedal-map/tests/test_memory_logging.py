import json
import threading
import tempfile
import unittest
from unittest.mock import patch

from mapmover import memory_logging as history


class MemoryHistoryTests(unittest.TestCase):
    def tearDown(self):
        if history._FILE_HANDLER is not None:
            history.logger.removeHandler(history._FILE_HANDLER)
            history._FILE_HANDLER.close()
            history._FILE_HANDLER = None

    def test_sample_preserves_unknown_memory_and_does_not_load_owners(self):
        import sys
        from mapmover.memory_diagnostics import OWNERS
        before = set(sys.modules)
        with patch.object(history.Path, 'read_text', side_effect=OSError('unavailable')):
            row = history.sample_memory()
        owner_modules = {module for _label, module, _attribute in OWNERS}
        self.assertFalse((set(sys.modules) - before) & owner_modules)
        self.assertIsNone(row['cgroup_current_bytes'])
        self.assertIn('status_error', row)
        self.assertEqual(row['process'], {})
        self.assertIn('glibc_allocator', row)
        self.assertIn('python_runtime', row)
        self.assertTrue(all('entry_estimates' not in owner for owner in row['owners'].values()))

    def test_monitor_records_and_stops_without_waiting_for_interval(self):
        sampled = threading.Event()
        logged = []
        def log(*args):
            logged.append(args)
            sampled.set()
        with patch.dict(history.os.environ, {'MEMORY_SAMPLE_SECONDS': '300'}), \
                patch.object(history, 'sample_memory', return_value={'process_epoch': history._EPOCH}), \
                patch.object(history.logger, 'info', side_effect=log):
            close = history.start_memory_logging()
            try:
                self.assertTrue(sampled.wait(2))
                memory_call = next(call for call in logged if call[0] == 'memory_sample %s')
                payload = json.loads(memory_call[1])
                self.assertEqual(payload['configured_interval_seconds'], 300)
                self.assertIn('scheduled_lag_seconds', payload)
                self.assertEqual(payload['missed_intervals'], 0)
            finally:
                close()
        self.assertFalse(any(t.name == 'memory-logging' for t in threading.enumerate()))

    def test_disabled_monitor_does_not_sample(self):
        with patch.dict(history.os.environ, {'MEMORY_SAMPLE_SECONDS': '0'}), \
                patch.object(history, 'sample_memory') as sample:
            history.start_memory_logging()()
        sample.assert_not_called()

    def test_persistent_log_is_bounded_and_contains_samples(self):
        sampled = threading.Event()
        with tempfile.TemporaryDirectory() as directory:
            path = history.Path(directory) / 'memory.jsonl'
            def sample():
                sampled.set()
                return {'process_epoch': history._EPOCH}
            with patch.dict(history.os.environ, {'MEMORY_SAMPLE_SECONDS': '60',
                                                  'MEMORY_SAMPLE_LOG_PATH': str(path)}), \
                    patch.object(history, 'sample_memory', side_effect=sample):
                close = history.start_memory_logging()
                try:
                    self.assertTrue(sampled.wait(2))
                finally:
                    close()
            history._FILE_HANDLER.flush()
            text = path.read_text(encoding='utf-8')
            self.assertIn('memory_logging_started', text)
            self.assertIn('memory_sample', text)
            self.assertEqual(history._FILE_HANDLER.maxBytes, 10 * 1024 * 1024)
            self.assertEqual(history._FILE_HANDLER.backupCount, 6)
            history.logger.removeHandler(history._FILE_HANDLER)
            history._FILE_HANDLER.close()
            history._FILE_HANDLER = None


if __name__ == '__main__':
    unittest.main()
