"""Independent, visible-rule drone snapshot controls; no flight or simulation.

The exact community adapter supplies Choice/Score/Noul questions. References
describe a disclosed geometric heuristic and observation-evidence criterion,
not real collision probabilities, physical target truth, or flight authority.
"""

import argparse
from collections import Counter
import copy
import hashlib
import json
import math
from pathlib import Path
import random

from .api import compile_request
from .community import DRONE_MANEUVERS, drone_request
from .data import _hash, _write_dataset, split_group


VERSION = "drone-control-v1"
FAMILIES = ("hold_course", "brake", "gap_left", "gap_right", "climb", "reacquire")
CONTROL_RULES = (
    "Synthetic snapshot policy, not flight instructions. Obstacles extend upward from the ground; "
    "ahead_m is surface separation and forward_speed_mps is measured in the route direction. "
    "An obstacle intersects the current course when abs(lateral_offset_m) <= width_m/2 + diameter_m/2 "
    "+ margin_m and top_altitude_m >= altitude_m - diameter_m/2 - margin_m. "
    "For each intersecting obstacle set closing=max(0, drone forward_speed_mps - obstacle forward_speed_mps), "
    "stopping_distance=closing*reaction_s + closing^2/(2*braking_deceleration_mps2) + margin_m, "
    "and TTC=ahead_m/closing (infinite when closing=0). Risk is level 2 if ahead_m <= stopping_distance "
    "or TTC <= imminent_ttc_s; otherwise level 1 if TTC <= caution_ttc_s or if ahead_m <= tight_clearance_range_m "
    "and either side gap is narrower than diameter_m+2*margin_m; otherwise level 0. "
    "The scene risk is the maximum obstacle level, or 0 with no intersecting obstacles. "
    "For level 2 choose brake. For level 1, a side gap is usable only if every risk-positive obstacle "
    "has gap width >= diameter_m+2*margin_m on that side and its gap maneuver is permitted. "
    "Choose the side with the larger minimum width, breaking exact ties with goal.preferred_gap. "
    "If neither side is usable, climb only when permitted and climb_clearance_verified=true, "
    "required_altitude=max(risk-positive top_altitude_m)+diameter_m/2+margin_m fits below "
    "ceiling_m-diameter_m/2-margin_m, and vertical_clearance_m >= max(0, required_altitude-altitude_m). "
    "Otherwise brake. At level 0, reacquire only for goal.task=follow_target when target-loss evidence "
    "is supported and reacquire is permitted; otherwise hold_course if permitted, else brake. "
    "Target-loss evidence is supported only when target.visible=false, seconds_unseen >= loss_grace_s, "
    "and at least failed_scan_count distinct history times within min(seconds_unseen, loss_evidence_window_s) "
    "show region_fully_visible=true and detected=false, with no detected=true history in that window. "
    "An occlusion timer alone never proves loss; this label is an evidence rule, not hidden physical truth. "
    "All legal actions are listed in permitted_maneuvers; brake is required as a fallback."
)


def _number(mapping, key, minimum=0, positive=False):
    value = mapping[key]
    if type(value) not in (int, float) or not math.isfinite(value) or (minimum is not None and value < minimum) or (positive and value <= 0):
        raise ValueError(f"{key} must be a finite number within the declared physical range")
    return value


