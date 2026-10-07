import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import jevbench_openjev as benchmark
from scripts import run_jevbench_hosted as hosted


UPSTREAM = Path(__file__).resolve().parents[1] / "runs/jevbench-20260921/upstream"


class HostedBoundsTest(unittest.TestCase):
    def test_output_cap_and_price_bounds_include_all_4096_tokens(self):
        for name in ("luna", "astra"):
            config = hosted.PROVIDERS[name]
            body = {"messages": [{"role": "user", "content": "fixture"}], "max_completion_tokens": 4096}
            bound = hosted.reservation(body, config)
            self.assertEqual(bound["output_token_bound"], 4096)
            self.assertEqual(bound["input_token_bound"], len(json.dumps(body).encode()) + 4096)
            self.assertAlmostEqual(bound["reserve_usd"],
                                   (bound["input_token_bound"] * config["input_price"] + 4096 * config["output_price"]) / 1e6)
            with self.assertRaises(ValueError):
                hosted.reservation({"max_completion_tokens": 4000}, config)

    def test_credentials_are_scoped_restored_and_rejected_in_git(self):
        with patch.dict(os.environ, {hosted.KEY_ENV: "previous"}), hosted.scoped_key("test-secret"):
            self.assertEqual(os.environ[hosted.KEY_ENV], "test-secret")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            key = root / "private.key"
            key.write_text("test-only-key\n")
            self.assertEqual(hosted.read_key(key), "test-only-key")
            (root / ".git").mkdir()
            with self.assertRaises(ValueError):
                hosted.read_key(key)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError), hosted.scoped_key("test-only-key"):
                raise RuntimeError("fixture")
            self.assertNotIn(hosted.KEY_ENV, os.environ)

    def test_failure_cost_rejects_missing_and_boolean_usage(self):
        config = hosted.PROVIDERS["astra"]
        self.assertAlmostEqual(hosted.usage_cost({"prompt_tokens": 10, "completion_tokens": 20}, config), .0011)
        self.assertIsNone(hosted.usage_cost({"input_tokens": True, "output_tokens": 20}, config))
        self.assertIsNone(hosted.usage_cost({}, config))


@unittest.skipUnless(UPSTREAM.is_dir(), "requires pinned JevBench source; no downloads in tests")
class HostedPinnedTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.upstream = benchmark.load_upstream(UPSTREAM)
        self.budget = importlib.import_module("jevbench.budget")

    def test_exact_gpt_options_and_native_probability_provenance(self):
        for name, effort in (("luna", "none"), ("astra", "low")):
            adapter = hosted.create_adapter(name, "test-key", 5)
            body = adapter.build_request(self.upstream.tasks[0])
            self.assertEqual(body["reasoning_effort"], effort)
            self.assertEqual(body["max_completion_tokens"], 4096)
            self.assertNotIn("temperature", body)
            self.assertNotIn("max_tokens", body)
            self.assertTrue(body["response_format"]["json_schema"]["strict"])
        self.assertEqual(hosted.PROVIDERS["jev"]["probabilities"], "native")
        self.assertEqual(hosted.PROVIDERS["luna"]["probabilities"], "verbalized")

    def test_auth_failure_stops_once_and_retains_billed_failure_usage(self):
        module = importlib.import_module("jevbench.adapters.openai_compat")
        ledger = self.budget.Ledger(self.root / "ledger.jsonl", cap_usd=25)
        payload = {"error": "test-secret", "usage": {"prompt_tokens": 10, "completion_tokens": 20}}
        with patch.object(module, "http_post_json", return_value=(429, payload, .01)) as http:
            report = hosted.stream(self.upstream, "astra", "test-secret", self.root / "astra", ledger, timeout=5)
        self.assertEqual(http.call_count, 1)
        self.assertEqual(report["attempted_requests"], 1)
        self.assertEqual(report["pending_requests"], 230)
        self.assertEqual(report["status"], "stopped_partial")
        summary = json.loads((self.root / "astra/summary.json").read_text())
        self.assertAlmostEqual(summary["failure_usage_cost_usd"], .0011)
        self.assertEqual(summary["planned_accuracy"], 0)
        self.assertGreater(ledger.charged, .0011)
        for path in (self.root / "astra").rglob("*"):
            if path.is_file():
                self.assertNotIn("test-secret", path.read_text())

    def test_budget_reserves_before_send_and_unknown_cost_remains_charged(self):
        module = importlib.import_module("jevbench.adapters.typesafe")
        ledger = self.budget.Ledger(self.root / "ledger.jsonl", cap_usd=1e-10)
        with patch.object(module, "http_post_json") as http:
            report = hosted.stream(self.upstream, "jev", "test-key", self.root / "jev", ledger, timeout=5)
        http.assert_not_called()
        self.assertEqual(report["started_requests"], 0)
        self.assertEqual(report["pending_requests"], 231)
        self.assertEqual(ledger.charged, 0)

    def test_wall_deadline_keeps_unknown_dispatch_and_restores_key(self):
        module = importlib.import_module("jevbench.adapters.typesafe")
        ledger = self.budget.Ledger(self.root / "ledger.jsonl", cap_usd=25)
        with patch.object(module, "http_post_json", side_effect=hosted.DeadlineReached()) as http, \
                patch.dict(os.environ, {hosted.KEY_ENV: "before"}):
            report = hosted.stream(self.upstream, "jev", "test-key", self.root / "jev", ledger, timeout=5)
            self.assertEqual(os.environ[hosted.KEY_ENV], "before")
        self.assertEqual(http.call_count, 1)
        self.assertEqual(report["status"], "stopped_time_limit")
        self.assertEqual((report["started_requests"], report["attempted_requests"], report["pending_requests"]), (1, 0, 230))
        self.assertGreater(ledger.charged, 0)


if __name__ == "__main__":
    unittest.main()
