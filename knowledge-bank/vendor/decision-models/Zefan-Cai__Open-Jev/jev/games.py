"""Text-state game loops, explicit baselines, and reproducible game data.

Only HTTPPolicy calls a model. Teachers are deliberately separate objects and
never receive control when model inference fails. Optional engines are lazy.
"""

from __future__ import annotations

from collections import deque
from functools import lru_cache
import json
import math
from pathlib import Path
import random
import time
from urllib.request import Request, urlopen

from .api import compile_request, format_response
from .data import _hash, _write_dataset, split_group
from .doom_control import (ATTACK_THRESHOLD, DECISION_MODES, decode_answers as decode_doom_answers,
                           is_typed_request as is_doom_typed_request, typed_request as doom_typed_request)


def choice_request(state: dict, actions: dict, instructions: str) -> dict:
    request = {"state": state, "questions": {"action": {
        "type": "choice", "instructions": instructions, "criteria": actions}}}
    compile_request(**request)
    return request


def game_request(game) -> dict:
    if game.terminal:
        raise ValueError("A terminal game has no decision to make")
    actions = game.legal_actions()
    if not actions:
        raise ValueError("The game has no legal actions")
    if isinstance(game, DoomBasic) and game.decision_mode == "typed-v1":
        return doom_typed_request(game.observe())
    return choice_request(game.observe(), actions, game.instructions)


def validate_action_answer(request: dict, answer: dict) -> str:
    if is_doom_typed_request(request):
        return decode_doom_answers(request, answer)["action"]
    legal = request["questions"]["action"]["criteria"]
    if not isinstance(answer, dict) or answer.get("type") != "choice":
        raise ValueError("The action answer must be a Choice object")
    action, probabilities = answer.get("choice"), answer.get("probabilities")
    if action not in legal:
        raise ValueError(f"Model or policy returned an illegal action: {action!r}")
    if not isinstance(probabilities, dict) or set(probabilities) != set(legal):
        raise ValueError("Action probabilities must cover exactly the legal candidates")
    values = list(probabilities.values())
    if any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1 for p in values):
        raise ValueError("Action probabilities must be finite numbers in [0, 1]")
    if not math.isclose(sum(values), 1.0, abs_tol=1e-6, rel_tol=1e-6):
        raise ValueError("Action probabilities must sum to one")
    return action


class HTTPPolicy:
    label = "model_http"
    is_model = True

    def __init__(self, url: str = "http://127.0.0.1:8791/v1/inference", *,
                 timeout: float = 60, api_key: str | None = None):
        if not url.startswith(("http://", "https://")) or timeout <= 0:
            raise ValueError("HTTP model policy needs an HTTP(S) URL and positive timeout")
        self.url, self.timeout, self.api_key = url, timeout, api_key

    def infer(self, request: dict) -> dict:
        compile_request(**request)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        wire = Request(self.url, data=json.dumps(request, allow_nan=False).encode(),
                       headers=headers, method="POST")
        # Network/protocol errors propagate. Never replace a failed model with a teacher.
        with urlopen(wire, timeout=self.timeout) as response:
            result = json.load(response)
        if not isinstance(result, dict) or not isinstance(result.get("answers"), dict):
            raise ValueError("Model response is missing the answers mapping")
        metadata = result.get("metadata", {})
        self.backend = {"model": result.get("model"),
                        "method": metadata.get("method") if isinstance(metadata, dict) else None,
                        "temperature": metadata.get("temperature") if isinstance(metadata, dict) else None}
        if isinstance(metadata, dict):
            for field in ("checkpoint_sha256", "base_revision", "code_commit", "candidate_sequences", "inference_seconds"):
                if field in metadata:
                    self.backend[field] = metadata[field]
        return result

    def choose(self, request: dict) -> dict:
        result = self.infer(request)
        if is_doom_typed_request(request):
            answer = result["answers"]
            validate_action_answer(request, answer)
            return answer
        if "action" not in result["answers"]:
            raise ValueError("Model response is missing its action answer")
        answer = result["answers"]["action"]
        validate_action_answer(request, answer)
        return answer


class RandomPolicy:
    label = "random_baseline"
    is_model = False

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def choose(self, request: dict) -> dict:
        if is_doom_typed_request(request):
            records = compile_request(**request)
            selected = [self.rng.randrange(len(record["options"])) for record in records]
            return format_response(records, [[float(i == index) for i in range(len(record["options"]))]
                                             for record, index in zip(records, selected)])["answers"]
        actions = list(request["questions"]["action"]["criteria"])
        return {"type": "choice", "choice": self.rng.choice(actions),
                "probabilities": {action: 1 / len(actions) for action in actions}}


class TeacherPolicy:
    """Explicitly selected baseline; full-graph Wiki teacher has privileged data."""
    is_model = False

    def __init__(self, game):
        if not hasattr(game, "teacher_actions"):
            raise ValueError("This game has no declared teacher")
        self.game = game
        self.label = game.teacher_label

    def choose(self, request: dict) -> dict:
        if is_doom_typed_request(request):
            from .case_doom import expert_decision
            decision = expert_decision(request["state"])
            records = compile_request(**request)
            selected = (decision["movement"], int(decision["attack"]), decision["suitability"])
            return format_response(records, [[float(i == index) for i in range(len(record["options"]))]
                                             for record, index in zip(records, selected)])["answers"]
        best = self.game.teacher_actions()
        actions = list(request["questions"]["action"]["criteria"])
        if not best or not set(best) <= set(actions):
            raise ValueError("Teacher did not return a nonempty subset of legal actions")
        return {"type": "choice", "choice": next(a for a in actions if a in best),
                "probabilities": {a: float(a in best) / len(best) for a in actions}}


