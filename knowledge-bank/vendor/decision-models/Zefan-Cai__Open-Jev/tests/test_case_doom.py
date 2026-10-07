import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

from jev.case_doom import (SCORE_OPTIONS, action_buttons, build_dataset, collect_episode,
                           episode_spec, expert_decision, records_from_episode,
                           relative_bearing, replay_dataset, replay_episode)
from jev.data import read_jsonl, validate_records


def state(bearing=0.0, velocity=0.0, ammo=10):
    return {"health": 100, "ammo": ammo,
            "movement": {"lateral_units_per_tic": velocity},
            "nearest_visible_enemy": {"relative_bearing_deg": bearing, "distance_units": 400}}


class DoomDecisionTests(unittest.TestCase):
    def test_bearing_coordinate_convention_and_wrap(self):
        self.assertEqual(relative_bearing(0, 0, 0, 1, 1), 45)
        self.assertEqual(relative_bearing(0, 0, 90, 1, 0), -90)
        self.assertAlmostEqual(relative_bearing(0, 0, 350, 1, 0), 10)

    def test_movement_momentum_and_action_button_order(self):
        self.assertEqual(expert_decision(state(10))["movement"], 0)
        self.assertEqual(expert_decision(state(-10))["movement"], 1)
        self.assertEqual(action_buttons(expert_decision(state())), [False, False, True])
        # A target on the left can require braking right when lateral speed is high.
        self.assertEqual(expert_decision(state(3, velocity=5))["movement"], 1)

    def test_shot_grade_boundaries_and_attack(self):
        for angle, expected in [(0, 4), (3, 4), (3.0001, 3), (6, 3),
                                (6.0001, 2), (12, 2), (12.0001, 1), (22, 1), (22.0001, 0)]:
            for sign in (-1, 1):
                decision = expert_decision(state(sign * angle))
                self.assertEqual(decision["suitability"], expected)
                self.assertEqual(decision["attack"], angle <= 3)
        empty = state(ammo=0)
        self.assertEqual(expert_decision(empty), {"movement": 2, "attack": False, "suitability": 0})
        empty["ammo"] = 10
        empty["nearest_visible_enemy"] = None
        self.assertFalse(expert_decision(empty)["attack"])

    def test_episode_splits_and_ood_seed_ranges(self):
        specs = [episode_spec(i, 10) for i in range(500)]
        self.assertEqual({s["split"] for s in specs}, {"train", "calibration", "validation", "test"})
        ood = [episode_spec(i, 10, True) for i in range(100)]
        self.assertFalse({s["seed"] for s in specs} & {s["seed"] for s in ood})
        self.assertEqual({s["split"] for s in ood}, {"ood"})
        self.assertEqual({s["frame_skip"] for s in ood}, {8})

    def test_three_tasks_share_episode_group_and_keep_labels_out_of_input(self):
        current = state(10)
        teacher = expert_decision(current)
        episode = {**episode_spec(0, 10), "steps": [
            {"state": current, "teacher": teacher, "action": action_buttons(teacher)}]}
        rows = records_from_episode(episode, "a" * 64)
        summary = validate_records(rows)
        self.assertEqual(summary["records"], 3)
        self.assertEqual(summary["groups"], 1)
        self.assertEqual({row["kind"] for row in rows}, {"choice", "noul", "score"})
        self.assertEqual(rows[2]["options"], SCORE_OPTIONS)
        self.assertEqual(rows[2]["metadata"]["score_values"], list(range(5)))
        self.assertFalse(any(k in current for k in ("teacher", "reward", "split", "seed", "episode_id")))
        episode["steps"][0]["action"] = [False, False, False]
        with self.assertRaisesRegex(ValueError, "teacher/action"):
            records_from_episode(episode, "a" * 64)


@unittest.skipUnless(importlib.util.find_spec("vizdoom"), "optional vizdoom environment unavailable")
class DoomEngineTests(unittest.TestCase):
    def test_real_rollout_replay_and_tamper_detection(self):
        episode = collect_episode(episode_spec(0, 1911))
        self.assertGreater(len(episode["steps"]), 1)
        self.assertTrue(episode["finished"])
        self.assertTrue(replay_episode(episode)["matched"])
        corrupt = copy.deepcopy(episode)
        corrupt["steps"][0]["state"]["ammo"] += 1
        with self.assertRaisesRegex(ValueError, "observation mismatch"):
            replay_episode(corrupt)
        corrupt = copy.deepcopy(episode)
        corrupt["steps"][0]["reward"] += 1
        with self.assertRaisesRegex(ValueError, "reward mismatch"):
            replay_episode(corrupt)

    def test_small_engine_dataset_validates_and_replays_id_and_ood(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = build_dataset(directory, episodes=3, ood_episodes=2, seed=102)
            records = [row for path in Path(directory).glob("*.jsonl") for row in read_jsonl(path)]
            self.assertEqual(validate_records(records), manifest["summary"])
            self.assertIn("ood", manifest["summary"]["splits"])
            self.assertEqual(manifest["rollout_summary"]["observed_states"],
                             manifest["rollout_summary"]["unique_retained_states"] +
                             manifest["rollout_summary"]["duplicate_states_removed"])
            report = replay_dataset(directory, limit=5)
            self.assertEqual(report["replayed_episodes"], 5)
            self.assertTrue(report["all_matched"])


if __name__ == "__main__":
    unittest.main()
