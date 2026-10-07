"""Audit pinned JF100 visible fields against existing Open-Jev dataset splits.

This never emits training records and never fingerprints benchmark gold labels.
Exact/substring matching is an overlap screen, not a semantic contamination test.
"""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from jev.data import SPLITS
from jev.eval_frontier import load_benchmark


OPTION_PREFIX = re.compile(r"^\s*(?:\(([A-D])\)|\[([A-D])\]|([A-D])[.:)])\s+(.+)$", re.DOTALL)


def normalize_text(value):
    if not isinstance(value, str):
        raise ValueError("visible text must be a string")
    return " ".join(unicodedata.normalize("NFC", value).split())


def normalize_state(value):
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("state object keys must be strings")
        return {key: normalize_state(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [normalize_state(item) for item in value]
    if value is None or type(value) in (int, float, bool):
        # json.dumps below rejects non-finite numbers.
        return value
    raise ValueError("unsupported state value")


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def normalized_options(options):
    """Ignore option order and only unambiguously positional A-D prefixes.

    A dictionary's exact A-D keys are outer labels; semantic keys remain visible. List
    labels are stripped only when all four entries have a standard prefix and
    collectively name A/B/C/D exactly once. Semantic names such as 'refund:' or
    an isolated 'A:' in an option's actual content are never stripped.
    """
    if isinstance(options, dict):
        descriptions = list(options.values()) if set(options) == set("ABCD") else [
            str(key) if value is None else f"{key}: {value}" for key, value in options.items()]
    elif isinstance(options, list):
        descriptions = list(options)
        matches = [OPTION_PREFIX.fullmatch(option) if isinstance(option, str) else None for option in descriptions]
        labels = [next((label for label in match.groups()[:3] if label is not None), None) for match in matches if match]
        if len(descriptions) == 4 and all(matches) and set(labels) == set("ABCD"):
            descriptions = [match.group(4) for match in matches]
    else:
        raise ValueError("options must be a dictionary or list")
    return sorted(normalize_text(option) for option in descriptions)


def visible_fingerprint(state, question, options):
    visible = {"state": normalize_state(state), "question": normalize_text(question),
               "options": normalized_options(options)}
    return hashlib.sha256(canonical(visible).encode()).hexdigest()


def state_text(value):
    normalized = normalize_state(value)
    return normalized if isinstance(normalized, str) else canonical(normalized)


def state_haystacks(value):
    """Full canonical state and actual string leaves, never label metadata."""
    yield state_text(value)
    if isinstance(value, dict):
        for child in value.values():
            yield from state_haystacks(child)
    elif isinstance(value, list):
        for child in value:
            yield from state_haystacks(child)


def contains_complete_text(haystack, needle):
    position = haystack.find(needle)
    while position >= 0:
        end = position + len(needle)
        word = lambda char: char.isalnum() or char == "_"
        left = position == 0 or not word(needle[0]) or not word(haystack[position - 1])
        right = end == len(haystack) or not word(needle[-1]) or not word(haystack[end])
        if left and right:
            return True
        position = haystack.find(needle, position + 1)
    return False


def benchmark_index(items, minimum_state_chars=80):
    if type(minimum_state_chars) is not int or minimum_state_chars < 1:
        raise ValueError("minimum_state_chars must be a positive integer")
    fingerprints, states = defaultdict(list), defaultdict(list)
    for item in items:
        # Explicit field selection prevents answer/rationale/difficulty leakage.
        fingerprint = visible_fingerprint(item["state"], item["question"], item["options"])
        fingerprints[fingerprint].append(item["id"])
        text = state_text(item["state"])
        if len(text) >= minimum_state_chars:
            states[text].append(item["id"])
    return dict(fingerprints), dict(states)


def match_row(row, fingerprints, benchmark_states, state_cache=None):
    exact = fingerprints.get(visible_fingerprint(row["state"], row["question"], row["options"]), [])
    state_key = hashlib.sha256(canonical(normalize_state(row["state"])).encode()).hexdigest()
    cache = state_cache if state_cache is not None else {}
    if state_key not in cache:
        haystacks = set(state_haystacks(row["state"]))
        cache[state_key] = sorted({item_id for needle, item_ids in benchmark_states.items()
                                   if any(contains_complete_text(haystack, needle) for haystack in haystacks)
                                   for item_id in item_ids})
    return {"exact_visible_item_ids": sorted(exact), "embedded_full_state_item_ids": cache[state_key]}, state_key


def frozen_dataset_splits(manifest):
    """Read release-mixture or native data manifests without weakening the freeze."""
    if not isinstance(manifest, dict):
        raise ValueError("Dataset manifest must be an object")

    def split_mapping(value, keys, label):
        if not isinstance(value, dict) or set(value) != set(keys):
            raise ValueError(f"Dataset manifest {label} must define all five splits exactly")
        return value

    declarations = []
    if "sha256" in manifest or "counts" in manifest:
        declarations.append((split_mapping(manifest.get("sha256"), SPLITS, "sha256"),
                             split_mapping(manifest.get("counts"), SPLITS, "counts")))
    summary = manifest.get("summary", {})
    if not isinstance(summary, dict):
        raise ValueError("Dataset manifest summary must be an object")
    if "files_sha256" in manifest:
        files = split_mapping(manifest["files_sha256"], [f"{split}.jsonl" for split in SPLITS], "files_sha256")
        declarations.append(({split: files[f"{split}.jsonl"] for split in SPLITS},
                             split_mapping(summary.get("splits"), SPLITS, "summary.splits")))
    if not declarations:
        raise ValueError("Dataset manifest must freeze counts and SHA-256 for all five splits")
    for hashes, counts in declarations:
        if any(not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
               for value in hashes.values()):
            raise ValueError("Dataset manifest SHA-256 values must be lowercase 64-digit hex strings")
        if any(type(value) is not int or value < 0 for value in counts.values()):
            raise ValueError("Dataset manifest split counts must be nonnegative integers")
    hashes, counts = declarations[0]
    if any(other_hashes != hashes or other_counts != counts for other_hashes, other_counts in declarations[1:]):
        raise ValueError("Dataset manifest contains contradictory split hashes/counts")
    if "splits" in summary:
        summary_counts = split_mapping(summary["splits"], SPLITS, "summary.splits")
        if any(type(value) is not int or value < 0 for value in summary_counts.values()) or summary_counts != counts:
            raise ValueError("Dataset manifest summary.splits contradicts frozen counts")
    if "records" in summary and (type(summary["records"]) is not int or summary["records"] != sum(counts.values())):
        raise ValueError("Dataset manifest summary.records contradicts frozen counts")
    return hashes, counts


def check_separation(benchmark_root, dataset, *, minimum_state_chars=80):
    items, _, _, source = load_benchmark(benchmark_root)
    fingerprints, benchmark_states = benchmark_index(items, minimum_state_chars)
    dataset = Path(dataset)
    manifest_path = dataset / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    declared_hashes, declared_counts = frozen_dataset_splits(manifest)
    splits, matches, state_cache = {}, [], {}
    for split in SPLITS:
        digest = hashlib.sha256()
        count, exact_rows, embedded_rows = 0, 0, 0
        unique_states, matched_items = set(), set()
        with (dataset / f"{split}.jsonl").open("rb") as handle:
            for line in handle:
                digest.update(line)
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("split") != split:
                    raise ValueError(f"Dataset row {row.get('id')} is in the wrong split file")
                count += 1
                found, state_key = match_row(row, fingerprints, benchmark_states, state_cache)
                unique_states.add(state_key)
                exact_rows += bool(found["exact_visible_item_ids"])
                embedded_rows += bool(found["embedded_full_state_item_ids"])
                item_ids = set(found["exact_visible_item_ids"]) | set(found["embedded_full_state_item_ids"])
                matched_items.update(item_ids)
                if item_ids:
                    matches.append({"split": split, "row_id": row["id"], "group_id": row.get("group_id"),
                                    "source": row.get("source"), **found})
        observed_hash = digest.hexdigest()
        if observed_hash != declared_hashes[split] or count != declared_counts[split]:
            raise ValueError(f"Frozen dataset checksum/count changed for {split}")
        splits[split] = {"sha256": observed_hash, "records": count, "unique_normalized_states": len(unique_states),
                         "exact_visible_match_rows": exact_rows, "embedded_full_state_match_rows": embedded_rows,
                         "matching_benchmark_items": len(matched_items)}
    return {"created_at_utc": datetime.now(timezone.utc).isoformat(),
            "auditor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "status": "overlap_detected" if matches else "no_detected_overlap",
            "benchmark": {"source_url": source["source_url"], "source_commit": source["source_commit"],
                          "dataset_version": source["dataset_version"], "license": source["license"],
                          "files_sha256": source["files_sha256"], "items": len(items),
                          "unique_visible_fingerprints": len(fingerprints),
                          "full_states_eligible_for_substring_check": sum(len(ids) for ids in benchmark_states.values())},
            "dataset": {"path": str(dataset), "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                        "records": sum(result["records"] for result in splits.values()), "splits": splits},
            "comparison": {"minimum_normalized_state_characters": minimum_state_chars,
                           "visible_fields": ["state", "question", "options"],
                           "excluded_fields": ["answer", "target", "rationale", "difficulty", "metadata"],
                           "normalization": "Unicode NFC and whitespace collapse, case preserved; sorted JSON keys; option order ignored; coherent A-D list prefixes stripped once",
                           "substring_scope": "Full benchmark state strings or canonical complete structured states inside dataset state/subtrees/string leaves; no question/rationale/metadata substring scan"},
            "exact_visible_match_rows": sum(result["exact_visible_match_rows"] for result in splits.values()),
            "embedded_full_state_match_rows": sum(result["embedded_full_state_match_rows"] for result in splits.values()),
            "matches": matches,
            "limits": ["Exact matching cannot rule out semantic paraphrases, shared concepts or independently derived tasks",
                       "This checks the specified fine-tuning dataset bytes only; it cannot establish pretraining uncontamination",
                       "Substring checking omits benchmark states shorter than the declared threshold; exact full-input matching still checks every item",
                       "Whitespace normalization is a conservative overlap screen, not proof of semantic equivalence for code",
                       "No benchmark gold labels, rationales or records are added to any training split by this audit"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", required=True, type=Path)
    parser.add_argument("--dataset", default=Path("data/release-v2"), type=Path)
    parser.add_argument("--minimum-state-chars", type=int, default=80)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = check_separation(args.benchmark_root, args.dataset, minimum_state_chars=args.minimum_state_chars)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "records": report["dataset"]["records"],
                      "exact_visible_match_rows": report["exact_visible_match_rows"],
                      "embedded_full_state_match_rows": report["embedded_full_state_match_rows"],
                      "output": str(args.output)}, indent=2))
    raise SystemExit(bool(report["matches"]))


if __name__ == "__main__":
    main()
