import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest

from jev.api import candidate_prompts, compile_request
from jev.data import validate_records
from jev.games import (DoomBasic, HTTPPolicy, RandomPolicy, Snake, TeacherPolicy,
                       TicTacToe, TilePlatformer, TrexRunner, WikiRacing, canonical_board, control_records, game_request,
                       mario_request, reachable_boards, replay_episode,
                       run_episode, snake_action_values, snake_records,
                       tictactoe_records, trex_collision, trex_request, validate_action_answer)


class GamesTest(unittest.TestCase):
    def test_minimax_takes_win_blocks_loss_and_selfplay_draws(self):
        for board, action in (("XX.OO....", "2"), ("OO.X...X.", "2")):
            game = TicTacToe(board)
            self.assertIn(action, game.teacher_actions())
            game.step(action)
            with self.assertRaises(ValueError):
                game.step(action)
        game = TicTacToe()
        trace = run_episode(game, TeacherPolicy(game))
        self.assertTrue(trace["metrics"]["draw"])
        self.assertEqual(trace["metrics"]["steps"], 9)
        self.assertFalse(trace["is_model"])
        self.assertTrue(replay_episode(TicTacToe(), trace)["matched"])

    def test_invalid_and_terminal_boards(self):
        for board in ("XXXOOO...", "O........", "garbage", "XXXXXOOOO"):
            with self.assertRaises(ValueError):
                TicTacToe(board)
        game = TicTacToe("XXXOO....")
        self.assertEqual(game.legal_actions(), {})
        with self.assertRaises(ValueError):
            game_request(game)
        trace = run_episode(game, RandomPolicy())
        self.assertEqual(trace["metrics"]["steps"], 0)
        self.assertEqual(trace["metrics"]["stop_reason"], "terminal")

    def test_seeded_replay_and_tamper_detection(self):
        traces = [run_episode(Snake(), RandomPolicy(99), seed=13, max_steps=50) for _ in range(2)]
        self.assertTrue(replay_episode(Snake(), traces[0])["matched"])
        for trace in traces:
            trace["metrics"].pop("mean_decision_latency_ms")
            for step in trace["steps"]:
                step.pop("latency_ms")
                step.pop("environment_latency_ms")
        self.assertEqual(traces[0], traces[1])
        bad = copy.deepcopy(traces[0])
        bad["steps"][0]["next_state"]["food"] = [-1, -1]
        with self.assertRaises(ValueError):
            replay_episode(Snake(), bad)

    def test_snake_reverse_wall_body_tail_and_growth(self):
        game = Snake()
        with self.assertRaises(ValueError):
            game.step("left")
        game.snake, game.direction, game.food = [(1, 1), (1, 2), (0, 2), (0, 1)], "up", (5, 5)
        self.assertEqual(snake_action_values(game.observe())["left"][0], 1)
        self.assertEqual(game.step("left"), 0)
        self.assertEqual(game.snake[0], (0, 1))
        game.food = (0, 0)
        self.assertEqual(game.step("up"), 1)
        self.assertEqual(len(game.snake), 5)
        self.assertNotIn(game.food, game.snake)
        self.assertEqual(game.step("up"), -1)
        self.assertTrue(game.terminal)
        with self.assertRaises(ValueError):
            game.step("right")
        game.reset(0)
        game.snake, game.direction, game.food = [(1, 1), (1, 2), (0, 2), (0, 1), (0, 0)], "up", (5, 5)
        self.assertEqual(snake_action_values(game.observe())["left"][0], 0)
        self.assertEqual(game.step("left"), -1)

    def test_wiki_shortest_path_dead_end_and_budget(self):
        graph = {"A": ["B", "C"], "B": ["T"], "C": [], "T": []}
        game = WikiRacing(graph, "A", "T")
        trace = run_episode(game, TeacherPolicy(game))
        self.assertEqual(trace["metrics"]["path"], ["A", "B", "T"])
        self.assertTrue(trace["metrics"]["success"])
        self.assertTrue(replay_episode(WikiRacing(graph, "A", "T"), trace)["matched"])
        dead = run_episode(WikiRacing(graph, "C", "T"), RandomPolicy())
        self.assertEqual(dead["metrics"]["stop_reason"], "no_legal_actions")
        self.assertEqual(dead["steps"], [])
        game = WikiRacing(graph, "A", "T")
        limited = run_episode(game, TeacherPolicy(game), max_steps=1)
        self.assertEqual(limited["metrics"]["stop_reason"], "max_steps")
        self.assertTrue(replay_episode(WikiRacing(graph, "A", "T"), limited)["matched"])
        with self.assertRaises(ValueError):
            game.step("A")

    def test_http_uses_only_visible_state_never_oracle_and_errors_propagate(self):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append((self.path, body))
                actions = list(body["questions"]["action"]["criteria"])
                # Deliberately select the dead end, not the oracle's best action.
                answer = {"type": "choice", "choice": "C", "probabilities": {a: float(a == "C") for a in actions}}
                payload = json.dumps({"answers": {"action": answer}}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            graph = {"A": ["B", "C"], "B": ["T"], "C": [], "T": []}
            game = WikiRacing(graph, "A", "T")
            def forbidden():
                self.fail("Model rollout called the graph oracle")
            game.teacher_actions = forbidden
            policy = HTTPPolicy(f"http://127.0.0.1:{server.server_port}/v1/inference")
            trace = run_episode(game, policy)
            self.assertTrue(trace["is_model"])
            self.assertEqual(trace["metrics"]["path"], ["A", "C"])
            self.assertFalse(trace["metrics"]["success"])
            self.assertEqual(requests[0][0], "/v1/inference")
            self.assertEqual(set(requests[0][1]), {"state", "questions"})
            self.assertNotIn("graph", requests[0][1]["state"])
            with self.assertRaises(ValueError):
                # C is unavailable in tic-tac-toe; do not repair the response.
                run_episode(TicTacToe(), policy)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        with self.assertRaises(OSError):
            run_episode(TicTacToe(), HTTPPolicy(f"http://127.0.0.1:{server.server_port}/v1/inference", timeout=1))

    def test_invalid_probability_and_move_responses(self):
        request = game_request(TicTacToe("XX.OO...."))
        valid = RandomPolicy().choose(request)
        validate_action_answer(request, valid)
        for mutation in ({"choice": "occupied"}, {"probabilities": {"2": 1}},
                         {"type": "noul"}, {"probabilities": {a: math.nan for a in valid["probabilities"]}},
                         {"probabilities": {a: 0 for a in valid["probabilities"]}}):
            with self.assertRaises(ValueError):
                validate_action_answer(request, {**valid, **mutation})

    def test_tictactoe_exhaustive_data_and_symmetry_split_isolation(self):
        self.assertEqual(len(reachable_boards()), 5478)
        rows = tictactoe_records()
        summary = validate_records(rows)
        self.assertGreater(summary["records"], 4000)
        groups = {}
        for row in rows:
            board = "".join(row["state"]["board"])
            group = canonical_board(board)
            groups.setdefault(group, row["split"])
            self.assertEqual(row["split"], groups[group])
            game = TicTacToe(board)
            targets = {a for a, p in zip(row["options"], row["target"]) if p > 0}
            self.assertEqual(targets, set(game.teacher_actions()))
        self.assertEqual(rows, tictactoe_records())

    def test_snake_data_exact_collisions_grouped_and_ood_grid(self):
        rows = snake_records(episodes=12, max_steps=25)
        summary = validate_records(rows)
        self.assertGreater(summary["records"], 100)
        self.assertEqual(rows, snake_records(episodes=12, max_steps=25))
        for row in rows:
            self.assertEqual(row["state"]["width"], 8 if row["split"] == "ood" else 6)
            if row["kind"] == "noul":
                action = row["id"].split("collision_")[-1]
                values = snake_action_values(row["state"])
                self.assertEqual(row["target"][1], float(values[action][0] == 0))
            self.assertNotIn("teacher", row["state"])

    def test_mario_and_trex_external_request_contracts(self):
        mario = mario_request({"player": {"grounded": True}, "hazard": {"jump_must_start_this_decision": True}}, ["right", "right_jump"])
        records = compile_request(**mario)
        self.assertEqual([r["kind"] for r in records], ["choice", "noul", "score"])
        self.assertEqual(records[0]["answer_keys"], ["right", "right_jump"])
        with self.assertRaises(ValueError):
            mario_request({}, [])
        with self.assertRaises(ValueError):
            mario_request({"player": {}}, ["teleport"])
        for terminal in ({"dead": True}, {"stage_clear": True}):
            with self.assertRaises(ValueError):
                mario_request({"episode": terminal})
        state = {"speed": 7, "speedMode": "normal", "dinosaurMotion": "running",
                 "obstacle": {"kind": "small_cactus", "group": "single", "flightPath": "ground_hazard"}}
        rex = trex_request(state)
        self.assertEqual(len(compile_request(**rex)), 2)
        self.assertEqual(rex["state"]["target_obstacle"]["kind"], "small_cactus")
        for mutation in ({"speed": float("nan")}, {"speed": 0}, {"dinosaurMotion": "flying"},
                         {"obstacle": {"kind": "small_cactus", "group": "single", "flightPath": "clears_running_dinosaur"}}):
            with self.assertRaises(ValueError):
                trex_request({**state, **mutation})

    def test_local_trex_box_physics_and_replay(self):
        for seed in range(10):
            game = TrexRunner(obstacles=20)
            trace = run_episode(game, TeacherPolicy(game), seed=seed)
            self.assertTrue(trace["metrics"]["success"], (seed, trace["metrics"]))
            self.assertTrue(replay_episode(TrexRunner(20), trace)["matched"])
        game = TrexRunner()
        game.obstacle = {"kind": "small_cactus", "group_size": "single", "flight_path": "ground_hazard",
                         "width": 0.8, "height": 1, "bottom": 0}
        self.assertTrue(trex_collision(game.observe(), "keep_running"))
        self.assertTrue(trex_collision(game.observe(), "duck"))
        self.assertFalse(trex_collision(game.observe(), "jump_short"))
        self.assertEqual(game.step("keep_running"), -1)
        self.assertTrue(game.terminal)
        with self.assertRaises(ValueError):
            game.step("jump_full")

    def test_tile_platformer_plays_replays_and_obeys_ground_collision(self):
        for seed in range(5):
            game = TilePlatformer()
            trace = run_episode(game, TeacherPolicy(game), seed=seed, max_steps=100)
            self.assertTrue(trace["metrics"]["success"])
            self.assertTrue(replay_episode(TilePlatformer(), trace)["matched"])
        game = TilePlatformer()
        game.columns[3] = 2
        self.assertEqual(game.step("right"), 0)
        self.assertEqual(game.position[0], 2)
        game.step("right_jump")
        self.assertEqual(game.position[0], 3)
        game.reset(0)
        game.columns[3] = None
        self.assertEqual(game.step("right"), -1)
        self.assertTrue(game.dead)
        with self.assertRaises(ValueError):
            game.step("jump")

    def test_control_data_matches_runtime_labels_and_excludes_provenance(self):
        rows = control_records(episodes=8, max_steps=15)
        self.assertEqual(rows, control_records(episodes=8, max_steps=15))
        summary = validate_records(rows)
        self.assertGreater(summary["records"], 100)
        self.assertEqual(set(summary["sources"]), {"tile_platformer-v1", "trex_runner-v1"})
        self.assertNotIn("ood", summary["splits"])
        for row in rows:
            state = row["state"]
            if row["source"] == "tile_platformer-v1":
                game = TilePlatformer(row["metadata"]["runtime_config"]["length"])
                game.columns = list(state["terrain"]["columns"])
                game.position = (state["player"]["x"], state["player"]["y"],
                                 state["trajectory"]["jump_tick"], state["trajectory"]["launch_height"])
            else:
                game = TrexRunner()
                game.speed = state["current_speed"]
                game.obstacle = dict(state["target_obstacle"])
            runtime = compile_request(**game_request(game))[0]
            for key in ("state", "question", "kind", "options"):
                self.assertEqual(row[key], runtime[key])
            answer = TeacherPolicy(game).choose(game_request(game))
            expected = [answer["probabilities"][a] for a in runtime["answer_keys"]]
            self.assertEqual(row["target"], expected)
            self.assertTrue({a for a, p in zip(row["options"], row["target"]) if p} <= set(game.legal_actions()))
            prompts = candidate_prompts(row)
            changed = copy.deepcopy(row)
            changed.update(target=list(reversed(row["target"])), split="hidden_split", id="hidden_id")
            changed["metadata"] = {"secret_target": "HIDDEN_TEACHER"}
            self.assertEqual(prompts, candidate_prompts(changed))

    def test_control_data_level_split_isolation_and_teacher_future_independence(self):
        rows = control_records(episodes=12, max_steps=15)
        levels, states = {}, set()
        for row in rows:
            fingerprint = json.dumps([row["state"], row["question"]], sort_keys=True)
            self.assertNotIn(fingerprint, states)
            states.add(fingerprint)
            if row["source"] == "tile_platformer-v1":
                level = tuple(row["state"]["terrain"]["columns"])
                levels.setdefault(level, row["split"])
                self.assertEqual(levels[level], row["split"])
        game = TrexRunner()
        before = game.teacher_actions()
        game.rng.seed(99999)
        game.cleared = 8
        self.assertEqual(game.teacher_actions(), before)
        for args in ({"episodes": 0}, {"max_steps": 0}, {"episodes": 1.5}):
            with self.assertRaises(ValueError):
                control_records(**args)

    def test_game_service_evaluator_records_paired_http_results_and_failures(self):
        from scripts.evaluate_game_service import run_evaluation
        mode = ["valid"]
        calls = [0]

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                calls[0] += 1
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                actions = list(request["questions"]["action"]["criteria"])
                action = "Physics" if "Physics" in actions else "Mathematics"
                response = {"model": "test-model", "metadata": {
                    "method": "fixture" if mode[0] == "fixture" else "lora_decision_head",
                    "temperature": 1, "candidate_sequences": len(actions), "checkpoint_sha256": "a" * 64},
                    "answers": {"action": {"type": "choice", "choice": action,
                                             "probabilities": {a: float(a == action) for a in actions}}}}
                if mode[0] == "nan":
                    response["answers"]["action"]["probabilities"][actions[0]] = float("nan")
                if mode[0] == "identity_change" and calls[0] >= 2:
                    response["metadata"]["checkpoint_sha256"] = "b" * 64
                payload = json.dumps(response).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        endpoint = f"http://127.0.0.1:{server.server_port}"
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                report = run_evaluation(root / "valid", endpoint=endpoint, seeds=(42, 43),
                                        games=("wikiracing",), max_steps=4, expected_model="test-model")
                self.assertEqual(report["attempted_episodes"], 6)
                self.assertEqual(report["error_episodes"], 0)
                self.assertTrue(report["complete"])
                game = report["by_game"]["wikiracing"]
                self.assertEqual(game["paired_initial_states_match"], {"42": True, "43": True})
                self.assertEqual(game["policies"]["model"]["native_successes"], 2)
                model_trace = json.loads((root / "valid/trajectories/wikiracing-model-seed-42.json").read_text())
                self.assertEqual(len(model_trace["http_responses"]), 2)
                self.assertEqual(model_trace["steps"][0]["backend"]["checkpoint_sha256"], "a" * 64)
                self.assertIn("environment_latency_ms", model_trace["steps"][0])
                with self.assertRaises(ValueError):
                    run_evaluation(root / "valid", endpoint=endpoint, games=("wikiracing",))
                for failure_mode in ("fixture", "nan", "identity_change"):
                    mode[0] = failure_mode
                    calls[0] = 0
                    report = run_evaluation(root / failure_mode, endpoint=endpoint, seeds=(42,),
                                            games=("wikiracing",), max_steps=4)
                    model = report["by_game"]["wikiracing"]["policies"]["model"]
                    self.assertEqual(model["valid"], 0)
                    self.assertEqual(model["errors"], 1)
                    self.assertIsNone(model["native_successes"])
                    self.assertEqual(model["stopping_reasons"], {"error": 1})
                    raw = json.loads((root / failure_mode / "trajectories/wikiracing-model-seed-42.json").read_text())
                    self.assertFalse(raw["valid"])
                    self.assertEqual(len(raw["http_responses"]), 2 if failure_mode == "identity_change" else 1)
                    self.assertIn("pending_decision", raw)
                    self.assertEqual(len(raw["steps"]), 1 if failure_mode == "identity_change" else 0)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    @unittest.skipUnless(importlib.util.find_spec("vizdoom"), "optional vizdoom is not installed")
    def test_doom_real_engine_closed_loop_replay(self):
        game = DoomBasic()
        trace = run_episode(game, TeacherPolicy(game), seed=42, max_steps=100)
        self.assertGreater(trace["metrics"]["steps"], 0)
        self.assertTrue(replay_episode(DoomBasic(), trace)["matched"])


if __name__ == "__main__":
    unittest.main()
