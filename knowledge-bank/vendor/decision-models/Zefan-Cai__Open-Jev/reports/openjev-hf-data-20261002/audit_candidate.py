"""CPU-only replay and visible-input screen; never exports upstream examples.

The raw upstream snapshots and benchmark input projection stay under ignored runs/.
"""
import argparse
import ast
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

from jev.data import read_split_directory, validate_records
from scripts.screen_training_overlap import build_index, fingerprint, leaves, norm, shingles
from tests.test_policy_controls_v6 import independent_answer


JOURNAL_FIELDS = {
    "classify_banking77": ("text",), "prompt_injection": ("text",),
    "policy": (), "guardrail": ("tool",), "nl_filter": (),
    "chess_openjev_vs_random": ("fen", "legal"),
    "poker_openjev_vs_random": ("hole", "board", "options"),
    "poker_openjev_vs_rulebot": ("hole", "board", "options"),
    "poker_openjev_vs_rulebot_60": ("hole", "board", "options"),
    "snake": ("options",),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(raw_dir, dataset, benchmark, routing_root, manifest_path):
    manifest = json.loads(manifest_path.read_text())
    for source in manifest["sources"]:
        path = raw_dir / source["snapshot"]
        if path.stat().st_size != source["bytes"] or sha(path) != source["sha256"]:
            raise ValueError("Source snapshot differs: " + path.name)
    rows = list(read_split_directory(dataset))
    schema = validate_records(rows)
    group_variants = defaultdict(set)
    for row in rows:
        answer = independent_answer(row["metadata"]["scenario_family"], row["state"])
        if row["kind"] == "noul":
            answer = "yes" if answer == row["metadata"]["proposed_outcome"] else "no"
        if row["options"][row["target"].index(1.0)] != answer:
            raise ValueError("Independent policy replay differs: " + row["id"])
        group_variants[row["group_id"]].add(row["metadata"]["provenance"]["variant"])
    if any(variants != {0, 1, 2, 3} for variants in group_variants.values()):
        raise ValueError("A counterfactual group is incomplete")
    docs = [json.loads(benchmark.read_text())]
    if len(docs[0]["workloads"]) != 231:
        raise ValueError("Expected all 231 public benchmark inputs")
    corpus_counts = {"jevbench_public_development": 231}
    auxiliary = []
    inventory = []

    def add_input(value):
        if list(leaves(value)):
            auxiliary.append({"request": {"state": value, "questions": {"visible_only": {
                "type": "noul", "instructions": "Visible-input lexical screening only."}}}})

    for split in ("test", "calibration"):
        path = routing_root / (split + "-inputs.csv")
        with path.open(newline="") as handle:
            inputs = list(csv.DictReader(handle))
        for item in inputs:
            add_input(item["text"])
        corpus_counts["natural_routing_" + split] = len(inputs)
    for name, fields in JOURNAL_FIELDS.items():
        path = raw_dir / ("author-demos--out--" + name + "--decisions.jsonl")
        journal = [json.loads(line) for line in path.read_text().splitlines()]
        for item in journal:
            add_input({field: item[field] for field in fields})
        inventory.append({"name": name, "rows": len(journal), "sha256": sha(path),
                          "selected_visible_fields": list(fields), "training_rows_imported": 0})
        corpus_counts["upstream_journal_" + name] = len(journal)
    # Read string literals in published source, without executing author code.
    literal_count = 0
    for name in ("policy", "guardrail", "nl_filter", "classify", "prompt_injection"):
        tree = ast.parse((raw_dir / ("author-demos--" + name + ".py")).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                add_input(node.value)
                literal_count += 1
    corpus_counts["upstream_demo_source_string_literals"] = literal_count
    for name in ("browser_hf", "browser_hn2", "browser_wikipedia"):
        run = json.loads((raw_dir / ("author-demos--out--" + name + "--run.json")).read_text())
        add_input({k: run[k] for k in ("task", "start_url")})
    corpus_counts["upstream_browser_task_descriptions"] = 3
    docs.append({"workloads": auxiliary})
    exact, grams, short, request_count = build_index(docs)
    matches = []
    for row in rows:
        reasons = []
        if fingerprint(row) in exact:
            reasons.append("exact_visible_input")
        state_text = list(leaves(row["state"]))
        if any(norm(s) in short for s in state_text):
            reasons.append("normalized_state_leaf_ge8_words")
        if any(shingles(s) & grams for s in state_text):
            reasons.append("state_13_token_shingle")
        if reasons:
            matches.append({"id": row["id"], "group_id": row["group_id"], "split": row["split"], "reasons": reasons})
    bindings = [{"name": p.name, "sha256": sha(p)} for p in
                [benchmark, routing_root / "test-inputs.csv", routing_root / "calibration-inputs.csv"]]
    return {"status": "passed" if not matches else "overlap_detected", "schema": schema,
            "independently_replayed_targets": len(rows), "counterfactual_groups_complete": True,
            "verified_upstream_snapshot_hashes": len(manifest["sources"]), "journal_inventory": inventory,
            "visible_corpus_inventory": corpus_counts, "compiled_visible_requests": request_count,
            "input_bindings": bindings, "split_sha256": {s + ".jsonl": sha(dataset / (s + ".jsonl")) for s in schema["splits"]},
            "original_rows": len(rows), "upstream_rows_imported": 0, "matched_rows": len(matches),
            "quarantined_groups": sorted({m["group_id"] for m in matches}), "matches": matches,
            "label_gold_score_probability_fields_used_for_screening": False,
            "limits": ["A lexical screen cannot establish semantic or pretraining independence.",
                       "Author policy and natural-filter journals omit full input state; only available source literals can be screened.",
                       "Author prompt-injection logs truncate 94 messages at 200 characters.",
                       "Chess/poker/snake journals and browser summaries expose partial game/page state only.",
                       "Public benchmark inputs are development reference material; private/judge inputs were not accessed."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--jevbench-inputs", type=Path, required=True)
    parser.add_argument("--routing-root", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite an audit receipt")
    result = audit(args.raw_dir, args.dataset, args.jevbench_inputs, args.routing_root, args.source_manifest)
    result["audit_script_sha256"] = sha(__file__)
    result["independent_oracle_source_sha256"] = sha(Path("tests/test_policy_controls_v6.py"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k in ("status", "original_rows", "upstream_rows_imported", "matched_rows", "quarantined_groups")}, indent=2))
    raise SystemExit(bool(result["matched_rows"]))


if __name__ == "__main__":
    main()
