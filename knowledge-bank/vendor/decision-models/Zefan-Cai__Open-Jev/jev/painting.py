"""Pixel decisions inspired by jev-paint; model probabilities become RGB in code.

The procedural scene generator is a geometry control, not a free-form art
benchmark. This module does not load a model or call a hosted service.
"""

import argparse
import colorsys
import hashlib
import json
import math
from pathlib import Path
import random

from .api import compile_request, format_response
from .data import SPLITS, split_group, validate_records


SOURCE = "https://github.com/achimala/jev-paint"
VERSION = "painting-geometry-v1"
MODES = ("palette", "silhouette", "rgb", "hsl")
PALETTE = {
    "black": [0, 0, 0], "white": [255, 255, 255], "gray": [128, 128, 128],
    "red": [255, 0, 0], "lime": [0, 255, 0], "blue": [0, 0, 255],
    "yellow": [255, 255, 0], "cyan": [0, 255, 255], "magenta": [255, 0, 255],
    "orange": [255, 165, 0], "purple": [128, 0, 128], "navy": [0, 0, 128],
    "green": [0, 128, 0], "teal": [0, 128, 128], "maroon": [128, 0, 0],
    "silver": [192, 192, 192],
}
HUES = {"neutral": 0, "red": 0, "orange": 1 / 12, "yellow": 1 / 6,
        "green": 1 / 3, "cyan": 1 / 2, "blue": 2 / 3,
        "purple": 3 / 4, "magenta": 5 / 6}


def build_requests(prompt, mode="palette", size=8, batch_questions=64, model="open-jev"):
    """Build bounded requests with coordinates in instructions, never only IDs."""
    if mode not in MODES or type(size) is not int or not 2 <= size <= 32:
        raise ValueError("mode must be palette/silhouette/rgb/hsl and size must be 2..32")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 8000:
        raise ValueError("prompt must contain 1..8000 characters")
    if type(batch_questions) is not int or not 1 <= batch_questions <= 1024:
        raise ValueError("batch_questions must be an integer in 1..1024")
    state = {"image_description": prompt.strip(), "width": size, "height": size,
             "coordinates": "Integer pixel coordinates. Origin (0,0) is top left; x increases right, y increases down.",
             "task": "Assign each pixel a color for the described image. Do not add text or a border."}
    if mode == "silhouette":
        state["task"] = "Mark foreground membership; render foreground black and background white. Ignore their described colors."
    if mode == "rgb":
        state["task"] += " Each channel is either 0 or 255; choose the nearest of the eight binary RGB colors."
    questions = {}
    for y in range(size):
        for x in range(size):
            key, location = f"x{x}_y{y}", f"pixel x={x}, y={y}"
            if mode == "palette":
                questions[key] = {"type": "choice", "instructions": f"Which palette color best represents {location}?",
                                  "criteria": {name: f"RGB {rgb}" for name, rgb in PALETTE.items()}}
            elif mode == "silhouette":
                questions[key] = {"type": "noul", "instructions": f"Is {location} part of a foreground object?"}
            elif mode == "rgb":
                for channel in ("red", "green", "blue"):
                    questions[f"{key}_{channel}"] = {"type": "noul", "instructions": f"For {location}, should its {channel} channel be 255 rather than 0?"}
            else:
                questions[f"{key}_hue"] = {"type": "choice", "instructions": f"Which hue describes {location}? Use neutral for black, gray, or white.",
                                           "criteria": {name: None for name in HUES}}
                questions[f"{key}_saturation"] = {"type": "score", "instructions": f"What is the HSL saturation of {location}?",
                                                  "criteria": ["No saturation, 0", "Half saturation, 0.5", "Full saturation, 1"]}
                questions[f"{key}_lightness"] = {"type": "score", "instructions": f"What is the HSL lightness of {location}?",
                                                 "criteria": ["Black, 0", "Dark, 0.25", "Middle lightness, 0.5", "Light, 0.75", "White, 1"]}
    entries = list(questions.items())
    return [{"model": model, "state": state, "questions": dict(entries[start:start + batch_questions])}
            for start in range(0, len(entries), batch_questions)]


