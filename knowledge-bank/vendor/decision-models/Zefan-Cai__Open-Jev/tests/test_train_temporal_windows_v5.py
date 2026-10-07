import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.train_temporal_windows_v5 import four_combinations, noul_status, paired_decisions
from scripts.temporal_pilot_lease import record_exit, register


def row(key, logits, target):
    return {"id": key, "kind": "noul", "family": "timeline", "target": target,
            "logits": logits, "wall_seconds": 0.0}


class TemporalPilotTest(unittest.TestCase):
    def test_lease_self_registration_and_controller_closing_preservation(self):
        pilot = {"pid": 123, "start_ticks": 456, "uid": 1000}
        controller = {"pid": 321, "start_ticks": 654, "uid": 1000}
        with tempfile.TemporaryDirectory() as tmp:
            lease = Path(tmp) / "gpu5-pilot-lease.json"
            original = {"status": "available", "controller_stamp": "frozen", "controller_identity": controller,
                        "gpu": 5, "gpu_uuid": "GPU-exact", "source_commit": "a" * 40,
                        "maximum_runtime_seconds": 300, "task_directory": tmp}
            lease.write_text(json.dumps(original))
            with patch("scripts.temporal_pilot_lease.os.getpid", return_value=123), \
                    patch("scripts.temporal_pilot_lease.os.getsid", return_value=123), \
                    patch("scripts.temporal_pilot_lease.process_identity", side_effect=lambda pid: pilot if pid == 123 else controller), \
                    patch.dict("os.environ", {"CUDA_VISIBLE_DEVICES": "GPU-exact"}):
                self.assertEqual(register(lease, "frozen", "GPU-exact", "a" * 40, Path(tmp) / "run"), pilot)
                running = json.loads(lease.read_text())
                self.assertEqual(running["status"], "running")
                self.assertEqual(running["controller_identity"], controller)
                running["status"] = "closing"
                lease.write_text(json.dumps(running))
                record_exit(lease, "frozen", pilot, "complete")
                closed = json.loads(lease.read_text())
                self.assertEqual(closed["status"], "closing")
                self.assertFalse(closed["session_cleanup_confirmed"])
                with self.assertRaisesRegex(ValueError, "closing"):
                    register(lease, "frozen", "GPU-exact", "a" * 40, Path(tmp) / "late")

    def test_temperature_ablation_keeps_argmax_but_changes_noul_threshold_behavior(self):
        before = [row("a", [0, 1], [0.0, 1.0]), row("b", [1, 0], [1.0, 0.0])]
        after = [row("a", [0, 2], [0.0, 1.0]), row("b", [2, 0], [1.0, 0.0])]
        combinations = four_combinations(before, after, 1.0, 0.5)
        self.assertEqual(len(combinations), 4)
        self.assertTrue(all(value["accuracy"] == 1.0 for value in combinations.values()))
        baseline = combinations["baseline_logits_at_released_temperature"]
        calibrated = combinations["baseline_logits_at_trained_temperature"]
        self.assertEqual(baseline["noul_thresholds_0.2_0.8"]["accepted"], 0)
        self.assertEqual(calibrated["noul_thresholds_0.2_0.8"]["accepted"], 2)
        self.assertLess(calibrated["nll"], baseline["nll"])
        self.assertEqual(noul_status(before[0], 1.0), "abstained")

    def test_paired_regression_counts_and_mismatched_evidence_rejection(self):
        before = [row("a", [1, 0], [0.0, 1.0]), row("b", [2, 0], [1.0, 0.0])]
        after = [row("a", [0, 2], [0.0, 1.0]), row("b", [0, 1], [1.0, 0.0])]
        result = paired_decisions(before, after, 1.0, 1.0)
        self.assertEqual(result["incorrect_to_correct"], 1)
        self.assertEqual(result["correct_to_incorrect"], 1)
        self.assertEqual(result["argmax_changed"], 2)
        with self.assertRaisesRegex(ValueError, "IDs differ"):
            paired_decisions(before, list(reversed(after)), 1.0, 1.0)
        after[0]["target"] = [1.0, 0.0]
        with self.assertRaisesRegex(ValueError, "targets or types differ"):
            paired_decisions(before, after, 1.0, 1.0)


if __name__ == "__main__":
    unittest.main()
