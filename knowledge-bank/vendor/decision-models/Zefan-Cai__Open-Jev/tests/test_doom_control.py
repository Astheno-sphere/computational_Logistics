import copy
import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from jev.api import candidate_prompts, compile_request, format_response
from jev.case_doom import (MOVEMENTS, action_buttons, episode_spec, expert_decision,
                           records_from_episode)
from jev.data import read_split_directory
from jev.doom_control import decode_answers, typed_request
from jev.game_cli import _game, main as game_main
from jev.games import (DoomBasic, HTTPPolicy, RandomPolicy, TeacherPolicy,
                       game_request, replay_episode, run_episode)
from scripts.evaluate_game_service import run_evaluation, service_identity


def state():
    return {"health": 100, "ammo": 12, "movement": {"lateral_units_per_tic": 0},
            "nearest_visible_enemy": {"relative_bearing_deg": 15, "distance_units": 400}}


def answers(request, movement=1, attack=0.5, alignment=0):
    return format_response(compile_request(**request), [
        [float(i == movement) for i in range(3)], [1 - attack, attack],
        [float(i == alignment) for i in range(5)]])["answers"]


class FakeEngine:
    """CPU test double for button dispatch/replay, never a model/engine score."""
    def __init__(self, spec):
        self.spec, self.actions = spec, []

    def is_episode_finished(self):
        return len(self.actions) >= 2

    def make_action(self, buttons, tics):
        self.actions.append((list(buttons), tics))
        return 1

    def get_total_reward(self):
        return len(self.actions)

    def get_episode_time(self):
        return len(self.actions) * self.spec["frame_skip"]

    def close(self):
        pass


def fake_observe(engine, frame_skip):
    if engine.is_episode_finished():
        return None
    return {**state(), "elapsed_tics": engine.get_episode_time(), "action_window_tics": frame_skip}


