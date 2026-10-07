"""Build public demo evidence from original examples and saved model artifacts.

No inference or training is performed. Full-pass reconstruction requires the
local captured prediction shards; --check validates the self-contained catalog.
Only explicitly allowlisted heldout sources/examples enter the website.
"""
import argparse
import base64
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from jev.painting import render_rgb

PILOT_COMMIT = "99e881108c6cacadafd364088505e84975ca43fc"
AUDIT = "reports/full-data-eval-n1-v1/9b-audit.json"
SMOKE = "reports/pilot-suite-n1-4k/9b/demo_requests.jsonl"
MODEL_FIELDS = ("state", "question", "kind", "options")
FULLPASS = {
    "customer-control-v1": ("customer-context", "Customer intent and sentiment", "Workflows", "workflow"),
    "workflow-controls-v1/customer_service": ("customer-workflow", "Customer service actions", "Workflows", "workflow"),
    "workflow-controls-v1/security_incidents": ("security-workflow", "Security incident triage", "Workflows", "workflow"),
    "workflow-controls-v1/agent_trace_observability": ("trace-workflow", "Agent trace review", "Workflows", "workflow"),
    "workflow-controls-v1/invoice_processing": ("invoice-workflow", "Invoice action selection", "Workflows", "workflow"),
    "tic_tac_toe-v1": ("tic-tac-toe", "Tic-tac-toe decisions", "Games", "tictactoe"),
}
REASONING = {
    "formal_logic": "Formal logic", "relations": "Relational reasoning", "arithmetic": "Arithmetic",
    "temporal": "Temporal reasoning", "code_semantics": "Code semantics", "algorithms": "Algorithm reasoning",
    "evidence_integration": "Evidence integration",
}
NEW = [
    ("citation-control", "Citation checking", "examples/recipes/citation_check.json", "citation-control-v1", "citation_check",
     "Check a claim against a supplied source."),
    ("entity-alignment", "Entity alignment", "examples/entity-alignment-fields.json", "entity-alignment-control-v1", "entity_alignment",
     "Compare identifiers and normalized catalog attributes."),
    ("amount-extraction", "Amount extraction", "examples/amount-extraction-selection.json", "amount-extraction-control-v1", None,
     "Select an exact amount span before conditional normalization."),
    ("email-extraction", "Email extraction", "examples/email-selection.json", "email-selection-control-v1", None,
     "Select the exact email for a requested contact role."),
    ("phone-extraction", "Phone extraction", "examples/phone-extraction-selection.json", "phone-extraction-control-v1", None,
     "Select a phone span before region-aware formatting."),
]
GAMES = [
    ("snake", "Snake", "snake", "snake", "snake-v1"),
    ("platformer", "Tile platformer", "tile_platformer", "platformer", "tile_platformer-v1"),
    ("trex", "T-Rex runner", "trex_runner", "trex", "trex_runner-v1"),
    ("doom", "ViZDoom telemetry", "doom_basic", "doom", "vizdoom-basic-v1"),
    ("wiki", "Wiki graph navigation", "wikiracing", "wiki", "wikispeedia-v1"),
]
COMMUNITY = [
    ("heist", "HEIST guard decisions", "examples/community/heist.json", "workflow"),
    ("runescape", "RuneScape action interface", "examples/community/runescape.json", "workflow"),
    ("pokemon", "Pokemon battle interface", "examples/community/pokemon.json", "workflow"),
    ("mario-adapter", "Mario state adapter", "examples/games/mario-request.json", "platformer"),
    ("code-security-4", "Code security · 4 fields", "examples/community/code_security_4.json", "code"),
    ("fraud-4", "Fraud review · 4 fields", "examples/community/fraud_4.json", "workflow"),
    ("tariff-255", "Catalog selection · 255 options", "examples/community/tariff_255.json", "document"),
    ("support-28", "Support review · 28 fields", "examples/community/support_28.json", "workflow"),
]
RECIPES = {
    "classification": "Classification", "rerank": "Reranking", "semantic_search": "Semantic search",
    "rag_filter": "RAG filtering", "citation_check": "Citation checking", "guardrails": "Guardrails",
    "entity_alignment": "Entity alignment", "value_extraction": "Span extraction", "date_extraction": "Date extraction",
    "structure_recovery": "Structure recovery", "function_calling": "Function proposals", "skill_suggestion": "Skill selection",
    "hierarchical_classification": "Hierarchical classification", "verification": "Extraction verification", "features": "Numeric features",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def objsha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sha(path):
    value = hashlib.sha256()
    with (ROOT / path).open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads((ROOT / path).read_bytes())


def rows(path):
    with (ROOT / path).open("rb") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def github(path, commit):
    return f"https://github.com/Zefan-Cai/Open-Jev-Dev/blob/{commit}/{path}"


def display(item):
    request = item["request"]
    state = request.get("state", {})
    item["display_context"] = json.dumps(state, ensure_ascii=False, indent=2)[:2400]
    if "questions" in request:
        item["display_questions"] = [{"id": key, "label": value.get("instructions", key), "type": value["type"]}
                                     for key, value in request["questions"].items()]
    else:
        item["display_questions"] = [{"id": "decision", "label": request["question"], "type": request["kind"]}]
    for field, extension in (("video", "mp4"), ("poster", "jpg"), ("captions", "vtt")):
        item[field] = f"media/{item['id']}.{extension}"
    item["transcript"] = f"media/{item['id']}.txt"
    return item


def base(ident, title, category, kind, description, source, commit):
    return {"id": ident, "title": title, "category": category, "description": description,
            "visual_kind": kind, "source_path": source, "source_sha256": sha(source), "source_url": github(source, commit)}


def typed_request(row):
    return {key: row[key] for key in MODEL_FIELDS}


def typed_result(row, prediction):
    probabilities = prediction["probabilities"]
    selected = max(range(len(probabilities)), key=lambda i: probabilities[i])
    if row["kind"] == "noul":
        return f"Recorded yes probability: {probabilities[1]:.3f}."
    if row["kind"] == "score":
        return f"Recorded ordinal expectation: {sum(i * p for i, p in enumerate(probabilities)):.3f}."
    return "Recorded choice: " + row["options"][selected][:150] + "."


def fullpass_inputs():
    audit = read(AUDIT)
    require(audit["status"] == "passed" and audit["coverage"]["expected_rows"] == 26452, "Missing completed 9B full-pass audit")
    predictions, evidence = {}, {}
    for rank in range(4):
        path = f"runs/full-data-eval-n1-v1/9b/shard-{rank}.jsonl"
        evidence[path] = sha(path)
        require(evidence[path] == audit["verification"]["source_files"][f"shard-{rank}.jsonl"]["sha256"],
                "Captured prediction shard differs from the completed independent audit")
        for row in rows(path):
            require(row["status"] == "ok" and row["id"] not in predictions, "Invalid or duplicated saved prediction")
            require(row["checkpoint"]["checkpoint_sha256"] == audit["checkpoint"]["checkpoint_sha256"], "Checkpoint binding differs")
            predictions[row["id"]] = row
    # Only allowlisted original synthetic test sources are retained here;
    # Wikispeedia and Doom use separately captured environment traces.
    permitted = set(FULLPASS) | {"painting-geometry-v1", "reasoning-control-v1"}
    selected = []
    require(sha("data/release-v2/test.jsonl") == audit["data_identity"]["split_sha256"]["test"], "Frozen test file differs")
    with (ROOT / "data/release-v2/test.jsonl").open("rb") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if row["source"] not in permitted:
                continue
            require(row["split"] == "test" and objsha(row) == predictions[row["id"]]["row_sha256"], "Saved prediction/input hash mismatch")
            selected.append(row)
    return selected, predictions, evidence, audit


def fullpass_item(row, prediction, definition, commit, evidence):
    ident, title, category, kind = definition
    item = base(ident, title, category, kind, "One original held-out decision from the completed 9B full-pass checkpoint.", AUDIT, commit)
    item.update(evidence_kind="model_replay", evidence_label="Saved held-out prediction · full-pass",
                model_label="Qwen3.5-9B · full-pass", request=typed_request(row), answer=prediction,
                answer_format="saved_prediction_record", selector=f"source={row['source']}; id={row['id']}",
                source_role="audit_binding_for_embedded_saved_prediction", result_summary=typed_result(row, prediction),
                covered_source_ids=[row["source"]], limitations=[
                    "One saved test decision, selected by the smallest matching ID, not by correctness.",
                    "The saved prediction record includes a separately labeled reference target; it is not a model output.",
                    "This does not demonstrate an executed business action or completed live task."],
                provenance={"data_path": "data/release-v2/test.jsonl", "data_selector": {"id": row["id"]},
                    "data_row_sha256": objsha(row), "input_sha256": objsha(typed_request(row)),
                    "prediction_record_sha256": objsha(prediction), "prediction_selector": {"id": row["id"]},
                    "prediction_file_sha256": evidence, "checkpoint": prediction["checkpoint"],
                    "request_binding": "Saved prediction row_sha256 equals the original heldout data row canonical hash.",
                    "reference_fields_in_answer": ["target"]})
    return display(item)


def new_items(commit):
    result = []
    for ident, title, path, source, recipe, description in NEW:
        request = read(path)
        item = base(ident, title, "Extraction", "extraction", description, path, commit)
        item.update(evidence_kind="interface_walkthrough", evidence_label="Interface walkthrough · untrained control",
                    model_label="No trained result", selector="$", source_role="original_example_request", request=request, answer=None,
                    result_summary="Request contract only. No model answer or probability is shown.",
                    limitations=["This new control corpus was not included in the existing trained checkpoints.",
                                 "The video illustrates the request interface; it is not an extraction-quality result."],
                    covered_source_ids=[source], covers_recipes=[recipe] if recipe else [],
                    provenance={"request_path": path, "request_file_sha256": sha(path), "request_selector": "$",
                                "request_sha256": objsha(request), "response_present": False})
        result.append(display(item))
    return result


def game_items(commit):
    result = []
    for ident, title, game, kind, source in GAMES:
        path = f"reports/pilot-suite-n1-4k/9b/games/trajectories/{game}-model-seed-10001.json"
        trace = read(path)
        require(trace["is_model"] and trace["valid"] and trace["seed"] == 10001, "Wrong game trajectory")
        first, metrics = trace["steps"][0], trace["metrics"]
        if game == "snake":
            summary = f"{metrics['food_collected']} food; collision: {metrics['collision']}"
        elif game == "tile_platformer":
            summary = f"Progress: {metrics['progress_tiles']} tiles; success: {metrics['success']}"
        elif game == "trex_runner":
            summary = f"{metrics['obstacles_cleared']} obstacles; success: {metrics['success']}"
        elif game == "doom_basic":
            summary = f"Engine reward: {metrics['engine_total_reward']}"
        else:
            summary = "Recorded path: " + " → ".join(metrics["path"])
        item = base(ident, title, "Games", kind, "Replay a complete saved episode from the original 100-step pilot.", path, commit)
        limits = ["Original 100-step pilot, not the later full-pass checkpoint.",
                  "Fixed seed 10001, selected without filtering by success.",
                  "Doom shows recorded telemetry, not first-person game footage." if game == "doom_basic" else
                  "Wiki uses the original tiny local graph, not redistributed Wikispeedia data." if game == "wikiracing" else
                  "Local game rules and this one episode do not establish general game competence."]
        if game == "trex_runner":
            limits.append("The later full-pass mixture contains only 28 distinct T-Rex training states; this earlier pilot replay is a separate result.")
        item.update(evidence_kind="model_replay", evidence_label="Recorded model episode · pilot", model_label="Qwen3.5-9B · pilot",
                    selector="$.steps", source_role="saved_model_trajectory", request=first["request"], answer=first["answer"],
                    frames=trace["steps"], initial_state=trace["initial_state"], episode_metrics=metrics,
                    result_summary=summary, limitations=limits, covered_source_ids=[source],
                    provenance={"trajectory_path": path, "trajectory_file_sha256": sha(path), "selector": "$.steps", "seed": trace["seed"],
                        "service_identity": trace["service_identity"], "selection_rule": "Fixed first registered model seed 10001; no outcome filtering.",
                        "source_coverage_role": "Related executable environment replay, not a full-pass source-dataset evaluation."})
        result.append(display(item))
    return result


def painting_items(data, predictions, evidence, commit):
    candidates = [row for row in data if row["source"] == "painting-geometry-v1"]
    group = min(row["group_id"] for row in candidates)
    result = []
    for mode in ("palette", "silhouette", "rgb", "hsl"):
        subset = sorted((row for row in candidates if row["group_id"] == group and row["metadata"]["mode"] == mode), key=lambda row: row["id"])
        projected, pixels_to_ids = {}, defaultdict(list)
        for row in subset:
            prediction, key = predictions[row["id"]], row["metadata"]["question_id"]
            if row["kind"] == "noul":
                projected[key] = {"type": "noul", "noul": prediction["probabilities"][1]}
            else:
                keys = [str(i) for i in range(len(row["options"]))] if row["kind"] == "score" else [s.split(": ", 1)[0] for s in row["options"]]
                projected[key] = {"type": row["kind"], "probabilities": dict(zip(keys, prediction["probabilities"]))}
            pixels_to_ids["_".join(key.split("_")[:2])].append(row["id"])
        size = subset[0]["state"]["width"]
        rgb = render_rgb(projected, mode, size)
        item = fullpass_item(subset[0], predictions[subset[0]["id"]],
            ("painting-" + mode, "Probability painting · " + mode.upper(), "Control", "painting"), commit, evidence)
        item.update(description="Reconstruct an entire 8×8 held-out canvas from saved pixel decisions.",
                    result_summary=f"{len(subset)} recorded {mode} decisions → 64 probability-mean RGB pixels.",
                    selector={"group_id": group, "mode": mode, "split": "test"},
                    records=[{"id": row["id"], "request": typed_request(row), "answer": predictions[row["id"]]} for row in subset],
                    pixel_predictions=[{"x": x, "y": y, "rgb": rgb[y * size + x], "record_ids": pixels_to_ids[f"x{x}_y{y}"]}
                                       for y in range(size) for x in range(size)],
                    rendering_rule="jev.painting.render_rgb: expected RGB from saved probabilities; HSL uses a product of marginals, not a learned joint.",
                    limitations=["One complete 8×8 test scene, chosen by minimum group ID; no correctness filtering.",
                                 "Pixels are derived only from saved model probabilities, not reference targets.",
                                 "Controlled geometry does not establish free-form artistic quality."])
        item["provenance"].update(grouped_record_ids=[row["id"] for row in subset], grouped_records_sha256=objsha(item["records"]),
            renderer_source="jev/painting.py", renderer_source_sha256=sha("jev/painting.py"), renderer_function="render_rgb")
        result.append(item)
    return result


def control_item(name, title, commit):
    prefix = f"reports/pilot-{name}-n1/9b/{name}"
    path = prefix + "/outcomes.jsonl"
    all_outcomes = rows(path)
    selected = min(all_outcomes, key=lambda row: (("test", "ood").index(row["split"]), row["case_id"]))
    require(selected["status"] == "ok", "First recorded control case has no valid model response")
    request_record = next(row for row in rows(prefix + "/requests.jsonl") if row["case_id"] == selected["case_id"])
    wire = request_record["request_json"].encode()
    require(hashlib.sha256(wire).hexdigest() == selected["request_body_sha256"], "Control request wire hash differs")
    request = json.loads(wire)
    response_wire = base64.b64decode(selected["response_body_base64"], validate=True)
    require(hashlib.sha256(response_wire).hexdigest() == selected["response_body_sha256"] and
            json.loads(response_wire) == selected["response"], "Control response wire hash/content differs")
    item = base(name, title, "Control", name, "Replay a saved synthetic snapshot decision; no physical action is executed.", path, commit)
    item.update(evidence_kind="model_replay", evidence_label="Recorded snapshot response · pilot", model_label="Qwen3.5-9B · pilot",
                selector={"case_id": selected["case_id"]}, source_role="saved_HTTP_outcome", request=request, answer=selected["response"],
                result_summary=("Recorded operation: " + selected["proposal"]["operation"] + "; full proposal reference match: " + str(bool(selected["correct"]["proposal_exact"])))
                               if name == "browser" else ("Recorded maneuver: " + selected["decision"]["maneuver"] + "; complete reference match: " + str(bool(selected["correct"]["complete_decision"]))),
                limitations=["Original pilot checkpoint; it was not trained on the later browser/drone expansion.",
                             "One fixed snapshot, not browser task completion, closed-loop control or flight evidence."],
                covered_source_ids=["browser-control-v1" if name == "browser" else "drone-control-v1"],
                provenance={"request_path": prefix + "/requests.jsonl", "request_source_sha256": sha(prefix + "/requests.jsonl"),
                    "request_selector": {"case_id": selected["case_id"]}, "request_body_sha256": selected["request_body_sha256"],
                    "response_selector": {"case_id": selected["case_id"]}, "response_record_sha256": objsha(selected),
                    "response_body_sha256": selected["response_body_sha256"], "service_identity": selected["service_identity"],
                    "selection_rule": "First test case by case ID; no correctness filtering."})
    return display(item)


def smoke_item(ident, title, category, kind, path, saved, commit):
    response = saved[path]
    require(response["status"] == "passed", "Saved interface response did not pass its original contract check")
    raw = subprocess.check_output(["git", "show", PILOT_COMMIT + ":" + path], cwd=ROOT)
    request = json.loads(raw)
    require(set(request["questions"]) == set(response["response"]["answers"]), "Historical question IDs do not match saved answers")
    item = base(ident, title, category, kind, "A saved 9B pilot response to an original local interface example.", SMOKE, commit)
    item.update(evidence_kind="model_replay", evidence_label="Recorded pilot interface response", model_label="Qwen3.5-9B · pilot",
                selector={"example": path}, source_role="saved_response_with_reconstructed_historical_example",
                request=request, answer=response["response"],
                result_summary=f"Saved response for {response['question_count']} typed questions; semantics were not scored.",
                limitations=["Contract smoke only; no dedicated training or task-quality result is established.",
                    "Original request bytes were not logged. The displayed request is reconstructed from the recorded example path at the service code revision.",
                    "A response is not proof that an external tool, emulator, transaction or game action executed."],
                provenance={"request_path": path, "request_source_commit": PILOT_COMMIT,
                    "request_source_url": github(path, PILOT_COMMIT), "request_file_sha256": hashlib.sha256(raw).hexdigest(),
                    "request_sha256": objsha(request), "request_byte_attested": False,
                    "request_binding": "Historical example reconstruction; original call logged example path but no request-body hash.",
                    "response_path": SMOKE, "response_file_sha256": sha(SMOKE), "response_selector": {"example": path},
                    "response_record_sha256": objsha(response), "service_identity": response["response"].get("metadata", {})})
    return display(item)


def build(commit):
    data, predictions, evidence, audit = fullpass_inputs()
    items = new_items(commit) + game_items(commit)
    for source, definition in FULLPASS.items():
        row = min((row for row in data if row["source"] == source), key=lambda row: row["id"])
        items.append(fullpass_item(row, predictions[row["id"]], definition, commit, evidence))
    items.extend(painting_items(data, predictions, evidence, commit))
    for domain, title in REASONING.items():
        row = min((row for row in data if row["source"] == "reasoning-control-v1" and row["metadata"]["domain"] == domain), key=lambda row: row["id"])
        items.append(fullpass_item(row, predictions[row["id"]],
            ("reasoning-" + domain.replace("_", "-"), title, "Reasoning", "code" if domain == "code_semantics" else "reasoning"), commit, evidence))
    items.extend([control_item("browser", "Browser snapshot decisions", commit), control_item("drone", "Drone snapshot decisions", commit)])
    saved = {row["example"]: row for row in rows(SMOKE)}
    for ident, title, path, kind in COMMUNITY:
        item = smoke_item(ident, title, "Community", kind, path, saved, commit)
        item["community_interface"] = ident
        if ident == "tariff-255":
            item["limitations"].append("The 255 labels are synthetic catalog groups, not official tariff classifications.")
        items.append(item)
    covered_recipes = {recipe for item in items for recipe in item.get("covers_recipes", [])}
    for recipe, title in RECIPES.items():
        if recipe in covered_recipes:
            continue
        item = smoke_item("recipe-" + recipe.replace("_", "-"), title, "Recipes", "document",
                          "examples/recipes/" + recipe + ".json", saved, commit)
        item["covers_recipes"] = [recipe]
        items.append(item)
    covered_sources = sorted({source for item in items for source in item.get("covered_source_ids", [])})
    mixture_sources = sorted(read("data/browser-drone-expansion-v1/manifest.json")["summary"]["sources"])
    require(set(mixture_sources) <= set(covered_sources), "A mixture task source lacks a demo")
    return {"version": 1, "title": "Open Jev demo evidence", "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_commit": commit, "status": "complete", "counts": {
                "items": len(items), **dict(Counter(item["evidence_kind"] for item in items)),
                "mixture_task_sources": len(mixture_sources), "new_control_sources": 5, "community_interfaces": 8,
                "recipe_forms": len(RECIPES), "reasoning_subdomains": len(REASONING), "painting_representations": 4},
            "source_coverage": {"mixture_task_sources": mixture_sources, "all_source_ids": covered_sources,
                "meaning": "A catalog entry covers an interface/domain, not necessarily dedicated training or measured task success. T-Rex has 28 distinct full-pass training states; browser/drone and game videos use older pilot checkpoints."},
            "selection_policy": "Original local examples; minimum test IDs/groups or fixed registered seed 10001; no selection by correctness. No official restricted evaluation records, training rows, ROM images, or redistributed Wikispeedia graph are embedded.",
            "items": items, "uncovered": [
                {"id": "playjev-visual-games", "title": "PlayJev visual policy and game collection",
                 "games": ["Tetris", "Pacman", "racer", "Space Invaders", "Sokoban", "Floppy Bird", "Breakout", "2048"],
                 "reason": "These games and the separate PlayJev pixel-policy pipeline are not implemented here. Our local Snake/platformer and Mario state adapter do not establish parity with PlayJev's versions.",
                 "source_url": "https://github.com/OmniJev/PlayJev"},
                {"id": "discovery-only-integrations", "title": "Community discovery leads",
                 "reason": "Household automation, semantic SQL, dataset filtering, sponsor detection, MCP execution and trading gates remain discovery leads; no complete integration or outcome evidence is supplied.",
                 "source_url": github("docs/public-capabilities.md", commit)}],
            "provenance": {"catalog_builder": "scripts/build_demo_catalog.py", "builder_sha256": sha("scripts/build_demo_catalog.py"),
                "fullpass_audit_path": AUDIT, "fullpass_audit_sha256": sha(AUDIT), "fullpass_checkpoint": audit["checkpoint"],
                "public_evidence_note": "Selected exact requests, saved predictions and original game steps are embedded. Repository links may require access while the repository is private."}}


def check(catalog):
    require(catalog["version"] == 1 and catalog["status"] == "complete", "Catalog is incomplete")
    items = catalog["items"]
    require(len({item["id"] for item in items}) == len(items) == catalog["counts"]["items"], "Duplicate IDs/count mismatch")
    recipes = {recipe for item in items for recipe in item.get("covers_recipes", [])}
    if catalog.get("showcase_selection"):
        require(catalog["showcase_selection"]["policy"] == "reviewed_success_or_interface", "Unknown showcase selection")
        require(all(item.get("showcase_review", {}).get("status") in ("success", "walkthrough") for item in items), "Unreviewed showcase item")
        require(catalog["counts"]["recipe_forms"] == len(recipes), "Selected recipe count differs")
    else:
        require(recipes == set(RECIPES), "Recipe coverage differs")
    for item in items:
        require(item["request"] and item["source_sha256"] and item["selector"] and item["source_role"], "Missing raw input/provenance")
        if item["evidence_kind"] == "interface_walkthrough":
            require(item["answer"] is None and not item.get("frames"), "Untrained interface contains a model answer")
        else:
            require(item["evidence_kind"] == "model_replay" and item["answer"], "Missing saved model answer")
        for field, extension in (("video", "mp4"), ("poster", "jpg"), ("captions", "vtt"), ("transcript", "txt")):
            media_id = item.get("media_id", item["id"])
            require(media_id in (item["id"], "gameplay-" + item["id"]), "Unexpected media identity")
            require(item[field] == f"media/{media_id}.{extension}", "Media path mismatch")
        for record in item.get("records", []):
            require(record["answer"]["status"] == "ok" and record["answer"]["id"] == record["id"], "Grouped prediction binding differs")
        for pixel in item.get("pixel_predictions", []):
            require(len(pixel["rgb"]) == 3 and all(type(c) is int and 0 <= c <= 255 for c in pixel["rgb"]), "Invalid derived pixel")
    return {"items": len(items), "evidence_kinds": dict(Counter(item["evidence_kind"] for item in items)),
            "categories": dict(Counter(item["category"] for item in items)), "recipe_forms": len(recipes)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate the existing self-contained catalog without captured shards")
    args = parser.parse_args()
    path = ROOT / "site/catalog.json"
    if args.check:
        catalog = json.loads(path.read_bytes())
    else:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        catalog = build(commit)
        check(catalog)
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps(check(catalog), sort_keys=True))


if __name__ == "__main__":
    main()
