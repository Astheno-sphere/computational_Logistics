import json
from pathlib import Path
import tempfile
import unittest

from jev.data import SPLITS, _write_dataset, read_jsonl
from scripts.build_community_hard_mix import build, replay_sample
from scripts.screen_training_overlap import build_index, fingerprint, screen, shingles


def source_dataset(path, source, train_count, legacy_manifest=False):
    rows = []
    for split in SPLITS:
        for i in range(train_count if split == "train" else 1):
            identifier = f"{path.name}:{split}:{i}"
            rows.append({"id": identifier, "group_id": identifier, "source": source, "split": split,
                         "state": "Independent example " + identifier, "question": "Select.",
                         "kind": "choice", "options": ["a", "b"], "target": [1.0, 0.0],
                         "metadata": {"provenance": {"type": "import", "license": "CC0-1.0", "input_sha256": "a" * 64,
                                                      "source_url": "https://example.org/test", "original_id": identifier,
                                                      "split_policy": "disjoint test fixture groups"}}})
    manifest = _write_dataset(rows, path, {})
    if legacy_manifest:
        manifest = {"sha256": {s: manifest["files_sha256"][s + ".jsonl"] for s in SPLITS}}
        (path / "manifest.json").write_text(json.dumps(manifest))
    return rows


class HardMixtureTests(unittest.TestCase):
    def test_replay_spreads_across_groups_and_never_duplicates(self):
        rows = [{"id": f"{s}:{g}:{i}", "source": s, "group_id": str(g)}
                for s in ("a", "b") for g in range(4) for i in range(3)]
        picked = replay_sample(rows, 5, 17)
        self.assertEqual(len(picked), 10)
        self.assertEqual(len({r["id"] for r in picked}), 10)
        for s in ("a", "b"):
            self.assertEqual(len({r["group_id"] for r in picked if r["source"] == s}), 4)
        self.assertEqual(picked, replay_sample(list(reversed(rows)), 5, 17))

    def test_mixture_checks_both_manifest_schemas_and_caps_across_replay_folders(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_dataset(root / "new", "new-source", 1)
            source_dataset(root / "replay-a", "same-source", 3, legacy_manifest=True)
            source_dataset(root / "replay-b", "same-source", 3)
            manifest = build([root / "new"], [root / "replay-a", root / "replay-b"], root / "mixed", cap=2,
                             version="community-hard-mix-v3")
            self.assertEqual(manifest["configuration"]["version"], "community-hard-mix-v3")
            self.assertEqual(manifest["training_by_source"], {"new-source": 1, "same-source": 2})
            self.assertEqual(manifest["full_pass_four_gpu_steps"], 1)
            self.assertEqual(manifest["full_pass_four_gpu_rows_consumed"], 4)
            self.assertEqual(manifest["full_pass_four_gpu_wrapped_rows"], 1)
            self.assertEqual(manifest["configuration"]["filtered"]["replay_train_cap"], 4)
            for split in SPLITS:
                rows = list(read_jsonl(root / "mixed" / (split + ".jsonl")))
                self.assertTrue(all(row["split"] == split for row in rows))
                self.assertEqual(len(rows), 3)

    def test_mixture_rejects_stale_or_missing_source_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_dataset(root / "source", "new-source", 1)
            path = root / "source/manifest.json"
            original = json.loads(path.read_text())
            for changed in ({}, {**original, "files_sha256": {}}):
                path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, "checksums disagree"):
                    build([root / "source"], [], root / "output")
                self.assertFalse((root / "output").exists())
            path.write_text(json.dumps(original))
            with (root / "source/train.jsonl").open("a") as handle:
                handle.write("\n")
            with self.assertRaisesRegex(ValueError, "checksums disagree"):
                build([root / "source"], [], root / "output")

    def test_mixture_allows_empty_output_but_never_overwrites_existing_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_dataset(root / "source", "new-source", 1)
            (root / "output").mkdir()
            build([root / "source"], [], root / "output")
            manifest = (root / "output/manifest.json").read_bytes()
            with self.assertRaisesRegex(ValueError, "new or empty"):
                build([root / "source"], [], root / "output")
            self.assertEqual((root / "output/manifest.json").read_bytes(), manifest)

    def test_quarantine_removes_whole_training_group(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = source_dataset(root / "source", "new-source", 3)
            training = [row for row in rows if row["split"] == "train"]
            training[1]["group_id"] = training[0]["group_id"]
            _write_dataset(rows, root / "source", {})
            manifest = build([root / "source"], [], root / "output", excluded_groups=[training[0]["group_id"]])
            self.assertEqual(manifest["counts"]["train"], 1)
            self.assertEqual(manifest["configuration"]["filtered"]["quarantined_group"], 2)
            self.assertEqual(list(read_jsonl(root / "output/train.jsonl"))[0]["id"], training[2]["id"])

    def test_benchmark_labels_are_excluded_and_candidate_order_ignored(self):
        # A direct record test establishes that target/metadata have no effect.
        row = {"state": "A B C D E F G H I J K L M N O.", "question": "Choose.",
               "kind": "choice", "options": ["Alpha", "Beta"], "target": [0, 1]}
        other = {**row, "options": ["Beta", "Alpha"], "target": [1, 0], "metadata": {"gold": "ignore"}}
        self.assertEqual(fingerprint(row), fingerprint(other))
        self.assertTrue(shingles(row["state"]) & shingles("PREFIX a b c d e f g h i j k l m n o suffix"))
        self.assertFalse(shingles("unrelated short text"))

    def test_request_index_reads_only_visible_fields(self):
        visible = "These thirteen ordinary visible words belong only to the independent evaluation state text."
        hidden = "This private answer must never become a training overlap seed or be inspected here."
        request = {"state": visible, "questions": {"q": {"type": "noul", "instructions": "Is this established?"}}}
        exact, grams, short, count = build_index([{"workloads": [{"request": request, "gold": hidden}]}])
        self.assertEqual(count, 1)
        self.assertEqual(len(exact), 1)
        self.assertTrue(grams & shingles(visible))
        self.assertFalse(grams & shingles(hidden))

    def test_empty_benchmark_cannot_pass_screen(self):
        for documents in ([], [{"workloads": []}]):
            with self.assertRaisesRegex(ValueError, "At least one frozen benchmark"):
                build_index(documents)

    def test_screen_never_exports_benchmark_text_or_uses_gold(self):
        visible = "These thirteen ordinary visible words belong only to the independent evaluation state text."
        hidden = "This private answer must never become a training overlap seed or be inspected here."
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = source_dataset(root / "source", "tiny", 2)
            training = [row for row in rows if row["split"] == "train"]
            training[0]["state"] = visible
            training[1]["state"] = hidden
            _write_dataset(rows, root / "source", {})
            request = {"state": visible, "questions": {"q": {"type": "noul", "instructions": "Is this established?"}}}
            path = root / "requests.json"
            path.write_text(json.dumps({"workloads": [{"request": request, "gold": hidden}]}))
            report = screen([path], [root / "source"])
            self.assertEqual(report["matched_rows"], 1)
            self.assertEqual(report["excluded_groups"], [training[0]["group_id"]])
            self.assertNotIn(visible, json.dumps(report))
            self.assertNotIn(hidden, json.dumps(report))


if __name__ == "__main__":
    unittest.main()
