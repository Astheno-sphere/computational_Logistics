"""Pinned, attributed WANLI conversion with seed/premise component holdouts.

Only official training examples can supply training/calibration/validation/OOD.
The OOD partition is a seed-family holdout, not a new-language/domain claim.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import unicodedata
import urllib.request

from .data import _write_dataset, read_jsonl


REPO = "alisawuffles/WANLI"
REVISION = "61c95318fd71c55b6ba355d76253254615f387ec"
VERSION = "wanli-decisions-v1"
FILES = {
    "train.jsonl": "85058cf017a911e89242dc29fa0a4ddaad3664cb923dc0a82145fdda14b694e5",
    "test.jsonl": "4276e0af7fcdf657d1ab7beb54eaf025fda592a76c9ee86b63b7871953fc74fd",
    "README.md": "63d95359bdd0c572c6196da6aff031593b1bc9d63c6d16d823a5f270b5ff0f9c",
}
LABELS = {
    "entailment": "The premise supports the claim.",
    "contradiction": "The premise contradicts the claim.",
    "neutral": "The premise leaves the claim undetermined.",
}
QUESTION = ("Treat the premise as given. Which relationship between the premise "
            "and the claim is supported? Missing evidence alone is not a contradiction.")


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def normalize(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def source_url(name):
    return f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{name}"


def fetch(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        path = directory / name
        if not path.exists():
            temporary = path.with_suffix(path.suffix + ".partial")
            with urllib.request.urlopen(source_url(name), timeout=120) as response, temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != expected:
                raise ValueError("Downloaded source checksum differs: " + name)
            temporary.replace(path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Pinned source checksum differs: " + name)


def convert_rows(sources, checksums, seed=20260921):
    """Group connected seed IDs and normalized premises before any splitting."""
    parent = {}

    def find(key):
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(first, second):
        a, b = find(first), find(second)
        if a != b:
            parent[max(a, b)] = min(a, b)

    all_rows, labels = [], defaultdict(set)
    for split in ("test", "train"):
        for row in sources[split]:
            if (row.get("gold") not in LABELS or not str(row.get("pairID", "")).strip()
                    or any(not isinstance(row.get(k), str) or not row[k].strip()
                           for k in ("premise", "hypothesis")) or "id" not in row):
                raise ValueError("Malformed WANLI example")
            premise = normalize(row["premise"])
            pair = (premise, normalize(row["hypothesis"]))
            key = "seed:" + str(row["pairID"])
            union(key, "premise:" + digest(premise))
            labels[pair].add(row["gold"])
            all_rows.append((split, row, key, pair))
    reserved = {find(key) for split, _, key, _ in all_rows if split == "test"}
    seen, result = set(), []
    removed = Counter()
    for original_split, raw, key, pair in all_rows:
        component = find(key)
        if original_split == "train" and component in reserved:
            removed["official_test_seed_or_premise_component"] += 1
            continue
        if len(labels[pair]) != 1:
            removed["conflicting_duplicate_pair"] += 1
            continue
        if pair in seen:
            removed["duplicate_pair"] += 1
            continue
        seen.add(pair)
        group = VERSION + ":" + digest(component)
        if original_split == "test":
            split = "test"
        else:
            bucket = int(digest(f"{seed}:{component}")[:16], 16) % 100
            split = "train" if bucket < 85 else "calibration" if bucket < 90 else "validation" if bucket < 95 else "ood"
        options = list(LABELS.values())
        random.Random(digest(f"{seed}:{raw['id']}:{component}")).shuffle(options)
        metadata = {
            "family": "natural_language_inference", "language": "en",
            "target_basis": "published_human_reviewed_label",
            "source_seed_id": str(raw["pairID"]), "source_genre": raw.get("genre"),
            "holdout_unit": "connected_MNLI_seed_and_normalized_premise",
            "ood_scope": "held_out_seed_components_within_WANLI",
            "provenance": {
                "type": "import", "license": "CC-BY-4.0", "revision": REVISION,
                "input_sha256": checksums[original_split],
                "source_url": source_url(original_split + ".jsonl"),
                "original_id": str(raw["id"]), "original_split": original_split,
                "split_policy": "reserve_official_test_components_then_85_5_5_5_seed_components_v1",
                "conversion": "premise/claim Choice; source text and human gold unchanged",
                "attribution": "Liu, Swayamdipta, Smith and Choi (2022), WANLI, Findings of EMNLP",
            },
        }
        result.append({
            "id": f"{VERSION}:{original_split}:{raw['id']}", "group_id": group,
            "split": split, "source": VERSION, "kind": "choice",
            "state": {"premise": raw["premise"], "claim": raw["hypothesis"]},
            "question": QUESTION, "options": options,
            "target": [float(option == LABELS[raw["gold"]]) for option in options],
            "metadata": metadata,
        })
    return result, dict(removed)


def build(source, output, seed=20260921):
    output = Path(output)
    if output.resolve() == Path(source).resolve():
        raise ValueError("WANLI output must differ from the pinned source directory")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("WANLI output must be a new or empty directory")
    fetch(source)
    source = Path(source)
    sources = {s: list(read_jsonl(source / (s + ".jsonl"))) for s in ("train", "test")}
    rows, removed = convert_rows(sources, {s: FILES[s + ".jsonl"] for s in sources}, seed)
    manifest = _write_dataset(rows, output, {
        "type": "import", "version": VERSION, "seed": seed, "repo": REPO,
        "revision": REVISION, "license": "CC-BY-4.0", "input_files_sha256": FILES,
        "source_counts": {s: len(v) for s, v in sources.items()}, "removed": removed,
        "limitations": ["Human reviewed labels are not infallible.",
                        "One English NLI source; not an additional collection of operational domains.",
                        "No JevBench or frontier instances were supplied to this conversion."],
    })
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=20260921)
    args = parser.parse_args()
    print(json.dumps(build(args.source_dir, args.output_dir, args.seed), indent=2))


if __name__ == "__main__":
    main()
