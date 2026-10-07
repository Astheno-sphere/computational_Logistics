"""Audit existing T-Rex train rows only; never generate states or read held-out rows."""
import argparse
import ast
from collections import Counter
import datetime
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def object_hash(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("trex-training-coverage.json"))
    args = parser.parse_args()
    source = ROOT / "jev/games.py"
    tree = ast.parse(source.read_text())
    collision = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "trex_collision")
    scope = {"math": math}
    # Execute only the pure collision function on EXISTING train observations.
    # Importing game/model packages and sampling hypothetical states are unnecessary.
    exec(compile(ast.Module(body=[collision], type_ignores=[]), str(source), "exec"), scope)
    evidence, manifests, rows = {}, {}, None
    for name in ("control-games-v1", "release-v1", "release-v2", "browser-drone-expansion-v1"):
        directory = ROOT / "data" / name
        manifest = json.loads((directory / "manifest.json").read_text())
        manifests[name] = manifest
        digest, selected = hashlib.sha256(), []
        with (directory / "train.jsonl").open("rb") as stream:
            for raw in stream:
                digest.update(raw)
                if b"trex_runner-v1" in raw:
                    row = json.loads(raw)
                    if row["source"] == "trex_runner-v1":
                        assert row["split"] == "train"
                        selected.append(row)
        expected = manifest["files_sha256"]["train.jsonl"] if name == "control-games-v1" else manifest["sha256"]["train"]
        assert digest.hexdigest() == expected
        assert len(selected) == 28
        if rows is None:
            rows = selected
        else:
            assert selected == rows
        evidence[name] = {"train_path": f"data/{name}/train.jsonl", "train_sha256": digest.hexdigest(),
                          "manifest_path": f"data/{name}/manifest.json", "manifest_sha256": file_hash(directory / "manifest.json"),
                          "trex_train_rows": len(selected), "trex_rows_ordered_canonical_sha256": object_hash(selected)}
    config = manifests["control-games-v1"]["configuration"]
    assert config["seed"] == 42 and config["episodes_per_game"] == 100 and config["max_steps"] == 40
    assert manifests["control-games-v1"]["summary"]["sources"]["trex_runner-v1"] == 36
    counts = {name: Counter() for name in ("label", "speed", "speed_mode", "motion", "obstacle_configuration", "safe_action_count", "safe_action_set")}
    episodes, geometries, questions, observations, buckets = [], set(), set(), set(), []
    unsafe_targets = no_safe_fallbacks = preference_matches = 0
    for row in rows:
        state, meta = row["state"], row["metadata"]
        obstacle = state["target_obstacle"]
        assert row["kind"] == "choice" and row["options"] == ["jump_short", "jump_full", "duck", "keep_running"]
        assert row["target"].count(1.0) == 1 and sum(row["target"]) == 1
        label = row["options"][row["target"].index(1.0)]
        safe = [action for action in row["options"] if not scope["trex_collision"](state, action)]
        preferred = ("keep_running" if obstacle["flight_path"] == "clears_running_dinosaur" else
                     "duck" if obstacle["flight_path"] == "blocks_running_only" else
                     "jump_short" if obstacle["kind"] == "small_cactus" and obstacle["group_size"] == "single" else "jump_full")
        unsafe_targets += label not in safe
        no_safe_fallbacks += not safe
        preference_matches += label == preferred
        for name, value in (("label", label), ("speed", str(state["current_speed"])), ("speed_mode", state["speed_mode"]),
                            ("motion", state["dinosaur_motion_when_observed"]),
                            ("obstacle_configuration", "/".join(obstacle[k] for k in ("kind", "group_size", "flight_path"))),
                            ("safe_action_count", str(len(safe))), ("safe_action_set", ",".join(safe))):
            counts[name][value] += 1
        episodes.append(meta["provenance"]["episode_index"])
        geometries.add(canonical(state["runner_geometry"]))
        questions.add(row["question"])
        observations.add(object_hash(state))
        assert row["group_id"] == "trex_runner-v1:" + object_hash(state)[:24]
        bucket = int(object_hash([42, row["group_id"]])[:16], 16) % 10000
        assert bucket < 8000
        buckets.append(bucket)
    assert len(observations) == 28 and len(geometries) == len(questions) == 1
    assert unsafe_targets == no_safe_fallbacks == 0 and preference_matches == 28
    assert all("jump_full" in actions.split(",") for actions in counts["safe_action_set"])
    report = {
        "schema_version": 1, "audited_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "status": "passed",
        "scope": "Read-only source, manifest and train-file analysis. No test/OOD/JF100 row or label reads, no model loading, no new states/data, and no remote operations.",
        "code": {"jev/games.py": {"sha256": file_hash(source), "references": {"obstacle_configuration": 542, "collision_rule": 554, "runtime_state": 585, "public_browser_adapter": 783, "deduplication": 899}},
                 "jev/data.py": {"sha256": file_hash(ROOT / "jev/data.py"), "references": {"group_hash_split": 35}},
                 "reproduction_script": {"path": "reports/data-manifests/check_trex_training_coverage.py", "sha256": file_hash(Path(__file__))}},
        "train_files": evidence,
        "mechanism": {"generator_configuration": config, "speed_values": [6, 8, 10, 12],
                      "obstacle_configurations": {"small_cactus_groups": 3, "large_cactus_groups": 3, "pterodactyl_flight_paths_single_group": 3},
                      "maximum_distinct_visible_states_from_code": 36, "manifest_total_trex_rows": 36, "train_rows": 28,
                      "deduplication": "Global exact runtime state/questions request hash; seed, episode and teacher provenance are excluded from model inputs.",
                      "split": "Label-independent group hash with an 80% train interval; all 28 train group hashes independently match.",
                      "train_hash_bucket_range": [min(buckets), max(buckets)],
                      "episode_limit": "Each local episode has at most 12 obstacles despite max_steps=40; random behavior may terminate earlier. The observed manifest nevertheless reaches the 36-state ceiling.",
                      "teacher_filter": "Teacher chooses labels but does not discard observations. No no-safe-action fallback occurs among these 28 train rows.",
                      "conclusion": "Current finite runtime is saturated. More seeds/episodes, longer rollouts or retaining duplicates do not add visible-state coverage; no generator fix is indicated."},
        "train_only_findings": {"counts": {key: dict(value) for key, value in counts.items()}, "distinct_visible_states": 28,
                                "unique_questions": 1, "unique_geometries": 1, "geometry": json.loads(next(iter(geometries))),
                                "first_seen_episode_range": [min(episodes), max(episodes)], "positive_unsafe_targets": unsafe_targets,
                                "declared_preference_matches": preference_matches, "no_safe_fallbacks": no_safe_fallbacks,
                                "jump_full_safe_on_existing_train_states": 28,
                                "safety_scope": "Collision checks used only the existing 28 train states. Multiple safe actions in 11 rows receive a single declared-preference target; this does not establish action safety outside train.",
                                "training_share_percent": {"release-v2": 100 * 28 / manifests["release-v2"]["counts"]["train"],
                                                           "browser-drone-expansion-v1": 100 * 28 / manifests["browser-drone-expansion-v1"]["counts"]["train"]},
                                "missing_dimensions": ["slow speed mode", "jumping/ducking observation phases", "variable geometry and distances", "continuous speed/acceleration", "inter-obstacle gaps and action latency", "browser adapter's separate maneuver and jump_profile questions"]},
        "unimplemented_future_options": [
            {"option": "Independent browser-format bridge", "status": "not implemented",
             "proposal": "A separate version could adapt only the existing 28 train observations to trex_request's two questions, producing 56 task rows over the same 28 states.",
             "coverage_claim": "Representation coverage only; zero new physical states. This would not modify current frozen mixtures or active training.",
             "validation": ["All source IDs must belong to these original train rows; never move reserved states into training.",
                            "Match the adapter exactly: maneuver has three candidates, jump_profile has two; preserve question IDs and keep both questions in one scene group.",
                            "Labels must follow the existing train observations and declared conditional question semantics; disclose that they are not measured browser physics.",
                            "Count both unique states and task rows; do not report 56 rows as 56 new states."]},
            {"option": "Independent browser trajectory corpus", "status": "not implemented",
             "proposal": "Use separately collected browser/controller trajectories when real dynamics are in scope; declare physically valid motion, distance, speed and timing fields and a controller-compatible oracle.",
             "validation": ["Freeze new scene/episode groups before evaluation and keep related variants together.",
                            "Check state and action coverage, valid labels and duplicate/group leakage independently; report per-action safety and closed-loop collision/success metrics separately from preference accuracy.",
                            "Leave existing frozen data, held-out labels and the running 27B job unchanged."]}],
        "limitations": ["The analysis explains dataset cardinality and train coverage, not a causal explanation of model errors.",
                        "No held-out behavior, actual Chrome physics, model performance or new-data benefit was evaluated."]}
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"status": "passed", "output": str(args.output), "sha256": file_hash(args.output), "train_rows": 28, "finite_state_ceiling": 36}))


if __name__ == "__main__":
    main()
