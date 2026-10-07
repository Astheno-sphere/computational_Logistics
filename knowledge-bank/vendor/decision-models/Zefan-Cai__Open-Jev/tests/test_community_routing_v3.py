from collections import Counter, defaultdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jev.community_routing_v3 import (ABSTAIN, OOS, build, convert_rows,
                                      load_sources, normalize, option_text, prepare_utterances)
from jev.data import validate_records


def example(identifier, text, label="card_payment_0"):
    return {"id": str(identifier), "text": text, "label": label}


def source_rows(count=180):
    return [example(i, f"Customer request number {i}.", f"card_payment_{i % 12}") for i in range(count)]


class RoutingV3Tests(unittest.TestCase):
    def test_global_official_holdouts_are_reserved_before_duplicate_and_conflict_filtering(self):
        bank = source_rows(24)
        clinc = [example(i, "Assistant " + row["text"], row["label"]) for i, row in enumerate(source_rows(24))]
        bank += [example(40, " SHARED request?! ", "card_payment_1"),
                 example(41, "Validation only", "card_payment_2"),
                 example(42, "Conflicting request", "card_payment_3")]
        clinc += [example(40, "Conflicting request", "card_payment_3")]
        sources = {"banking77": {"train": bank, "test": [example(1, "shared request", "card_payment_2"),
                                                           example(2, "conflicting request", "card_payment_4")]},
                   "clinc150": {"train": clinc, "val": [example(1, "validation only", "card_payment_2")],
                                "test": [example(2, "shared request", "card_payment_5")]}}
        kept, _, audit = prepare_utterances(sources, 20260921)
        for row in kept:
            if normalize(row["text"]) in {"shared request", "validation only", "conflicting request"}:
                self.assertNotEqual(row["original_split"], "train")
        self.assertGreaterEqual(audit["removed"]["official_heldout_group_reserved_from_train"], 4)
        self.assertGreater(audit["removed"]["conflicting_labels_within_catalog"], 0)
        self.assertGreaterEqual(len(audit["cross_source_components"]), 2)
        # Conflicting test labels do not make their corresponding train text eligible again.
        self.assertFalse(any(row["normalized"] == "conflicting request" for row in kept))

    def test_catalog_specific_shared_labels_keep_one_global_split_and_explicit_catalog(self):
        bank, clinc = source_rows(60), [example(i, "Other " + row["text"], row["label"]) for i, row in enumerate(source_rows(60))]
        bank.append(example(99, "Same shared utterance", "card_payment_0"))
        clinc.append(example(99, "same shared utterance!", "card_payment_1"))
        rows, audit, _ = convert_rows({"banking77": {"train": bank}, "clinc150": {"train": clinc}})
        shared = [row for row in rows if normalize(row["state"]["utterance"]) == "same shared utterance"]
        self.assertEqual(len(shared), 6)
        self.assertEqual(len({row["group_id"] for row in shared}), 1)
        self.assertEqual(len({row["split"] for row in shared}), 1)
        self.assertEqual(len({row["state"]["catalog"] for row in shared}), 2)
        self.assertEqual(len(audit["cross_source_components"]), 1)
        validate_records(rows)

    def test_gold_present_omitted_and_noul_contracts_are_exact_and_bounded(self):
        sources = {"clinc150": {"train": source_rows(180),
                                "oos_train": [example(i, f"Outside request {i}", OOS) for i in range(12)]}}
        rows, audit, protocols = convert_rows(sources)
        validate_records(rows)
        groups = defaultdict(list)
        for row in rows:
            groups[row["group_id"]].append(row)
            meta = row["metadata"]
            gold = meta["provenance"]["original_label"]
            self.assertNotIn("original_label", row["state"])
            self.assertNotIn("expected", row["state"])
            self.assertEqual(sum(row["target"]), 1)
            if row["kind"] == "choice":
                self.assertIn(len(row["options"]), (2, 4, 8))
                labels = meta["option_label_ids"]
                self.assertEqual(len(labels), len(set(labels)))
                self.assertIn(ABSTAIN, labels)
                correct = labels[row["target"].index(1.0)]
                if meta["view"] == "choice_present":
                    self.assertEqual(correct, gold)
                else:
                    self.assertNotIn(gold, labels)
                    self.assertEqual(correct, ABSTAIN)
            else:
                candidate, = meta["option_label_ids"]
                self.assertEqual(bool(row["target"][1]), candidate == gold)
                self.assertEqual(row["state"]["proposed_handler"], option_text(candidate))
        for values in groups.values():
            self.assertEqual(len({row["split"] for row in values}), 1)
            self.assertEqual(sum(row["kind"] == "noul" for row in values), 1)
            self.assertEqual(len(values), 2 if values[0]["metadata"]["provenance"]["original_label"] == OOS else 3)
        self.assertEqual(audit["retained_catalog_utterances"], 192)
        self.assertTrue(protocols["clinc150"]["evaluation_only"])

    def test_choice_target_and_abstain_positions_and_noul_labels_are_balanced(self):
        rows, audit, _ = convert_rows({"banking77": {"train": source_rows(480)}})
        targets, abstains = defaultdict(Counter), defaultdict(Counter)
        for row in rows:
            if row["kind"] != "choice":
                continue
            key = (row["split"], row["metadata"]["view"], len(row["options"]))
            targets[key][row["target"].index(1.0)] += 1
            abstains[key][row["metadata"]["option_label_ids"].index(ABSTAIN)] += 1
        for table in (targets, abstains):
            for key, counts in table.items():
                values = [counts[i] for i in range(key[-1])]
                self.assertLessEqual(max(values)-min(values), 1)
        for counts in audit["noul_positive_negative"].values():
            self.assertLessEqual(abs(counts.get("yes", 0)-counts.get("no", 0)), 1)

    def test_order_independence_and_duplicate_conflicts(self):
        train = source_rows(120)
        train += [example(500, "Duplicated utterance", "card_payment_0"),
                  example(501, "duplicated utterance!", "card_payment_0"),
                  example(502, "Conflicted utterance", "card_payment_0"),
                  example(503, "conflicted utterance", "card_payment_1")]
        a = convert_rows({"banking77": {"train": train}})
        b = convert_rows({"banking77": {"train": list(reversed(train))}})
        self.assertEqual(a, b)
        self.assertEqual(a[1]["removed"]["duplicate_utterance_within_catalog"], 1)
        self.assertEqual(a[1]["removed"]["conflicting_labels_within_catalog"], 2)

    def test_full_catalog_protocol_uses_only_official_test_and_is_not_training_rows(self):
        sources = {"banking77": {"train": source_rows(120), "test": [example(0, "Original heldout", "card_payment_0")]},
                   "clinc150": {"train": [example(i, "Clinc " + row["text"], row["label"]) for i, row in enumerate(source_rows(120))],
                                "test": [example(0, "Clinc official heldout", "card_payment_1")],
                                "oos_test": [example(0, "Other original heldout", OOS)]}}
        rows, _, protocols = convert_rows(sources)
        self.assertEqual(protocols["banking77"]["candidate_count"], 12)
        self.assertEqual(protocols["clinc150"]["candidate_count"], 13)
        self.assertEqual(protocols["banking77"]["eligible_original_ids"], ["test:0"])
        self.assertEqual(set(protocols["clinc150"]["eligible_original_ids"]), {"test:0", "oos_test:0"})
        self.assertFalse(any(len(row["options"]) > 8 for row in rows))
        self.assertTrue(all(row["split"] == "test" for row in rows if "heldout" in row["state"]["utterance"]))

    def test_pinned_source_mutation_and_existing_output_fail_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/"banking-train.csv").write_text("modified source")
            with self.assertRaisesRegex(ValueError, "checksum"):
                load_sources(root)
            output = root/"out"
            output.mkdir()
            marker = output/"manifest.json"
            marker.write_text("immutable")
            with patch("jev.community_routing_v3.load_sources") as load, self.assertRaisesRegex(ValueError, "new or empty"):
                build(root, output)
            load.assert_not_called()
            self.assertEqual(marker.read_text(), "immutable")
            with self.assertRaisesRegex(ValueError, "pinned source"):
                build(root, root)


if __name__ == "__main__":
    unittest.main()