def run_episode(game, policy, *, seed: int = 42, max_steps: int = 100,
                trace: dict | None = None) -> dict:
    """Run one bounded episode; an optional caller-owned trace retains failures."""
    if max_steps < 1:
        raise ValueError("max_steps must be positive")
    trace = {} if trace is None else trace
    trace.clear()
    trace.update(game=game.config, seed=seed, policy=policy.label,
                 is_model=policy.is_model, max_steps=max_steps, steps=[])
    try:
        game.reset(seed)
        trace["initial_state"] = game.observe()
        while len(trace["steps"]) < max_steps and not game.terminal:
            if not game.legal_actions():
                break
            request = game_request(game)
            trace["pending_decision"] = {"request": request}
            started = time.perf_counter()
            answer = policy.choose(request)
            latency_ms = (time.perf_counter() - started) * 1000
            trace["pending_decision"].update(answer=answer, latency_ms=latency_ms)
            action = validate_action_answer(request, answer)
            doom_control = decode_doom_answers(request, answer) if is_doom_typed_request(request) else None
            if doom_control is not None:
                trace["pending_decision"]["control_decision"] = doom_control
            started = time.perf_counter()
            reward = float(game.step(action))
            next_state = game.observe()
            environment_latency_ms = (time.perf_counter() - started) * 1000
            step = {"request": request, "answer": answer, "action": action,
                    "reward": reward, "next_state": next_state,
                    "terminal": game.terminal, "latency_ms": latency_ms,
                    "environment_latency_ms": environment_latency_ms}
            if doom_control is not None:
                step.update(control_decision=doom_control, executed_buttons=list(game.last_executed_buttons))
            if isinstance(policy, HTTPPolicy):
                step["backend"] = dict(policy.backend)
            trace["steps"].append(step)
            del trace["pending_decision"]
        reason = "terminal" if game.terminal else "no_legal_actions" if not game.legal_actions() else "max_steps"
        times = [step["latency_ms"] for step in trace["steps"]]
        trace["metrics"] = {"steps": len(trace["steps"]), "stop_reason": reason,
                            "total_reward": sum(step["reward"] for step in trace["steps"]),
                            "mean_decision_latency_ms": sum(times) / len(times) if times else None,
                            **game.outcome()}
        return trace
    except Exception as error:
        trace["error"] = {"type": type(error).__name__, "message": str(error)}
        trace["metrics"] = {"steps": len(trace["steps"]), "stop_reason": "error",
                            "total_reward": sum(step["reward"] for step in trace["steps"])}
        # A partial native outcome is diagnostic only, never a successful result.
        if "initial_state" in trace:
            try:
                trace["partial_outcome"] = game.outcome()
            except Exception as outcome_error:
                trace["partial_outcome_error"] = type(outcome_error).__name__
        raise
    finally:
        game.close()


def replay_episode(game, trace: dict) -> dict:
    """Replay recorded actions, checking observations and rewards without any policy."""
    if game.config != trace["game"]:
        raise ValueError("Replay game configuration differs")
    game.reset(trace["seed"])
    try:
        if game.observe() != trace["initial_state"]:
            raise ValueError("Replay initial observation differs")
        for i, step in enumerate(trace["steps"]):
            if game_request(game) != step["request"]:
                raise ValueError(f"Replay request mismatch at step {i}")
            if validate_action_answer(step["request"], step["answer"]) != step["action"]:
                raise ValueError(f"Replay answer/action mismatch at step {i}")
            if is_doom_typed_request(step["request"]):
                control = decode_doom_answers(step["request"], step["answer"])
                if control != step.get("control_decision") or control["buttons"] != step.get("executed_buttons"):
                    raise ValueError(f"Replay Doom judgment/button mismatch at step {i}")
            reward = game.step(step["action"])
            if is_doom_typed_request(step["request"]) and game.last_executed_buttons != step["executed_buttons"]:
                raise ValueError(f"Replay executed Doom buttons differ at step {i}")
            if (not math.isclose(reward, step["reward"], abs_tol=1e-8)
                    or game.observe() != step["next_state"] or game.terminal != step["terminal"]):
                raise ValueError(f"Replay transition mismatch at step {i}")
        reason = "terminal" if game.terminal else "no_legal_actions" if not game.legal_actions() else "max_steps"
        if reason != trace["metrics"]["stop_reason"]:
            raise ValueError("Replay stopping reason differs")
        if reason == "max_steps" and len(trace["steps"]) != trace["max_steps"]:
            raise ValueError("Trace stops before its declared action limit")
        if trace["metrics"]["steps"] != len(trace["steps"]):
            raise ValueError("Trace step count differs")
        if not math.isclose(sum(step["reward"] for step in trace["steps"]),
                            trace["metrics"]["total_reward"], abs_tol=1e-8):
            raise ValueError("Trace reward total differs")
        if any(trace["metrics"].get(k) != v for k, v in game.outcome().items()):
            raise ValueError("Trace outcome differs")
        return {"matched": True, "game": game.config["name"], "steps": len(trace["steps"])}
    finally:
        game.close()


class _Game:
    def close(self):
        pass


_LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))


def _winner(board: str) -> str | None:
    return next((board[a] for a, b, c in _LINES if board[a] != "." and board[a] == board[b] == board[c]), None)


