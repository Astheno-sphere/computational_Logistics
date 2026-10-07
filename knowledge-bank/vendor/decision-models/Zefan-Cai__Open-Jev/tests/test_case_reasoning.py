import copy
import itertools
import unittest

from jev.api import candidate_prompts
from jev.case_reasoning import (DOMAINS, algorithm_result, arithmetic_value,
                                eval_boolean, generate_cases, graph_distances,
                                program_value, resolve_evidence, utc_order)
from jev.data import validate_records


class ReasoningControlTest(unittest.TestCase):
    def test_logic_truth_tables(self):
        for a, b in itertools.product((False, True), repeat=2):
            values = {"a": a, "b": b}
            self.assertEqual(eval_boolean(["IMPLIES", "a", "b"], values), (a, b) != (True, False))
            self.assertEqual(eval_boolean(["XOR", "a", "b"], values), sum((a, b)) == 1)
            self.assertEqual(eval_boolean(["NOT", ["AND", "a", "b"]], values), not a or not b)

    def test_directed_reachability_handles_cycles_and_disconnected_nodes(self):
        self.assertEqual(graph_distances(["a", "b", "c", "d"], [("a", "b"), ("b", "c"), ("c", "a")], "a"), {"a": 0, "b": 1, "c": 2})
        self.assertEqual(graph_distances(["a", "b"], [("b", "a")], "a"), {"a": 0})
        with self.assertRaises(ValueError):
            graph_distances(["a"], [("a", "missing")], "a")

    def test_arithmetic_uses_exact_integer_floor_and_remainder(self):
        self.assertEqual(arithmetic_value("(a // b) - abs(c)", {"a": -7, "b": 3, "c": -4}), -7)
        self.assertEqual(arithmetic_value("max(a, b) + (c % b)", {"a": -7, "b": 3, "c": -4}), 5)
        with self.assertRaises(ValueError):
            arithmetic_value("__import__('os')", {})

    def test_code_interpreter_matches_hand_calculated_branches(self):
        source = "x = 2\nfor item in [2, -1, 4, 3]:\n    if item % 2 == 0:\n        x += item\n    else:\n        x -= 1\nresult = x * -3"
        self.assertEqual(program_value(source), -18)
        for invalid in ("import os\nresult = 0", "while True:\n    result = 1", "result = open('anything')"):
            with self.assertRaises(ValueError):
                program_value(invalid)

    def test_temporal_order_compares_instants_not_local_dates(self):
        events = [{"id": "late", "timestamp": "2028-02-29T00:30:00-04:00"},
                  {"id": "early", "timestamp": "2028-02-29T05:00:00+05:30"},
                  {"id": "middle", "timestamp": "2028-02-29T01:00:00+00:00"}]
        self.assertEqual([event["id"] for event in utc_order(events)], ["early", "middle", "late"])

    def test_filter_sort_and_missing_rank(self):
        self.assertEqual(algorithm_result([5, -6, 3, 12, 2], 3, True, 1), (3, 3))
        self.assertEqual(algorithm_result([1, 3, 5], 2, False, 0), (None, 0))

    def test_evidence_filters_aliases_retractions_and_tied_conflicts(self):
        rows = [dict(entity="old", property="status", value="active", revision=2, authoritative=True, retracted=False),
                dict(entity="current", property="status", value="closed", revision=99, authoritative=False, retracted=False),
                dict(entity="current", property="status", value="paused", revision=3, authoritative=True, retracted=True)]
        aliases = {"old": "intermediate", "intermediate": "current"}
        self.assertEqual(resolve_evidence(rows, "current", "status", aliases), ("active", 1))
        conflict = dict(entity="current", property="status", value="paused", revision=2, authoritative=True, retracted=False)
        self.assertEqual(resolve_evidence([*rows, conflict], "current", "status", aliases), ("conflict", 2))
        self.assertEqual(resolve_evidence(rows, "absent", "status", aliases), ("not_stated", 0))

    def test_generated_records_have_domain_coverage_and_grouped_splits(self):
        rows = [row for case in generate_cases(140) for row in case]
        report = validate_records(rows)
        self.assertEqual(report["groups"], 140)
        self.assertEqual(report["records"], 420)
        self.assertEqual(set(row["metadata"]["domain"] for row in rows), set(DOMAINS))
        for domain in DOMAINS:
            splits = {row["split"] for row in rows if row["metadata"]["domain"] == domain}
            self.assertIn("ood", splits)
            self.assertIn("train", splits)
        self.assertEqual(rows, [row for case in generate_cases(140) for row in case])
        for row in rows:
            self.assertEqual(sum(row["target"]), 1)
            self.assertTrue(all(value in (0, 1) for value in row["target"]))

    def test_oracles_labels_and_ids_do_not_leak_into_candidate_prompts(self):
        for row in next(generate_cases(1)):
            before = candidate_prompts(row)
            altered = copy.deepcopy(row)
            altered.update(id="HIDDEN", target=list(reversed(row["target"])), metadata={"answer": "HIDDEN"}, split="test")
            self.assertEqual(before, candidate_prompts(altered))


if __name__ == "__main__":
    unittest.main()
