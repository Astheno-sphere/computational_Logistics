"""Verify archived length evidence and derive workload/cap summaries; no tokenizer needed."""

import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
import gzip
import hashlib
from itertools import zip_longest
import json
from pathlib import Path


SPLITS = ("train", "calibration", "validation", "test", "ood")
TAGS = ("2b", "9b", "27b")
CAPS = (512, 1536, 2048, 4096, 8192, 16384)
MODELS = {
    "2b": ("Qwen/Qwen3.5-2B", "15852e8c16360a2fea060d615a32b45270f8a8fc"),
    "9b": ("Qwen/Qwen3.5-9B", "c202236235762e1c871ad0ccb60c8ee5ba337b9a"),
    "27b": ("Qwen/Qwen3.8-27B", "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"),
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    repo = root.parents[2]
    manifest = json.loads((args.data / "manifest.json").read_text())
    reports = {tag: json.loads((root / tag / "report.json").read_text()) for tag in TAGS}
    artifacts = {}
    for tag, report in reports.items():
        assert report["complete"] and report["passes_required_limit"], tag
        assert (report["model"], report["revision"]) == MODELS[tag], tag
        assert report["required_max_length"] == 4096, tag
        assert report["dataset_manifest_sha256"] == sha256(args.data / "manifest.json"), tag
        assert report["script_sha256"] == sha256(repo / "scripts/audit_candidate_lengths.py"), tag
        for filename, expected in report["implementation_sha256"].items():
            assert sha256(repo / filename) == expected, (tag, filename)
        assert report["dataset_split_sha256"] == manifest["sha256"], tag
        assert report["cpu_only"] == {"CUDA_VISIBLE_DEVICES": "", "offline": True,
                                      "cuda_initialized": False, "denied_weight_opens": []}, tag
        assert report["observed_training_pids_before"] == report["observed_training_pids_after"], tag
        assert all(item["exists"] for item in report["observed_training_pids_after"].values()), tag
        assert not report["existing_preflight_comparison"]["mismatches"], tag
        for filename in ("report.json", "row-lengths.jsonl.gz"):
            path = root / tag / filename
            artifacts[str(path.relative_to(root))] = {"sha256": sha256(path), "bytes": path.stat().st_size}
        assert artifacts[f"{tag}/row-lengths.jsonl.gz"]["sha256"] == report["row_lengths_sha256"], tag
    statistics = defaultdict(Counter)

    def add(key, lengths):
        stats = statistics[key]
        stats.update(rows=1, candidate_sequences=len(lengths), input_tokens=sum(lengths),
                     padded_tokens_if_each_row_encoded_separately=max(lengths) * len(lengths))
        stats["max_tokens"] = max(stats["max_tokens"], max(lengths))
        stats["max_candidate_sequences_per_row"] = max(stats["max_candidate_sequences_per_row"], len(lengths))
        for cap in CAPS:
            stats[f"rows_over_{cap}"] += max(lengths) > cap
            stats[f"candidates_over_{cap}"] += sum(length > cap for length in lengths)

    def dataset_rows():
        for split in SPLITS:
            path = args.data / f"{split}.jsonl"
            assert sha256(path) == manifest["sha256"][split], split
            with path.open() as stream:
                for line in stream:
                    if line.strip():
                        row = json.loads(line)
                        assert row["split"] == split
                        yield row

    with ExitStack() as stack:
        streams = [stack.enter_context(gzip.open(root / tag / "row-lengths.jsonl.gz", "rt")) for tag in TAGS]
        for row, *lines in zip_longest(dataset_rows(), *streams):
            assert row is not None and all(lines), "Missing/extra row in an evidence file"
            entries = [json.loads(line) for line in lines]
            assert all(entry == entries[0] for entry in entries), row["id"]
            entry = entries[0]
            assert all(row[key] == entry[key] for key in ("id", "source", "split", "kind")), row["id"]
            inputs = {key: row[key] for key in ("state", "question", "kind", "options")}
            assert hashlib.sha256(canonical(inputs).encode()).hexdigest() == entry["model_input_sha256"], row["id"]
            lengths = entry["candidate_tokens"]
            assert lengths and all(type(length) is int and length > 0 for length in lengths)
            assert len(lengths) == (1 if row["kind"] == "noul" else len(row["options"])), row["id"]
            dataset = {"browser-control-v1": "browser-v1", "drone-control-v1": "drone-control-v1"}.get(row["source"], "release-v2")
            for key in ("overall", f"split/{row['split']}", f"source/{row['source']}",
                        f"dataset/{dataset}", f"split_dataset/{row['split']}/{dataset}"):
                add(key, lengths)
    for tag, report in reports.items():
        sections = [("overall", report["overall"])]
        sections += [(f"split/{split}", report["by_split"][split]) for split in SPLITS]
        sections += [(f"source/{source}", value) for source, value in report["by_source"].items()]
        for key, expected in sections:
            actual = statistics[key]
            for name in ("rows", "candidate_sequences", "input_tokens", "max_tokens",
                         "max_candidate_sequences_per_row", "padded_tokens_if_each_row_encoded_separately"):
                assert actual[name] == expected[name], (tag, key, name)
            for cap, counts in expected["over_limits"].items():
                assert actual[f"rows_over_{cap}"] == counts["rows"], (tag, key, cap)
                assert actual[f"candidates_over_{cap}"] == counts["candidate_sequences"], (tag, key, cap)
    print(json.dumps({"verified": True, "models": {tag: reports[tag]["model"] for tag in TAGS},
                      "dataset_manifest_sha256": sha256(args.data / "manifest.json"),
                      "verifier_sha256": sha256(Path(__file__)), "artifacts": artifacts,
                      "all_per_row_candidate_lengths_identical": True,
                      "all_model_token_ids_identical": "not checked",
                      "statistics": dict(sorted(statistics.items()))}, indent=2) + "\n", end="")


if __name__ == "__main__":
    main()
