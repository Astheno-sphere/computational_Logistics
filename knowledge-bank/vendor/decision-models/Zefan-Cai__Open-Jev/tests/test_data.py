import copy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from jev.data import (build_dataset, evidence_answer, import_classification,
                      main, policy_answer, read_jsonl, read_split_directory, routing_answer, rubric_answer,
                      synthetic_records, validate_records)


class SyntheticDataTests(unittest.TestCase):
    def test_deterministic_and_every_target_matches_explicit_oracle(self):
        records = list(synthetic_records(200, seed=7, ood_groups=40))
        self.assertEqual(records, list(synthetic_records(200, seed=7, ood_groups=40)))
        answers = {"policy": policy_answer, "routing": routing_answer,
                   "evidence": evidence_answer, "rubric": rubric_answer}
        for row in records:
            answer = str(answers[row["metadata"]["family"]](row["state"]))
            if row["kind"] == "noul":
                candidate = row["question"].split("'")[1]
                answer = "yes" if answer == candidate else "no"
            elif row["kind"] == "score":
                answer = row["options"][row["metadata"]["score_values"].index(int(answer))]
            self.assertEqual(row["target"], [float(option == answer) for option in row["options"]])
        summary = validate_records(records)
        self.assertEqual(set(summary["families"]), {"policy", "routing", "evidence", "rubric"})
        self.assertEqual(set(summary["kinds"]), {"choice", "noul", "score"})

    def test_policy_boundaries_and_rule_precedence(self):
        state = {"age_years": 18, "annual_income_usd": 50000, "debt_ratio_basis_points": 3000,
                 "fraud_flag": False, "policy": {"minimum_age_years": 18,
                 "minimum_income_usd": 50000, "maximum_debt_ratio_basis_points": 3000}}
        self.assertEqual(policy_answer(state), "eligible")
        state["annual_income_usd"] -= 1
        self.assertEqual(policy_answer(state), "manual review")
        state["fraud_flag"] = True
        self.assertEqual(policy_answer(state), "ineligible")

    def test_evidence_absence_is_unknown(self):
        self.assertEqual(evidence_answer({"facts": [], "query": {"subject": "A", "relation": "owns", "object": "B"}}), "unknown")

    def test_routing_priorities_and_threshold(self):
        state = {"unauthorized_access": True, "service_unavailable": True, "affected_users": 100,
                 "topic": "invoice", "routing_policy": {"incident_user_threshold": 100}}
        self.assertEqual(routing_answer(state), "security")
        state["unauthorized_access"] = False
        self.assertEqual(routing_answer(state), "incident")
        state["affected_users"] = 99
        self.assertEqual(routing_answer(state), "billing")

    def test_split_grouping_and_ood_isolation(self):
        records = list(synthetic_records(300, ood_groups=60))
        groups = {}
        entities, templates = {False: set(), True: set()}, {False: set(), True: set()}
        for row in records:
            self.assertEqual(groups.setdefault(row["group_id"], row["split"]), row["split"])
            ood = row["split"] == "ood"
            entities[ood].update(row["metadata"]["entity_ids"])
            templates[ood].add(row["metadata"]["template_id"])
        self.assertFalse(entities[False] & entities[True])
        self.assertFalse(templates[False] & templates[True])
        self.assertEqual(set(validate_records(records)["splits"]), {"train", "calibration", "validation", "test", "ood"})

    def test_rejects_bad_probabilities_and_provenance(self):
        row = next(synthetic_records(1, ood_groups=0))
        for target in ([0.0] * len(row["options"]), [float("nan")] + [0.0] * (len(row["options"]) - 1)):
            invalid = copy.deepcopy(row)
            invalid["target"] = target
            with self.assertRaises(ValueError):
                validate_records([invalid])
        row["metadata"].pop("provenance")
        with self.assertRaisesRegex(ValueError, "provenance"):
            validate_records([row])

    def test_duplicate_input_cannot_evade_detection_by_shuffling(self):
        row = next(synthetic_records(1, ood_groups=0))
        other = copy.deepcopy(row)
        other.update(id="another", group_id="another", split="test" if row["split"] != "test" else "train")
        other["options"].reverse()
        other["target"].reverse()
        with self.assertRaisesRegex(ValueError, "duplicate input appears across splits"):
            validate_records([row, other])

    def test_same_context_with_changed_candidates_cannot_cross_splits(self):
        row = next(synthetic_records(1, ood_groups=0))
        row.update(split="train", options=["billing", "support"], target=[1.0, 0.0])
        other = copy.deepcopy(row)
        other.update(id="another", group_id="another", split="test", options=["billing", "security"])
        with self.assertRaisesRegex(ValueError, "same state/question/kind"):
            validate_records([row, other])

    def test_same_split_allows_changed_candidates_and_question_variants(self):
        row = next(synthetic_records(1, ood_groups=0))
        row.update(split="train", options=["billing", "support"], target=[1.0, 0.0])
        other = copy.deepcopy(row)
        other.update(id="another", options=["billing", "security"])
        paraphrase = copy.deepcopy(row)
        paraphrase.update(id="paraphrase", question="Which team handles this request?")
        self.assertEqual(validate_records([row, other, paraphrase])["records"], 3)

    def test_build_roundtrip(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = build_dataset(temporary, groups=80, ood_groups=8)
            records = [row for path in Path(temporary).glob("*.jsonl") for row in read_jsonl(path)]
            self.assertEqual(manifest["summary"], validate_records(records))
            self.assertEqual(len(manifest["files_sha256"]), 5)

    def test_directory_validation_ignores_auxiliary_workflow_jsonl(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = build_dataset(temporary, groups=24, ood_groups=4)
            (Path(temporary) / "workflow_cases.jsonl").write_text('{"state": "auxiliary workflow"}\n', encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["validate", temporary]), 0)
            self.assertEqual(json.loads(output.getvalue()), manifest["summary"])

    def test_split_directory_rejects_row_in_wrong_split_file(self):
        row = next(synthetic_records(1, ood_groups=0))
        row["split"] = "test"
        with tempfile.TemporaryDirectory() as temporary:
            (Path(temporary) / "train.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "has split 'test', expected 'train'"):
                list(read_split_directory(temporary))


class ImportDataTests(unittest.TestCase):
    def _import(self, directory, rows, **extra):
        source = Path(directory) / "raw.jsonl"
        source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        output = Path(directory) / "converted"
        manifest = import_classification(source, output, labels=["negative", "positive"],
                                         question="Is the sentiment positive?", source="example",
                                         source_url="https://example.org/data", license_name="CC0-1.0", **extra)
        records = [row for path in output.glob("*.jsonl") for row in read_jsonl(path)]
        return manifest, records

    def test_noul_maps_labels_and_preserves_official_test(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, rows = self._import(temporary, [{"text": "Excellent.", "label": "positive", "split": "test"}], kind="noul")
            self.assertEqual(rows[0]["split"], "test")
            self.assertEqual(rows[0]["options"], ["no", "yes"])
            self.assertEqual(rows[0]["target"], [0.0, 1.0])

    def test_source_train_never_becomes_test_and_duplicates_share_group(self):
        raw = [{"text": f"Review {i}", "label": "positive", "split": "train"} for i in range(100)]
        raw.append(raw[0].copy())
        with tempfile.TemporaryDirectory() as temporary:
            _, rows = self._import(temporary, raw)
            self.assertNotIn("test", {r["split"] for r in rows})
            duplicates = [r for r in rows if r["state"]["text"] == "Review 0"]
            self.assertEqual(len({r["group_id"] for r in duplicates}), 1)

    def test_group_spanning_source_train_and_test_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "group appears in multiple splits"):
                self._import(temporary, [{"text": "Good", "label": "positive", "group_id": "a", "split": "train"},
                                         {"text": "Good paraphrase", "label": "positive", "group_id": "a", "split": "test"}])

    def test_unknown_label_is_not_silently_remapped(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "unknown label"):
                self._import(temporary, [{"text": "Meh", "label": "neutral"}])


if __name__ == "__main__":
    unittest.main()
