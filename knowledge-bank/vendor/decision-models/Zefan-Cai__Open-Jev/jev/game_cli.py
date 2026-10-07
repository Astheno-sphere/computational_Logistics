"""Run/replay local game loops, build data, or format external simulator requests."""

import argparse
import json
import os
from pathlib import Path

from .doom_control import DECISION_MODES
from .games import (DoomBasic, HTTPPolicy, RandomPolicy, Snake, TeacherPolicy,
                    TicTacToe, TilePlatformer, TrexRunner, WikiRacing, build_control_dataset,
                    build_game_dataset, mario_request,
                    replay_episode, run_episode, trex_request)


def _game(config, graph_path=None):
    if config["name"] == "snake":
        return Snake(config["width"], config["height"])
    if config["name"] == "tic_tac_toe":
        return TicTacToe(config["board"])
    if config["name"] == "doom_basic":
        return DoomBasic(config.get("decision_mode", "combined-v1"))
    if config["name"] == "trex_runner":
        return TrexRunner(config["obstacles"])
    if config["name"] == "tile_platformer":
        return TilePlatformer(config["length"])
    if config["name"] == "wikiracing":
        if graph_path is None:
            raise ValueError("Wikiracing requires --graph; no graph is downloaded implicitly")
        return WikiRacing(json.loads(Path(graph_path).read_text()), config["source"],
                          config["target"], config["max_candidates"])
    raise ValueError("Unknown game")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    play = commands.add_parser("play")
    play.add_argument("game", choices=("snake", "tic_tac_toe", "wikiracing", "doom_basic", "trex_runner", "tile_platformer"))
    play.add_argument("--policy", choices=("random", "teacher", "http"), required=True)
    play.add_argument("--url", default="http://127.0.0.1:8791/v1/inference")
    play.add_argument("--api-key-env", default="OPEN_JEV_API_KEY")
    play.add_argument("--timeout", type=float, default=60)
    play.add_argument("--seed", type=int, default=42)
    play.add_argument("--episodes", type=int, default=1)
    play.add_argument("--max-steps", type=int, default=100)
    play.add_argument("--doom-decision-mode", choices=DECISION_MODES, default="combined-v1")
    play.add_argument("--obstacles", type=int, default=12)
    play.add_argument("--length", type=int, default=48)
    play.add_argument("--width", type=int, default=6)
    play.add_argument("--height", type=int, default=6)
    play.add_argument("--board", default=".........")
    play.add_argument("--graph", type=Path)
    play.add_argument("--source")
    play.add_argument("--target")
    play.add_argument("--max-candidates", type=int, default=12)
    play.add_argument("--output", type=Path, required=True)
    replay = commands.add_parser("replay")
    replay.add_argument("trace", type=Path)
    replay.add_argument("--graph", type=Path)
    build = commands.add_parser("build-data")
    build.add_argument("game", choices=("snake", "tic_tac_toe", "all"))
    build.add_argument("--output-dir", type=Path, required=True)
    build.add_argument("--seed", type=int, default=42)
    build.add_argument("--episodes", type=int, default=100)
    build.add_argument("--max-steps", type=int, default=80)
    control = commands.add_parser("build-control-data")
    control.add_argument("--output-dir", type=Path, required=True)
    control.add_argument("--seed", type=int, default=42)
    control.add_argument("--episodes", type=int, default=100)
    control.add_argument("--max-steps", type=int, default=40)
    request = commands.add_parser("request")
    request.add_argument("game", choices=("mario", "trex"))
    request.add_argument("state", type=Path)
    request.add_argument("--output", type=Path)
    request.add_argument("--legal-actions", nargs="+")
    args = parser.parse_args(argv)
    if args.command == "play":
        if args.episodes < 1:
            parser.error("--episodes must be positive")
        if args.game != "doom_basic" and args.doom_decision_mode != "combined-v1":
            parser.error("--doom-decision-mode applies only to doom_basic")
        config = {"name": args.game, "width": args.width, "height": args.height,
                  "board": args.board, "source": args.source, "target": args.target,
                  "max_candidates": args.max_candidates, "obstacles": args.obstacles, "length": args.length}
        if args.game == "doom_basic":
            config["decision_mode"] = args.doom_decision_mode
        episodes = []
        for index in range(args.episodes):
            seed = args.seed + index
            game = _game(config, args.graph)
            policy = (HTTPPolicy(args.url, timeout=args.timeout, api_key=os.environ.get(args.api_key_env))
                      if args.policy == "http" else TeacherPolicy(game) if args.policy == "teacher" else RandomPolicy(seed))
            episodes.append(run_episode(game, policy, seed=seed, max_steps=args.max_steps))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"schema_version": 1, "episodes": episodes}, indent=2) + "\n")
        result = {"trace": str(args.output), "policy": episodes[0]["policy"],
                  "is_model": episodes[0]["is_model"], "episodes": len(episodes),
                  "metrics": [trace["metrics"] for trace in episodes]}
    elif args.command == "replay":
        trace = json.loads(args.trace.read_text())
        result = {"replays": [replay_episode(_game(ep["game"], args.graph), ep) for ep in trace["episodes"]]}
    elif args.command == "build-data":
        result = build_game_dataset(args.output_dir, game=args.game, episodes=args.episodes,
                                    max_steps=args.max_steps, seed=args.seed)
    elif args.command == "build-control-data":
        result = build_control_dataset(args.output_dir, episodes=args.episodes,
                                       max_steps=args.max_steps, seed=args.seed)
    else:
        state = json.loads(args.state.read_text())
        if args.game == "trex" and args.legal_actions is not None:
            parser.error("T-Rex uses its declared three maneuver candidates; --legal-actions is for Mario")
        result = mario_request(state, args.legal_actions) if args.game == "mario" else trex_request(state)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
