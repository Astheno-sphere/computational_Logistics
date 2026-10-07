"""Real headless ViZDoom trajectories with explicitly weak decision supervision.

The optional vizdoom package is imported only by the rollout/replay commands.
No screenshots, hidden objects, future rewards or teacher labels enter state.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path

from jev.data import _hash, _json, _write_dataset, read_jsonl, split_group


VERSION = "vizdoom-basic-v1"
SOURCE_URL = "https://github.com/Farama-Foundation/ViZDoom/tree/1.2.4/scenarios"
MOVEMENTS = ["Strafe left", "Strafe right", "Hold lateral movement"]
SCORE_OPTIONS = [
    "Cannot usefully aim a shot: no live visible target, no ammunition, dead player, or absolute target bearing above 22 degrees.",
    "Very poor alignment: live visible target and ammunition, player alive, absolute target bearing above 12 and at most 22 degrees.",
    "Coarse alignment: live visible target and ammunition, player alive, absolute target bearing above 6 and at most 12 degrees.",
    "Near alignment: live visible target and ammunition, player alive, absolute target bearing above 3 and at most 6 degrees.",
    "Aligned for the script's shot: live visible target and ammunition, player alive, absolute target bearing at most 3 degrees.",
]


def relative_bearing(player_x: float, player_y: float, heading_deg: float,
                     enemy_x: float, enemy_y: float) -> float:
    """Positive angles point left in Doom's world coordinate convention."""
    return (math.degrees(math.atan2(enemy_y - player_y, enemy_x - player_x))
            - heading_deg + 180.0) % 360.0 - 180.0


def expert_decision(state: dict) -> dict:
    """Transparent tracking heuristic, not an optimal policy or value oracle."""
    enemy = state["nearest_visible_enemy"]
    ready = enemy is not None and state["health"] > 0 and state["ammo"] > 0
    if not ready:
        return {"movement": 2, "attack": False, "suitability": 0}
    bearing = enemy["relative_bearing_deg"]
    error = enemy["distance_units"] * math.sin(math.radians(bearing))
    # Account for strafe momentum using only the current measured velocity.
    predicted_error = error - state["movement"]["lateral_units_per_tic"] * 8.0
    movement = 0 if predicted_error > 10.0 else 1 if predicted_error < -10.0 else 2
    angle = abs(bearing)
    score = 4 if angle <= 3 else 3 if angle <= 6 else 2 if angle <= 12 else 1 if angle <= 22 else 0
    return {"movement": movement, "attack": angle <= 3.0, "suitability": score}


def action_buttons(decision: dict) -> list[bool]:
    """The basic scenario's exact MOVE_LEFT, MOVE_RIGHT, ATTACK ordering."""
    return [decision["movement"] == 0, decision["movement"] == 1, bool(decision["attack"])]


def episode_spec(index: int, seed: int, ood: bool = False) -> dict:
    if index < 0 or not 0 <= seed < 1_000_000:
        raise ValueError("index must be nonnegative and seed must be in [0, 1000000)")
    engine_seed = seed + index + (1_000_000 if ood else 0)
    episode_id = f"{VERSION}:{seed}:{'ood' if ood else 'id'}:{index}"
    return {"episode_id": episode_id, "seed": engine_seed,
            "split": "ood" if ood else split_group(episode_id, seed),
            "scenario": "basic", "map": "map01", "doom_skill": 1 if ood else 5,
            "frame_skip": 8 if ood else 4, "episode_timeout": 300,
            "episode_start_time": 14,
            "ood_axis": "unseen_seeds_skill_and_action_duration" if ood else None}


def _engine():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    try:
        import vizdoom
    except ImportError as exc:
        raise RuntimeError("Install vizdoom==1.2.4 in an isolated optional environment") from exc
    if vizdoom.__version__ != "1.2.4":
        raise RuntimeError("This trajectory protocol requires vizdoom==1.2.4")
    return vizdoom


def engine_provenance() -> dict:
    vzd = _engine()
    files = {"scenario_config": Path(vzd.scenarios_path) / "basic.cfg",
             "scenario_wad": Path(vzd.scenarios_path) / "basic.wad",
             "game_wad": Path(vzd.__file__).parent / "freedoom2.wad"}
    return {"vizdoom_version": vzd.__version__, "assets_sha256": {
        name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()}}