@lru_cache(maxsize=1)
def reachable_boards() -> frozenset[str]:
    seen, stack = set(), ["........."]
    while stack:
        board = stack.pop()
        if board in seen:
            continue
        seen.add(board)
        if not _winner(board):
            player = "X" if board.count("X") == board.count("O") else "O"
            stack.extend(board[:i] + player + board[i + 1:] for i, x in enumerate(board) if x == ".")
    return frozenset(seen)


@lru_cache(maxsize=None)
def _minimax(board: str) -> int:
    if _winner(board):
        return -1  # Previous player just won.
    if "." not in board:
        return 0
    player = "X" if board.count("X") == board.count("O") else "O"
    return max(-_minimax(board[:i] + player + board[i + 1:]) for i, x in enumerate(board) if x == ".")


def canonical_board(board: str) -> str:
    variants = []
    for reflected in (False, True):
        grid = [list(board[i:i + 3]) for i in (0, 3, 6)]
        if reflected:
            grid = [row[::-1] for row in grid]
        for _ in range(4):
            variants.append("".join("".join(row) for row in grid))
            grid = [list(row) for row in zip(*grid[::-1])]
    return min(variants)


class TicTacToe(_Game):
    instructions = "Choose a legal square to maximize the current player's result against optimal opposition: win, then draw, then loss."
    teacher_label = "exact_minimax_baseline"

    def __init__(self, board: str = "........."):
        if board not in reachable_boards():
            raise ValueError("Board is not reachable under alternating play that stops at a win")
        self.initial_board = board
        self.config = {"name": "tic_tac_toe", "board": board}
        self.reset(0)

    def reset(self, seed):
        self.board = self.initial_board
        self.terminal = bool(_winner(self.board)) or "." not in self.board

    def observe(self):
        return {"game": "tic_tac_toe", "board": [self.board[i:i + 3] for i in (0, 3, 6)],
                "current_player": "X" if self.board.count("X") == self.board.count("O") else "O",
                "rules": "X starts; alternate placing a mark; three in a row wins. Squares 0..8 are row-major; . is empty."}

    def legal_actions(self):
        return {} if self.terminal else {str(i): None for i, x in enumerate(self.board) if x == "."}

    def step(self, action):
        if action not in self.legal_actions():
            raise ValueError("Illegal tic-tac-toe move")
        i, player = int(action), self.observe()["current_player"]
        self.board = self.board[:i] + player + self.board[i + 1:]
        self.terminal = bool(_winner(self.board)) or "." not in self.board
        return float(_winner(self.board) == player)

    def outcome(self):
        return {"winner": _winner(self.board), "draw": self.terminal and _winner(self.board) is None}

    def teacher_actions(self):
        player = self.observe()["current_player"]
        values = {a: -_minimax(self.board[:int(a)] + player + self.board[int(a) + 1:]) for a in self.legal_actions()}
        return [a for a, v in values.items() if v == max(values.values())] if values else []


DIRECTIONS = {"up": (0, -1), "right": (1, 0), "down": (0, 1), "left": (-1, 0)}
OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}


class Snake(_Game):
    instructions = "Choose a direction to keep the snake alive and collect food. The tail vacates on a move unless food is eaten; reversing direction is forbidden."
    teacher_label = "snake_bfs_heuristic_baseline"

    def __init__(self, width: int = 6, height: int = 6):
        if type(width) is not int or type(height) is not int or min(width, height) < 4:
            raise ValueError("Snake grid dimensions must be integers of at least four")
        self.width, self.height = width, height
        self.config = {"name": "snake", "width": width, "height": height}
        self.reset(0)

    def reset(self, seed):
        self.rng = random.Random(seed)
        x, y = self.width // 2, self.height // 2
        self.snake, self.direction = [(x, y), (x - 1, y)], "right"
        self.terminal, self.collision, self.score = False, False, 0
        self.food = self._new_food()

    def _new_food(self):
        available = [(x, y) for y in range(self.height) for x in range(self.width) if (x, y) not in self.snake]
        return self.rng.choice(available) if available else None

    def observe(self):
        return {"game": "snake", "width": self.width, "height": self.height,
                "snake_head_first": [list(cell) for cell in self.snake],
                "direction": self.direction, "food": list(self.food) if self.food is not None else None,
                "coordinates": "x increases right; y increases down; walls are outside the board"}

    def legal_actions(self):
        return {} if self.terminal else {a: None for a in DIRECTIONS if a != OPPOSITE[self.direction]}

    def step(self, action):
        if action not in self.legal_actions():
            raise ValueError("Illegal snake direction or terminal game")
        dx, dy = DIRECTIONS[action]
        head = (self.snake[0][0] + dx, self.snake[0][1] + dy)
        eating = head == self.food
        occupied = self.snake if eating else self.snake[:-1]
        self.direction = action
        if not (0 <= head[0] < self.width and 0 <= head[1] < self.height) or head in occupied:
            self.terminal = self.collision = True
            return -1.0
        self.snake = [head] + (self.snake if eating else self.snake[:-1])
        if eating:
            self.score += 1
            self.food = self._new_food()
            self.terminal = self.food is None
        return float(eating)

    def outcome(self):
        return {"food_collected": self.score, "collision": self.collision,
                "success": self.terminal and not self.collision}

    def teacher_actions(self):
        values = snake_action_values(self.observe())
        return [a for a, value in values.items() if value == max(values.values())]


