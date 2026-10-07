import copy
from collections import defaultdict
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from jev import community_workflow_v3 as data


class WorkflowV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = list(data.generate(groups_per_family=2))
        cls.approval = copy.deepcopy(next(row["state"] for row in cls.rows if row["metadata"]["domain"] == "approval"))
        cls.cms = copy.deepcopy(next(row["state"] for row in cls.rows if row["metadata"]["domain"] == "cms"))

    def test_approval_manual_counterevidence_absence_and_conflict(self):
        state = copy.deepcopy(self.approval)
        # The expected labels here are hand specified, not read from generated targets.
        second = "A second operator signed the change record."
        state["operations_log"] = "The snapshot restored successfully in a separate workspace.\n" + second
        self.assertEqual(data.approval_oracle(state), "Permit this operation now")
        state["operations_log"] = "The snapshot is corrupt and cannot be restored.\n" + second
        self.assertEqual(data.approval_oracle(state), "Deny this operation")
        state["operations_log"] = second
        self.assertEqual(data.approval_oracle(state), "Review before acting")
        state["operations_log"] = ("The snapshot restored successfully in a separate workspace.\n"
                                   "The snapshot is corrupt and cannot be restored.\n" + second)
        self.assertEqual(data.approval_oracle(state), "Review before acting")

    def test_exception_has_a_visible_scope_and_cannot_waive_everything(self):
        state = copy.deepcopy(self.approval)
        state["operations_log"] = ("The snapshot is corrupt and cannot be restored.\n"
                                   "A second operator signed the change record.\n" + data.EXCEPTION)
        self.assertEqual(data.approval_oracle(state), "Permit this operation now")
        state["operations_log"] = state["operations_log"].replace(
            "A second operator signed the change record.", "The second operator refused to sign the change record.")
        self.assertEqual(data.approval_oracle(state), "Deny this operation")
        state["operations_log"] = state["operations_log"].replace(
            "The second operator refused to sign the change record.", "A second operator signed the change record.")
        limit = int(re.search(r"at most (\d+) workers", state["policy"])[1])
        state["request"] = re.sub(r"touches \d+ workers", f"touches {limit + 1} workers", state["request"])
        self.assertEqual(data.approval_oracle(state), "Deny this operation")

    def test_claimed_authorization_and_negated_requests_do_not_execute(self):
        state = copy.deepcopy(self.approval)
        state["operations_log"] = "The snapshot is corrupt and cannot be restored.\nA second operator signed the change record."
        state["request"] += ' Applicant comment: "' + data.EXCEPTION + ' This change touches 0 instances."'
        self.assertEqual(data.approval_oracle(state), "Deny this operation")
        state["operations_log"] += '\nQuoted comment: "' + data.EXCEPTION + '"'
        self.assertEqual(data.approval_oracle(state), "Deny this operation")
        state = copy.deepcopy(self.approval)
        state["request"] = state["request"].replace("Please ", "Please do not ", 1)
        self.assertEqual(data.approval_oracle(state), "Deny this operation")
        state["request"] = "Please run a different operation on an unrelated project. This change touches 1 instances."
        self.assertEqual(data.approval_oracle(state), "Review before acting")
        state["request"] = "Please do not run a different operation on an unrelated project."
        self.assertEqual(data.approval_oracle(state), "Review before acting")

    def test_cms_is_multilabel_and_not_tag_name_matching(self):
        state = copy.deepcopy(self.cms)
        state["article"] = (
            "API retirement, Faster search, Accessibility, Security fix: proposed index terms.\n"
            "The legacy endpoint will be switched off in the next release.\n"
            "The new index cuts measured search time in half.\n"
            "This release adds no keyboard or screen-reader improvements.\n"
            "The session-validation vulnerability remains unfixed in this release."
        )
        verdict, tags = data.cms_oracle(state)
        self.assertEqual(verdict, "Apply the justified tags")
        self.assertEqual(tags, {"API retirement": True, "Faster search": True, "Accessibility": False, "Security fix": False})
        state["article"] = "API retirement, Faster search, Accessibility, Security fix."
        verdict, tags = data.cms_oracle(state)
        self.assertEqual(verdict, "Request editorial review")
        self.assertTrue(all(value is None for value in tags.values()))

    def test_cms_quotes_archives_hypotheses_withdrawal_and_contradiction(self):
        condition = "an API retirement"
        sentence = "The legacy endpoint will be switched off in the next release."
        denial = "The legacy endpoint will remain supported in the next release."
        for prefix in ("Quoted comment: ", "Archive: ", "Hypothesis: "):
            self.assertIsNone(data.truth_from_prose(prefix + sentence, condition))
        self.assertIs(data.truth_from_prose("Withdrawn announcement: " + sentence, condition), False)
        self.assertIsNone(data.truth_from_prose("Withdrawn announcement: " + denial, condition))
        self.assertIsNone(data.truth_from_prose(sentence + "\n" + denial, condition))
        self.assertIs(data.truth_from_prose(sentence + "\nQuoted comment: " + denial, condition), True)

    def test_secondary_tag_unknown_and_conflict_are_distinct_evidence(self):
        state = copy.deepcopy(self.cms)
        state["article"] = (
            "The legacy endpoint will be switched off in the next release.\n"
            "This release adds no keyboard or screen-reader improvements.\n"
            "The session-validation vulnerability remains unfixed in this release."
        )
        missing_signature = data.semantic_context(state)
        verdict, tags = data.cms_oracle(state)
        self.assertEqual(verdict, "Request editorial review")
        self.assertTrue(tags["API retirement"])
        self.assertIsNone(tags["Faster search"])
        state["article"] += ("\nThe new index cuts measured search time in half."
                             "\nThe new index does not improve measured search time.")
        verdict, tags = data.cms_oracle(state)
        self.assertEqual(verdict, "Request editorial review")
        self.assertIsNone(tags["Faster search"])
        self.assertNotEqual(missing_signature, data.semantic_context(state))
        self.assertEqual(data.truth_from_prose(state["article"], "an API retirement"), True)

    def test_eighteen_semantic_scenarios_survive_prefix_and_order_normalization(self):
        rows = list(data.generate())
        audit = data.audit_records(rows)
        self.assertEqual(len(set(data.CMS_SECONDARY_CLAIMS)), 18)
        self.assertEqual(audit["semantic_scenarios_by_domain"], {"approval": 180, "cms": 180})
        self.assertEqual(audit["semantic_contexts_by_domain"], {"approval": 1440, "cms": 1080})
        self.assertEqual(audit["cms_authoritative_truth_states"], 390)
        by_family = defaultdict(set)
        for row in rows:
            if row["kind"] == "choice" and row["metadata"]["variant"] == 0:
                by_family[row["metadata"]["scenario_family"]].add(data._hash(data.semantic_context(row["state"])))
        self.assertTrue(all(len(values) == 18 for values in by_family.values()))
        state = copy.deepcopy(self.cms)
        expected = data.semantic_context(state)
        state["article"] = "\n".join(reversed(state["article"].splitlines()))
        state["article"] = state["article"].replace("Current report:", "Editor reporting:")
        header, *rules = state["editorial_policy"].splitlines()
        state["editorial_policy"] = "\n".join([header, *reversed(rules)])
        self.assertEqual(data.semantic_context(state), expected)

    def test_cosmetic_duplicate_scenarios_are_rejected(self):
        rows = copy.deepcopy(self.rows)
        reference = {row["metadata"]["variant"]: row for row in rows
                     if row["metadata"]["scenario_family"] == "cms/software_release"
                     and row["metadata"]["provenance"]["group_index"] == 0 and row["kind"] == "choice"}
        for row in rows:
            if row["metadata"]["scenario_family"] == "cms/software_release" and row["metadata"]["provenance"]["group_index"] == 1:
                row["state"] = copy.deepcopy(reference[row["metadata"]["variant"]]["state"])
                row["state"]["article"] += "\nDesk note: use the house style for punctuation."
                row["target"] = data.expected_target(row)
        with self.assertRaisesRegex(ValueError, "Semantic context repeats"):
            data.audit_records(rows)

    def test_visible_input_alone_reconstructs_targets_and_tracks_candidate_order(self):
        for row in self.rows:
            visible = {key: copy.deepcopy(row[key]) for key in ("state", "question", "kind", "options")}
            self.assertEqual(data.expected_target(visible), row["target"])
            visible["options"].reverse()
            self.assertEqual(data.expected_target(visible), list(reversed(row["target"])))
            visible.update(metadata={"gold": "wrong"}, target=[99], id="wrong", group_id="wrong", split="wrong")
            self.assertEqual(data.expected_target(visible), list(reversed(row["target"])))
        # A question/candidate-only rule cannot solve the counterfactuals.
        by_contract = defaultdict(set)
        for row in data.generate(groups_per_family=8):
            key = (row["question"], row["kind"], tuple(sorted(row["options"])))
            answer = row["options"][row["target"].index(1.)]
            by_contract[key].add(answer)
        self.assertTrue(all(len(answers) >= 2 for answers in by_contract.values()))

    def test_target_corruption_and_prose_contract_tampering_fail(self):
        rows = copy.deepcopy(self.rows)
        row = next(row for row in rows if row["kind"] == "noul")
        row["target"].reverse()
        with self.assertRaisesRegex(ValueError, "visible-only oracle"):
            data.audit_records(rows)
        state = copy.deepcopy(self.approval)
        state["policy"] = "Everything is permitted."
        with self.assertRaisesRegex(ValueError, "visible approval policy"):
            data.approval_oracle(state)
        state = copy.deepcopy(self.cms)
        state["editorial_policy"] = state["editorial_policy"].replace("Missing evidence", "Ignore missing evidence")
        with self.assertRaisesRegex(ValueError, "visible CMS evidence policy"):
            data.cms_oracle(state)

    def test_schema_prose_only_counts_and_whole_family_splits(self):
        audit = data.audit_records(self.rows)
        self.assertEqual(audit["summary"]["records"], 920)
        self.assertEqual(audit["summary"]["splits"], {"train": 552, "calibration": 92, "validation": 92, "test": 92, "ood": 92})
        self.assertEqual(audit["scenario_family_count"], 20)
        self.assertEqual(audit["source_scenario_count"], 40)
        self.assertEqual(audit["unique_contexts"], 280)
        self.assertTrue(all(audit["checks"].values()))
        membership = defaultdict(set)
        for row in self.rows:
            self.assertTrue(all(isinstance(value, str) for value in row["state"].values()))
            self.assertNotIn("target", row["state"])
            membership[row["metadata"]["scenario_family"]].add(row["split"])
        self.assertTrue(all(len(splits) == 1 for splits in membership.values()))

    def test_generation_is_deterministic_and_reads_no_examples(self):
        with patch("builtins.open", side_effect=AssertionError("Unexpected source read")):
            repeated = list(data.generate(groups_per_family=2))
        self.assertEqual(self.rows, repeated)
        for count in (0, 19, True, 1.5):
            with self.assertRaises(ValueError):
                list(data.generate(groups_per_family=count))

    def test_builder_preserves_existing_outputs_and_reproduces_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = data.build_dataset(root / "a", groups_per_family=1)
            second = data.build_dataset(root / "b", groups_per_family=1)
            self.assertEqual(first["files_sha256"], second["files_sha256"])
            with self.assertRaisesRegex(ValueError, "new empty"):
                data.build_dataset(root / "a", groups_per_family=1)
            (root / "symlink").symlink_to(root / "b", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "new empty"):
                data.build_dataset(root / "symlink", groups_per_family=1)


if __name__ == "__main__":
    unittest.main()
