"""Freeze new hard sources plus a bounded, group-diverse replay of old sources."""
import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path

from jev.data import SPLITS, _write_dataset, read_jsonl


def rank(value, seed):
    return hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()


def replay_sample(rows, cap, seed):
    by_source = defaultdict(lambda: defaultdict(list))
    for row in rows:
        by_source[row["source"]][row["group_id"]].append(row)
    selected = []
    for source, groups in sorted(by_source.items()):
        queues = deque(deque(sorted(groups[g], key=lambda r: rank(r["id"], seed)))
                       for g in sorted(groups, key=lambda g: rank(g, seed)))
        kept = 0
        while queues and kept < cap:
            group = queues.popleft()
            selected.append(group.popleft())
            kept += 1
            if group:
                queues.append(group)
    return selected


def build(new_inputs, replay_inputs, output, cap=1500, seed=20260921, excluded_groups=(),
          version="community-hard-mix-v2"):
    output = Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Mixture output must be a new or empty directory")
    if cap < 1 or not new_inputs:
        raise ValueError("At least one new dataset and a positive replay cap are required")
    excluded = set(excluded_groups)
    records, replay_train, bindings, seen_ids = [], [], [], set()
    filtered = Counter()
    for category, inputs in (("new", new_inputs), ("replay", replay_inputs)):
        for folder in inputs:
            folder = Path(folder)
            source_manifest = json.loads((folder / "manifest.json").read_text())
            hashes = {s: hashlib.sha256((folder / (s + ".jsonl")).read_bytes()).hexdigest() for s in SPLITS}
            declared = []
            if "files_sha256" in source_manifest:
                declared.append({s: source_manifest["files_sha256"].get(s + ".jsonl") for s in SPLITS})
            if "sha256" in source_manifest:
                declared.append({s: source_manifest["sha256"].get(s) for s in SPLITS})
            if not declared or any(value != hashes for value in declared):
                raise ValueError("Source split checksums disagree with manifest: " + str(folder))
            bindings.append({"category": category, "path": str(folder),
                             "manifest_sha256": hashlib.sha256((folder / "manifest.json").read_bytes()).hexdigest(),
                             "files_sha256": hashes})
            for split in SPLITS:
                rows = list(read_jsonl(folder / (split + ".jsonl")))
                if any(row["split"] != split for row in rows):
                    raise ValueError("Source split file disagrees with row split")
                for row in rows:
                    if row["group_id"] in excluded:
                        filtered["quarantined_group"] += 1
                        continue
                    if row["id"] in seen_ids:
                        raise ValueError("Duplicate source row supplied to mixture: " + row["id"])
                    seen_ids.add(row["id"])
                    if category == "replay" and split == "train":
                        replay_train.append(row)
                    else:
                        records.append(row)
    selected_replay = replay_sample(replay_train, cap, seed)
    filtered["replay_train_cap"] += len(replay_train) - len(selected_replay)
    records.extend(selected_replay)
    manifest = _write_dataset(records, output, {
        "version": version, "seed": seed,
        "replay_cap_per_source": cap, "input_bindings": bindings,
        "replay_policy": "Hash-ordered round robin across parent groups; no duplication or oversampling.",
        "new_source_policy": "One full pass over retained rows; four-rank training wraps at most three rows to complete its final step.",
        "excluded_groups": sorted(excluded), "filtered": dict(filtered),
    })
    train = [r for r in records if r["split"] == "train"]
    manifest["counts"] = {s: manifest["summary"]["splits"].get(s, 0) for s in SPLITS}
    manifest["sha256"] = {s: manifest["files_sha256"][s + ".jsonl"] for s in SPLITS}
    manifest["training_by_source"] = dict(sorted(Counter(r["source"] for r in train).items()))
    manifest["training_groups_by_source"] = {s: len({r["group_id"] for r in train if r["source"] == s}) for s in manifest["training_by_source"]}
    manifest["full_pass_four_gpu_steps"] = (len(train) + 3) // 4
    manifest["full_pass_four_gpu_rows_consumed"] = manifest["full_pass_four_gpu_steps"] * 4
    manifest["full_pass_four_gpu_wrapped_rows"] = manifest["full_pass_four_gpu_rows_consumed"] - len(train)
    (Path(output) / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new-inputs", nargs="+", required=True)
    parser.add_argument("--replay-inputs", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--replay-cap", type=int, default=1500)
    parser.add_argument("--version", default="community-hard-mix-v2")
    parser.add_argument("--exclude-groups-json")
    args = parser.parse_args()
    excluded = json.loads(Path(args.exclude_groups_json).read_text()) if args.exclude_groups_json else []
    print(json.dumps(build(args.new_inputs, args.replay_inputs, args.output, args.replay_cap,
                           excluded_groups=excluded, version=args.version), indent=2))


if __name__ == "__main__":
    main()