def snake_action_values(state: dict) -> dict[str, tuple]:
    """Visible-state heuristic: survive, then shortest reachable food, then space.

    The flood fill treats the post-move body as static; it cannot prove eventual
    survival and never reads the RNG or location of future food.
    """
    snake = [tuple(cell) for cell in state["snake_head_first"]]
    food = tuple(state["food"]) if state["food"] is not None else None
    width, height = state["width"], state["height"]
    values = {}
    for action, (dx, dy) in DIRECTIONS.items():
        if action == OPPOSITE[state["direction"]]:
            continue
        head = (snake[0][0] + dx, snake[0][1] + dy)
        blocked = set(snake if head == food else snake[:-1])
        if head in blocked or not (0 <= head[0] < width and 0 <= head[1] < height):
            values[action] = (0, 0, 0, 0)
            continue
        distances, queue = {head: 0}, deque([head])
        while queue:
            x, y = queue.popleft()
            for vx, vy in DIRECTIONS.values():
                cell = x + vx, y + vy
                if (0 <= cell[0] < width and 0 <= cell[1] < height
                        and cell not in blocked and cell not in distances):
                    distances[cell] = distances[(x, y)] + 1
                    queue.append(cell)
        values[action] = (1, int(food in distances), -distances.get(food, width * height), len(distances))
    return values


class WikiRacing(_Game):
    instructions = "Choose an offered outgoing link to reach the target article in as few steps as possible."
    teacher_label = "full_graph_shortest_path_oracle_baseline"

    def __init__(self, graph: dict, source: str, target: str, max_candidates: int = 12):
        if source not in graph or target not in graph:
            raise ValueError("Wiki endpoints must exist in the graph")
        if not 2 <= max_candidates <= 255:
            raise ValueError("max_candidates must be between 2 and 255")
        if any(not isinstance(v, list) or any(p not in graph for p in v) for v in graph.values()):
            raise ValueError("Graph adjacency lists must point to known pages")
        self.graph = {page: sorted(set(links)) for page, links in graph.items()}
        self.source, self.target, self.max_candidates = source, target, max_candidates
        self.config = {"name": "wikiracing", "source": source, "target": target,
                       "graph_sha256": _hash(self.graph), "max_candidates": max_candidates}
        self.reset(0)

    def reset(self, seed):
        self.seed, self.current, self.path = seed, self.source, [self.source]
        self.terminal = self.current == self.target

    def observe(self):
        # Deliberately excludes hidden graph, BFS distances and expert path.
        return {"current_page": self.current, "target_page": self.target,
                "navigation": "Select one of the offered outgoing article links."}

    def legal_actions(self):
        from .case_wikiracing import sample_candidates
        return {} if self.terminal else {p: None for p in sample_candidates(
            self.graph[self.current], self.current, self.seed, self.max_candidates)}

    def step(self, action):
        if action not in self.legal_actions():
            raise ValueError("Illegal wiki link")
        self.current = action
        self.path.append(action)
        self.terminal = action == self.target
        return float(self.terminal)

    def outcome(self):
        return {"success": self.current == self.target, "path": list(self.path)}

    def teacher_actions(self):
        from .case_wikiracing import distances_to
        distances = distances_to(self.graph, self.target)
        actions = self.legal_actions()
        if not actions:
            return []
        best = min(distances.get(a, math.inf) for a in actions)
        return [a for a in actions if distances.get(a, math.inf) == best]


class DoomBasic(_Game):
    instructions = "Choose lateral movement and attack for the next action window to align with and shoot the visible target."
    teacher_label = "doom_tracking_heuristic_baseline"

    def __init__(self, decision_mode="combined-v1"):
        if decision_mode not in DECISION_MODES:
            raise ValueError("Unknown Doom decision mode")
        self.decision_mode = decision_mode
        self.config = {"name": "doom_basic", "protocol": "vizdoom-basic-v1"}
        if decision_mode == "typed-v1":
            self.config.update(protocol="vizdoom-basic-typed-v1", decision_mode=decision_mode,
                               attack_threshold=ATTACK_THRESHOLD)
        self.game = None
        self.last_executed_buttons = None

    def reset(self, seed):
        from .case_doom import _open_game, episode_spec
        self.close()
        self.spec = episode_spec(0, seed)
        self.game = _open_game(self.spec)
        self.last_executed_buttons = None
        self.terminal = bool(self.game.is_episode_finished())

    def observe(self):
        from .case_doom import observe
        return observe(self.game, self.spec["frame_skip"])

    def legal_actions(self):
        if self.terminal:
            return {}
        return {f"{movement}_{attack}": None for movement in ("left", "right", "hold") for attack in ("wait", "attack")}

    def step(self, action):
        if action not in self.legal_actions():
            raise ValueError("Illegal Doom action")
        movement, attack = action.split("_")
        buttons = [movement == "left", movement == "right", attack == "attack"]
        reward = self.game.make_action(buttons, self.spec["frame_skip"])
        self.last_executed_buttons = buttons
        self.terminal = bool(self.game.is_episode_finished())
        return float(reward)

    def outcome(self):
        return {"engine_total_reward": float(self.game.get_total_reward()),
                "elapsed_tics": int(self.game.get_episode_time())}

    def teacher_actions(self):
        from .case_doom import expert_decision
        decision = expert_decision(self.observe())
        movement = ("left", "right", "hold")[decision["movement"]]
        return [movement + ("_attack" if decision["attack"] else "_wait")]

    def close(self):
        if self.game is not None:
            self.game.close()
            self.game = None