def derive_decision(state):
    """Derive all three answers and an audit trace solely from model-visible state."""
    observation = state["observation"]
    policy, flight, target = (observation[key] for key in ("control_policy", "flight", "target"))
    legal, goal = observation["permitted_maneuvers"], observation["goal"]
    drone_request(observation, legal)
    if policy.get("rules") != CONTROL_RULES:
        raise ValueError("Synthetic drone observations must disclose the exact decision policy")
    if "brake" not in legal or goal.get("task") not in ("follow_target", "continue_route") or goal.get("preferred_gap") not in ("left", "right"):
        raise ValueError("Synthetic drone goals require a declared task, side preference, and brake fallback")
    values = {key: _number(policy, key, positive=True) for key in (
        "margin_m", "reaction_s", "braking_deceleration_mps2", "imminent_ttc_s", "caution_ttc_s",
        "tight_clearance_range_m", "loss_grace_s", "loss_evidence_window_s")}
    if values["caution_ttc_s"] <= values["imminent_ttc_s"]:
        raise ValueError("Caution TTC must exceed imminent TTC")
    required_scans = policy["failed_scan_count"]
    if type(required_scans) is not int or required_scans < 1:
        raise ValueError("failed_scan_count must be a positive integer")
    diameter = _number(flight, "diameter_m", positive=True)
    speed = _number(flight, "forward_speed_mps")
    altitude = _number(flight, "altitude_m")
    ceiling = _number(flight, "ceiling_m")
    upward_clearance = _number(flight, "vertical_clearance_m")
    if type(flight.get("climb_clearance_verified")) is not bool:
        raise ValueError("climb_clearance_verified must be an observed boolean")
    radius, margin = diameter / 2, values["margin_m"]
    required_width = diameter + 2 * margin
    obstacle_trace, active = [], []
    for obstacle in observation["obstacles"]:
        distance = _number(obstacle, "ahead_m")
        offset = _number(obstacle, "lateral_offset_m", minimum=None)
        width = _number(obstacle, "width_m", positive=True)
        top = _number(obstacle, "top_altitude_m")
        obstacle_speed = _number(obstacle, "forward_speed_mps", minimum=None)
        left = _number(obstacle, "left_gap_width_m")
        right = _number(obstacle, "right_gap_width_m")
        intersects = abs(offset) <= width / 2 + radius + margin and top >= altitude - radius - margin
        closing = max(0, speed - obstacle_speed)
        stopping = closing * values["reaction_s"] + closing ** 2 / (2 * values["braking_deceleration_mps2"]) + margin
        ttc = distance / closing if closing else math.inf
        risk = 0
        if intersects:
            if distance <= stopping or ttc <= values["imminent_ttc_s"]:
                risk = 2
            elif ttc <= values["caution_ttc_s"] or (distance <= values["tight_clearance_range_m"] and min(left, right) < required_width):
                risk = 1
        obstacle_trace.append({"obstacle_id": obstacle["id"], "intersects_course": intersects,
                               "closing_speed_mps": closing, "stopping_distance_m": stopping,
                               "time_to_collision_s": ttc if math.isfinite(ttc) else None, "risk_level": risk})
        if risk:
            active.append(obstacle)
    risk = max((item["risk_level"] for item in obstacle_trace), default=0)
    window = min(target["seconds_unseen"], values["loss_evidence_window_s"])
    negative_times, positive_times = set(), set()
    if not isinstance(target.get("history"), list):
        raise ValueError("Target history must be an observed list")
    for scan in target["history"]:
        age = _number(scan, "seconds_ago")
        if type(scan.get("region_fully_visible")) is not bool or type(scan.get("detected")) is not bool:
            raise ValueError("Target history requires measured visibility/detection booleans")
        if age <= window:
            if scan["detected"]:
                positive_times.add(age)
            elif scan["region_fully_visible"]:
                negative_times.add(age)
    lost = (not target["visible"] and target["seconds_unseen"] >= values["loss_grace_s"]
            and len(negative_times) >= required_scans and not positive_times)
    side_widths = {side: min((item[f"{side}_gap_width_m"] for item in active), default=None) for side in ("left", "right")}
    required_altitude = max((item["top_altitude_m"] for item in active), default=altitude - radius - margin) + radius + margin
    can_climb = (bool(active) and "climb" in legal and flight["climb_clearance_verified"]
                 and required_altitude <= ceiling - radius - margin
                 and upward_clearance >= max(0, required_altitude - altitude))
    if risk == 2:
        maneuver = "brake"
    elif risk == 1:
        sides = [side for side in ("left", "right") if f"gap_{side}" in legal and side_widths[side] >= required_width]
        if sides:
            side = max(sides, key=lambda side: (side_widths[side], side == goal["preferred_gap"]))
            maneuver = f"gap_{side}"
        else:
            maneuver = "climb" if can_climb else "brake"
    elif goal["task"] == "follow_target" and lost and "reacquire" in legal:
        maneuver = "reacquire"
    else:
        maneuver = "hold_course" if "hold_course" in legal else "brake"
    answers = {"maneuver": maneuver, "risk": str(risk), "target_truly_lost": "true" if lost else "false"}
    trace = {"obstacles": obstacle_trace, "required_gap_width_m": required_width,
             "minimum_active_gap_widths_m": side_widths,
             "required_climb_altitude_m": required_altitude if active else None,
             "climb_geometry_and_permission_satisfied": can_climb,
             "qualifying_failed_scan_times_s": sorted(negative_times), "positive_scan_times_s": sorted(positive_times)}
    return answers, trace


def drone_teacher(state):
    return derive_decision(state)[0]