def _probability(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("probabilities must be finite numbers in [0,1]")
    return float(value)


def _distribution(answer, keys, kind):
    if answer.get("type") != kind or set(answer.get("probabilities", {})) != set(keys):
        raise ValueError("answer type or probability keys do not match the question")
    values = [_probability(answer["probabilities"][key]) for key in keys]
    if not math.isclose(sum(values), 1, abs_tol=1e-6, rel_tol=1e-6):
        raise ValueError("probabilities must sum to one")
    return values


def render_rgb(answers, mode, size):
    """Mean RGB per pixel, using a product of HSL marginals, not a learned joint."""
    if mode not in MODES or type(size) is not int or not 2 <= size <= 32:
        raise ValueError("invalid painting representation")
    pixels = []
    for y in range(size):
        for x in range(size):
            key = f"x{x}_y{y}"
            try:
                if mode == "palette":
                    probabilities = _distribution(answers[key], list(PALETTE), "choice")
                    rgb = [sum(p * color[c] for p, color in zip(probabilities, PALETTE.values())) for c in range(3)]
                elif mode in ("silhouette", "rgb"):
                    names = [key] if mode == "silhouette" else [f"{key}_{c}" for c in ("red", "green", "blue")]
                    if any(answers[name].get("type") != "noul" for name in names):
                        raise ValueError("expected a Noul answer")
                    values = [_probability(answers[name]["noul"]) for name in names]
                    rgb = [255 * (1 - values[0])] * 3 if mode == "silhouette" else [255 * p for p in values]
                else:
                    hp = _distribution(answers[f"{key}_hue"], list(HUES), "choice")
                    sp = _distribution(answers[f"{key}_saturation"], [str(i) for i in range(3)], "score")
                    lp = _distribution(answers[f"{key}_lightness"], [str(i) for i in range(5)], "score")
                    rgb = [0.0, 0.0, 0.0]
                    for (name, hue), h in zip(HUES.items(), hp):
                        for saturation, s in enumerate(sp):
                            for lightness, l in enumerate(lp):
                                color = colorsys.hls_to_rgb(hue, lightness / 4, 0 if name == "neutral" else saturation / 2)
                                for c in range(3):
                                    rgb[c] += 255 * h * s * l * color[c]
                pixels.append([round(channel) for channel in rgb])
            except (KeyError, TypeError, AttributeError) as exc:
                raise ValueError(f"missing or malformed answer for {key}") from exc
    return pixels


def geometry_scene(index, seed=42):
    """ID rectangles and OOD circles, exact integer-coordinate ground truth."""
    if type(index) is not int or index < 0:
        raise ValueError("index must be a nonnegative integer")
    rng = random.Random(f"{VERSION}:{seed}:{index}")
    ood = index % 10 == 0
    size = 12 if ood else 8
    names = list(PALETTE)[:2] + list(PALETTE)[3:9]
    background, foreground = rng.sample(names, 2)
    if ood:
        cx, cy, radius = rng.randint(3, 8), rng.randint(3, 8), rng.randint(2, 4)
        prompt = f"Background is {background}. One solid {foreground} foreground circle contains exactly integer coordinates with (x-{cx}) squared plus (y-{cy}) squared <= {radius * radius}. All remaining pixels are background."
        inside = lambda x, y: (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2
    else:
        x0, x1 = sorted(rng.sample(range(size), 2))
        y0, y1 = sorted(rng.sample(range(size), 2))
        prompt = f"Background is {background}. One solid {foreground} foreground rectangle includes exactly {x0} <= x <= {x1} and {y0} <= y <= {y1}. All remaining pixels are background."
        inside = lambda x, y: x0 <= x <= x1 and y0 <= y <= y1
    mask = [inside(x, y) for y in range(size) for x in range(size)]
    colors = [foreground if value else background for value in mask]
    # Identical descriptions always share a split, even with a different seed.
    group = VERSION + ":" + hashlib.sha256(prompt.encode()).hexdigest()[:24]
    return {"prompt": prompt, "size": size, "mask": mask, "colors": colors, "group_id": group,
            "split": "ood" if ood else split_group(group), "seed": seed}


def geometry_answers(scene, mode):
    """Programmatic reference output, explicitly not an Open-Jev prediction."""
    answers = {}
    for request in build_requests(scene["prompt"], mode, scene["size"]):
        records, targets = compile_request(request["state"], request["questions"]), []
        for record in records:
            parts = record["id"].split("_")
            x, y = int(parts[0][1:]), int(parts[1][1:])
            i = y * scene["size"] + x
            color = scene["colors"][i]
            rgb = PALETTE[color]
            if mode == "silhouette":
                value = str(bool(scene["mask"][i])).lower()
            elif mode == "rgb":
                value = str(bool(rgb[("red", "green", "blue").index(parts[2])])).lower()
            elif mode == "palette":
                value = color
            elif parts[2] == "hue":
                value = "green" if color == "lime" else "neutral" if color in ("black", "white") else color
            elif parts[2] == "saturation":
                value = "0" if color in ("black", "white") else "2"
            else:
                value = "0" if color == "black" else "4" if color == "white" else "2"
            targets.append([float(candidate == value) for candidate in record["answer_keys"]])
        answers.update(format_response(records, targets)["answers"])
    return answers


def geometry_records(groups=100, seed=42):
    """Yield reproducible training records; keep every pixel/mode in its scene split."""
    if type(groups) is not int or groups < 1:
        raise ValueError("groups must be positive")
    seen = set()
    for index in range(groups):
        scene = geometry_scene(index, seed)
        if scene["group_id"] in seen:
            continue
        seen.add(scene["group_id"])
        for mode in MODES:
            answers = geometry_answers(scene, mode)
            for request in build_requests(scene["prompt"], mode, scene["size"]):
                for record in compile_request(request["state"], request["questions"]):
                    answer = answers[record["id"]]
                    target = [1 - answer["noul"], answer["noul"]] if record["kind"] == "noul" else [answer["probabilities"][key] for key in record["answer_keys"]]
                    metadata = {"case_name": "probability_painting", "mode": mode, "question_id": record["id"],
                                "family": {"choice": "routing", "noul": "evidence", "score": "rubric"}[record["kind"]],
                                "template_id": VERSION + (":circle" if scene["split"] == "ood" else ":rectangle"),
                                "target_basis": "exact_procedural_geometry", "provenance": {
                                    "type": "synthetic", "source_url": SOURCE, "license": "CC0-1.0",
                                    "generator_version": VERSION, "seed": seed, "group_index": index, "variant": 0,
                                    "annotation_status": "programmatic_control_not_art_quality",
                                    "split_policy": "circle_ood_rectangle_group_hash"}}
                    if record["kind"] == "score":
                        metadata["score_values"] = list(range(len(target)))
                    yield {"id": f"{scene['group_id']}:{mode}:{record['id']}", "group_id": scene["group_id"],
                           "split": scene["split"], "source": VERSION, "state": record["state"],
                           "question": record["question"], "kind": record["kind"], "options": record["options"],
                           "target": target, "metadata": metadata}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--groups", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    records = list(geometry_records(args.groups, args.seed))
    summary = validate_records(records)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    checksums = {}
    for split in SPLITS:
        path = args.output_dir / f"{split}.jsonl"
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records if row["split"] == split))
        checksums[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {"dataset": VERSION, "requested_groups": args.groups, "seed": args.seed,
                "summary": summary, "files_sha256": checksums,
                "limitation": "Procedural geometry controls only; no aesthetic quality or Jev parity claim."}
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