def _trex_obstacle(rng):
    kind = rng.choice(("small_cactus", "large_cactus", "pterodactyl"))
    group = rng.choice(("single", "double", "triple")) if kind != "pterodactyl" else "single"
    count = ("single", "double", "triple").index(group) + 1
    flight = rng.choice(TREX_FLIGHTS[1:]) if kind == "pterodactyl" else "ground_hazard"
    return {"kind": kind, "group_size": group, "flight_path": flight,
            "width": (0.8 if kind == "small_cactus" else 1.1) * count,
            "height": 1.0 if kind != "large_cactus" else 1.75,
            "bottom": {"ground_hazard": 0, "blocks_running_and_ducking": 0.4,
                       "blocks_running_only": 1.1, "clears_running_dinosaur": 2.5}[flight]}


def trex_collision(state, action):
    """Simulate one obstacle in a small original box-physics runner.

    The controller schedules jump apex at the middle of horizontal overlap,
    matching the public demo's separation between maneuver choice and timing.
    This is our physics, not Chrome dinosaur/source-game physics.
    """
    if action not in ("jump_short", "jump_full", "duck", "keep_running"):
        raise ValueError("Unknown local T-Rex macro")
    obstacle, geometry = state["target_obstacle"], state["runner_geometry"]
    speed = state["current_speed"] / 20
    start = geometry["obstacle_start_x"]
    player_width = geometry["player_width"]
    height = geometry["duck_height"] if action == "duck" else geometry["standing_height"]
    velocity, gravity = (0.48, 0.08) if action == "jump_short" else (0.8, 0.06)
    midpoint = (start + (obstacle["width"] - player_width) / 2) / speed
    launch = max(0, midpoint - velocity / gravity)
    end = (start + obstacle["width"]) / speed
    # Substeps bound horizontal movement below 0.1 units for the declared speeds.
    for tick in range(math.ceil(end * 10) + 1):
        t = tick / 10
        x = start - speed * t
        if x >= player_width or x + obstacle["width"] <= 0:
            continue
        elapsed = max(0, t - launch)
        bottom = max(0, velocity * elapsed - gravity * elapsed * elapsed / 2) if action.startswith("jump_") else 0
        if bottom < obstacle["bottom"] + obstacle["height"] and bottom + height > obstacle["bottom"]:
            return True
    return False


class TrexRunner(_Game):
    """Maneuver-level local runner; each step executes one encountered obstacle."""
    instructions = ("Choose a maneuver to pass the obstacle. Prefer keep_running when it clears a standing dinosaur, "
                    "duck when only standing is blocked, and a jump otherwise. Use jump_short only for one small cactus; "
                    "use jump_full for larger obstacles. The controller handles launch timing using the supplied box geometry.")
    teacher_label = "trex_one_obstacle_physics_oracle_baseline"

    def __init__(self, obstacles: int = 12):
        if type(obstacles) is not int or obstacles < 1:
            raise ValueError("The local runner needs a positive obstacle count")
        self.obstacles = obstacles
        self.config = {"name": "trex_runner", "obstacles": obstacles, "physics": "open-jev-box-runner-v1"}
        self.reset(0)

    def reset(self, seed):
        self.rng = random.Random(seed)
        self.terminal, self.collision, self.cleared = False, False, 0
        self.speed = self.rng.choice((6, 8, 10, 12))
        self.obstacle = _trex_obstacle(self.rng)

    def observe(self):
        return {"objective": "Pass every obstacle without a collision.", "current_speed": self.speed,
                "speed_mode": "normal", "dinosaur_motion_when_observed": "running",
                "target_obstacle": dict(self.obstacle),
                "runner_geometry": {"player_width": 1, "standing_height": 2,
                                    "duck_height": 0.8, "obstacle_start_x": 12},
                "timing_policy": "One choice per obstacle; controller centers the jump apex on horizontal overlap. Local box physics, not Chrome physics."}

    def legal_actions(self):
        return {} if self.terminal else {a: None for a in ("jump_short", "jump_full", "duck", "keep_running")}

    def step(self, action):
        if action not in self.legal_actions():
            raise ValueError("Illegal local T-Rex maneuver or terminal game")
        if trex_collision(self.observe(), action):
            self.terminal = self.collision = True
            return -1.0
        self.cleared += 1
        self.terminal = self.cleared == self.obstacles
        if not self.terminal:
            self.speed = self.rng.choice((6, 8, 10, 12))
            self.obstacle = _trex_obstacle(self.rng)
        return 1.0

    def outcome(self):
        return {"obstacles_cleared": self.cleared, "collision": self.collision,
                "success": self.cleared == self.obstacles}

    def teacher_actions(self):
        safe = [a for a in self.legal_actions() if not trex_collision(self.observe(), a)]
        if not safe:
            return list(self.legal_actions())
        flight = self.obstacle["flight_path"]
        preferred = ("keep_running" if flight == "clears_running_dinosaur" else "duck" if flight == "blocks_running_only"
                     else "jump_short" if self.obstacle["kind"] == "small_cactus" and self.obstacle["group_size"] == "single" else "jump_full")
        return [preferred] if preferred in safe else safe


MARIO_ACTIONS = ("noop", "right", "right_jump", "right_run", "right_run_jump", "jump", "left")


