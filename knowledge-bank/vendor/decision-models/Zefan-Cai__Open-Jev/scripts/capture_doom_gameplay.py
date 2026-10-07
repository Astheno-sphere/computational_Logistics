"""Replay a saved model episode in ViZDoom and capture every available game tic.

CPU only. No model is loaded, no actions are selected, and every decision
boundary must match the saved observation, reward and terminal flag exactly.
Requires the original ViZDoom 1.2.4 / Freedoom basic environment and Pillow.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-checkout", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    sys.path.insert(0, str(args.source_checkout.resolve()))
    from PIL import Image
    from jev.case_doom import _open_game, episode_spec, observe, engine_provenance
    import vizdoom

    trace = json.loads(args.trace.read_bytes())
    if trace["game"]["name"] != "doom_basic" or not trace["is_model"] or not trace["valid"]:
        raise ValueError("Expected a valid saved model ViZDoom episode")
    args.output.mkdir(parents=True, exist_ok=False)
    frames = args.output / "frames"
    frames.mkdir()
    spec = episode_spec(0, trace["seed"])
    game = _open_game(spec)
    captured, boundaries = [], []

    def save_frame(decision, tick):
        raw = game.get_state()
        if raw is None:
            return
        pixels = raw.screen_buffer
        if pixels.ndim == 3 and pixels.shape[0] in (3, 4):
            pixels = pixels.transpose(1, 2, 0)
        path = frames / f"{len(captured):05d}.png"
        Image.fromarray(pixels).convert("RGB").save(path)
        captured.append({"file": str(path.relative_to(args.output)), "decision": decision,
                         "action_tick": tick, "engine_tic": game.get_episode_time(),
                         "sha256": digest(path)})

    try:
        if observe(game, spec["frame_skip"]) != trace["initial_state"]:
            raise ValueError("Initial native game state differs from the saved episode")
        save_frame(0, 0)
        total_reward = 0.0
        for index, step in enumerate(trace["steps"]):
            if observe(game, spec["frame_skip"]) != step["request"]["state"]:
                raise ValueError(f"Before decision {index}, state differs")
            if step["answer"]["choice"] != step["action"]:
                raise ValueError(f"Decision {index} does not match the recorded model choice")
            movement, attack = step["action"].split("_")
            buttons = [movement == "left", movement == "right", attack == "attack"]
            reward, advanced = 0.0, 0
            for tick in range(spec["frame_skip"]):
                if game.is_episode_finished():
                    break
                reward += float(game.make_action(buttons, 1))
                advanced += 1
                save_frame(index + 1, tick + 1)
            terminal = bool(game.is_episode_finished())
            state = observe(game, spec["frame_skip"])
            if reward != step["reward"] or terminal != step["terminal"] or state != step["next_state"]:
                raise ValueError(f"Native replay differs at decision {index}")
            total_reward += reward
            boundaries.append({"index": index, "action": step["action"], "buttons": buttons,
                               "reward": reward, "terminal": terminal, "advanced_tics": advanced,
                               "state_reward_terminal_match": True})
        if total_reward != trace["metrics"]["total_reward"] or game.get_total_reward() != total_reward:
            raise ValueError("Episode total reward differs from the saved model run")
        report = {
            "status": "passed", "captured_at": datetime.now(timezone.utc).isoformat(),
            "presentation": "Native ViZDoom screen frames from exact saved model-action replay; no fresh inference.",
            "trace_sha256": digest(args.trace), "capture_script_sha256": digest(__file__),
            "seed": trace["seed"], "model_identity": trace["service_identity"],
            "environment": engine_provenance(), "episode_spec": spec, "frames": captured,
            "decision_boundaries": boundaries, "all_saved_decisions_replayed": True,
            "decision_count": len(boundaries), "total_reward": total_reward,
            "terminal": bool(game.is_episode_finished()), "kill_count": game.get_game_variable(vizdoom.GameVariable.KILLCOUNT),
            "goal": "Eliminate the target in the basic scenario.",
            "gpu_used": False, "frame_source": "game.get_state().screen_buffer",
            "limitations": ["Original 100-step 9B pilot checkpoint, not the completed full-pass model.",
                            "ViZDoom returns no screen buffer after terminal; the last available frame is retained before the outcome overlay.",
                            "Display may slow the complete sequence for readability; playback duration is not inference latency."],
        }
        (args.output / "capture.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({k: report[k] for k in ("status", "decision_count", "total_reward", "terminal", "kill_count", "gpu_used")}))
        print(json.dumps({"frames": len(captured), "output": str(args.output)}))
    finally:
        game.close()


if __name__ == "__main__":
    main()
