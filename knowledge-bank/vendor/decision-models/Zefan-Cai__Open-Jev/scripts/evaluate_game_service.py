"""Bounded learned-HTTP versus random/teacher game rollouts on paired seeds.

This is a small integration evaluation, not an official-game benchmark or a
guaranteed training holdout. Teachers are separate code baselines, never model
fallbacks. Every attempted episode is saved, including incomplete failures.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import statistics
from urllib.parse import urlsplit, urlunsplit

from jev.api import candidate_prompts, compile_request
from jev.data import _hash
from jev.doom_control import DECISION_MODES
from jev.games import (DoomBasic, HTTPPolicy, RandomPolicy, Snake, TeacherPolicy,
                       TilePlatformer, TrexRunner, WikiRacing, run_episode)


LEARNED_METHODS = {"lora_decision_head", "pretrained_yes_minus_no_no_training"}
DEFAULT_GAMES = ("snake", "trex_runner", "tile_platformer", "wikiracing")
ALL_GAMES = (*DEFAULT_GAMES, "doom_basic")


def normalize_endpoint(endpoint):
    parsed = urlsplit(endpoint)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("endpoint must be an HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("use the API-key environment variable for authentication, not endpoint URL credentials or query parameters")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path if parsed.path not in ("", "/") else "/v1/inference", "", ""))


def service_identity(response, request, *, expected_model=None, expected_method=None):
    model, metadata = response.get("model"), response.get("metadata")
    if not isinstance(model, str) or not model or not isinstance(metadata, dict):
        raise ValueError("model response lacks model identity or metadata")
    json.dumps(metadata, allow_nan=False)
    method, temperature = metadata.get("method"), metadata.get("temperature")
    if method not in LEARNED_METHODS:
        raise ValueError("service is not an accepted learned scorer")
    if expected_model is not None and model != expected_model:
        raise ValueError("model identity differs from --expected-model")
    if expected_method is not None and method != expected_method:
        raise ValueError("scorer method differs from --expected-method")
    if type(temperature) not in (int, float) or not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("service temperature must be finite and positive")
    if set(response["answers"]) != set(request["questions"]):
        raise ValueError("service must return exactly the submitted game questions")
    candidate_count = sum(len(candidate_prompts(record)) for record in compile_request(**request))
    if metadata.get("candidate_sequences") != candidate_count:
        raise ValueError("service candidate count differs from the request")
    identity = {"model": model, "method": method, "temperature": temperature}
    for field in ("checkpoint_sha256", "base_revision", "code_commit"):
        if field in metadata:
            value = metadata[field]
            if not isinstance(value, str) or not value:
                raise ValueError(f"invalid service provenance field: {field}")
            if field == "checkpoint_sha256" and not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError("checkpoint_sha256 must be a SHA-256 hex digest")
            identity[field] = value
    return identity


class AuditedHTTPPolicy(HTTPPolicy):
    def __init__(self, endpoint, tracker, *, expected_model=None, expected_method=None, **kwargs):
        super().__init__(endpoint, **kwargs)
        self.tracker, self.responses = tracker, []
        self.verified_identity = None
        self.expected_model, self.expected_method = expected_model, expected_method

    def infer(self, request):
        response = super().infer(request)
        # Preserve even malformed numeric values as text inside valid trace JSON.
        # This is the parsed response reserialized, not a claim of raw wire bytes.
        self.responses.append({"request_sha256": _hash(request),
                               "response_json": json.dumps(response, ensure_ascii=False, allow_nan=True)})
        identity = service_identity(response, request, expected_model=self.expected_model,
                                    expected_method=self.expected_method)
        if self.tracker.get("identity") is not None and identity != self.tracker["identity"]:
            raise ValueError("model, method, calibration or checkpoint/code identity changed during evaluation")
        self.tracker["identity"] = identity
        self.verified_identity = identity
        return response


def make_game(name, graph_path, doom_decision_mode="combined-v1"):
    if name == "snake":
        return Snake()
    if name == "trex_runner":
        return TrexRunner()
    if name == "tile_platformer":
        return TilePlatformer()
    if name == "doom_basic":
        return DoomBasic(doom_decision_mode)
    if name == "wikiracing":
        return WikiRacing(json.loads(Path(graph_path).read_text()), "Computer", "Physics")
    raise ValueError("unknown evaluation game")


def _mean(values):
    return statistics.mean(values) if values else None


def summarize(episodes, games, seeds):
    report = {}
    for name in games:
        paired, by_policy = {}, {}
        for seed in seeds:
            entries = [e for e in episodes if e["game"] == name and e["seed"] == seed]
            hashes = [e.get("initial_state_sha256") for e in entries]
            paired[str(seed)] = len(set(hashes)) == 1 if len(hashes) == 3 and all(hashes) else None
        for policy in ("model", "random", "teacher"):
            chosen = [e for e in episodes if e["game"] == name and e["policy"] == policy]
            valid = [e for e in chosen if e["valid"]]
            successes = [e["metrics"]["success"] for e in valid if "success" in e["metrics"]]
            numeric_native = {}
            for field in ("food_collected", "obstacles_cleared", "progress_tiles", "engine_total_reward", "elapsed_tics"):
                values = [e["metrics"][field] for e in valid if field in e["metrics"]]
                if values:
                    numeric_native[field] = _mean(values)
            by_policy[policy] = {
                "attempted": len(chosen), "valid": len(valid), "errors": len(chosen) - len(valid),
                "stopping_reasons": dict(Counter(e["metrics"]["stop_reason"] for e in chosen)),
                "native_successes": sum(successes) if successes else None,
                "native_success_outcomes_observed": len(successes),
                "native_success_rate_among_valid_with_outcome": _mean(successes),
                "mean_steps_valid": _mean([e["metrics"]["steps"] for e in valid]),
                "mean_reward_valid": _mean([e["metrics"]["total_reward"] for e in valid]),
                "mean_native_outcomes_valid": numeric_native,
                "decision_timing_kind": "learned HTTP round trip" if policy == "model" else "local baseline code",
                "mean_episode_decision_latency_ms_valid": _mean([e["timing"]["mean_decision_latency_ms"] for e in valid if e["timing"]["mean_decision_latency_ms"] is not None]),
                "mean_episode_environment_latency_ms_valid": _mean([e["timing"]["mean_environment_latency_ms"] for e in valid if e["timing"]["mean_environment_latency_ms"] is not None]),
            }
        report[name] = {"paired_initial_states_match": paired, "policies": by_policy}
    return report


def run_evaluation(output_dir, *, endpoint="http://127.0.0.1:8791/v1/inference",
                   seeds=(42, 43, 44), max_steps=40, games=DEFAULT_GAMES,
                   graph_path=None, timeout=60, api_key=None,
                   expected_model=None, expected_method=None, doom_decision_mode="combined-v1"):
    endpoint = normalize_endpoint(endpoint)
    if (not seeds or len(set(seeds)) != len(seeds)
            or any(type(seed) is not int or not 0 <= seed < 1_000_000 for seed in seeds)):
        raise ValueError("seeds must be distinct integers in [0, 1000000)")
    if not games or len(set(games)) != len(games) or not set(games) <= set(ALL_GAMES):
        raise ValueError("choose distinct supported games")
    if doom_decision_mode not in DECISION_MODES:
        raise ValueError("unknown Doom decision mode")
    if type(max_steps) is not int or max_steps < 1 or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("max_steps and timeout must be positive")
    graph_path = Path(graph_path or Path(__file__).resolve().parents[1] / "examples/games/wiki-graph.json")
    output = Path(output_dir)
    if (output / "report.json").exists() or (output / "configuration.json").exists() or (output / "trajectories").exists():
        raise ValueError("output directory already contains game evaluation artifacts; choose a fresh directory")
    (output / "trajectories").mkdir(parents=True, exist_ok=True)
    configuration = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "endpoint": endpoint,
                     "seeds": list(seeds), "max_steps": max_steps, "games": list(games),
                     "expected_model": expected_model, "expected_method": expected_method,
                     "timeout_seconds": timeout, "policy_order": ["model", "random", "teacher"],
                     "wiki_graph_sha256": _hash(json.loads(graph_path.read_text())) if "wikiracing" in games else None,
                     "scope": "Paired seeded integration rollouts; seeds/layouts are not guaranteed held out from training. Local simplified games and tiny Wiki fixture, not original-game benchmark scores.",
                     "teacher_role": "Separately evaluated code baseline; never invoked to repair model output or scored as ground-truth action accuracy.",
                     "timing_scope": "Policy timing excludes environment stepping. Model policy includes HTTP and scorer work; baseline policies measure local code. No proprietary Jev latency comparison."}
    if "doom_basic" in games:
        configuration["doom_decision_mode"] = doom_decision_mode
    (output / "configuration.json").write_text(json.dumps(configuration, indent=2) + "\n")
    episodes, tracker = [], {}
    for name in games:
        for seed in seeds:
            for policy_name in ("model", "random", "teacher"):
                trace, policy = {}, None
                try:
                    game = make_game(name, graph_path, doom_decision_mode)
                    policy = (AuditedHTTPPolicy(endpoint, tracker, timeout=timeout, api_key=api_key,
                                               expected_model=expected_model, expected_method=expected_method)
                              if policy_name == "model" else RandomPolicy(seed) if policy_name == "random" else TeacherPolicy(game))
                    run_episode(game, policy, seed=seed, max_steps=max_steps, trace=trace)
                    valid = True
                except Exception as error:
                    valid = False
                    if trace.get("metrics", {}).get("stop_reason") != "error":
                        if "metrics" in trace:
                            trace["partial_metrics"] = trace["metrics"]
                        steps = trace.get("steps", [])
                        trace["metrics"] = {"steps": len(steps), "stop_reason": "error",
                                            "total_reward": sum(step["reward"] for step in steps)}
                    trace["error"] = {"type": type(error).__name__, "message": str(error)}
                trace.update(evaluation_policy=policy_name, evaluation_game=name, evaluation_seed=seed,
                             valid=valid, service_identity=policy.verified_identity if isinstance(policy, AuditedHTTPPolicy) else None)
                if isinstance(policy, AuditedHTTPPolicy):
                    trace["http_responses"] = policy.responses
                path = output / "trajectories" / f"{name}-{policy_name}-seed-{seed}.json"
                path.write_text(json.dumps(trace, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
                steps = trace.get("steps", [])
                entry = {"game": name, "policy": policy_name, "seed": seed, "valid": valid,
                         "trace": str(path.relative_to(output)), "metrics": trace["metrics"],
                         "initial_state_sha256": _hash(trace["initial_state"]) if "initial_state" in trace else None,
                         "timing": {"mean_decision_latency_ms": _mean([s["latency_ms"] for s in steps]),
                                    "mean_environment_latency_ms": _mean([s["environment_latency_ms"] for s in steps])}}
                if "error" in trace:
                    entry["error"] = trace["error"]
                episodes.append(entry)
                # Save after every attempt so interruption does not lose earlier episodes.
                report = {"configuration": configuration, "service_identity": tracker.get("identity"),
                          "requested_episodes": len(games) * len(seeds) * 3,
                          "attempted_episodes": len(episodes), "error_episodes": sum(not e["valid"] for e in episodes),
                          "complete": len(episodes) == len(games) * len(seeds) * 3,
                          "by_game": summarize(episodes, games, seeds), "episodes": episodes}
                (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8791/v1/inference")
    parser.add_argument("--seeds", default="42,43,44", help="comma-separated distinct episode seeds")
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--games", nargs="+", choices=ALL_GAMES, default=list(DEFAULT_GAMES))
    parser.add_argument("--include-doom", action="store_true")
    parser.add_argument("--doom-decision-mode", choices=DECISION_MODES, default="combined-v1")
    parser.add_argument("--graph", dest="graph_path", type=Path)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--api-key-env", default="OPEN_JEV_API_KEY")
    parser.add_argument("--expected-model")
    parser.add_argument("--expected-method", choices=sorted(LEARNED_METHODS))
    parser.add_argument("--output-dir", required=True, type=Path)
    args = vars(parser.parse_args())
    try:
        args["seeds"] = tuple(int(value) for value in args["seeds"].split(","))
    except ValueError:
        parser.error("--seeds must contain comma-separated integers")
    if args.pop("include_doom") and "doom_basic" not in args["games"]:
        args["games"].append("doom_basic")
    args["api_key"] = os.environ.get(args.pop("api_key_env"))
    report = run_evaluation(**args)
    print(json.dumps({"output_dir": str(args["output_dir"]), "service_identity": report["service_identity"],
                      "attempted_episodes": report["attempted_episodes"], "error_episodes": report["error_episodes"],
                      "by_game": report["by_game"]}, ensure_ascii=False, indent=2))
    return 1 if report["error_episodes"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