class TilePlatformer(_Game):
    """Original tile platformer with explicit four-tick jumps, no NES assets."""
    instructions = ("Choose a controller macro to reach the right-hand flag without falling into a gap. "
                    "Walking moves one tile; running moves two. A jump from the ground follows the "
                    "four-tick heights 2, 3, 2, 0 above its starting height; airborne jump requests do not restart it. "
                    "Solid columns block horizontal movement below their top. Read the terrain and trajectory.")
    teacher_label = "tile_platformer_bfs_baseline"

    def __init__(self, length: int = 48):
        if type(length) is not int or length < 20:
            raise ValueError("The tile platformer needs at least 20 columns")
        self.length = length
        self.config = {"name": "tile_platformer", "length": length, "physics": "open-jev-tile-platformer-v1"}
        self.reset(0)

    def reset(self, seed):
        rng = random.Random(seed)
        self.columns = [0] * self.length
        for start in range(8, self.length - 5, 10):
            for x in range(start, start + rng.choice((1, 2))):
                self.columns[x] = None
            self.columns[start + 5] = rng.choice((1, 2))
        # x, feet height, jump index (-1 means grounded), jump launch height.
        self.position = (2, 0, -1, 0)
        self.terminal, self.dead = False, False
        self.moves, self.previous_action = 0, None

    def _transition(self, position, action):
        x, y, phase, launch_height = position
        if phase == -1 and "jump" in action:
            phase, launch_height = 0, y
        elif phase >= 0:
            phase += 1
        new_y = launch_height + (2, 3, 2, 0)[phase] if 0 <= phase < 4 else y
        dx = -1 if action == "left" else 2 if action in ("right_run", "right_run_jump") else 1 if action in ("right", "right_jump") else 0
        direction = -1 if dx < 0 else 1
        for _ in range(abs(dx)):
            proposed = min(self.length - 1, max(0, x + direction))
            floor = self.columns[proposed]
            if floor is not None and floor > new_y:
                break
            x = proposed
        floor = self.columns[x]
        descending = phase >= 2 or phase == -1
        if floor is not None and (phase == -1 or (descending and new_y <= floor)):
            new_y, phase, launch_height = floor, -1, floor
        elif phase >= 3:
            # Four-tick flight ended above lower terrain: drop to its floor.
            if floor is not None:
                new_y, phase, launch_height = floor, -1, floor
        dead = floor is None and (phase == -1 or phase >= 3)
        done = dead or x >= self.length - 2
        return (x, new_y, phase, launch_height), dead, done

    def observe(self):
        x, y, phase, launch = self.position
        ahead = list(enumerate(self.columns[x + 1:x + 9], 1))
        gap = next((distance for distance, height in ahead if height is None), None)
        obstacle = next((distance for distance, height in ahead if height is not None and height > y), None)
        return {"objective": "Reach the flag without falling into a gap.",
                "player": {"x": x, "y": y, "grounded": phase == -1,
                           "jump_phase": "grounded" if phase == -1 else "rising" if phase < 2 else "falling"},
                "trajectory": {"jump_tick": phase, "launch_height": launch,
                               "crossing_known_gap": self.columns[x] is None},
                "terrain": {"observation_reliability": "exact_local_engine",
                            "columns": list(self.columns), "null_means": "gap", "flag_x": self.length - 2,
                            "gap_distance_tiles": gap, "obstacle_distance_tiles": obstacle},
                "hazard": {"jump_must_start_this_decision": phase == -1 and any(d is not None and d <= 3 for d in (gap, obstacle))},
                "reaction_timing": {"action_horizon_ticks": 1, "inference_delay_ticks": 0},
                "episode": {"dead": self.dead, "stage_clear": self.terminal and not self.dead},
                "physics": "Original discrete tile simulator; no emulator, enemies, momentum or sprites. Full terrain is visible."}

    def legal_actions(self):
        return {} if self.terminal else {a: None for a in MARIO_ACTIONS}

    def step(self, action):
        if action not in self.legal_actions():
            raise ValueError("Illegal tile-platformer macro or terminal game")
        previous = self.position[0]
        self.position, self.dead, self.terminal = self._transition(self.position, action)
        self.moves += 1
        self.previous_action = action
        return -1.0 if self.dead else float(self.position[0] - previous)

    def outcome(self):
        return {"success": self.terminal and not self.dead, "dead": self.dead,
                "progress_tiles": self.position[0] - 2}

    def teacher_actions(self):
        # Exact BFS over the disclosed toy physics and terrain. No learned model.
        queue, seen = deque([(self.position, None)]), {self.position}
        while queue:
            position, first = queue.popleft()
            for action in ("right_run_jump", "right_run", "right_jump", "right", "jump", "noop", "left"):
                following, dead, done = self._transition(position, action)
                if dead:
                    continue
                first_action = first or action
                if done:
                    return [first_action]
                if following not in seen:
                    seen.add(following)
                    queue.append((following, first_action))
        raise ValueError("No successful path under the local platformer's physics")


def mario_request(state: dict, legal_actions: list[str] | None = None) -> dict:
    """Adapter for externally supplied Mario RAM-derived observations, no emulator."""
    if not isinstance(state, dict) or not state:
        raise ValueError("Mario requires a nonempty observation mapping")
    episode = state.get("episode", {})
    if isinstance(episode, dict) and (episode.get("dead") is True or episode.get("stage_clear") is True):
        raise ValueError("A terminated Mario episode must not request another action")
    actions = list(MARIO_ACTIONS) if legal_actions is None else list(legal_actions)
    if not actions or len(set(actions)) != len(actions) or not set(actions) <= set(MARIO_ACTIONS):
        raise ValueError("Supply distinct available Mario controller macros")
    request = {"state": state, "questions": {
        "next_action": {"type": "choice", "instructions": (
            "Select a controller macro that advances toward the flag and avoids death. "
            "Use reliable terrain, hazard projections, trajectory, recent control outcomes and "
            "reaction timing. Start a forward jump when its takeoff deadline is now; preserve "
            "forward motion and a rising jump while crossing a known gap. The emulator holds "
            "the macro for at least eight frames."), "criteria": {a: None for a in actions}},
        "jump_needed": {"type": "noul", "instructions": (
            "Do reliable terrain or projected hazards require starting or holding a forward "
            "jump now? Include an immediate takeoff deadline, a gap or blocking obstacle within "
            "three tiles, or a rising jump across a known gap.")},
        "danger": {"type": "score", "instructions": "Rate the immediate collision or falling threat.",
                   "criteria": ["Clear movement", "Approaching obstacle or enemy", "Immediate danger"]},
    }}
    compile_request(**request)
    return request