def _open_game(spec: dict):
    vzd = _engine()
    game = vzd.DoomGame()
    game.load_config(str(Path(vzd.scenarios_path) / "basic.cfg"))
    game.set_doom_game_path(str(Path(vzd.__file__).parent / "freedoom2.wad"))
    game.set_doom_map(spec["map"])
    game.set_mode(vzd.Mode.PLAYER)
    game.set_window_visible(False)
    game.set_sound_enabled(False)
    game.set_labels_buffer_enabled(True)
    game.set_objects_info_enabled(True)
    game.set_doom_skill(spec["doom_skill"])
    game.set_episode_start_time(spec["episode_start_time"])
    game.set_episode_timeout(spec["episode_timeout"])
    game.set_seed(spec["seed"])
    game.set_available_buttons([vzd.Button.MOVE_LEFT, vzd.Button.MOVE_RIGHT, vzd.Button.ATTACK])
    game.set_available_game_variables([
        vzd.GameVariable.HEALTH, vzd.GameVariable.AMMO2,
        vzd.GameVariable.POSITION_X, vzd.GameVariable.POSITION_Y,
        vzd.GameVariable.ANGLE, vzd.GameVariable.VELOCITY_X, vzd.GameVariable.VELOCITY_Y,
    ])
    game.init()
    game.new_episode()
    return game


def observe(game, frame_skip: int) -> dict | None:
    raw = game.get_state()
    if raw is None:
        return None
    health, ammo, x, y, angle, vx, vy = map(float, raw.game_variables)
    enemies = []
    # This scenario contains Cacodemon targets. Labels, unlike state.objects,
    # limit the detector to objects currently visible on screen.
    for label in raw.labels:
        if label.object_name != "Cacodemon" or label.width <= 0 or label.height <= 0:
            continue
        enemies.append({"name": label.object_name,
                        "relative_bearing_deg": round(relative_bearing(x, y, angle,
                            label.object_position_x, label.object_position_y), 6),
                        "distance_units": round(math.hypot(label.object_position_x - x,
                                                          label.object_position_y - y), 6)})
    enemies.sort(key=lambda enemy: (enemy["distance_units"], enemy["relative_bearing_deg"]))
    theta = math.radians(angle)
    return {"health": health, "ammo": ammo,
            "player": {"x_units": round(x, 6), "y_units": round(y, 6), "heading_deg": round(angle, 6)},
            "movement": {"forward_units_per_tic": round(vx * math.cos(theta) + vy * math.sin(theta), 6),
                         "lateral_units_per_tic": round(-vx * math.sin(theta) + vy * math.cos(theta), 6)},
            "visible_enemy_count": len(enemies),
            "nearest_visible_enemy": enemies[0] if enemies else None,
            "elapsed_tics": int(game.get_episode_time()), "action_window_tics": frame_skip}


def collect_episode(spec: dict) -> dict:
    game = _open_game(spec)
    steps = []
    try:
        while not game.is_episode_finished():
            state = observe(game, spec["frame_skip"])
            if state is None:
                raise RuntimeError("Engine produced no observation before terminal state")
            teacher = expert_decision(state)
            action = action_buttons(teacher)
            reward = float(game.make_action(action, spec["frame_skip"]))
            next_state = observe(game, spec["frame_skip"])
            steps.append({"state": state, "state_sha256": _hash(state), "teacher": teacher,
                          "action": action, "reward": reward,
                          "next_state_sha256": _hash(next_state),
                          "done": bool(game.is_episode_finished())})
        return {**spec, "steps": steps, "total_reward": float(game.get_total_reward()),
                "finished": bool(game.is_episode_finished()), "elapsed_tics": int(game.get_episode_time())}
    finally:
        game.close()


