import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jev.data import build_dataset, read_jsonl, validate_records
from jev.mix_data import mix
from jev.public_data import convert


class PublicDataTests(unittest.TestCase):
    def test_passage_group_isolation_and_import_provenance(self):
        passage = "A shared document containing explicit facts."
        filtered_passage = " ".join(["long"] * 100)
        sources = {
            "validation": [
                {"passage": passage, "question": "First question?", "answer": True},
                {"passage": passage, "question": "Second question?", "answer": False},
                {"passage": filtered_passage, "question": " ".join(["question"] * 60), "answer": True},
            ],
            "train": [
                {"passage": passage.upper(), "question": "Training question?", "answer": True},
                {"passage": filtered_passage, "question": "Short question?", "answer": True},
                {"passage": "A separate source document.", "question": "Question one?", "answer": True},
                {"passage": "A separate source document.", "question": "Question two?", "answer": False},
                {"passage": "A separate source document.", "question": "Question one?", "answer": True},
            ],
        }
        loader = lambda split: (sources[split], "https://example.org/" + split, "a" * 64)
        with tempfile.TemporaryDirectory() as temporary, patch("jev.public_data._load_split", side_effect=loader), contextlib.redirect_stdout(io.StringIO()):
            manifest = convert(temporary)
            rows = [r for path in Path(temporary).glob("*.jsonl") for r in read_jsonl(path)]
            self.assertEqual(validate_records(rows)["records"], 4)
            self.assertEqual(manifest["counts"]["test"], 2)
            self.assertEqual(manifest["filtered"]["cross_split_passages"], 2)
            self.assertEqual(manifest["filtered"]["duplicates"], 1)
            self.assertEqual(manifest["filtered"]["length_filtered"], 1)
            by_passage = {}
            for row in rows:
                self.assertEqual(by_passage.setdefault(row["group_id"], row["split"]), row["split"])
                self.assertEqual(row["metadata"]["provenance"]["input_sha256"], "a" * 64)
                if row["metadata"]["original_split"] == "validation":
                    self.assertEqual(row["split"], "test")
                else:
                    self.assertNotEqual(row["split"], "test")

    def test_identical_inputs_with_conflicting_labels_fail(self):
        rows = [{"passage": "One document", "question": "One question?", "answer": answer} for answer in (True, False)]
        with tempfile.TemporaryDirectory() as temporary, patch("jev.public_data._load_split", return_value=(rows, "https://example.org/validation", "b" * 64)):
            with self.assertRaisesRegex(ValueError, "conflicting labels"):
                convert(temporary)


class MixDataTests(unittest.TestCase):
    def test_mixed_counts_and_metadata_validate(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, second, output = [Path(temporary) / x for x in ("first", "second", "mixed")]
            build_dataset(first, groups=24, ood_groups=4, seed=1)
            build_dataset(second, groups=24, ood_groups=4, seed=2)
            manifest = mix([first, second], output)
            rows = [r for path in output.glob("*.jsonl") for r in read_jsonl(path)]
            self.assertEqual(manifest["summary"], validate_records(rows))
            self.assertEqual(sum(manifest["counts"].values()), len(rows))

    def test_file_split_mismatch_fails_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / "source", Path(temporary) / "mixed"
            source.mkdir()
            (source / "train.jsonl").write_text(json.dumps({"id": "wrong", "split": "test"}) + "\n")
            with self.assertRaisesRegex(ValueError, "expected 'train'"):
                mix([source], output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