TREX_FLIGHTS = ("ground_hazard", "blocks_running_and_ducking", "blocks_running_only", "clears_running_dinosaur")


def trex_request(state: dict) -> dict:
    """Adapt the public T-Rex browser state; timing/physics stay in its controller."""
    if not isinstance(state, dict):
        raise ValueError("T-Rex state must be an object")
    speed, obstacle = state.get("speed"), state.get("obstacle")
    if type(speed) not in (int, float) or not math.isfinite(speed) or not 0 < speed <= 50:
        raise ValueError("T-Rex speed must be finite and in (0, 50]")
    if state.get("speedMode") not in ("normal", "slow") or state.get("dinosaurMotion") not in ("running", "jumping", "ducking"):
        raise ValueError("Unknown T-Rex speed mode or dinosaur motion")
    if (not isinstance(obstacle, dict) or obstacle.get("kind") not in ("small_cactus", "large_cactus", "pterodactyl")
            or obstacle.get("group") not in ("single", "double", "triple") or obstacle.get("flightPath") not in TREX_FLIGHTS):
        raise ValueError("Unknown T-Rex obstacle kind, group or flight path")
    if obstacle["kind"] != "pterodactyl" and obstacle["flightPath"] != "ground_hazard":
        raise ValueError("A cactus is a ground hazard")
    model_state = {"objective": "Avoid the obstacle and survive.", "current_speed": speed,
                   "speed_mode": state["speedMode"], "dinosaur_motion_when_observed": state["dinosaurMotion"],
                   "target_obstacle": {"kind": obstacle["kind"], "group_size": obstacle["group"],
                                       "flight_path": obstacle["flightPath"]},
                   "timing_policy": "Observed motion is transient; the external controller schedules the chosen maneuver."}
    request = {"state": model_state, "questions": {
        "maneuver": {"type": "choice", "instructions": "Select a safe maneuver for the obstacle. Let the external controller determine timing.",
                     "criteria": {"jump": "Clear a ground hazard or a bird that blocks both standing and ducking.",
                                  "duck": "Pass below a bird that only blocks standing.",
                                  "keep_running": "The obstacle clears the standing dinosaur."}},
        "jump_profile": {"type": "choice", "instructions": "Assuming a jump, select its trajectory. Use a short jump only for a single small cactus.",
                         "criteria": {"short": "One small cactus.", "full": "Any other obstacle."}},
    }}
    compile_request(**request)
    return request


def _synthetic_row(group: str, split: str, record: dict, target: list, seed: int, game: str, basis: str) -> dict:
    metadata = {"family": "policy", "case_name": game, "target_basis": basis,
                "template_id": f"{game}-v1-{'ood' if split == 'ood' else 'id'}",
                "provenance": {"type": "synthetic", "license": "CC0-1.0",
                               "generator_version": f"{game}-v1", "seed": seed,
                               "group_index": group, "variant": record["id"],
                               "split_policy": "identical_board_grouped; tic_tac_toe_rotations_and_reflections_grouped; snake_ood_grid_size"}}
    if record["kind"] == "score":
        metadata["score_values"] = list(range(len(target)))
    return {"id": group + ":" + record["id"], "group_id": group, "split": split,
            "source": f"{game}-v1", "state": record["state"], "question": record["question"],
            "kind": record["kind"], "options": record["options"], "target": target, "metadata": metadata}


def tictactoe_records(seed: int = 42) -> list[dict]:
    rows = []
    for board in sorted(reachable_boards()):
        game = TicTacToe(board)
        # The training schema requires >=2 candidates; runtime accepts a forced move.
        if len(game.legal_actions()) < 2:
            continue
        group = "tic_tac_toe-v1:" + canonical_board(board)
        record = compile_request(**game_request(game))[0]
        record["id"] = board
        best = game.teacher_actions()
        rows.append(_synthetic_row(group, split_group(group, seed), record,
                                   [float(a in best) / len(best) for a in record["answer_keys"]],
                                   seed, "tic_tac_toe", "exact minimax; ties are uniform optimal actions, not win probabilities"))
    return rows


