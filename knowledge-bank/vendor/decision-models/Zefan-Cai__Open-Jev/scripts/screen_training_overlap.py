"""Read-only lexical screen against PRIVATE frozen evaluation requests, never gold.

No benchmark content is exported or used to generate training examples. A match
quarantines the training parent group; zero matches cannot prove semantic or
pretraining independence.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from jev.api import compile_request
from jev.data import read_jsonl


def norm(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def leaves(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from leaves(item)
    elif isinstance(value, list):
        for item in value:
            yield from leaves(item)


def words(text):
    return re.findall(r"\w+", norm(text))


def shingles(text, n=13):
    tokens = words(text)
    return {hashlib.sha256(" ".join(tokens[i:i+n]).encode()).digest() for i in range(len(tokens)-n+1)}


def fingerprint(row):
    return hashlib.sha256(canonical([norm(canonical(row["state"])), norm(row["question"]),
                                    row["kind"], sorted(norm(x) for x in row["options"])]).encode()).hexdigest()


def build_index(documents):
    exact, grams, short = set(), set(), set()
    requests = 0
    for doc in documents:
        for work in doc["workloads"]:
            request = work["request"]
            records = compile_request(request["state"], request["questions"])
            requests += 1
            for row in records:
                exact.add(fingerprint(row))
            for text in leaves(request["state"]):
                grams.update(shingles(text))
                if len(words(text)) >= 8:
                    short.add(norm(text))
    if not requests:
        raise ValueError("At least one frozen benchmark request is required for overlap screening")
    return exact, grams, short, requests


def screen(request_files, datasets):
    index = build_index([json.loads(Path(p).read_text()) for p in request_files])
    exact, grams, short, request_count = index
    matches, bindings, groups, counts = [], [], set(), Counter()
    for dataset in datasets:
        path = Path(dataset) / "train.jsonl"
        bindings.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        for row in read_jsonl(path):
            counts[str(dataset)] += 1
            reasons = []
            if fingerprint(row) in exact:
                reasons.append("exact_visible_input")
            state_leaves = list(leaves(row["state"]))
            if any(norm(text) in short for text in state_leaves):
                reasons.append("normalized_state_leaf_ge8_words")
            if any(shingles(text) & grams for text in state_leaves):
                reasons.append("state_13_token_shingle")
            if reasons:
                groups.add(row["group_id"])
                matches.append({"id": row["id"], "group_id": row["group_id"], "source": row["source"], "reasons": reasons})
    return {"status": "overlap_detected" if matches else "no_detected_overlap",
            "request_files": [{"sha256": hashlib.sha256(Path(p).read_bytes()).hexdigest(), "name": Path(p).name} for p in request_files],
            "request_count": request_count, "dataset_files": bindings, "training_rows": dict(counts),
            "matched_rows": len(matches), "excluded_groups": sorted(groups), "matches": matches,
            "policy": "Visible state/question/options only; no targets, gold, answers or rationales read from benchmark requests.",
            "limits": ["Lexical screen cannot detect paraphrases or prove semantic independence.",
                       "Does not assess foundation-model pretraining exposure.",
                       "13-token overlap may also flag harmless shared wording; matching groups are quarantined conservatively.",
                       "Shorter state leaves are covered by full-input exact matching only."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", nargs="+", required=True)
    parser.add_argument("--datasets", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = screen(args.requests, args.datasets)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("matches", "excluded_groups")}, indent=2))
    raise SystemExit(bool(result["matched_rows"]))


if __name__ == "__main__":
    main()
