"""Make complete, verified gameplay recordings the gallery's game demos."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    catalog_path = ROOT / "site/catalog.json"
    manifest_path = ROOT / "site/media/gameplay-verification.json"
    catalog = json.loads(catalog_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    items = {item["id"]: item for item in catalog["items"]}
    updated = []
    for game in manifest["items"]:
        ident = game["id"].removeprefix("gameplay-")
        if ident not in items:
            continue
        item = items[ident]
        if not game["all_logged_actions_included"] or game["new_inference"]:
            raise ValueError("Expected a complete saved-action replay")
        if item["source_sha256"] != game["source_sha256"]:
            raise ValueError(f"Gameplay trace differs from existing demo: {ident}")
        if sha(ROOT / "site" / game["video"]) != game["sha256"]:
            raise ValueError(f"Gameplay bytes differ from manifest: {ident}")
        item.setdefault("decision_view", {key: item[key] for key in ("video", "poster", "captions", "transcript")})
        for key in ("video", "poster", "captions", "transcript"):
            item[key] = game[key]
        item.update(media_id=game["id"], presentation="continuous_gameplay",
                    title=game["title"] + " · full episode", duration_seconds=game["duration_seconds"],
                    description=game["goal"],
                    result_summary=game["outcome_title"] + ". " + game["outcome_summary"],
                    evidence_label="Complete saved model-action replay")
        item["provenance"]["gameplay"] = game
        item["limitations"] = [value for value in item["limitations"]
                               if value != "Doom shows recorded telemetry, not first-person game footage."]
        note = "Every logged decision is replayed; motion timing is adjusted for readability. No new model inference was performed."
        if note not in item["limitations"]:
            item["limitations"].append(note)
        if ident == "doom":
            note = "Native ViZDoom / Freedoom screen frames. The engine exposes no frame after terminal; the last available frame is held for the outcome card."
            if note not in item["limitations"]:
                item["limitations"].append(note)
        updated.append(ident)
    overview = manifest["overview"]
    overview_ids = {chapter["id"] for chapter in overview["chapters"]}
    successful_ids = {game["id"] for game in manifest["items"]
                      if game["episode_metrics"].get("success") is True}
    if not overview_ids or overview_ids != successful_ids:
        raise ValueError("Overview must contain exactly the successful complete episodes")
    if not {ident.removeprefix("gameplay-") for ident in overview_ids} <= set(updated):
        raise ValueError("An overview episode is missing its catalog entry")
    if sha(ROOT / "site" / overview["video"]) != overview["sha256"]:
        raise ValueError("Overview bytes differ from manifest")
    catalog["overview"] = {
        **{key: overview[key] for key in ("video", "poster", "captions", "transcript", "duration_seconds")},
        "id": "gameplay-overview", "title": "Open-Jev plays: successful complete episodes",
        "category": "Games", "evidence_kind": "model_replay",
        "evidence_label": "Complete saved model-action replays",
        "model_label": "Qwen3.5-9B · original 100-step pilot",
        "description": "Selected successful episodes, each shown in full from the opening state to its goal.",
        "request": None, "answer": None,
        "source_path": "site/media/gameplay-verification.json", "source_sha256": sha(manifest_path),
        "source_url": "https://github.com/Zefan-Cai/Open-Jev-Dev/tree/main/site/media",
        "provenance": overview,
        "result_summary": " ".join(game["title"] + ": " + game["outcome_summary"] + "."
                                    for game in manifest["items"] if game["id"] in overview_ids),
        "limitations": ["Selected successful examples, not an aggregate success-rate evaluation.",
                        "Complete replays of saved pilot actions, not fresh inference from the final models.",
                        "Local game rules and these fixed episodes do not establish general gameplay competence.",
                        "Playback timing is adjusted for readability and does not measure inference speed."],
    }
    catalog["presentation_updated_at"] = datetime.now(timezone.utc).isoformat()
    catalog["provenance"]["gameplay_attachment"] = {
        "script": "scripts/attach_gameplay_catalog.py", "script_sha256": sha(Path(__file__)),
        "manifest": "site/media/gameplay-verification.json", "manifest_sha256": sha(manifest_path),
    }
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"updated_games": updated, "overview_seconds": overview["duration_seconds"]}))


if __name__ == "__main__":
    main()
