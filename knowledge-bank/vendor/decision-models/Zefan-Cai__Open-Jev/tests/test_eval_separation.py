import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jev.data import SPLITS
from scripts.check_eval_separation import (benchmark_index, check_separation, contains_complete_text,
                                           frozen_dataset_splits, match_row, normalized_options,
                                           visible_fingerprint)


class EvaluationSeparationTests(unittest.TestCase):
    def setUp(self):
        self.item = {"id": "synthetic-eval-case", "state": "A sufficiently detailed synthetic benchmark state describes one case and its observed records, without disclosing its answer.",
                     "question": "Which alternative follows from the recorded observations?",
                     "options": {"A": "alpha", "B": "beta", "C": "gamma", "D": "delta"}, "answer": "C", "rationale": "gold rationale"}

    def test_exact_match_ignores_option_rotation_and_standard_list_labels(self):
        item = self.item
        original = visible_fingerprint(item["state"], item["question"], item["options"])
        options = ["A: gamma", "B) delta", "(C) alpha", "[D] beta"]
        changed = visible_fingerprint("  " + item["state"].replace(" ", "\n") + " ", item["question"], options)
        self.assertEqual(changed, original)
        self.assertEqual(original, visible_fingerprint(item["state"], item["question"], ["delta", "beta", "alpha", "gamma"]))

    def test_semantic_or_partial_option_prefixes_are_not_stripped(self):
        self.assertEqual(normalized_options(["A: alpha", "beta", "gamma", "delta"]), ["A: alpha", "beta", "delta", "gamma"])
        self.assertIn("refund: Return the charge", normalized_options({"refund": "Return the charge"}))
        self.assertIn("A:alpha", normalized_options(["A:alpha", "B: beta", "C: gamma", "D: delta"]))
        self.assertNotEqual(normalized_options(["A: beta", "A: gamma", "C: alpha", "D: delta"]), ["alpha", "beta", "delta", "gamma"])

    def test_matcher_uses_only_visible_fields_and_catches_embedded_state(self):
        original_index = benchmark_index([self.item])
        altered = copy.deepcopy(self.item)
        altered.update(answer=object(), rationale=object(), difficulty=object())
        self.assertEqual(benchmark_index([altered]), original_index)
        row = {"state": {"conversation": [{"text": "Wrapper before. " + self.item["state"] + " Wrapper after."}]},
               "question": "Different question", "options": ["yes", "no"], "target": object(), "metadata": object()}
        matches, _ = match_row(row, *original_index)
        self.assertEqual(matches["exact_visible_item_ids"], [])
        self.assertEqual(matches["embedded_full_state_item_ids"], [self.item["id"]])

    def test_structured_state_keys_normalize_without_erasing_values_or_case(self):
        options = self.item["options"]
        first = visible_fingerprint({"records": [1, 2], "name": "Case"}, "Question", options)
        self.assertEqual(first, visible_fingerprint({"name": "Case", "records": [1, 2]}, "Question", options))
        self.assertNotEqual(first, visible_fingerprint({"name": "case", "records": [1, 2]}, "Question", options))
        self.assertNotEqual(first, visible_fingerprint({"name": "Case", "records": [2, 1]}, "Question", options))

    def test_short_state_is_excluded_only_from_substrings_and_boundaries_hold(self):
        item = {**self.item, "state": "case 1"}
        exact, substrings = benchmark_index([item], minimum_state_chars=80)
        self.assertEqual(substrings, {})
        matches, _ = match_row({"state": item["state"], "question": item["question"], "options": list(item["options"].values())}, exact, substrings)
        self.assertEqual(matches["exact_visible_item_ids"], [item["id"]])
        self.assertFalse(contains_complete_text("case 10", "case 1"))
        self.assertTrue(contains_complete_text("prefix: case 1; suffix", "case 1"))

    def test_manifest_layouts_preserve_identical_frozen_hashes_and_counts(self):
        hashes = {split: hashlib.sha256(split.encode()).hexdigest() for split in SPLITS}
        counts = {split: index for index, split in enumerate(SPLITS)}
        release = {"sha256": hashes, "counts": counts}
        native = {"files_sha256": {f"{split}.jsonl": value for split, value in hashes.items()},
                  "summary": {"splits": counts, "records": sum(counts.values())}}
        for manifest in (release, native, {**release, **native}):
            with self.subTest(keys=list(manifest)):
                self.assertEqual(frozen_dataset_splits(manifest), (hashes, counts))

    def test_manifest_rejects_missing_and_contradictory_definitions(self):
        hashes = {split: "a" * 64 for split in SPLITS}
        counts = {split: 1 for split in SPLITS}
        release = {"sha256": hashes, "counts": counts}
        native = {"files_sha256": {f"{split}.jsonl": value for split, value in hashes.items()},
                  "summary": {"splits": counts, "records": 5}}
        invalid = [
            {}, {"sha256": hashes}, {"counts": counts}, {"files_sha256": native["files_sha256"]},
            {**native, "summary": {"splits": {"train": 1}}},
            {**native, "files_sha256": hashes},
            {**release, "sha256": {**hashes, "train": "not-a-checksum"}},
            {**release, "counts": {**counts, "train": True}},
            {**release, **native, "sha256": {**hashes, "train": "b" * 64}},
            {**release, "summary": {"splits": {**counts, "train": 2}}},
            {**native, "summary": {"splits": counts, "records": 6}},
            {**native, "counts": counts},
        ]
        for index, manifest in enumerate(invalid):
            with self.subTest(index=index), self.assertRaises(ValueError):
                frozen_dataset_splits(manifest)

    def test_audit_checks_bytes_and_counts_for_each_manifest_layout(self):
        source = {"source_url": "synthetic", "source_commit": "synthetic", "dataset_version": "synthetic",
                  "license": "synthetic", "files_sha256": {}}
        with tempfile.TemporaryDirectory() as directory, patch(
                "scripts.check_eval_separation.load_benchmark", return_value=([self.item], None, None, source)):
            dataset = Path(directory)
            hashes, counts = {}, dict.fromkeys(SPLITS, 1)
            for split in SPLITS:
                row = {key: self.item[key] for key in ("state", "question", "options")}
                row.update(id=f"synthetic-{split}", split=split)
                content = (json.dumps(row) + "\n").encode()
                (dataset / f"{split}.jsonl").write_bytes(content)
                hashes[split] = hashlib.sha256(content).hexdigest()
            manifests = [
                {"sha256": hashes, "counts": counts},
                {"files_sha256": {f"{split}.jsonl": value for split, value in hashes.items()},
                 "summary": {"splits": counts, "records": 5}},
            ]
            for manifest in manifests:
                with self.subTest(keys=list(manifest)):
                    manifest_path = dataset / "manifest.json"
                    manifest_path.write_text(json.dumps(manifest))
                    report = check_separation("synthetic", dataset)
                    self.assertEqual(report["dataset"]["records"], 5)
                    self.assertEqual(report["exact_visible_match_rows"], 5)
                    self.assertEqual({split: value["sha256"] for split, value in report["dataset"]["splits"].items()}, hashes)
                    path = dataset / "train.jsonl"
                    original = path.read_bytes()
                    path.write_bytes(original + b"\n")
                    with self.assertRaisesRegex(ValueError, "checksum/count changed for train"):
                        check_separation("synthetic", dataset)
                    path.write_bytes(original)
                    wrong_count = copy.deepcopy(manifest)
                    if "counts" in wrong_count:
                        wrong_count["counts"]["train"] = 2
                    else:
                        wrong_count["summary"]["splits"]["train"] = 2
                        wrong_count["summary"]["records"] = 6
                    manifest_path.write_text(json.dumps(wrong_count))
                    with self.assertRaisesRegex(ValueError, "checksum/count changed for train"):
                        check_separation("synthetic", dataset)


if __name__ == "__main__":
    unittest.main()
