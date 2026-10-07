import copy
import json
from pathlib import Path
import tempfile
import unittest

from jev.api import candidate_prompts, compile_request, format_response
from jev.case_drone import (CONTROL_RULES, derive_decision, drone_teacher,
                            build_dataset, generate_cases, records_from_cases)
from jev.community import drone_proposal, drone_request
from jev.data import read_jsonl, read_split_directory, validate_records


def fixture():
    observation = {
        "observation_id": "measured-1",
        "goal": {"task": "follow_target", "preferred_gap": "right"},
        "target": {"visible": True, "seconds_unseen": 0, "history": []},
        "flight": {"altitude_m": 1, "forward_speed_mps": 2, "diameter_m": 0.5,
                   "ceiling_m": 5, "vertical_clearance_m": 3, "climb_clearance_verified": False},
        "obstacles": [{"id": "wall", "ahead_m": 6, "lateral_offset_m": 0, "width_m": 2,
                       "top_altitude_m": 2.5, "forward_speed_mps": 0,
                       "left_gap_width_m": 1.5, "right_gap_width_m": 1.2}],
        "permitted_maneuvers": ["hold_course", "brake", "gap_right", "gap_left", "reacquire"],
        "control_policy": {"rules": CONTROL_RULES, "margin_m": 0.25, "reaction_s": 0.5,
                           "braking_deceleration_mps2": 2, "imminent_ttc_s": 1,
                           "caution_ttc_s": 4, "tight_clearance_range_m": 3,
                           "loss_grace_s": 3, "loss_evidence_window_s": 30, "failed_scan_count": 2},
    }
    return drone_request(observation, observation["permitted_maneuvers"])["state"]


def failed_scans(state):
    state["observation"]["target"] = {"visible": False, "seconds_unseen": 3,
        "history": [{"seconds_ago": 1, "region_fully_visible": True, "detected": False},
                    {"seconds_ago": 2, "region_fully_visible": True, "detected": False}]}