class DoomControlTest(unittest.TestCase):
    def test_training_and_runtime_candidate_prompts_are_identical(self):
        current = state()
        teacher = expert_decision(current)
        episode = {**episode_spec(0, 42), "steps": [{"state": current, "teacher": teacher,
                                                      "action": action_buttons(teacher)}]}
        trained = records_from_episode(episode, "a" * 64)
        runtime = compile_request(**typed_request(current))
        self.assertEqual([record["kind"] for record in runtime], ["choice", "noul", "score"])
        self.assertEqual([candidate_prompts(row) for row in trained], [candidate_prompts(row) for row in runtime])
        self.assertEqual(sum(len(candidate_prompts(row)) for row in runtime), 9)

    @unittest.skipUnless(Path("data/doom-basic-v1").is_dir(), "frozen local Doom corpus is unavailable")
    def test_all_frozen_training_rows_match_runtime_prompts(self):
        count = 0
        for row in read_split_directory("data/doom-basic-v1"):
            runtime = {record["kind"]: record for record in compile_request(**typed_request(row["state"]))}
            self.assertEqual(candidate_prompts(row), candidate_prompts(runtime[row["kind"]]))
            count += 1
        self.assertGreater(count, 0)

    def test_attack_threshold_and_alignment_never_override_model_action(self):
        request = typed_request(state())
        with patch("jev.case_doom.expert_decision", side_effect=AssertionError("oracle called")):
            for probability, attack in ((0, False), (0.499999, False), (0.5, True), (1, True)):
                for grade in range(5):
                    decision = decode_answers(request, answers(request, attack=probability, alignment=grade))
                    self.assertEqual(decision["buttons"], [False, True, attack])
                    self.assertEqual(decision["action"], "right_attack" if attack else "right_wait")
                    self.assertEqual(decision["alignment_score"], grade)

    def test_malformed_heads_probabilities_confidence_and_legend_fail(self):
        request = typed_request(state())
        original = answers(request)
        mutations = [lambda a: a.pop("alignment"), lambda a: a.update(extra={}),
                     lambda a: a["attack"].update(noul=True), lambda a: a["attack"].update(noul="0.5"),
                     lambda a: a["attack"].update(noul=1.1), lambda a: a["attack"].update(noul=float("nan")),
                     lambda a: a["movement"].update(choice=MOVEMENTS[0]),
                     lambda a: a["movement"].update(type="score"),
                     lambda a: a["movement"]["probabilities"].update({MOVEMENTS[1]: "1"}),
                     lambda a: a["movement"]["probabilities"].update({MOVEMENTS[1]: True}),
                     lambda a: a["alignment"]["probabilities"].update({"0": True}),
                     lambda a: a["alignment"]["probabilities"].update({"0": "1"}),
                     lambda a: a["alignment"]["probabilities"].update({"0": -1}),
                     lambda a: a["alignment"]["probabilities"].update({"0": float("inf")}),
                     lambda a: a["movement"].update(confidence=False),
                     lambda a: a["movement"].update(confidence=0),
                     lambda a: a["movement"].update(confidence=1 + 5e-7),
                     lambda a: a["alignment"].update(confidence="1"),
                     lambda a: a["alignment"].update(confidence=0),
                     lambda a: a["alignment"].update(confidence=1 + 5e-7),
                     lambda a: a["alignment"].pop("legend"),
                     lambda a: a["alignment"]["legend"].update({"0": "Different rubric"}),
                     lambda a: a["alignment"].update(score=1)]
        for mutate in mutations:
            corrupted = copy.deepcopy(original)
            mutate(corrupted)
            with self.assertRaises(ValueError):
                decode_answers(request, corrupted)
        for grade, invalid in ((0, -1e-7), (4, 4 + 1e-7)):
            corrupted = answers(request, alignment=grade)
            corrupted["alignment"]["score"] = invalid
            with self.assertRaises(ValueError):
                decode_answers(request, corrupted)
        uniform = format_response(compile_request(**request), [[1/3] * 3, [0.5, 0.5], [0.2] * 5])["answers"]
        for key in ("movement", "alignment"):
            corrupted = copy.deepcopy(uniform)
            corrupted[key]["confidence"] = -1e-7
            with self.assertRaises(ValueError):
                decode_answers(request, corrupted)

    def test_service_identity_counts_noul_as_one_sequence(self):
        request = typed_request(state())
        response = {"model": "test-model", "metadata": {"method": "lora_decision_head",
                    "temperature": 1, "candidate_sequences": 9}, "answers": answers(request)}
        self.assertEqual(service_identity(response, request)["model"], "test-model")
        response["metadata"]["candidate_sequences"] = 10
        with self.assertRaisesRegex(ValueError, "candidate count"):
            service_identity(response, request)

    @patch("jev.case_doom.observe", side_effect=fake_observe)
    @patch("jev.case_doom._open_game", side_effect=FakeEngine)
    def test_legacy_mode_is_default_and_typed_cli_replay_is_explicit(self, *_):
        legacy = DoomBasic()
        legacy.reset(42)
        self.assertEqual(legacy.config, {"name": "doom_basic", "protocol": "vizdoom-basic-v1"})
        self.assertEqual(set(game_request(legacy)["questions"]), {"action"})
        legacy.close()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "typed.json"
            game_main(["play", "doom_basic", "--doom-decision-mode", "typed-v1", "--policy", "random",
                       "--max-steps", "2", "--output", str(output)])
            trace = json.loads(output.read_text())["episodes"][0]
            self.assertEqual(trace["game"]["decision_mode"], "typed-v1")
            self.assertTrue(replay_episode(_game(trace["game"]), trace)["matched"])
            self.assertEqual(set(trace["steps"][0]["answer"]), {"movement", "attack", "alignment"})
            self.assertEqual(trace["steps"][0]["executed_buttons"], trace["steps"][0]["control_decision"]["buttons"])
            trace["steps"][0]["executed_buttons"][0] = not trace["steps"][0]["executed_buttons"][0]
            with self.assertRaisesRegex(ValueError, "judgment/button"):
                replay_episode(_game(trace["game"]), trace)

    @patch("jev.case_doom.observe", side_effect=fake_observe)
    @patch("jev.case_doom._open_game", side_effect=FakeEngine)
    def test_http_typed_loop_keeps_raw_heads_and_never_calls_teacher(self, *_):
        game = DoomBasic("typed-v1")
        policy = HTTPPolicy()

        def response(request):
            policy.backend = {"model": "test-model"}
            return {"answers": answers(request, movement=1, attack=0.8, alignment=0)}

        with patch.object(policy, "infer", side_effect=response), patch("jev.case_doom.expert_decision", side_effect=AssertionError("oracle called")):
            trace = run_episode(game, policy, max_steps=1)
        step = trace["steps"][0]
        self.assertEqual(step["answer"]["attack"]["noul"], 0.8)
        self.assertEqual(step["answer"]["alignment"]["score"], 0)
        self.assertEqual(step["executed_buttons"], [False, True, True])
        self.assertEqual(step["action"], "right_attack")

    @patch("jev.case_doom.observe", side_effect=fake_observe)
    @patch("jev.case_doom._open_game", side_effect=FakeEngine)
    def test_audited_http_suite_records_typed_errors_without_fallback(self, *_):
        corrupt = [False]

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                result = {"model": "test-model", "metadata": {"method": "lora_decision_head", "temperature": 1,
                          "candidate_sequences": 9}, "answers": answers(request)}
                if corrupt[0]:
                    result["answers"]["alignment"]["confidence"] = 0
                payload = json.dumps(result).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for invalid in (False, True):
                    corrupt[0] = invalid
                    output = root / str(invalid)
                    report = run_evaluation(output, endpoint=f"http://127.0.0.1:{server.server_port}",
                                            games=("doom_basic",), doom_decision_mode="typed-v1", seeds=(42,), max_steps=2)
                    self.assertEqual(report["error_episodes"], int(invalid))
                    self.assertEqual(report["configuration"]["doom_decision_mode"], "typed-v1")
                    trace = json.loads((output / "trajectories/doom_basic-model-seed-42.json").read_text())
                    self.assertTrue(trace["http_responses"])
                    self.assertIn("alignment", json.loads(trace["http_responses"][0]["response_json"])["answers"])
                    self.assertEqual(len(trace["steps"]), 0 if invalid else 2)
                    if invalid:
                        self.assertIn("pending_decision", trace)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    @unittest.skipUnless(importlib.util.find_spec("vizdoom"), "optional local ViZDoom is unavailable")
    def test_real_typed_engine_rollout_and_replay(self):
        game = DoomBasic("typed-v1")
        trace = run_episode(game, TeacherPolicy(game), seed=42, max_steps=30)
        self.assertGreater(len(trace["steps"]), 0)
        self.assertTrue(replay_episode(DoomBasic("typed-v1"), trace)["matched"])


if __name__ == "__main__":
    unittest.main()