def records_from_episode(episode: dict, episode_sha256: str) -> list[dict]:
    records = []
    for index, step in enumerate(episode["steps"]):
        state, teacher = step["state"], step["teacher"]
        if teacher != expert_decision(state) or step["action"] != action_buttons(teacher):
            raise ValueError("Episode teacher/action does not match the declared tracking script")
        tasks = [
            ("choice", "Which lateral movement does the momentum-aware tracking policy choose to align with the nearest visible target?", MOVEMENTS, teacher["movement"]),
            ("noul", "Should the tracking policy press attack now: a visible target is within 3 degrees, ammunition remains, and the player is alive?", ["no", "yes"], int(teacher["attack"])),
            ("score", "Rate the current shot alignment using the supplied ordered suitability grades. These grades are an aiming heuristic, not expected game reward.", SCORE_OPTIONS, teacher["suitability"]),
        ]
        for kind, question, options, answer in tasks:
            metadata = {"family": "doom_basic", "target_basis": "weak_script_expert_v1",
                        "expert_optimality_claim": False, "episode_step": index,
                        "provenance": {"type": "import", "input_sha256": episode_sha256,
                            "source_url": SOURCE_URL, "original_id": f"{episode['episode_id']}:{index}",
                            "license": "CC0-1.0 (generated numeric trajectories; no game assets)",
                            "split_policy": "episode_grouped_v1_with_separate_ood_seeds_and_control_regime",
                            "generator_version": VERSION, "engine_seed": episode["seed"]}}
            if kind == "score":
                metadata["score_values"] = list(range(5))
            records.append({"id": f"{episode['episode_id']}:{index}:{kind}",
                            "group_id": episode["episode_id"], "split": episode["split"],
                            "source": VERSION, "state": state, "question": question,
                            "kind": kind, "options": list(options),
                            "target": [float(i == answer) for i in range(len(options))], "metadata": metadata})
    return records


def build_dataset(output_dir: str | Path, episodes: int = 400, ood_episodes: int = 80,
                  seed: int = 190919) -> dict:
    if not 1 <= episodes <= 10000 or not 0 <= ood_episodes <= 10000:
        raise ValueError("Require 1–10000 ID episodes and 0–10000 OOD episodes")
    # Validate seed before starting any game, and keep seed ranges disjoint.
    episode_spec(0, seed)
    output = Path(output_dir)
    if (output / "manifest.json").exists():
        raise ValueError("Output already contains a dataset; choose a new directory")
    trajectory_dir = output / "trajectories"
    trajectory_dir.mkdir(parents=True, exist_ok=True)
    trajectory_path = trajectory_dir / "episodes.jsonl"
    provenance = engine_provenance()
    records, rewards, seen_states = [], [], set()
    dropped_states, observed_states = 0, 0
    episode_splits, movement_counts, attack_counts, score_counts = Counter(), Counter(), Counter(), Counter()
    with trajectory_path.open("w", encoding="utf-8") as raw_file:
        for ood, count in ((False, episodes), (True, ood_episodes)):
            for index in range(count):
                episode = collect_episode(episode_spec(index, seed, ood))
                encoded = _json(episode)
                raw_file.write(encoded + "\n")
                raw_file.flush()
                digest = hashlib.sha256(encoded.encode()).hexdigest()
                episode_splits[episode["split"]] += 1
                rewards.append(episode["total_reward"])
                episode_records = records_from_episode(episode, digest)
                for step_index, step in enumerate(episode["steps"]):
                    observed_states += 1
                    fingerprint = _hash(step["state"])
                    # Never add artificial episode/seed identifiers to model
                    # input merely to disguise repeated physical observations.
                    if fingerprint in seen_states:
                        dropped_states += 1
                        continue
                    seen_states.add(fingerprint)
                    records.extend(episode_records[step_index * 3:step_index * 3 + 3])
                    movement_counts[MOVEMENTS[step["teacher"]["movement"]]] += 1
                    attack_counts[str(step["teacher"]["attack"])] += 1
                    score_counts[step["teacher"]["suitability"]] += 1
                if (index + 1) % 20 == 0 or index + 1 == count:
                    print(_json({"event": "rollout_progress", "ood": ood,
                                 "episodes": index + 1, "states": observed_states}), flush=True)
    manifest = _write_dataset(records, output, {"type": "engine_trajectory",
        "generator_version": VERSION, "episodes": episodes, "ood_episodes": ood_episodes,
        "seed": seed, "expert": "momentum_tracking_weak_script_v1", **provenance})
    manifest["trajectory_file"] = "trajectories/episodes.jsonl"
    manifest["trajectory_sha256"] = hashlib.sha256(trajectory_path.read_bytes()).hexdigest()
    manifest["rollout_summary"] = {"episodes_by_split": dict(episode_splits),
        "observed_states": observed_states, "unique_retained_states": len(seen_states),
        "duplicate_states_removed": dropped_states, "movement_counts": dict(movement_counts),
        "attack_counts": dict(attack_counts), "suitability_counts": {str(i): score_counts[i] for i in range(5)},
        "mean_episode_reward": sum(rewards) / len(rewards),
        "minimum_episode_reward": min(rewards), "maximum_episode_reward": max(rewards)}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def replay_episode(episode: dict) -> dict:
    game = _open_game(episode)
    try:
        for index, step in enumerate(episode["steps"]):
            actual = observe(game, episode["frame_skip"])
            if _hash(actual) != step["state_sha256"] or _hash(step["state"]) != step["state_sha256"]:
                raise ValueError(f"Replay observation mismatch at {episode['episode_id']} step {index}")
            if expert_decision(actual) != step["teacher"] or action_buttons(step["teacher"]) != step["action"]:
                raise ValueError(f"Replay expert/action mismatch at step {index}")
            reward = float(game.make_action(step["action"], episode["frame_skip"]))
            if not math.isclose(reward, step["reward"], rel_tol=0, abs_tol=1e-8):
                raise ValueError(f"Replay reward mismatch at step {index}")
            if _hash(observe(game, episode["frame_skip"])) != step["next_state_sha256"]:
                raise ValueError(f"Replay next observation mismatch at step {index}")
            if bool(game.is_episode_finished()) != step["done"]:
                raise ValueError(f"Replay terminal flag mismatch at step {index}")
        if not game.is_episode_finished() or not episode["finished"]:
            raise ValueError("Replay ends before terminal engine state")
        if not math.isclose(game.get_total_reward(), episode["total_reward"], rel_tol=0, abs_tol=1e-8):
            raise ValueError("Replay total reward mismatch")
        return {"episode_id": episode["episode_id"], "steps": len(episode["steps"]), "matched": True}
    finally:
        game.close()


