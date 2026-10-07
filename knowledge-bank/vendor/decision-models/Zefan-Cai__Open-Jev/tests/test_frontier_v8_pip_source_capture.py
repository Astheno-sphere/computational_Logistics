"""Fresh synthetic fixtures; no installed pip/vendor or MS observation."""

import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = REPO_ROOT / "scripts/frontier_v8_pip_source_capture.py"
LOCK_PATH = REPO_ROOT / "requirements-linux-py311-cu128-20261002.lock"
SPEC = importlib.util.spec_from_file_location("fixture_pip_source_capture", SOURCE_PATH)
capture = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = capture
SPEC.loader.exec_module(capture)

LINUX_FD_REASON = "requires Linux FD-anchored scandir and /proc fixture identity"
LINUX_FD_AVAILABLE = sys.platform == "linux" and os.scandir in os.supports_fd
BASE_FILES = {
    "__init__.py": b'raise AssertionError("opaque fixture, never import")\n',
    "__main__.py": b'raise AssertionError("opaque fixture, never execute")\n',
    "_internal/commands/check.py": b"# synthetic source, not installed pip\n",
    "_vendor/__init__.py": b"\xff\x00opaque vendor source\n",
}
STAT_KEYS = {"dev", "ino", "mode", "uid", "gid", "nlink", "size", "mtime_ns", "ctime_ns"}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def make_site(root, files=None):
    """Create synthetic76 from the selected frozen lock, never from installed pip."""
    site = root / "site"
    site.mkdir(mode=0o700)
    versions = capture.parse_lock(LOCK_PATH.read_bytes())
    for name, version in versions.items():
        dist = site / (name.replace("-", "_") + "-fixture.dist-info")
        dist.mkdir(mode=0o700)
        (dist / "METADATA").write_bytes(
            ("Metadata-Version: 2.1\nName: " + name + "\nVersion: " + version
             + "\nRequires-Dist: deliberately-unparsed [ fixture\n\n").encode("utf-8")
        )
    pip_root = site / "pip"
    pip_root.mkdir(mode=0o700)
    for relative, body in (BASE_FILES if files is None else files).items():
        path = pip_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    (pip_root / "_vendor").mkdir(exist_ok=True)
    return site, versions


def dist_path(site, name):
    return site / (name.replace("-", "_") + "-fixture.dist-info")


class LockFixtures(unittest.TestCase):
    def test_exact_frozen76_lock_and_normalized_names(self):
        versions = capture.parse_lock(LOCK_PATH.read_bytes())
        self.assertEqual(len(versions), 76)
        self.assertEqual(versions["pip"], "24.0")
        self.assertEqual(versions["huggingface-hub"], "1.33.0")
        self.assertEqual(versions["jinja2"], "3.1.6")

    def test_lock_independent_hash_rejects_tampering(self):
        data = LOCK_PATH.read_bytes().replace(b"pip==24.0", b"pip==24.1")
        with self.assertRaises(capture.CaptureError):
            capture.parse_lock(data)

    def test_synthetic_lock_duplicate_and_missing_rejected(self):
        original = LOCK_PATH.read_bytes()
        for data in (original + b"pip==24.0\n", original.replace(b"pip==24.0\n", b"")):
            with self.subTest(kind="duplicate" if len(data) > len(original) else "missing"):
                with self.assertRaises(capture.CaptureError):
                    capture.parse_lock(data, expected_sha256=sha256(data))


class RuntimeGateFixtures(unittest.TestCase):
    """Synthetic startup-state injection does not import any named package."""

    def test_runtime_module_self_and_submodule_pollution_rejected(self):
        flags = SimpleNamespace(dont_write_bytecode=1, isolated=1, no_site=1, ignore_environment=1)
        for package in ("pip", "torch", "transformers", "peft", "triton", "safetensors", "accelerate"):
            for name in (package, package + ".fixture"):
                with self.subTest(name=name):
                    context = capture._Capture(clock=lambda: 0.0)
                    with mock.patch.object(capture.sys, "platform", "linux"), \
                            mock.patch.object(capture.sys, "flags", flags), \
                            mock.patch.dict(capture.os.environ, {"PIP_CONFIG_FILE": "/dev/null"}, clear=True), \
                            mock.patch.dict(capture.sys.modules, {name: SimpleNamespace(__file__=None)}):
                        with self.assertRaises(capture.CaptureError):
                            capture._runtime_check(context, "/synthetic/readonly/site")
                    self.assertFalse(context.receipt["source_capture_verified"])


