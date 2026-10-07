"""Decision/threshold regressions that probability error alone cannot catch."""
import copy
import math
import unittest
from types import SimpleNamespace

from scripts.benchmark_efficiency import (compare_responses, independent_fixture_suite,
                                          loopback_http_benchmark, percentile, summarize)


def choice(a=.6, b=.4):
    return {"answers": {"route": {"type": "choice", "choice": "a" if a >= b else "b",
                                  "probabilities": {"a": a, "b": b}}},
            "usage": {"input_tokens": 100, "output_tokens": 0}}


class EfficiencyMetricsTest(unittest.TestCase):
    def test_small_error_without_crossing_passes(self):
        check = compare_responses(choice(), choice(.60001, .39999))
        self.assertTrue(check["passed"])
        self.assertAlmostEqual(check["max_probability_error"], .00001)
        self.assertAlmostEqual(check["boundary_margins"][0]["top_two_margin"], .2)

    def test_tiny_probability_error_still_fails_decision_boundary(self):
        check = compare_responses(choice(.500001, .499999), choice(.499999, .500001))
        self.assertFalse(check["passed"])
        self.assertLess(check["max_probability_error"], 1e-4)
        self.assertEqual(check["changed_decisions"], ["route"])

    def test_tiny_coverage_boundary_flip_is_reported(self):
        check = compare_responses(choice(.899999, .100001), choice(.900001, .099999))
        self.assertFalse(check["passed"])
        self.assertEqual(check["changed_decisions"], [])
        self.assertEqual(check["threshold_flips"]["0.9"]["confidence_coverage"], 1)

    def test_noul_equal_boundary_uses_true_at_half(self):
        a = {"answers": {"gate": {"type": "noul", "noul": .5}}}
        b = {"answers": {"gate": {"type": "noul", "noul": .499999}}}
        check = compare_responses(a, b)
        self.assertEqual(check["changed_decisions"], ["gate"])
        self.assertEqual(check["threshold_flips"]["0.5"]["noul_true"], 1)

    def test_official_noul_thresholds_point_two_and_point_eight_are_audited(self):
        for threshold in (.2, .8):
            a = {"answers": {"gate": {"type": "noul", "noul": threshold - 1e-6}}}
            b = {"answers": {"gate": {"type": "noul", "noul": threshold + 1e-6}}}
            check = compare_responses(a, b)
            self.assertFalse(check["passed"])
            self.assertEqual(check["threshold_flips"][str(threshold)]["noul_true"], 1)

    def test_independent_suite_is_deterministic_and_compiles_mixed_types(self):
        from jev.api import compile_request
        first = independent_fixture_suite()
        self.assertEqual(first, independent_fixture_suite())
        self.assertEqual(len(first), 7)
        compiled = [compile_request(w["request"]["state"], w["request"]["questions"]) for w in first]
        self.assertEqual({r["kind"] for r in compiled[0]}, {"choice", "noul", "score"})
        self.assertGreater(len(first[2]["request"]["state"]["audit_trail"]),
                           len(first[1]["request"]["state"]["audit_trail"]))

    def test_loopback_http_audits_real_transport_and_separates_scope(self):
        from jev.serving import Predictor

        class FixtureScorer:
            def score(self, records):
                return [[0.0, 1.0] for _ in records], 100

        predictor = Predictor(FixtureScorer(), model_name="fixture", method="fixture")
        request = {"state": "fixture", "questions": {
            "route": {"type": "choice", "instructions": "Select a route.", "criteria": {"a": "First", "b": "Second"}}}}
        expected = predictor.predict(request)
        report = loopback_http_benchmark(predictor, request, SimpleNamespace(type="cpu"),
                                          iterations=2, warmup=0, reference_response=expected, tolerance=1e-4)
        self.assertTrue(report["parity_passed"])
        self.assertEqual(len(report["warm_samples_ms"]), 2)
        self.assertIn("loopback HTTP", report["scope"])

    def test_missing_reordered_and_nonfinite_probabilities_fail(self):
        b = copy.deepcopy(choice())
        b["answers"]["route"]["probabilities"] = {"b": .4, "a": .6}
        with self.assertRaisesRegex(ValueError, "candidate coverage"):
            compare_responses(choice(), b)
        b = copy.deepcopy(choice())
        b["answers"]["route"]["probabilities"]["a"] = math.nan
        with self.assertRaises(ValueError):
            compare_responses(choice(), b)
        with self.assertRaisesRegex(ValueError, "question coverage"):
            compare_responses(choice(), {"answers": {}})

    def test_usage_mismatch_fails_parity(self):
        b = choice()
        b["usage"]["input_tokens"] += 1
        self.assertFalse(compare_responses(choice(), b)["passed"])

    def test_interpolated_percentiles_and_throughput(self):
        self.assertEqual(percentile([1, 2, 3, 4], .5), 2.5)
        self.assertAlmostEqual(percentile([1, 2, 3, 4], .95), 3.85)
        metrics = summarize([100, 200], candidates=8, questions=2)
        self.assertAlmostEqual(metrics["requests_per_second"], 2 / .3)
        self.assertAlmostEqual(metrics["candidate_sequences_per_second"], 16 / .3)