def _opaque(rng):
    return "n" + f"{rng.getrandbits(80):020x}"


def _request(observation):
    return drone_request(observation, observation["permitted_maneuvers"])


def _set_loss(observation, mode, ood):
    target = observation["target"]
    ages = (4.0, 6.0) if ood else (0.5, 1.5)
    if mode == "visible":
        target.update(visible=True, seconds_unseen=0,
                      history=[{"seconds_ago": 0, "region_fully_visible": True, "detected": True}])
    else:
        unseen = 24.0 if ood else 8.0
        if mode == "brief":
            unseen, ages = 2.0, (0.5, 1.5)
        target.update(visible=False, seconds_unseen=unseen,
                      history=[{"seconds_ago": age, "region_fully_visible": mode != "occluded", "detected": False} for age in ages])


def _geometry(observation, barrier_ids, mode):
    policy, flight = observation["control_policy"], observation["flight"]
    required_width = flight["diameter_m"] + 2 * policy["margin_m"]
    for obstacle in observation["obstacles"]:
        if obstacle["id"] not in barrier_ids:
            continue
        closing = max(0, flight["forward_speed_mps"] - obstacle["forward_speed_mps"])
        stopping = closing * policy["reaction_s"] + closing ** 2 / (2 * policy["braking_deceleration_mps2"]) + policy["margin_m"]
        critical = max(stopping, closing * policy["imminent_ttc_s"])
        obstacle["ahead_m"] = (critical / 2 if mode == "imminent" else
                                closing * policy["caution_ttc_s"] + critical + policy["tight_clearance_range_m"] + 2 if mode == "distant" else
                                (critical + closing * policy["caution_ttc_s"]) / 2)
        for side in ("left", "right"):
            obstacle[f"{side}_gap_width_m"] = required_width + 0.8 if mode in ("distant", "tie", side) else required_width / 2


def _scene(index, seed, ood):
    rng = random.Random(int(_hash([VERSION, index, seed]), 16))
    policy = {"rules": CONTROL_RULES, "margin_m": 0.2, "reaction_s": 0.25,
              "braking_deceleration_mps2": 3, "imminent_ttc_s": 1, "caution_ttc_s": 4,
              "tight_clearance_range_m": 3, "loss_grace_s": 3, "loss_evidence_window_s": 30,
              "failed_scan_count": 2}
    flight = {"forward_speed_mps": round(rng.uniform(4, 7) if ood else rng.uniform(0.8, 2.5), 5),
              "diameter_m": round(rng.uniform(0.9, 1.3) if ood else rng.uniform(0.3, 0.7), 5),
              "altitude_m": round(rng.uniform(3.5, 4.5) if ood else rng.uniform(1.5, 2.5), 5),
              "ceiling_m": 10 if ood else 7, "vertical_clearance_m": 4,
              "climb_clearance_verified": False}
    barriers = [{"id": _opaque(rng), "ahead_m": 10, "lateral_offset_m": round(rng.uniform(-0.2, 0.2), 5),
                 "width_m": round(rng.uniform(3.5, 5) if ood else rng.uniform(1, 3), 5),
                 "top_altitude_m": flight["altitude_m"] + round(rng.uniform(0.4, 1), 5),
                 "forward_speed_mps": round(rng.uniform(-1, 1.5) if ood else rng.uniform(-0.3, 0.5), 5),
                 "left_gap_width_m": 2, "right_gap_width_m": 2} for _ in range(2 if ood else 1)]
    barrier_ids = {item["id"] for item in barriers}
    distractor = copy.deepcopy(barriers[0])
    distractor.update(id=_opaque(rng), lateral_offset_m=20, ahead_m=0.1)
    obstacles = [*barriers, distractor]
    if ood:
        low = copy.deepcopy(barriers[0])
        low.update(id=_opaque(rng), ahead_m=0.1, top_altitude_m=0.1)
        obstacles.append(low)
    rng.shuffle(obstacles)
    legal = [name for name in DRONE_MANEUVERS if name != "climb"]
    rng.shuffle(legal)
    observation = {"observation_id": _opaque(rng), "goal": {"task": "follow_target", "preferred_gap": rng.choice(("left", "right"))},
                   "target": {}, "obstacles": obstacles, "flight": flight,
                   "permitted_maneuvers": legal, "control_policy": policy}
    family = FAMILIES[index % len(FAMILIES)]
    _set_loss(observation, "supported" if family == "reacquire" else "visible", ood)
    _geometry(observation, barrier_ids, {"hold_course": "distant", "reacquire": "distant", "brake": "imminent",
                                       "gap_left": "left", "gap_right": "right", "climb": "narrow"}[family])
    if family == "climb":
        flight["climb_clearance_verified"] = True
        legal.append("climb")
        rng.shuffle(legal)
    return observation, {"barrier_ids": barrier_ids, "family": family, "ood": ood}, rng


