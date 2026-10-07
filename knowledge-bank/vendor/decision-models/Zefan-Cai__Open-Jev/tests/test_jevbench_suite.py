"""Owned-process orchestration checks; never load a model or call an API."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import run_jevbench_suite as suite


class JevBenchSuiteTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.args = argparse.Namespace(
            checkpoint_2b=self.checkpoint("2b"), checkpoint_9b=self.checkpoint("9b"),
            requests=self.root / "requests.json", upstream=self.root / "upstream",
            output_root=self.root / "output", input_sha256=suite.PUBLIC_REQUESTS_SHA256,
            max_length=16384, batch_size=1, port=18791, startup_timeout=10,
            collection_timeout=20, request_timeout=5)

    def checkpoint(self, tag):
        directory = self.root / tag
        (directory / "adapter").mkdir(parents=True)
        (directory / "model.json").write_text(json.dumps({
            "model_id": "Qwen/Qwen3.5-" + tag.upper(), "revision": "1" * 40,
            "lora_rank": 8, "max_length": 384}))
        (directory / "temperature.json").write_text('{"temperature":1.25}')
        (directory / "head.pt").write_bytes(b"fixture-not-real-weights")
        (directory / "adapter/weights").write_bytes(b"fixture")
        return directory

    def test_slurm_mapping_is_preserved_and_broad_visibility_rejected(self):
        with patch.dict(os.environ, {"SLURM_JOB_ID": "123", "CUDA_VISIBLE_DEVICES": "GPU-granted"}, clear=True):
            env, allocation = suite.slurm_environment()
        self.assertEqual(env["CUDA_VISIBLE_DEVICES"], "GPU-granted")
        self.assertEqual(allocation["logical_device"], "cuda:0")
        self.assertNotIn("CUDA_DEVICE_ORDER", env)
        for visibility in ("", "0,1", "-1", "NoDevFiles", "all", "0 1"):
            with self.subTest(visibility=visibility), patch.dict(
                    os.environ, {"SLURM_JOB_ID": "123", "CUDA_VISIBLE_DEVICES": visibility}, clear=True):
                with self.assertRaises(ValueError):
                    suite.slurm_environment()
        with patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": "0"}, clear=True), self.assertRaises(ValueError):
            suite.slurm_environment()

    def test_n1_mode_verifies_host_and_idle_card_before_selecting_uuid(self):
        args = argparse.Namespace(expected_host="kwade5342000001", physical_gpu=0)
        with patch.object(suite.socket, "gethostname", return_value="kwade5342000001"), \
                patch.object(suite, "require_free_gpu", return_value={"uuid": "GPU-allocated"}) as free:
            env, allocation = suite.allocated_environment(args)
        free.assert_called_once_with(0)
        self.assertEqual(env["CUDA_VISIBLE_DEVICES"], "GPU-allocated")
        self.assertEqual(allocation["mode"], "n1_explicit")
        for host, gpu in (("another-host", 0), ("kwade5342000001", 4), (None, 0)):
            with patch.object(suite.socket, "gethostname", return_value="kwade5342000001"), \
                    patch.object(suite, "require_free_gpu") as free, self.assertRaises(ValueError):
                suite.allocated_environment(argparse.Namespace(expected_host=host, physical_gpu=gpu))
            free.assert_not_called()

    def simulate(self, fail_phase=None):
        events, servers = [], []

        def popen(command, **kwargs):
            self.assertTrue(all(server.poll() is not None for server in servers))
            self.assertEqual(kwargs["env"]["CUDA_VISIBLE_DEVICES"], "3")
            self.assertEqual(command[command.index("--device") + 1], "cuda:0")
            self.assertIn("--no-prefix-cache", command)
            child = Mock(pid=100 + len(servers), returncode=None)
            child.poll.return_value = None
            servers.append(child)
            events.append("server-start")
            return child

        def stop(server):
            if server is None:
                return None
            server.poll.return_value = 0
            server.returncode = 0
            events.append("server-stop")
            return 0

        def ready(server, log_path, identity, port, timeout):
            if fail_phase == "startup":
                raise TimeoutError("startup timeout")
            return {"status": "ready", "model": identity["model"], "method": identity["method"]}

        def collect(server, command, log_path, env, timeout, record, save):
            events.append("collect")
            if fail_phase == "collection":
                raise TimeoutError("collection timeout")
            self.assertNotIn("--upstream", command)
            identity = json.loads(Path(command[command.index("--identity") + 1]).read_text())
            output = Path(command[command.index("--output") + 1])
            output.mkdir()
            report = {"status": "complete", "expected_identity": identity, "in_flight_requests": 0,
                      "planned_requests": 231, "input_sha256": suite.PUBLIC_REQUESTS_SHA256}
            if fail_phase == "identity":
                report["expected_identity"]["checkpoint_sha256"] = "9" * 64
            (output / "report.json").write_text(json.dumps(report))
            record["exit_code"] = 0
            return 0

        def summarize(upstream, run):
            self.assertTrue(all(server.poll() is not None for server in servers))
            events.append("gold-summary")
            return {"n_planned": 231, "n_attempted": 231, "n_correct": 100,
                    "accuracy": 100 / 231, "complete": True, "failed_requests": 0, "pending_requests": 0}

        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {"SLURM_JOB_ID": "123", "CUDA_VISIBLE_DEVICES": "3"}, clear=True))
            stack.enter_context(patch.object(suite.benchmark, "load_workloads", return_value=([{}] * 231, b"")))
            stack.enter_context(patch.object(suite.subprocess, "check_output", side_effect=["2" * 40, "", suite.benchmark.UPSTREAM_COMMIT]))
            stack.enter_context(patch.object(suite.subprocess, "Popen", side_effect=popen))
            stack.enter_context(patch.object(suite, "stop_child", side_effect=stop))
            stack.enter_context(patch.object(suite, "wait_ready", side_effect=ready))
            stack.enter_context(patch.object(suite, "run_collection", side_effect=collect))
            stack.enter_context(patch.object(suite.benchmark, "summarize", side_effect=summarize))
            stack.enter_context(patch.object(suite.socket, "socket"))
            if fail_phase:
                with self.assertRaises((TimeoutError, ValueError)):
                    suite.run_suite(self.args)
                result = json.loads((self.args.output_root / "manifest.json").read_text())
            else:
                result = suite.run_suite(self.args)
        self.assertTrue(all(server.poll() is not None for server in servers))
        return result, events

    def test_serial_servers_and_gold_read_only_after_both_are_stopped(self):
        result, events = self.simulate()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(events, ["server-start", "collect", "server-stop",
                                  "server-start", "collect", "server-stop", "gold-summary", "gold-summary"])
        self.assertEqual(list(result["models"]), ["2b", "9b"])

    def test_only_new_27b_checkpoint_runs_after_training(self):
        self.args.checkpoint_2b = self.args.checkpoint_9b = None
        self.args.checkpoint_27b = self.checkpoint("27b")
        config = self.args.checkpoint_27b / "model.json"
        info = json.loads(config.read_text())
        info["model_id"] = "Qwen/Qwen3.8-27B"
        config.write_text(json.dumps(info))
        result, events = self.simulate()
        self.assertEqual(result["model_order"], ["27b"])
        self.assertEqual(list(result["models"]), ["27b"])
        self.assertEqual(events, ["server-start", "collect", "server-stop", "gold-summary"])

    def test_startup_failure_reaps_only_first_server_and_never_collects(self):
        result, events = self.simulate("startup")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(events, ["server-start", "server-stop"])

    def test_collection_timeout_reaps_server_without_starting_next_model(self):
        result, events = self.simulate("collection")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(events, ["server-start", "collect", "server-stop"])

    def test_collection_identity_failure_stops_before_second_model(self):
        result, events = self.simulate("identity")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(events, ["server-start", "collect", "server-stop", "gold-summary"])

    def test_existing_output_refused_without_children(self):
        self.args.output_root.mkdir()
        with patch.dict(os.environ, {"SLURM_JOB_ID": "123", "CUDA_VISIBLE_DEVICES": "0"}, clear=True), \
                patch.object(suite.benchmark, "load_workloads", return_value=([{}] * 231, b"")), \
                patch.object(suite.subprocess, "check_output", side_effect=["2" * 40, "", suite.benchmark.UPSTREAM_COMMIT]), \
                patch.object(suite.subprocess, "Popen") as child, self.assertRaises(FileExistsError):
            suite.run_suite(self.args)
        child.assert_not_called()

    def test_collection_guard_reaps_collector_when_owned_server_exits(self):
        server = Mock()
        server.poll.side_effect = [None, 9]
        process = Mock(pid=333, returncode=None)
        process.poll.return_value = None
        record = {}
        with patch.object(suite.subprocess, "Popen", return_value=process), \
                patch.object(suite, "stop_child", return_value=-15) as stop, \
                self.assertRaisesRegex(RuntimeError, "Owned server exited"):
            suite.run_collection(server, ["fake-collector"], self.root / "collect.log", {}, 5, record, lambda: None)
        stop.assert_called_once_with(process)
        self.assertEqual(record["child_exit_code"], -15)

    def test_collection_hard_timeout_reaps_exact_child(self):
        server = Mock()
        server.poll.return_value = None
        process = Mock(pid=333, returncode=None)
        process.poll.return_value = None
        with patch.object(suite.subprocess, "Popen", return_value=process), \
                patch.object(suite.time, "monotonic", side_effect=[0, 6, 6]), \
                patch.object(suite, "stop_child", return_value=-15) as stop, \
                self.assertRaisesRegex(TimeoutError, "wall-clock"):
            suite.run_collection(server, ["fake-collector"], self.root / "collect.log", {}, 5, {}, lambda: None)
        stop.assert_called_once_with(process)


if __name__ == "__main__":
    unittest.main()