@unittest.skipUnless(LINUX_FD_AVAILABLE, LINUX_FD_REASON)
class SourceTreeFixtures(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jev-pip-source-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.site, self.versions = make_site(self.root)
        self.pip = self.site / "pip"

    def candidate(self, **kwargs):
        return capture.capture_site(str(self.site), self.versions, **kwargs)

    def failed(self, **kwargs):
        with self.assertRaises(capture.CaptureError) as caught:
            self.candidate(**kwargs)
        receipt = caught.exception.receipt
        self.assertEqual(receipt["status"], "failed")
        self.assertFalse(receipt["source_capture_complete"])
        self.assertFalse(receipt["source_capture_verified"])
        self.assertFalse(receipt["output_completion_claimed"])
        self.assertFalse(receipt["dependency_consistency_verified"])
        self.assertEqual(receipt["pipcheck"], 0)
        self.assertTrue(all(value is False for value in receipt["authority"].values()))
        self.assertLessEqual(len(receipt["error"]["message"]), 1024)
        return receipt

    def assert_body(self, item, body, *, complete):
        self.assertEqual(bytes.fromhex(item["raw_hex"]), body)
        self.assertEqual(item["byte_count"], len(body))
        self.assertEqual(item["sha256"], sha256(body))
        self.assertIs(item["complete"], complete)
        self.assertIs(item["partial"], not complete)

    def test_nested_opaque_capture_sorted_manifest_and_exact_counts(self):
        receipt = self.candidate()
        self.assertEqual(receipt["status"], "source_capture_candidate_ready")
        self.assertTrue(receipt["source_capture_complete"])
        self.assertFalse(receipt["source_capture_verified"])
        self.assertFalse(receipt["output_completion_claimed"])
        files = receipt["completed_files"]
        self.assertEqual([item["path"] for item in files], sorted(BASE_FILES))
        for item in files:
            self.assert_body(item, BASE_FILES[item["path"]], complete=True)
            self.assertEqual(set(item["observed_stat"]), STAT_KEYS)
        manifest = receipt["manifest"]
        self.assertEqual(manifest["first_pass_unique_entries"], 7)
        self.assertEqual(manifest["actual_source_yielded_entries"], 14)
        self.assertEqual(manifest["traversed_directories"], 4)
        self.assertEqual(manifest["max_depth"], 2)
        self.assertEqual(manifest["selected_paths"], sorted(BASE_FILES))
        self.assertEqual(manifest["site_scan_calls"], 4)
        self.assertEqual(manifest["site_scan_yielded_entries"], [77] * 4)
        self.assertEqual(manifest["actual_site_yielded_entries"], 308)
        self.assertEqual(len(receipt["metadata_snapshots"]), 2)
        self.assertEqual(receipt["metadata_snapshots"][0], receipt["metadata_snapshots"][1])

    def test_empty_pyi_and_identical_bodies_keep_distinct_paths(self):
        for name, body in (("empty.pyi", b""), ("same_a.py", b"opaque"), ("same_b.py", b"opaque")):
            (self.pip / name).write_bytes(body)
        files = {item["path"]: item for item in self.candidate()["completed_files"]}
        self.assert_body(files["empty.pyi"], b"", complete=True)
        self.assertEqual(files["same_a.py"]["sha256"], files["same_b.py"]["sha256"])
        self.assertNotEqual(files["same_a.py"]["path"], files["same_b.py"]["path"])

    def test_ignored_data_and_untraversed_cache_are_not_captured(self):
        (self.pip / "LICENSE").write_bytes(b"opaque data")
        (self.pip / "native.so").write_bytes(b"not a source file")
        cache = self.pip / "__pycache__"
        cache.mkdir()
        (cache / "unobserved.py").symlink_to(self.pip / "__init__.py")
        receipt = self.candidate()
        self.assertEqual(receipt["manifest"]["selected_paths"], sorted(BASE_FILES))
        self.assertEqual(receipt["manifest"]["first_pass_unique_entries"], 10)
        self.assertEqual(receipt["manifest"]["actual_source_yielded_entries"], 20)
        self.assertEqual(receipt["manifest"]["traversed_directories"], 4)
        excluded = json.dumps(receipt["manifest"]["excluded_entries"])
        self.assertIn("__pycache__", excluded)
        self.assertNotIn("unobserved.py", excluded)

    def test_selected_symlink_rejected(self):
        (self.pip / "bad.py").symlink_to(self.pip / "__init__.py")
        self.failed()

    def test_directory_symlink_rejected(self):
        (self.pip / "alias").symlink_to(self.pip / "_vendor", target_is_directory=True)
        self.failed()

    def test_unselected_symlink_rejected(self):
        (self.pip / "bad.data").symlink_to(self.pip / "__init__.py")
        self.failed()

    def test_fifo_special_entry_rejected_without_reading_it(self):
        os.mkfifo(self.pip / "blocked.py")
        self.failed()

    def test_non_ascii_and_dot_names_rejected(self):
        for name in ("caf\u00e9.py", ".hidden.py"):
            with self.subTest(name=name):
                path = self.pip / name
                path.write_bytes(b"opaque")
                self.failed()
                path.unlink()

    def test_ambiguous_absolute_path_rejected(self):
        for path in (str(self.site) + "/../site", str(self.site) + "//", str(self.site) + "/."):
            with self.subTest(path=path):
                with self.assertRaises(capture.CaptureError):
                    capture.capture_site(path, self.versions)

    def test_mandatory_entry_absence_rejected(self):
        (self.pip / "__main__.py").unlink()
        self.failed()

    def test_observed_file_drift_keeps_read_bytes_partial(self):
        original_read = capture.os.read
        target = self.pip / "__main__.py"
        changed = False

        def read_and_change(fd, count):
            nonlocal changed
            data = original_read(fd, count)
            if data and not changed and os.readlink("/proc/self/fd/" + str(fd)) == str(target):
                before = target.stat()
                os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000))
                changed = True
            return data

        with mock.patch.object(capture.os, "read", side_effect=read_and_change):
            receipt = self.failed()
        self.assertTrue(changed)
        self.assertEqual([item["path"] for item in receipt["completed_files"]], ["__init__.py"])
        self.assert_body(receipt["current_file_partial"], BASE_FILES["__main__.py"], complete=False)

    def test_directory_name_drift_rejected(self):
        original_scandir = capture.os.scandir
        changed = False

        class Iterator:
            def __init__(self, inner, watched):
                self.inner, self.watched = inner, watched

            def __iter__(self):
                return self

            def __next__(self):
                nonlocal changed
                try:
                    return next(self.inner)
                except StopIteration:
                    if self.watched and not changed:
                        (target / "late.py").write_bytes(b"late opaque fixture")
                        changed = True
                    raise

            def close(self):
                self.inner.close()

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.close()

        target = self.pip

        def scan(path):
            watched = isinstance(path, int) and os.readlink("/proc/self/fd/" + str(path)) == str(target)
            return Iterator(original_scandir(path), watched)

        with mock.patch.object(capture.os, "scandir", side_effect=scan):
            self.failed()
        self.assertTrue(changed)

    def test_synthetic_cross_device_entry_rejected_before_body_read(self):
        original_stat = capture.os.stat

        def stat_with_device(path, *args, **kwargs):
            observed = original_stat(path, *args, **kwargs)
            if path == "__init__.py" and kwargs.get("dir_fd") is not None:
                fields = {key: getattr(observed, key) for key in dir(observed) if key.startswith("st_")}
                fields["st_dev"] += 1
                return SimpleNamespace(**fields)
            return observed

        with mock.patch.object(capture.os, "stat", side_effect=stat_with_device):
            receipt = self.failed()
        self.assertEqual(receipt["completed_files"], [])
        self.assertIsNone(receipt["current_file_partial"])

    def test_second_metadata_snapshot_drift_retains_completed_source_bodies(self):
        original_read = capture.os.read
        target = self.pip / "_vendor/__init__.py"
        pip_metadata = dist_path(self.site, "pip") / "METADATA"
        changed = False

        def read_and_change_metadata(fd, count):
            nonlocal changed
            data = original_read(fd, count)
            if data and not changed and os.readlink("/proc/self/fd/" + str(fd)) == str(target):
                pip_metadata.write_bytes(pip_metadata.read_bytes().replace(b"Version: 24.0", b"Version: 24.1"))
                changed = True
            return data

        with mock.patch.object(capture.os, "read", side_effect=read_and_change_metadata):
            receipt = self.failed()
        self.assertTrue(changed)
        self.assertEqual([item["path"] for item in receipt["completed_files"]], sorted(BASE_FILES))
        self.assertIsNone(receipt["current_file_partial"])

    def test_source_entry_cap_boundary_and_one_over(self):
        self.assertTrue(self.candidate(caps={"pip_tree_total_entries": 7})["source_capture_complete"])
        receipt = self.failed(caps={"pip_tree_total_entries": 6})
        self.assertEqual(receipt["manifest"]["first_pass_unique_entries"], 7)

    def test_directory_and_depth_cap_boundaries(self):
        self.assertTrue(self.candidate(caps={"pip_tree_directories": 4, "pip_tree_depth": 2})["source_capture_complete"])
        for caps in ({"pip_tree_directories": 3}, {"pip_tree_depth": 1}):
            with self.subTest(caps=caps):
                self.failed(caps=caps)

    def test_actual_enumeration_and_site_scan_caps(self):
        self.assertTrue(self.candidate(caps={"pip_tree_actual_yielded_entries": 14})["source_capture_complete"])
        self.failed(caps={"pip_tree_actual_yielded_entries": 13})
        self.failed(caps={"site_entries_per_explicit_scan": 76})
        self.failed(caps={"site_total_yielded_entries": 307})

    def test_declared_file_over_cap_rejects_before_body_read(self):
        limit = len(BASE_FILES["__init__.py"]) - 1
        receipt = self.failed(caps={"selected_file_bytes": limit})
        self.assertEqual(receipt["completed_files"], [])
        self.assertIsNone(receipt["current_file_partial"])

    def test_synthetic_actual_read_cap_retains_limit_plus_one_partial(self):
        original_read = capture.os.read
        target = self.pip / "__init__.py"
        injected = False

        def oversized_read(fd, count):
            nonlocal injected
            data = original_read(fd, count)
            if data and not injected and os.readlink("/proc/self/fd/" + str(fd)) == str(target):
                injected = True
                return data + b"X"
            return data

        with mock.patch.object(capture.os, "read", side_effect=oversized_read):
            receipt = self.failed(caps={"selected_file_bytes": len(BASE_FILES["__init__.py"])})
        self.assertTrue(injected)
        self.assertEqual(receipt["completed_files"], [])
        partial = receipt["current_file_partial"]
        self.assertEqual(partial["path"], "__init__.py")
        self.assert_body(partial, BASE_FILES["__init__.py"] + b"X", complete=False)

    def test_total_source_cap_retains_completed_prefix_without_preopen_partial(self):
        limit = len(BASE_FILES["__init__.py"])
        receipt = self.failed(caps={"selected_source_total_bytes": limit})
        self.assertEqual([item["path"] for item in receipt["completed_files"]], ["__init__.py"])
        self.assert_body(receipt["completed_files"][0], BASE_FILES["__init__.py"], complete=True)
        self.assertIsNone(receipt["current_file_partial"])

    def test_source_byte_cap_exact_boundaries(self):
        receipt = self.candidate(caps={
            "selected_source_total_bytes": sum(map(len, BASE_FILES.values())),
            "selected_file_bytes": max(map(len, BASE_FILES.values())),
        })
        self.assertTrue(receipt["source_capture_complete"])

    def test_fd_budget_counts_iterator_and_closes_owned_handles(self):
        self.failed(caps={"simultaneously_owned_input_FDs": 1})
        before = set(os.listdir("/proc/self/fd"))
        self.failed(caps={"simultaneously_owned_input_FDs": 3})
        self.assertEqual(set(os.listdir("/proc/self/fd")), before)

    def test_metadata_missing_extra_duplicate_and_version_drift(self):
        pip_metadata = dist_path(self.site, "pip") / "METADATA"
        original = pip_metadata.read_bytes()
        mutations = (
            original.replace(b"Version: 24.0", b"Version: 24.1"),
            original.replace(b"Name: pip\n", b"Name: pip\nName: pip\n"),
            b"Metadata-Version: 2.1\nName: different-package\nVersion: 24.0\n\n",
        )
        for data in mutations:
            with self.subTest(data=data):
                pip_metadata.write_bytes(data)
                self.failed()
        pip_metadata.write_bytes(original)
        extra = self.site / "extra-fixture.dist-info"
        extra.mkdir()
        (extra / "METADATA").write_bytes(b"Name: extra\nVersion: 1\n\n")
        self.failed()
        (extra / "METADATA").unlink()
        extra.rmdir()
        pip_metadata.unlink()
        self.failed()

    def test_metadata_normalized_duplicate_rejected(self):
        duplicate = self.site / "alias-fixture.dist-info"
        duplicate.mkdir()
        (duplicate / "METADATA").write_bytes(b"Name: HuggingFace_Hub\nVersion: 1.33.0\n\n")
        self.failed()

    def test_metadata_symlink_and_invalid_utf8_rejected(self):
        metadata = dist_path(self.site, "pip") / "METADATA"
        original = metadata.read_bytes()
        metadata.write_bytes(b"Name: p\xffp\nVersion: 24.0\n\n")
        self.failed()
        alternate = self.root / "alternate-metadata"
        alternate.write_bytes(original)
        metadata.unlink()
        metadata.symlink_to(alternate)
        self.failed()

    def test_metadata_byte_caps_rejected_before_source_capture(self):
        for caps in ({"metadata_file_bytes": 8}, {"metadata_total_per_snapshot": 16}):
            with self.subTest(caps=caps):
                receipt = self.failed(caps=caps)
                self.assertEqual(receipt["completed_files"], [])
                self.assertIsNone(receipt["current_file_partial"])

    def test_work_expiry_reverse_and_nonfinite_clocks_fail(self):
        for clock in (
            iter((0.0, 31.0)).__next__,
            iter((10.0, 9.0)).__next__,
            lambda: float("nan"),
            lambda: float("inf"),
        ):
            with self.subTest(clock=clock):
                receipt = self.failed(clock=clock)
                self.assertEqual(receipt["completed_files"], [])