def snake_records(*, episodes: int = 100, max_steps: int = 80, seed: int = 42) -> list[dict]:
    if episodes < 1 or max_steps < 1:
        raise ValueError("episodes and max_steps must be positive")
    rows, seen = [], set()
    for ood, count in ((False, episodes), (True, max(1, episodes // 5))):
        for index in range(count):
            game = Snake(8 if ood else 6, 8 if ood else 6)
            episode_seed = seed + index + (1_000_000 if ood else 0)
            game.reset(episode_seed)
            policy = TeacherPolicy(game) if index % 2 == 0 else RandomPolicy(episode_seed)
            for _ in range(max_steps):
                if game.terminal:
                    break
                request = game_request(game)
                fingerprint = _hash(request["state"])
                values = snake_action_values(request["state"])
                best = [a for a, v in values.items() if v == max(values.values())]
                if fingerprint not in seen:
                    seen.add(fingerprint)
                    group = "snake-v1:" + fingerprint[:24]
                    split = "ood" if ood else split_group(group, seed)
                    for action in game.legal_actions():
                        request["questions"]["collision_" + action] = {
                            "type": "noul", "instructions": f"Will moving {action} cause an immediate wall or body collision? The tail vacates unless food is eaten."}
                    for record in compile_request(**request):
                        target = ([float(a in best) / len(best) for a in record["answer_keys"]] if record["kind"] == "choice"
                                  else [float(values[record["id"][10:]][0] == 1), float(values[record["id"][10:]][0] == 0)])
                        rows.append(_synthetic_row(group, split, record, target, seed, "snake",
                            "Choice: visible-state BFS/flood-fill heuristic, not optimal. Noul: exact one-step collision rule."))
                # Only the action question is used by the rollout policy.
                action_request = game_request(game)
                game.step(validate_action_answer(action_request, policy.choose(action_request)))
    return rows


def control_records(*, episodes: int = 100, max_steps: int = 40, seed: int = 42) -> list[dict]:
    """Label observed local control states using the exact runtime request.

    Labels use current visible geometry only. Seed/episode and teacher details
    are provenance, never inserted into model inputs. No OOD is manufactured.
    """
    if type(episodes) is not int or type(max_steps) is not int or episodes < 1 or max_steps < 1:
        raise ValueError("episodes and max_steps must be positive integers")
    rows, seen = [], set()
    for game_type in (TrexRunner, TilePlatformer):
        for episode_index in range(episodes):
            game = game_type()
            episode_seed = seed + episode_index
            game.reset(episode_seed)
            teacher = TeacherPolicy(game)
            behavior = teacher if episode_index % 2 == 0 else RandomPolicy(episode_seed)
            for step_index in range(max_steps):
                if game.terminal or not game.legal_actions():
                    break
                request = game_request(game)
                fingerprint = _hash(request)
                answer = teacher.choose(request)
                validate_action_answer(request, answer)
                if fingerprint not in seen:
                    seen.add(fingerprint)
                    name = game.config["name"]
                    if name == "tile_platformer":
                        # A seeded level may recur across episodes. Keep all its
                        # states together, including randomly reached positions.
                        group_key = {"columns": request["state"]["terrain"]["columns"]}
                        split_policy = "full_visible_terrain_layout_grouped_hash_v1; no_ood"
                        basis = "Deterministic BFS first action on a shortest successful path in the disclosed local tile physics and full visible terrain; not NES gameplay."
                    else:
                        group_key = request["state"]
                        split_policy = "identical_visible_observation_grouped_hash_v1; no_ood"
                        basis = "One-obstacle box-physics simulation with declared maneuver preference using current visible geometry; no future obstacle or RNG access; not Chrome physics."
                    group = f"{name}-v1:" + _hash(group_key)[:24]
                    record = compile_request(**request)[0]
                    record["id"] = fingerprint[:24]
                    row = _synthetic_row(group, split_group(group, seed), record,
                                         [answer["probabilities"][a] for a in record["answer_keys"]],
                                         seed, name, basis)
                    row["metadata"].update(runtime_config=dict(game.config), teacher=teacher.label,
                                             behavior_policy=behavior.label, episode_step=step_index)
                    row["metadata"]["provenance"].update(
                        split_policy=split_policy, episode_seed=episode_seed,
                        episode_index=episode_index, observed_request_sha256=fingerprint,
                        label_scope="current_visible_observation_only")
                    rows.append(row)
                # Behavior selects the transition; a random behavior action is
                # never confused with the teacher target recorded above.
                selected = answer if behavior is teacher else behavior.choose(request)
                game.step(validate_action_answer(request, selected))
            game.close()
    return rows


def build_control_dataset(output_dir: str | Path, *, episodes: int = 100,
                          max_steps: int = 40, seed: int = 42) -> dict:
    return _write_dataset(control_records(episodes=episodes, max_steps=max_steps, seed=seed),
        output_dir, {"type": "synthetic", "generator_version": "control-games-v1", "seed": seed,
                     "games": ["trex_runner", "tile_platformer"], "episodes_per_game": episodes,
                     "max_steps": max_steps, "behavior": "even episode indices teacher; odd indices seeded random",
                     "deduplication": "exact runtime state/questions request",
                     "split_groups": {"trex_runner": "complete visible observation",
                                      "tile_platformer": "complete terrain layout, all positions kept together"},
                     "ood": "none; all episodes use the unchanged local runtime configuration",
                     "target_basis": "deterministic current-observation teacher, independent of behavior action",
                     "representation": "exact compile_request(**game_request(runtime)) model inputs"})


def build_game_dataset(output_dir: str | Path, *, game: str, episodes: int = 100,
                       max_steps: int = 80, seed: int = 42) -> dict:
    if game == "tic_tac_toe":
        rows = tictactoe_records(seed)
    elif game == "snake":
        rows = snake_records(episodes=episodes, max_steps=max_steps, seed=seed)
    elif game == "all":
        rows = tictactoe_records(seed) + snake_records(episodes=episodes, max_steps=max_steps, seed=seed)
    else:
        raise ValueError("Supported data generators: snake, tic_tac_toe, all")
    return _write_dataset(rows, output_dir, {"type": "synthetic", "game": game,
        "seed": seed, "episodes": episodes if game in ("snake", "all") else None,
        "max_steps": max_steps if game in ("snake", "all") else None})
