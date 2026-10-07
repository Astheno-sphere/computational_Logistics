import copy
from pathlib import Path
import tempfile
import unittest

from jev.api import candidate_prompts
from jev.temporal_windows_v5 import POLICY, build, outcome, records
from scripts.audit_temporal_windows_v5 import audit_directory, audit_rows, epoch_seconds, expected_outcome
from scripts.train_frontier_controls_v4 import load_selection


class TemporalWindowsV5Test(unittest.TestCase):
    def test_epoch_seconds_equivalent_instants_and_strict_timestamp_grammar(self):
        instants = ("2028-02-29T00:00:00+00:00", "2028-02-29T05:30:00+05:30", "2028-02-28T20:00:00-04:00")
        self.assertEqual({epoch_seconds(value) for value in instants}, {1835395200})
        for invalid in ("2028-02-29T00:00:00", "2028-02-29T00:00:00+24:00",
                        "2028-02-30T00:00:00+00:00", "2028-02-29T00:00:60+00:00"):
            with self.assertRaises(ValueError):
                epoch_seconds(invalid)

    def test_hand_calculated_lower_upper_leap_boundaries_and_exception(self):
        state = {"delivered_at": "2028-02-29T05:29:59+05:30", "return_window_hours": 1,
                 "exception_approved": False, "policy": POLICY}
        # Delivery is Feb 28 23:59:59 UTC; the inclusive deadline is Feb 29 00:59:59 UTC.
        cases = (("2028-02-28T19:59:58-04:00", "reject"),
                 ("2028-02-28T19:59:59-04:00", "accept"),
                 ("2028-02-28T20:00:00-04:00", "accept"),
                 ("2028-02-28T20:59:59-04:00", "accept"),
                 ("2028-02-28T21:00:00-04:00", "reject"))
        for timestamp, expected in cases:
            current = {**state, "request_received_at": timestamp}
            self.assertEqual(outcome(current), expected)
            self.assertEqual(expected_outcome(current), expected)
            self.assertEqual(expected_outcome({**current, "exception_approved": True}), "review")
            self.assertEqual(outcome({**current, "exception_approved": True}), "review")

    def test_complete_frozen_groups_disjoint_splits_and_boundary_offset_coverage(self):
        rows = list(records())
        self.assertEqual(rows, list(records()))
        result = audit_rows(rows)
        self.assertEqual(result["oracle_checked"], 256)
        self.assertEqual(result["complete_four_row_groups"], 64)
        self.assertEqual(result["schema"]["splits"], {"train": 128, "calibration": 32, "validation": 32, "test": 32, "ood": 32})
        sets = [{row["group_id"] for row in rows if row["split"] == split} for split in result["schema"]["splits"]]
        self.assertTrue(all(not a & b for i, a in enumerate(sets) for b in sets[i + 1:]))
        for coverage in result["coverage"].values():
            self.assertTrue(all(coverage[key] > 0 for key in ("before_delivery", "at_delivery", "at_deadline", "after_deadline", "different_display_offsets", "cross_utc_month", "cross_utc_year")))
        self.assertGreater(result["coverage"]["ood"]["touches_utc_leap_day"], 0)
        self.assertTrue(set(result["display_offsets"]["ood"]).isdisjoint(result["display_offsets"]["train"]))

    def test_independent_validator_rejects_corrupted_gold_proposal_and_incomplete_group(self):
        rows = list(records(8, 8))
        altered = copy.deepcopy(rows)
        row = altered[0]
        row["target"] = list(reversed(row["target"]))
        with self.assertRaisesRegex(ValueError, "Independent epoch oracle disagrees"):
            audit_rows(altered)
        altered = copy.deepcopy(rows)
        row = next(row for row in altered if row["kind"] == "noul")
        row["metadata"]["proposed_outcome"] = "review" if row["metadata"]["proposed_outcome"] != "review" else "accept"
        with self.assertRaisesRegex(ValueError, "Visible Noul proposal"):
            audit_rows(altered)
        with self.assertRaisesRegex(ValueError, "four complete variants"):
            audit_rows(rows[1:])

    def test_generator_labels_are_checked_by_separate_epoch_implementation(self):
        # Corrupt the generator's labels, retaining valid schema/probability vectors.
        rows = list(records(8, 8))
        for row in rows:
            old = row["target"].index(1.0)
            row["target"] = [float(i == (old + 1) % len(row["options"])) for i in range(len(row["options"]))]
        with self.assertRaisesRegex(ValueError, "Independent epoch oracle disagrees"):
            audit_rows(rows)

    def test_relabeling_case_ids_cannot_disguise_repeated_temporal_facts(self):
        rows = list(records(8, 8))
        train = [row for row in rows if row["group_id"] == "temporal-windows-v5/train/0"]
        cal = [row for row in rows if row["group_id"] == "temporal-windows-v5/calibration/0"]
        for source, destination in zip(train, cal):
            case_id = destination["state"]["case"]
            destination["state"] = {**source["state"], "case": case_id}
        with self.assertRaisesRegex(ValueError, "Case-ID-independent temporal facts repeat"):
            audit_rows(rows)

    def test_freeze_hashes_refuses_overwrite_and_detects_changed_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "data"
            manifest = build(directory, 8, 8)
            self.assertEqual(audit_directory(directory)["files_sha256"], manifest["files_sha256"])
            selected, identity = load_selection(directory, 32, 32, 32, 20261002)
            self.assertTrue(all(len(rows) == 32 for rows in selected.values()))
            self.assertEqual(identity["split_sha256"], manifest["files_sha256"])
            with self.assertRaises(FileExistsError):
                build(directory, 8, 8)
            with (directory / "test.jsonl").open("a") as handle:
                handle.write("\n")
            with self.assertRaisesRegex(ValueError, "checksum changed"):
                audit_directory(directory)
        with self.assertRaises(ValueError):
            list(records(9, 8))

    def test_hidden_labels_ids_and_metadata_do_not_enter_model_prompts(self):
        for row in list(records(8, 8))[:4]:
            expected = candidate_prompts(row)
            altered = copy.deepcopy(row)
            altered.update(id="HIDDEN", group_id="HIDDEN", split="ood", metadata={"answer": "HIDDEN"},
                           target=list(reversed(row["target"])))
            self.assertEqual(candidate_prompts(altered), expected)


if __name__ == "__main__":
    unittest.main()
