import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts import evaluate_community_pair as pair


def row_for(source, split, group, view):
    identifier = f"{source}:{split}:{group}:{view}"
    return {"id": identifier, "group_id": f"{source}:{split}:{group}", "source": source, "split": split,
            "state": {"visible_case": identifier}, "question": "Choose the admissible candidate.",
            "kind": "choice", "options": ["first", "second", "third"], "target": [1., 0., 0.],
            "metadata": {"provenance": {"type": "import", "license": "CC0-1.0", "split_policy": "group",
                         "input_sha256": "1" * 64, "source_url": "https://example.org/original", "original_id": identifier}}}


def write_source(path, version="sql-semantics-v3", source="sql-semantics-v3", groups=2, views=3):
    path.mkdir(parents=True)
    rows = {split: [row_for(source, split, group, view) for group in range(groups) for view in range(views)] for split in pair.SPLITS}
    for split, values in rows.items():
        (path / (split + ".jsonl")).write_text("".join(pair.canonical(row) + "\n" for row in values))
    update_source_manifest(path, version)
    return rows


def update_source_manifest(path, version="sql-semantics-v3"):
    pair.write_json(path / "manifest.json", {"configuration": {"generator_version": version},
        "files_sha256": {split + ".jsonl": pair.file_hash(path / (split + ".jsonl")) for split in pair.SPLITS}})


class FakeScorer:
    def __init__(self, errors=()):
        self.errors = set(errors)
        self.calls = []

    def score(self, records):
        self.calls.extend(copy.deepcopy(records))
        assert all(set(row) == set(pair.INPUT_FIELDS) for row in records)
        if any(row["state"].get("visible_case") in self.errors for row in records):
            raise RuntimeError("Intentional inference failure")
        return [[float(option.split("-")[-1]) if option.startswith("score-") else 1.0 for option in row["options"]] for row in records], 20


class CommunityPairTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / "sql"
        self.source = write_source(self.data)

    def tearDown(self):
        self.temp.cleanup()

    def checkpoint(self):
        path = self.root / "run" / "checkpoint"
        (path / "adapter").mkdir(parents=True)
        (path / "head.pt").write_bytes(b"test head")
        (path / "adapter/adapter_config.json").write_text('{}')
        (path / "adapter/adapter_model.safetensors").write_bytes(b"test adapter")
        hashes = {split: pair.file_hash(self.data / (split + ".jsonl")) for split in pair.SPLITS}
        expected = {"steps": 2, "trained_rows_consumed": 8, "training_commit": "a" * 40,
                    "run_identity_sha256": "b" * 64, "data_sha256": hashes}
        ids = [row["id"] for row in self.source["calibration"]]
        run = {"model": pair.MODEL, "revision": pair.REVISION, "steps": 2, "training_rows_consumed": 8,
               "commit": expected["training_commit"], "identity_sha256": expected["run_identity_sha256"],
               "max_length": 4096, "lora_rank": 8, "data_sha256": hashes, "calibration_ids": ids}
        summary = {"status": "complete", "model": pair.MODEL, "steps": 2, "trained_rows_consumed": 8,
                   "checkpoint_reload_max_error": .001, "temperature": 2.0}
        pair.write_json(path / "model.json", {"model_id": pair.MODEL, "revision": pair.REVISION,
                                             "max_length": 4096, "lora_rank": 8})
        pair.write_json(path / "temperature.json", {"temperature": 2.0, "split": "calibration", "n": len(ids),
                        "ids_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest()})
        pair.write_json(path.parent / "run.json", run)
        pair.write_json(path.parent / "summary.json", summary)
        (path.parent / "calibration.jsonl").write_text("".join(json.dumps({"id": identifier, "logits": [1, 0, 0]}) + "\n" for identifier in ids))
        return {"checkpoint": str(path), "training_data": str(self.data), "expected": expected}

    def test_panel_is_reproducible_group_round_robin_with_honest_counts(self):
        first, manifest = pair.select_panel([self.data], per_source_split=5)
        second, repeated = pair.select_panel([self.data], per_source_split=5)
        self.assertEqual((first, manifest), (second, repeated))
        self.assertEqual(manifest["rows"], 10)
        self.assertEqual(manifest["unique_groups"], 4)
        self.assertEqual(manifest["correlated_views_beyond_first_per_group"], 6)
        self.assertFalse(manifest["independent_case_count_claimed"])
        for split in ("test", "ood"):
            selected = [row for row in first if row["split"] == split]
            self.assertNotEqual(selected[0]["group_id"], selected[1]["group_id"])
            self.assertEqual(len({row["group_id"] for row in selected}), 2)
        all_rows, _ = pair.select_panel([self.data], per_source_split=128)
        self.assertEqual(len(all_rows), 12)  # Up to 128, not invented extra cases.

    def test_three_new_versions_and_multiple_sources_are_bound(self):
        routing = self.root / "routing"
        workflow = self.root / "workflow"
        write_source(routing, "community-routing-v3", "banking77-routing-v3")
        write_source(workflow, "community-workflow-v3", "community-workflow-v3/approval")
        rows, manifest = pair.select_panel([self.data, routing, workflow], 3)
        self.assertEqual(len(rows), 18)
        self.assertEqual({item["version"] for item in manifest["source_bindings"]}, pair.NEW_VERSIONS)
        self.assertTrue(all(len(item["files_sha256"]) == 5 for item in manifest["source_bindings"]))
        update_source_manifest(workflow, "old-v2")
        with self.assertRaisesRegex(ValueError, "new"):
            pair.select_panel([workflow])

    def test_frozen_panel_and_all_five_source_hashes_are_checked(self):
        output = self.root / "panel"
        pair.build_panel([self.data], output, 4)
        rows, _ = pair.load_panel(output, [self.data])
        self.assertEqual(len(rows), 8)
        (self.data / "train.jsonl").write_text((self.data / "train.jsonl").read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "checksum"):
            pair.load_panel(output, [self.data])
        update_source_manifest(self.data)
        with self.assertRaisesRegex(ValueError, "frozen"):
            pair.load_panel(output, [self.data])
        with self.assertRaises(FileExistsError):
            pair.build_panel([self.data], output, 4)

    def test_group_and_input_leakage_rejected_even_under_new_ids(self):
        values = copy.deepcopy(self.source["test"])
        values[0]["group_id"] = self.source["train"][0]["group_id"]
        file = self.data / "test.jsonl"
        file.write_text("".join(pair.canonical(row) + "\n" for row in values))
        update_source_manifest(self.data)
        with self.assertRaisesRegex(ValueError, "group crosses"):
            pair.select_panel([self.data])
        values[0]["group_id"] = "different-group"
        for key in pair.INPUT_FIELDS:
            values[0][key] = self.source["train"][0][key]
        values[0]["options"].reverse()
        file.write_text("".join(pair.canonical(row) + "\n" for row in values))
        update_source_manifest(self.data)
        with self.assertRaisesRegex(ValueError, "overlaps"):
            pair.select_panel([self.data])

    def test_completed_checkpoint_identity_and_changed_content(self):
        specification = self.checkpoint()
        panel, _ = pair.select_panel([self.data], 2)
        before = pair.completed_identity(specification, panel, "c" * 40)
        self.assertEqual(before["base_revision"], pair.REVISION)
        self.assertEqual(before["temperature"], 2)
        Path(specification["checkpoint"], "head.pt").write_bytes(b"changed weights")
        after = pair.completed_identity(specification, panel, "c" * 40)
        self.assertNotEqual(before["checkpoint_sha256"], after["checkpoint_sha256"])

    def test_identical_checkpoint_content_is_a_valid_negative_result(self):
        identities = {tag: {"base_revision": pair.REVISION, "checkpoint_sha256": "c" * 64,
            "training_completion": {"run_identity_sha256": identifier * 64}}
            for tag, identifier in zip(pair.TAGS, ("a", "b"))}
        self.assertTrue(pair.validate_pair_identities(identities))
        identities["v3-final"]["checkpoint_sha256"] = "d" * 64
        self.assertFalse(pair.validate_pair_identities(identities))
        identities["v3-final"]["training_completion"]["run_identity_sha256"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "distinct completed runs"):
            pair.validate_pair_identities(identities)
        identities["v3-final"]["training_completion"]["run_identity_sha256"] = "b" * 64
        identities["v3-final"]["base_revision"] = "e" * 40
        with self.assertRaisesRegex(ValueError, "same base revision"):
            pair.validate_pair_identities(identities)

    def test_incomplete_wrong_revision_reload_and_calibration_fail_closed(self):
        specification = self.checkpoint()
        path = Path(specification["checkpoint"])
        panel, _ = pair.select_panel([self.data], 2)
        for file, key, value in [(path.parent / "summary.json", "status", "running"),
                                 (path / "model.json", "revision", "d" * 40),
                                 (path.parent / "summary.json", "checkpoint_reload_max_error", .1),
                                 (path / "temperature.json", "split", "test"),
                                 (path / "temperature.json", "temperature", float("nan"))]:
            original = file.read_text()
            changed = json.loads(original)
            changed[key] = value
            file.write_text(json.dumps(changed))
            with self.subTest(key=key), self.assertRaises(ValueError):
                pair.completed_identity(specification, panel, "c" * 40)
            file.write_text(original)
        contaminated = self.source["calibration"][:1]
        with self.assertRaisesRegex(ValueError, "overlaps"):
            pair.completed_identity(specification, contaminated, "c" * 40)

    def test_candidate_microbatches_preserve_all_logits_without_gold(self):
        row = copy.deepcopy(self.source["test"][0])
        row.update(options=[f"score-{i}" for i in range(9)], target=[0.] * 8 + [1.])
        scorer = FakeScorer()
        logits, tokens = pair.score_one(scorer, row)
        self.assertEqual(logits, list(map(float, range(9))))
        self.assertEqual([len(item["options"]) for item in scorer.calls], [4, 4, 1])
        self.assertEqual(tokens, 60)
        self.assertTrue(all(set(item) == set(pair.INPUT_FIELDS) for item in scorer.calls))

    def test_errors_and_soft_targets_keep_complete_denominators(self):
        rows = copy.deepcopy(self.source["test"][:4])
        rows[0].update(options=["score-2", "score-0"], target=[1., 0.])
        rows[1].update(options=["score-2", "score-0"], target=[0., 1.])
        rows[2].update(options=["score-2", "score-0"], target=[.5, .5])
        rows[3].update(options=["score-0", "score-0", "score-2"], target=[.5, .5, 0.])
        scorer = FakeScorer([rows[1]["state"]["visible_case"]])
        results = pair.evaluate_rows(rows, scorer, {"checkpoint_sha256": "a" * 64, "temperature": 2}, self.root / "predictions.jsonl")
        metrics = pair.summarize(rows, results)["overall"]
        self.assertEqual(len(scorer.calls), 4)
        self.assertEqual(metrics["denominator"], 4)
        self.assertEqual(metrics["errors"], 1)
        self.assertEqual(metrics["valid_vector_coverage"], .75)
        self.assertEqual(metrics["all_row_positive_set_accuracy"], .5)
        self.assertEqual(metrics["hard_label_denominator"], 2)
        self.assertEqual(metrics["hard_label_accuracy"], .5)
        self.assertEqual(metrics["soft_target_rows_excluded_from_hard_accuracy"], 2)
        self.assertEqual(metrics["distribution_metrics_valid_vectors_only"]["calibrated"]["count"], 3)
        self.assertNotEqual(results[0]["probabilities_calibrated"], results[0]["probabilities_uncalibrated"])
        self.assertNotIn("probabilities_calibrated", results[1])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            pair.summarize(rows, results + results[:1])
        pending = pair.summarize(rows, results[:1])["overall"]
        self.assertEqual(pending["pending"], 3)
        self.assertEqual(pending["all_row_positive_set_accuracy"], .25)

    def test_group_macro_equal_weights_keep_errors_missing_and_soft_only_groups(self):
        rows = [row_for("source-a", "test", "many", view) for view in range(4)]
        rows += [row_for("source-a", "test", "sparse", 0), row_for("source-b", "test", "sparse", 0)]
        rows += [row_for("source-a", "test", "soft", view) for view in range(2)]
        # Equal group IDs in distinct catalogs remain separate groups.
        rows[4]["group_id"] = rows[5]["group_id"] = "shared-case-name"
        for index, row in enumerate(rows):
            row.update(options=["score-2", "score-0"], target=[.5, .5] if index >= 6 else [1., 0.])
        scorer = FakeScorer([rows[4]["state"]["visible_case"]])
        results = pair.evaluate_rows([row for index, row in enumerate(rows) if index != 5], scorer,
            {"checkpoint_sha256": "a" * 64, "temperature": 1}, self.root / "group-macro.jsonl")
        summary = pair.summarize(rows, results)
        metrics = summary["overall"]
        self.assertEqual((metrics["errors"], metrics["pending"]), (1, 1))
        self.assertEqual(metrics["all_row_positive_set_accuracy"], 6 / 8)
        self.assertEqual(metrics["hard_label_accuracy"], 4 / 6)
        macro = metrics["group_macro"]
        self.assertEqual(macro["group_key"], ["source", "group_id"])
        self.assertEqual(macro["group_count"], 4)
        self.assertEqual(macro["hard_label_group_count"], 3)
        self.assertEqual(macro["groups_without_hard_labels"], 1)
        self.assertEqual(macro["positive_set_accuracy"], .5)  # Mean of 1, 0, 0, 1.
        self.assertAlmostEqual(macro["hard_label_accuracy"], 1 / 3)
        source_a = next(bucket for bucket in summary["by_source_split_kind"] if bucket["source"] == "source-a")
        self.assertEqual(source_a["group_macro"]["group_count"], 3)
        self.assertAlmostEqual(source_a["group_macro"]["positive_set_accuracy"], 2 / 3)
        soft_only = pair.summarize(rows[6:], results[-2:])["overall"]["group_macro"]
        self.assertEqual(soft_only["group_count"], 1)
        self.assertEqual(soft_only["hard_label_group_count"], 0)
        self.assertIsNone(soft_only["hard_label_accuracy"])

    def test_noul_imbalance_and_failures_have_class_conditional_denominators(self):
        rows = [row_for("cms", "test", index, 0) for index in range(10)]
        for index, row in enumerate(rows):
            row.update(kind="noul", options=["no", "yes"], target=[0., 1.] if index == 9 else [1., 0.])
        results = pair.evaluate_rows(rows, FakeScorer(), {"checkpoint_sha256": "a" * 64, "temperature": 1},
                                     self.root / "noul.jsonl")
        metrics = pair.summarize(rows, results)["overall"]
        diagnostic = metrics["noul_binary"]
        self.assertEqual(metrics["hard_label_accuracy"], .9)
        self.assertEqual(diagnostic["always_no_accuracy_reference"], .9)
        self.assertEqual(diagnostic["all_row_balanced_accuracy"], .5)
        self.assertEqual(diagnostic["gold_counts"], {"no": 9, "yes": 1})
        self.assertEqual(diagnostic["valid_prediction_confusion"], {"tp": 0, "fp": 0, "fn": 1, "tn": 9})
        results[0] = {**results[0], "status": "error"}
        results = [result for result in results if result["id"] != rows[1]["id"]]
        metrics = pair.summarize(rows, results)["overall"]
        diagnostic = metrics["noul_binary"]
        self.assertEqual(metrics["hard_label_accuracy"], .7)
        self.assertEqual(diagnostic["errors_by_gold"], {"no": 1, "yes": 0})
        self.assertEqual(diagnostic["pending_by_gold"], {"no": 1, "yes": 0})
        self.assertEqual(diagnostic["correct_by_gold"], {"no": 7, "yes": 0})
        self.assertEqual(diagnostic["all_row_specificity"], 7 / 9)
        self.assertEqual(diagnostic["all_row_sensitivity"], 0.)
        self.assertEqual(diagnostic["all_row_balanced_accuracy"], 7 / 18)
        self.assertNotIn("noul_binary", pair.summarize(self.source["test"], [])["overall"])

    def test_nonfinite_logits_and_deadline_record_no_fake_probabilities(self):
        class Invalid:
            def score(self, rows):
                return [[math.nan] * len(rows[0]["options"])], 20
        rows = self.source["test"][:1]
        result = pair.evaluate_rows(rows, Invalid(), {"checkpoint_sha256": "a" * 64, "temperature": 1}, self.root / "bad.jsonl")[0]
        self.assertEqual(result["status"], "error")
        self.assertNotIn("probabilities_uncalibrated", result)
        with self.assertRaises(TimeoutError):
            pair.evaluate_rows(rows, FakeScorer(), {"checkpoint_sha256": "a" * 64, "temperature": 1},
                               self.root / "timeout.jsonl", time.monotonic() - 1)

    def test_cpu_panel_validation_precedes_gpu_environment_check(self):
        output = self.root / "panel"
        pair.build_panel([self.data], output, 2)
        plan = {"schema_version": 1, "evaluation_commit": "a" * 40,
                "panel_manifest_sha256": pair.file_hash(output / "manifest.json"),
                "models": {tag: {} for tag in pair.TAGS}}
        plan_path = self.root / "plan.json"
        pair.write_json(plan_path, plan)
        with patch.object(pair.subprocess, "check_output", return_value="a" * 40), patch.object(pair.subprocess, "run"), \
                patch.object(pair, "completed_identity", side_effect=ValueError("CPU identity rejected")), \
                patch.dict(pair.os.environ, {"CUDA_VISIBLE_DEVICES": ""}):
            with self.assertRaisesRegex(ValueError, "CPU identity rejected"):
                pair.run(output, [self.data], plan_path, self.root / "result")


if __name__ == "__main__":
    unittest.main()