class OutputFixtures(unittest.TestCase):
    """Private local FIFO and fake writer observations are not MS evidence."""

    def setUp(self):
        self.read_fd, self.write_fd = os.pipe()
        self.addCleanup(os.close, self.read_fd)
        self.addCleanup(os.close, self.write_fd)
        self.receipt = {
            "schema_version": 1,
            "scope": capture.SCOPE,
            "status": "source_capture_candidate_ready",
            "source_capture_complete": True,
            "source_capture_verified": False,
            "output_completion_claimed": False,
            "completed_files": [],
        }

    def test_prepare_stdout_requires_fifo_and_enables_nonblocking(self):
        facts = capture.prepare_stdout(self.write_fd, declared={
            "kind": "private_FIFO", "exclusive_channel_assumption": True,
        })
        self.assertTrue(facts["nonblocking_verified"])
        self.assertTrue(fcntl.fcntl(self.write_fd, fcntl.F_GETFL) & os.O_NONBLOCK)
        with tempfile.TemporaryFile() as regular:
            with self.assertRaises(capture.CaptureError):
                capture.prepare_stdout(regular.fileno(), declared={
                    "kind": "private_FIFO", "exclusive_channel_assumption": True,
                })

    def test_shortwrite_and_eagain_advance_exact_cursor_once(self):
        capture.prepare_stdout(self.write_fd, declared={
            "kind": "private_FIFO", "exclusive_channel_assumption": True,
        })
        written = []
        calls = 0

        def writer(fd, data):
            nonlocal calls
            self.assertEqual(fd, self.write_fd)
            calls += 1
            if calls == 2:
                raise BlockingIOError(errno.EAGAIN, "synthetic would-block")
            chunk = bytes(data[:7])
            written.append(chunk)
            return len(chunk)

        with mock.patch.object(capture.os, "write", side_effect=writer):
            facts = capture.emit_json(self.receipt, self.write_fd)
        body = b"".join(written)
        self.assertEqual(json.loads(body), self.receipt)
        self.assertEqual(facts["byte_count"], len(body))
        self.assertEqual(facts["positive_returned_bytes"], len(body))
        self.assertEqual(facts["sha256"], sha256(body))
        self.assertEqual(facts["eagain_count"], 1)
        self.assertFalse(self.receipt["source_capture_verified"])
        self.assertFalse(self.receipt["output_completion_claimed"])

    def test_output_cap_and_zero_write_reject_without_reconstruction(self):
        capture.prepare_stdout(self.write_fd, declared={
            "kind": "private_FIFO", "exclusive_channel_assumption": True,
        })
        with mock.patch.object(capture.os, "write") as writer:
            with self.assertRaises(capture.CaptureError):
                capture.emit_json(self.receipt, self.write_fd, caps={"stdout_UTF8_bytes": 1})
            writer.assert_not_called()
        with mock.patch.object(capture.os, "write", return_value=0) as writer:
            with self.assertRaises(capture.CaptureError):
                capture.emit_json(self.receipt, self.write_fd)
            self.assertEqual(writer.call_count, 1)

    def test_total_expiry_stops_emission_and_keeps_candidate_unverified(self):
        capture.prepare_stdout(self.write_fd, declared={
            "kind": "private_FIFO", "exclusive_channel_assumption": True,
        })
        with mock.patch.object(capture.os, "write") as writer:
            with self.assertRaises(capture.CaptureError):
                capture.emit_json(self.receipt, self.write_fd, t0=0.0, clock=lambda: 40.0)
            writer.assert_not_called()
        self.assertFalse(self.receipt["source_capture_verified"])

    def test_unknown_write_failure_keeps_original_prefix_without_reemission(self):
        capture.prepare_stdout(self.write_fd, declared={
            "kind": "private_FIFO", "exclusive_channel_assumption": True,
        })
        prefix = []
        calls = 0

        def writer(fd, data):
            nonlocal calls
            self.assertEqual(fd, self.write_fd)
            calls += 1
            if calls == 1:
                prefix.append(bytes(data[:5]))
                return 5
            raise OSError(errno.EIO, "synthetic unknown write outcome")

        with mock.patch.object(capture.os, "write", side_effect=writer):
            with self.assertRaises(OSError):
                capture.emit_json(self.receipt, self.write_fd)
        self.assertEqual(calls, 2)
        self.assertEqual(len(b"".join(prefix)), 5)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(b"".join(prefix))
        self.assertFalse(self.receipt["source_capture_verified"])

    def test_failure_output_can_follow_work_expiry_until_total_deadline(self):
        failed = dict(self.receipt, status="failed", source_capture_complete=False)
        capture.prepare_stdout(self.write_fd, declared={
            "kind": "private_FIFO", "exclusive_channel_assumption": True,
        })
        facts = capture.emit_json(failed, self.write_fd, t0=0.0, clock=lambda: 31.0)
        body = os.read(self.read_fd, 65536)
        self.assertEqual(facts["byte_count"], len(body))
        self.assertEqual(json.loads(body), failed)
        self.assertFalse(failed["source_capture_verified"])