def _variants(observed, spec, rng):
    def fresh(mode=None):
        observation = copy.deepcopy(observed)
        observation["observation_id"] = _opaque(rng)
        if mode:
            _geometry(observation, spec["barrier_ids"], mode)
        return observation

    def no_climb(observation):
        observation["flight"]["climb_clearance_verified"] = False
        observation["permitted_maneuvers"] = [item for item in observation["permitted_maneuvers"] if item != "climb"]

    yield "observed", observed
    for name, mode in (("imminent_geometry", "imminent"), ("distant_geometry", "distant"),
                       ("left_gap_geometry", "left"), ("right_gap_geometry", "right")):
        yield name, fresh(mode)
    climb = fresh("narrow")
    climb["flight"]["climb_clearance_verified"] = True
    if "climb" not in climb["permitted_maneuvers"]:
        climb["permitted_maneuvers"].append("climb")
    rng.shuffle(climb["permitted_maneuvers"])
    yield "climb_available", climb
    unverified = copy.deepcopy(climb)
    unverified["observation_id"] = _opaque(rng)
    no_climb(unverified)
    yield "climb_unverified", unverified
    required = max(item["top_altitude_m"] for item in climb["obstacles"] if item["id"] in spec["barrier_ids"]) + climb["flight"]["diameter_m"] / 2 + climb["control_policy"]["margin_m"]
    low_ceiling = copy.deepcopy(climb)
    low_ceiling["observation_id"] = _opaque(rng)
    low_ceiling["flight"]["ceiling_m"] = required + climb["flight"]["diameter_m"] / 2 + climb["control_policy"]["margin_m"] - 0.1
    yield "climb_height_limit", low_ceiling
    low_clearance = copy.deepcopy(climb)
    low_clearance["observation_id"] = _opaque(rng)
    low_clearance["flight"]["vertical_clearance_m"] = required - climb["flight"]["altitude_m"] - 0.1
    yield "climb_clearance_limit", low_clearance
    tie = fresh("tie")
    for side in ("left", "right"):
        goal_variant = copy.deepcopy(tie)
        goal_variant["goal"]["preferred_gap"] = side
        yield f"side_goal_{side}", goal_variant
    distant = fresh("distant")
    for name, mode in (("brief_occlusion", "brief"), ("occlusion_timer_only", "occluded"),
                       ("observed_failed_scans", "supported"), ("positive_reappearance", "visible")):
        visibility = copy.deepcopy(distant)
        visibility["observation_id"] = _opaque(rng)
        _set_loss(visibility, mode, spec["ood"])
        yield name, visibility
        if mode == "supported":
            route = copy.deepcopy(visibility)
            route["goal"]["task"] = "continue_route"
            yield "route_goal_counterfactual", route
    unavailable = fresh("left")
    no_climb(unavailable)
    unavailable["permitted_maneuvers"].remove("gap_left")
    yield "missing_gap_action", unavailable
    forced = fresh()
    forced["permitted_maneuvers"] = ["brake"]
    yield "single_permitted_maneuver", forced
    permuted = fresh()
    for item in permuted["obstacles"]:
        item["id"] = _opaque(rng)
    rng.shuffle(permuted["obstacles"])
    rng.shuffle(permuted["permitted_maneuvers"])
    rng.shuffle(permuted["target"]["history"])
    yield "id_and_order_permutation", permuted