class DroneRuleTest(unittest.TestCase):
    def test_stopping_distance_ttc_and_clearance_boundaries(self):
        state = fixture()
        obstacle = state["observation"]["obstacles"][0]
        self.assertEqual(drone_teacher(state), {"maneuver": "gap_left", "risk": "1", "target_truly_lost": "false"})
        self.assertEqual(derive_decision(state)[1]["obstacles"][0]["stopping_distance_m"], 2.25)
        for distance, risk in ((2.25, "2"), (2.25001, "1"), (8, "1"), (8.00001, "0")):
            obstacle["ahead_m"] = distance
            self.assertEqual(drone_teacher(state)["risk"], risk)
        # Here TTC, rather than stopping distance, sets the imminent boundary.
        state["observation"]["control_policy"].update(reaction_s=0.1, braking_deceleration_mps2=20)
        for distance, risk in ((2, "2"), (2.00001, "1")):
            obstacle["ahead_m"] = distance
            self.assertEqual(drone_teacher(state)["risk"], risk)
        state["observation"]["flight"]["forward_speed_mps"] = 0
        obstacle.update(left_gap_width_m=0.9, right_gap_width_m=1, ahead_m=3)
        self.assertEqual(drone_teacher(state)["risk"], "1")
        obstacle["ahead_m"] = 3.00001
        self.assertEqual(drone_teacher(state)["risk"], "0")

    def test_relative_motion_and_off_course_obstacles(self):
        state = fixture()
        obstacle = state["observation"]["obstacles"][0]
        obstacle["forward_speed_mps"] = 3
        self.assertEqual(drone_teacher(state)["risk"], "0")
        self.assertIsNone(derive_decision(state)[1]["obstacles"][0]["time_to_collision_s"])
        obstacle["forward_speed_mps"] = -2
        self.assertEqual(drone_teacher(state)["risk"], "2")
        obstacle["lateral_offset_m"] = 1.50001
        self.assertEqual(drone_teacher(state)["risk"], "0")
        obstacle["lateral_offset_m"] = 1.5
        self.assertEqual(drone_teacher(state)["risk"], "2")
        obstacle.update(lateral_offset_m=0, top_altitude_m=0.49999)
        self.assertEqual(drone_teacher(state)["risk"], "0")
        obstacle["top_altitude_m"] = 0.5
        self.assertEqual(drone_teacher(state)["risk"], "2")

    def test_gap_width_tie_goal_and_all_barriers(self):
        state = fixture()
        obstacle = state["observation"]["obstacles"][0]
        obstacle.update(left_gap_width_m=1, right_gap_width_m=1)
        self.assertEqual(drone_teacher(state)["maneuver"], "gap_right")
        state["observation"]["goal"]["preferred_gap"] = "left"
        self.assertEqual(drone_teacher(state)["maneuver"], "gap_left")
        obstacle["left_gap_width_m"] = 0.99999
        self.assertEqual(drone_teacher(state)["maneuver"], "gap_right")
        second = copy.deepcopy(obstacle)
        second.update(id="second", left_gap_width_m=2, right_gap_width_m=0.9)
        state["observation"]["obstacles"].append(second)
        self.assertEqual(drone_teacher(state)["maneuver"], "brake")
        # A narrow off-course obstacle cannot invalidate an observed side gap.
        second["lateral_offset_m"] = 20
        self.assertEqual(drone_teacher(state)["maneuver"], "gap_right")

    def test_climb_requires_permission_verified_clearance_and_geometry(self):
        state = fixture()
        observation = state["observation"]
        observation["obstacles"][0].update(left_gap_width_m=0.9, right_gap_width_m=0.9)
        self.assertEqual(drone_teacher(state)["maneuver"], "brake")
        observation["permitted_maneuvers"].append("climb")
        with self.assertRaisesRegex(ValueError, "verified clearance"):
            drone_teacher(state)
        observation["flight"].update(climb_clearance_verified=True, ceiling_m=3.5, vertical_clearance_m=2)
        self.assertEqual(drone_teacher(state)["maneuver"], "climb")
        observation["flight"]["ceiling_m"] = 3.49999
        self.assertEqual(drone_teacher(state)["maneuver"], "brake")
        observation["flight"].update(ceiling_m=3.5, vertical_clearance_m=1.99999)
        self.assertEqual(drone_teacher(state)["maneuver"], "brake")
        observation["flight"]["vertical_clearance_m"] = 2
        observation["obstacles"][0]["ahead_m"] = 1
        self.assertEqual(drone_teacher(state)["maneuver"], "brake")

    def test_target_loss_needs_independent_unoccluded_evidence(self):
        state = fixture()
        failed_scans(state)
        self.assertEqual(drone_teacher(state)["target_truly_lost"], "true")
        mutations = [lambda t: t.update(visible=True), lambda t: t.update(seconds_unseen=2.99999),
                     lambda t: t["history"][1].update(seconds_ago=1),
                     lambda t: t["history"][1].update(region_fully_visible=False),
                     lambda t: t["history"][1].update(detected=True),
                     lambda t: t["history"][1].update(seconds_ago=3.00001),
                     lambda t: t.update(seconds_unseen=100, history=[])]
        for mutate in mutations:
            changed = copy.deepcopy(state)
            mutate(changed["observation"]["target"])
            self.assertEqual(drone_teacher(changed)["target_truly_lost"], "false")
        changed = copy.deepcopy(state)
        changed["observation"]["target"].update(seconds_unseen=100)
        for scan in changed["observation"]["target"]["history"]:
            scan["seconds_ago"] += 31
        self.assertEqual(drone_teacher(changed)["target_truly_lost"], "false")

    def test_goal_changes_reacquisition_but_not_evidence_or_risk(self):
        state = fixture()
        failed_scans(state)
        state["observation"]["obstacles"] = []
        self.assertEqual(drone_teacher(state), {"maneuver": "reacquire", "risk": "0", "target_truly_lost": "true"})
        state["observation"]["goal"]["task"] = "continue_route"
        self.assertEqual(drone_teacher(state), {"maneuver": "hold_course", "risk": "0", "target_truly_lost": "true"})
        state["observation"]["permitted_maneuvers"].remove("hold_course")
        self.assertEqual(drone_teacher(state)["maneuver"], "brake")

    def test_missing_disclosure_or_invalid_measurements_do_not_get_labels(self):
        for mutate in (lambda o: o["control_policy"].update(rules="Hidden rubric"),
                       lambda o: o["flight"].update(diameter_m=0),
                       lambda o: o["obstacles"][0].update(ahead_m=float("nan")),
                       lambda o: o["control_policy"].update(failed_scan_count=True),
                       lambda o: o["permitted_maneuvers"].remove("brake")):
            state = fixture()
            mutate(state["observation"])
            with self.assertRaises(ValueError):
                drone_teacher(state)


class DroneDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = generate_cases(groups=30, ood_groups=6)
        cls.rows, cls.counts = records_from_cases(cls.cases)

    def test_exact_runtime_prompts_targets_and_typed_proposals(self):
        rows = {row["id"]: row for row in self.rows}
        for case in self.cases:
            request = case["request"]
            observation = request["state"]["observation"]
            expected = drone_request(observation, observation["permitted_maneuvers"])
            self.assertEqual(compile_request(**request), compile_request(**expected))
            compiled = compile_request(**request)
            probabilities = []
            for record in compiled:
                target = [float(key == case["answers"][record["id"]]) for key in record["answer_keys"]]
                probabilities.append(target)
                row_id = case["id"] + ":" + record["id"]
                if len(record["options"]) == 1:
                    self.assertNotIn(row_id, rows)
                else:
                    row = rows[row_id]
                    self.assertEqual(candidate_prompts(row), candidate_prompts(record))
                    self.assertEqual(row["target"], target)
                    if row["kind"] == "score":
                        self.assertEqual(row["metadata"]["score_values"], [0, 1, 2])
            actual = drone_proposal(request, format_response(compiled, probabilities))
            self.assertEqual(actual, {"maneuver": case["answers"]["maneuver"], "risk": int(case["answers"]["risk"]),
                                      "target_lost_probability": int(case["answers"]["target_truly_lost"] == "true")})

    def test_all_actions_kinds_and_parent_ood_splits_are_present(self):
        report = validate_records(self.rows)
        self.assertEqual(report["groups"], 30)
        self.assertEqual(set(report["kinds"]), {"choice", "score", "noul"})
        self.assertEqual({case["answers"]["maneuver"] for case in self.cases},
                         {"hold_course", "gap_left", "gap_right", "brake", "climb", "reacquire"})
        groups, templates = {}, {"ood": set(), "id": set()}
        for case in self.cases:
            groups.setdefault(case["group_id"], set()).add(case["split"])
            templates["ood" if case["split"] == "ood" else "id"].add(case["template_id"])
            observation = case["request"]["state"]["observation"]
            self.assertEqual(len(observation["obstacles"]), 4 if case["split"] == "ood" else 2)
            self.assertGreater(observation["flight"]["forward_speed_mps"], 3 if case["split"] == "ood" else 0)
            if case["split"] != "ood":
                self.assertLess(observation["flight"]["forward_speed_mps"], 3)
        self.assertTrue(all(len(splits) == 1 for splits in groups.values()))
        self.assertEqual(sum(splits == {"ood"} for splits in groups.values()), 6)
        self.assertFalse(templates["ood"] & templates["id"])
        self.assertEqual(self.cases, generate_cases(groups=30, ood_groups=6))

    def test_same_sensor_facts_different_side_goals(self):
        parents = {}
        for case in self.cases:
            if case["variant"].startswith("side_goal_"):
                parents.setdefault(case["group_id"], []).append(case)
        self.assertEqual(len(parents), 30)
        for cases in parents.values():
            self.assertEqual(len(cases), 2)
            observations = [copy.deepcopy(case["request"]["state"]["observation"]) for case in cases]
            for observation in observations:
                observation.pop("goal")
            self.assertEqual(*observations)
            self.assertEqual({case["answers"]["maneuver"] for case in cases}, {"gap_left", "gap_right"})

    def test_single_candidate_omission_and_no_inactive_heads(self):
        self.assertEqual(self.counts["forced_single_candidate_maneuvers_omitted"], 30)
        self.assertEqual(len(self.rows) + 30, len(self.cases) * 3)
        for case in self.cases:
            if case["variant"] == "single_permitted_maneuver":
                rows, counts = records_from_cases([case])
                self.assertEqual({row["kind"] for row in rows}, {"noul", "score"})
                self.assertEqual(counts["forced_single_candidate_maneuvers_omitted"], 1)

    def test_ids_order_and_metadata_do_not_decide_references(self):
        for case in self.cases[::13]:
            state = copy.deepcopy(case["request"]["state"])
            expected = drone_teacher(state)
            state["metadata"] = {"hidden_truth": "contradicts all answers"}
            observation = state["observation"]
            observation["observation_id"] = "different"
            observation["obstacles"].reverse()
            observation["permitted_maneuvers"].reverse()
            observation["target"]["history"].reverse()
            for i, obstacle in enumerate(observation["obstacles"]):
                obstacle["id"] = str(i)
            self.assertEqual(drone_teacher(state), expected)
        for row in self.rows[::13]:
            changed = copy.deepcopy(row)
            changed.update(id="HIDDEN", group_id="HIDDEN", target=row["target"][::-1], metadata={"answer": "HIDDEN"})
            self.assertEqual(candidate_prompts(row), candidate_prompts(changed))

    def test_corrupt_questions_answers_or_derivation_are_rejected(self):
        for field in ("question", "answer", "trace", "order"):
            case = copy.deepcopy(self.cases[0])
            if field == "question":
                case["request"]["questions"]["risk"]["instructions"] = "Different question"
            elif field == "answer":
                case["answers"]["risk"] = "2"
            elif field == "trace":
                case["derivation"]["required_gap_width_m"] = 999
            else:
                question = case["request"]["questions"]["maneuver"]
                question["criteria"] = dict(reversed(list(question["criteria"].items())))
            with self.assertRaises(ValueError):
                records_from_cases([case])

    def test_disk_roundtrip_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "drone"
            manifest = build_dataset(output, groups=12, ood_groups=3)
            cases = list(read_jsonl(output / "cases.jsonl"))
            rebuilt, counts = records_from_cases(cases)
            persisted = {row["id"]: row for row in read_split_directory(output)}
            self.assertEqual(manifest["summary"], validate_records(persisted.values()))
            self.assertEqual(counts, manifest["supervision"])
            for row in rebuilt:
                self.assertEqual(candidate_prompts(row), candidate_prompts(persisted[row["id"]]))
            self.assertEqual(json.loads((output / "manifest.json").read_text()), manifest)
            with self.assertRaisesRegex(ValueError, "not empty"):
                build_dataset(output, groups=12, ood_groups=3)


if __name__ == "__main__":
    unittest.main()
