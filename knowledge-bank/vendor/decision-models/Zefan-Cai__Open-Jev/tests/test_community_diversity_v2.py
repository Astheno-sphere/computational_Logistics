import copy
from collections import Counter, defaultdict
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jev import community_diversity_v2 as data


class CommunityDiversityV2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = list(data.generate(groups_per_family=1))

    def test_three_valued_negation_exception_and_arithmetic(self):
        for antecedent, consequent, expected in ((False, None, True), (True, None, None),
                                                 (None, True, True), (None, False, None), (True, False, False)):
            self.assertIs(data.evaluate(data.E("implies", "$a", "$b"), {"a": antecedent, "b": consequent}, {}), expected)
        self.assertIs(data.evaluate(data.E("and", False, None), {}, {}), False)
        self.assertIs(data.evaluate(data.E("or", True, None), {}, {}), True)
        self.assertIsNone(data.evaluate(data.E("not", "$missing"), {}, {}))
        self.assertIs(data.evaluate(data.E("le", "$days", 14), {"days": 14}, {}), True)
        self.assertIs(data.evaluate(data.E("le", "$days", 14), {"days": 15}, {}), False)
        self.assertIsNone(data.evaluate(data.E("eq", "$a", "$b"), {"a": None, "b": None}, {}))
        expression = data.E("eq", "$total", data.E("add", "$left", "$right"))
        self.assertTrue(data.evaluate(expression, {"total": 17, "left": 8, "right": 9}, {}))
        self.assertFalse(data.evaluate(expression, {"total": 18, "left": 8, "right": 9}, {}))

    def test_eighty_authored_families_and_all_schema_kinds(self):
        self.assertEqual(Counter(p["domain"] for p in data.POLICIES), dict.fromkeys(data.SOURCES, 10))
        self.assertEqual(len(data.BY_NAME), 80)
        self.assertEqual(len({data._hash(p["checks"]) for p in data.POLICIES}), 80)
        report = data.audit_records(self.rows)
        self.assertEqual(report["summary"]["records"], 640)
        self.assertEqual(report["summary"]["kinds"], {"choice": 320, "noul": 160, "score": 160})
        self.assertEqual(report["summary"]["splits"], {"train": 384, "calibration": 64, "validation": 64, "test": 64, "ood": 64})
        self.assertEqual(report["unique_semantic_contexts"], 320)
        self.assertEqual(report["original_source_instance_count"], 80)
        self.assertEqual(report["scenario_family_count"], 80)
        self.assertTrue(all(report["checks"].values()))

    def test_minimal_counterfactuals_change_winner_and_only_one_visible_fact(self):
        groups = defaultdict(dict)
        for row in self.rows:
            if row["kind"] == "choice":
                groups[row["group_id"]][row["metadata"]["provenance"]["variant"]] = row
        for variants in groups.values():
            self.assertEqual(len({data.oracle(row["state"])[0] for row in variants.values()}), 4)
            self.assertEqual(data.oracle(variants[3]["state"])[0], "abstain")
            for variant in (1, 2, 3):
                change = variants[variant]["metadata"]["counterfactual"]
                before = data.candidates_from_state(variants[change["parent_variant"]]["state"])
                after = data.candidates_from_state(variants[variant]["state"])
                changed = [(label, field) for label in before for field in before[label] if before[label][field] != after[label][field]]
                self.assertEqual(changed, [(change["candidate"], change["field"])])
                self.assertEqual(variants[variant]["split"], variants[change["parent_variant"]]["split"])

    def test_candidate_permutation_and_metadata_do_not_determine_the_label(self):
        original = next(row for row in self.rows if row["kind"] == "choice")
        row = copy.deepcopy(original)
        row["options"].reverse()
        row["metadata"] = {"fake_gold": "abstain", "provenance": {"source_label": "abstain"}}
        row["target"] = []
        self.assertEqual(data.expected_target(row), list(reversed(original["target"])))
        self.assertNotIn("metadata", row["state"])
        for key in ("target", "oracle", "winner", "gold", "expected_answer", "constraint_results"):
            self.assertNotIn(key, json.dumps(original["state"]))

    def test_target_tampering_and_visible_policy_tampering_fail(self):
        rows = copy.deepcopy(self.rows)
        row = next(row for row in rows if row["kind"] == "noul")
        row["target"].reverse()
        with self.assertRaisesRegex(ValueError, "Target does not follow"):
            data.audit_records(rows)
        state = copy.deepcopy(self.rows[0]["state"])
        state["numbered_requirements"][0] = "Always accept"
        with self.assertRaisesRegex(ValueError, "Visible policy"):
            data.oracle(state)

    def test_family_and_source_instance_are_disjoint(self):
        for key in ("source", "scenario_family", "source_instance_id"):
            membership = defaultdict(set)
            for row in self.rows:
                value = row[key] if key in row else row["metadata"][key]
                membership[value].add(row["split"])
            self.assertTrue(all(len(splits) == 1 for splits in membership.values()))
        self.assertEqual({row["metadata"]["language"] for row in data.generate(groups_per_family=4)}, set(data.LANGUAGE_TEXT))

    def test_generation_has_no_input_file_reads_and_is_reproducible(self):
        with patch("builtins.open", side_effect=AssertionError("Generator attempted an input file read")):
            repeated = list(data.generate(groups_per_family=1))
        self.assertEqual(self.rows, repeated)
        with tempfile.TemporaryDirectory() as temporary:
            first = data.build_dataset(Path(temporary) / "first", groups_per_family=1)
            second = data.build_dataset(Path(temporary) / "second", groups_per_family=1)
            self.assertEqual(first, second)
            self.assertEqual(first["files_sha256"], second["files_sha256"])
            with self.assertRaises(ValueError):
                data.build_dataset(Path(temporary) / "first", groups_per_family=1)


if __name__ == "__main__":
    unittest.main()