def generate_cases(groups=500, seed=42, ood_groups=None):
    if type(groups) is not int or groups < 1:
        raise ValueError("groups must be a positive integer")
    ood_groups = groups // 5 if ood_groups is None else ood_groups
    if type(ood_groups) is not int or not 0 <= ood_groups < groups:
        raise ValueError("ood_groups must be a nonnegative integer smaller than groups")
    cases = []
    for index in range(groups):
        ood = index >= groups - ood_groups
        group = VERSION + ":parent:" + _hash([seed, index])[:24]
        split = "ood" if ood else split_group(group, seed)
        observation, spec, rng = _scene(index, seed, ood)
        seen = set()
        for variant, observation in _variants(observation, spec, rng):
            comparison = copy.deepcopy(observation)
            comparison.pop("observation_id")
            fingerprint = _hash(comparison)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            request = _request(observation)
            answers, derivation = derive_decision(request["state"])
            cases.append({"id": group + ":" + variant, "group_id": group, "split": split,
                          "source": VERSION, "variant": variant, "control_family": spec["family"],
                          "template_id": VERSION + ("/ood_multiple_barriers_scaled" if ood else "/id_single_barrier"),
                          "request": request, "answers": answers, "derivation": derivation,
                          "provenance": {"type": "synthetic", "generator_version": VERSION, "seed": seed,
                                         "group_index": index, "variant": variant, "license": "CC0-1.0",
                                         "split_policy": "parent_geometry_and_all_counterfactuals_grouped; dedicated_scaled_multi_barrier_ood"}})
    return cases


def records_from_cases(cases):
    rows, counts = [], Counter()
    for case in cases:
        request = case["request"]
        expected = _request(request["state"]["observation"])
        compiled = compile_request(**request)
        if request != expected or compiled != compile_request(**expected):
            raise ValueError("Drone case must preserve the exact runtime request and candidate ordering")
        answers, derivation = derive_decision(request["state"])
        if answers != case["answers"] or derivation != case["derivation"]:
            raise ValueError("Saved drone references disagree with visible-state derivation")
        for record in compiled:
            if len(record["options"]) == 1:
                counts["forced_single_candidate_maneuvers_omitted"] += 1
                continue
            selected = answers[record["id"]]
            if selected not in record["answer_keys"]:
                raise ValueError("Drone answer is absent from runtime candidates")
            metadata = {"family": "policy", "case_name": "drone", "case_id": case["id"],
                        "question_id": record["id"], "template_id": case["template_id"],
                        "variant": case["variant"], "control_family": case["control_family"],
                        "target_basis": "Disclosed visible-state geometry/evidence rule; no physical outcomes or calibrated risk claim.",
                        "provenance": copy.deepcopy(case["provenance"])}
            if record["kind"] == "score":
                metadata["score_values"] = [0, 1, 2]
            rows.append({"id": case["id"] + ":" + record["id"], "group_id": case["group_id"],
                         "split": case["split"], "source": VERSION, "state": record["state"],
                         "question": record["question"], "kind": record["kind"], "options": record["options"],
                         "target": [float(key == selected) for key in record["answer_keys"]], "metadata": metadata})
            counts["emitted_" + record["kind"] + "_rows"] += 1
    return rows, dict(counts)


def build_dataset(output_dir, groups=500, seed=42, ood_groups=None):
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory is not empty; choose a separate drone dataset directory")
    cases = generate_cases(groups, seed, ood_groups)
    rows, supervision = records_from_cases(cases)
    manifest = _write_dataset(rows, output, {"type": "synthetic", "generator_version": VERSION,
        "groups": groups, "ood_groups": groups // 5 if ood_groups is None else ood_groups, "seed": seed,
        "runtime_builder": "jev.community.drone_request", "model_input": "exact compiled runtime state/question/kind/options",
        "teacher_reads": "visible goal, permitted maneuvers, disclosed policy and thresholds, measured obstacle/flight geometry and speeds, target visibility/history",
        "ood_axes": ["two blocking barriers instead of one", "higher speeds, larger body/obstacle widths and altitude", "longer occlusion history and low-obstacle distractor"],
        "source_files_sha256": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                 for name in ("case_drone.py", "community.py", "api.py")}})
    path = output / "cases.jsonl"
    path.write_text("".join(json.dumps(case, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n" for case in cases), encoding="utf-8")
    manifest.update(case_count=len(cases), cases_file=path.name,
                    cases_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), supervision=supervision,
                    maneuver_counts=dict(Counter(case["answers"]["maneuver"] for case in cases)),
                    risk_counts=dict(Counter(case["answers"]["risk"] for case in cases)),
                    target_loss_counts=dict(Counter(case["answers"]["target_truly_lost"] for case in cases)),
                    variant_counts=dict(Counter(case["variant"] for case in cases)),
                    limits="Synthetic snapshot controls only; no simulator trajectories, collision outcomes, physical target-loss truth, real flight, external/JF100 records, GPU inference, or release-v2/browser-v1 mixing.")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--groups", type=int, default=500)
    parser.add_argument("--ood-groups", type=int)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(build_dataset(args.output_dir, args.groups, args.seed, args.ood_groups), indent=2))


if __name__ == "__main__":
    main()