@unittest.skipUnless(LINUX_FD_AVAILABLE, LINUX_FD_REASON)
class LiteralBootstrapLinuxFixtures(unittest.TestCase):
    """Each test uses a new local root/request/attempt and one harness child."""

    def run_case(self, *, observer_sha_wrong=False, request_sha_wrong=False,
                 request_count_wrong=False, metadata_wrong=False):
        with tempfile.TemporaryDirectory(prefix="jev-pip-literal-fixture-") as directory:
            base = Path(directory).resolve()
            root = base / "attempt-root"
            root.mkdir(mode=0o700)
            site_parent = base / "readonly-site-fixture"
            site_parent.mkdir(mode=0o700)
            site, _versions = make_site(site_parent)
            if metadata_wrong:
                metadata = dist_path(site, "pip") / "METADATA"
                metadata.write_bytes(metadata.read_bytes().replace(b"Version: 24.0", b"Version: 24.1"))
            observer = root / "frontier_v8_pip_source_capture.py"
            observer_bytes = SOURCE_PATH.read_bytes()
            observer.write_bytes(observer_bytes)
            lock = root / LOCK_PATH.name
            lock.write_bytes(LOCK_PATH.read_bytes())
            interpreter = Path("/proc/self/exe").resolve()
            executable_bytes = interpreter.read_bytes()
            request_path = root / "source-capture-request.json"
            request = {
                "schema_version": 1,
                "scope": capture.SCOPE,
                "case": "source_capture",
                "nonce": os.urandom(32).hex(),
                "attempt": "attempt-r1",
                "root": str(root),
                "observer_path": str(observer),
                "observer_sha256": sha256(observer_bytes),
                "request_path": str(request_path),
                "lock_path": str(lock),
                "lock_sha256": capture.LOCK_SHA256,
                "site_path": str(site),
                "host": {
                    "hostname": os.uname().nodename,
                    "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                    "uid": os.getuid(),
                },
                "runtime": {
                    "interpreter_path": str(interpreter),
                    "byte_count": len(executable_bytes),
                    "sha256": sha256(executable_bytes),
                },
                "stdout": {"kind": "private_FIFO", "exclusive_channel_assumption": True},
            }
            request_bytes = (json.dumps(request, sort_keys=True, separators=(",", ":")) + "\n").encode()
            request_path.write_bytes(request_bytes)
            command = [
                str(interpreter), "-B", "-I", "-S", "-c", capture.BOOTSTRAP,
                str(observer), "0" * 64 if observer_sha_wrong else sha256(observer_bytes),
                str(request_path), "0" * 64 if request_sha_wrong else sha256(request_bytes),
                str(len(request_bytes) + 1 if request_count_wrong else len(request_bytes)),
            ]
            result = subprocess.run(command, env={"PIP_CONFIG_FILE": "/dev/null"},
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            self.assertLessEqual(len(result.stdout), capture.CAPS["stdout_UTF8_bytes"])
            if request_count_wrong:
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
                self.assertFalse((root / "attempt-r1.marker.json").exists())
            return result, request

    def test_linux_literal_bootstrap_normal_source_candidate(self):
        result, request = self.run_case()
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["status"], "source_capture_candidate_ready")
        self.assertEqual(receipt["scope"], request["scope"])
        self.assertTrue(receipt["source_capture_complete"])
        self.assertFalse(receipt["source_capture_verified"])
        self.assertFalse(receipt["output_completion_claimed"])
        self.assertFalse(receipt["dependency_consistency_verified"])
        self.assertEqual(receipt["pipcheck"], 0)
        self.assertTrue(all(value is False for value in receipt["authority"].values()))
        files = {item["path"]: bytes.fromhex(item["raw_hex"]) for item in receipt["completed_files"]}
        self.assertEqual(files, BASE_FILES)

    def test_linux_literal_bootstrap_wrong_observer_sha(self):
        result, _request = self.run_case(observer_sha_wrong=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")

    def test_linux_literal_bootstrap_wrong_independent_request_sha(self):
        result, _request = self.run_case(request_sha_wrong=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")

    def test_linux_literal_bootstrap_wrong_independent_request_count(self):
        self.run_case(request_count_wrong=True)

    def test_linux_literal_bootstrap_metadata_mismatch_failed_receipt(self):
        result, _request = self.run_case(metadata_wrong=True)
        self.assertNotEqual(result.returncode, 0)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["status"], "failed")
        self.assertFalse(receipt["source_capture_complete"])
        self.assertFalse(receipt["source_capture_verified"])
        self.assertEqual(receipt["completed_files"], [])


if __name__ == "__main__":
    unittest.main()
