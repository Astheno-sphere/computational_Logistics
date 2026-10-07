from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jev.data import validate_records
from jev.wanli_data import LABELS, build, convert_rows


def example(index, premise, hypothesis="A claim.", label="neutral", seed=None):
    return {"id": index, "premise": premise, "hypothesis": hypothesis,
            "gold": label, "pairID": str(seed if seed is not None else index), "genre": "generated"}


class WanliTests(unittest.TestCase):
    def convert(self, train, test=None):
        return convert_rows({"train": train, "test": test or []}, {"train": "a" * 64, "test": "b" * 64})

    def test_test_components_are_reserved_transitively(self):
        test = [example(1, "Reserved premise", seed=1)]
        train = [example(2, "Another premise", seed=1),
                 example(3, " ANOTHER PREMISE ", seed=2),
                 example(4, "Third premise", seed=2), example(5, "Independent premise")]
        rows, removed = self.convert(train, test)
        self.assertEqual(len(rows), 2)
        self.assertEqual(removed["official_test_seed_or_premise_component"], 3)
        self.assertEqual(rows[0]["split"], "test")
        self.assertEqual(rows[1]["metadata"]["provenance"]["original_split"], "train")
        validate_records(rows)

    def test_conflicts_are_removed_not_arbitrarily_resolved(self):
        rows, removed = self.convert([example(1, "Same premise", label="entailment"),
                                     example(2, "same premise", label="contradiction"),
                                     example(3, "Other premise"), example(4, "Other premise")])
        self.assertEqual(len(rows), 1)
        self.assertEqual(removed["conflicting_duplicate_pair"], 2)
        self.assertEqual(removed["duplicate_pair"], 1)

    def test_candidate_permutation_preserves_labels_and_source_groups(self):
        raw = [example(i, f"Premise {i // 2}", f"Claim {i}", list(LABELS)[i % 3], i // 3) for i in range(60)]
        rows, _ = self.convert(raw)
        self.assertGreater(len({tuple(r["options"]) for r in rows}), 1)
        for row, original in zip(rows, raw):
            self.assertEqual(row["options"][row["target"].index(1.0)], LABELS[original["gold"]])
            self.assertNotIn("gold", row["state"])
        validate_records(rows)
        self.assertEqual(rows, self.convert(list(reversed(raw)))[0][::-1])

    def test_malformed_source_fails(self):
        for bad in [example(1, " "), example(1, "Text", label="unsupported")]:
            with self.assertRaisesRegex(ValueError, "Malformed"):
                self.convert([bad])

    def test_existing_output_fails_before_source_download_or_modification(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            output.mkdir()
            marker = output / "manifest.json"
            marker.write_text("immutable dataset")
            with patch("jev.wanli_data.fetch") as fetch, self.assertRaisesRegex(ValueError, "new or empty"):
                build(Path(temporary) / "source", output)
            fetch.assert_not_called()
            self.assertEqual(marker.read_text(), "immutable dataset")
            source = Path(temporary) / "fresh-source"
            with patch("jev.wanli_data.fetch") as fetch, self.assertRaisesRegex(ValueError, "differ from the pinned source"):
                build(source, source)
            fetch.assert_not_called()
            self.assertFalse(source.exists())


if __name__ == "__main__":
    unittest.main()