def replay_dataset(output_dir: str | Path, limit: int = 10) -> dict:
    if limit < 1:
        raise ValueError("replay limit must be positive")
    output = Path(output_dir)
    manifest = json.loads((output / "manifest.json").read_text())
    current = engine_provenance()
    if any(manifest["configuration"].get(k) != v for k, v in current.items()):
        raise ValueError("Replay engine version or scenario/Freedoom assets differ from the manifest")
    path = output / manifest["trajectory_file"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["trajectory_sha256"]:
        raise ValueError("Trajectory checksum mismatch")
    episodes = list(read_jsonl(path))
    # Cover both ID and OOD, instead of taking only the leading train episodes.
    selected = []
    for split in ("train", "calibration", "validation", "test", "ood"):
        candidates = [ep for ep in episodes if ep["split"] == split]
        if candidates and len(selected) < limit:
            selected.append(candidates[0])
    selected_ids = {ep["episode_id"] for ep in selected}
    selected.extend(ep for ep in episodes if ep["episode_id"] not in selected_ids)
    results = [replay_episode(ep) for ep in selected[:limit]]
    if not results:
        raise ValueError("No episodes available to replay")
    report = {"replayed_episodes": len(results), "all_matched": True, "episodes": results}
    (output / "replay-report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--output-dir", required=True, type=Path)
    build.add_argument("--episodes", type=int, default=400)
    build.add_argument("--ood-episodes", type=int, default=80)
    build.add_argument("--seed", type=int, default=190919)
    replay = commands.add_parser("replay")
    replay.add_argument("output_dir", type=Path)
    replay.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    if args.command == "build":
        result = build_dataset(args.output_dir, args.episodes, args.ood_episodes, args.seed)
    else:
        result = replay_dataset(args.output_dir, args.limit)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
