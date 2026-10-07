"""Convert pinned BoolQ into Noul, preserving official validation as our test."""
import argparse
import hashlib
import json
import urllib.request
from pathlib import Path


REPO = "google/boolq"
REVISION = "35b264d03638db9f4ce671b711558bf7ff0f80d5"


def _load_split(original_split):
    import pyarrow.parquet as pq
    import pyarrow as pa

    url = f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/data/{original_split}-00000-of-00001.parquet"
    with urllib.request.urlopen(url, timeout=60) as handle:
        raw = handle.read()
    return pq.read_table(pa.BufferReader(raw)).to_pylist(), url, hashlib.sha256(raw).hexdigest()


def convert(output, max_train=3000):
    from .data import validate_records
    if max_train < 0:
        raise ValueError("max_train must be nonnegative")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    buckets = {s: [] for s in ["train", "calibration", "validation", "test"]}
    test_groups, seen_inputs = set(), {}
    counts = {"duplicates": 0, "cross_split_passages": 0, "length_filtered": 0, "train_cap": 0}
    input_checksums = {}
    # Reserve every official validation passage, including length-filtered rows.
    # Distinct questions about one passage stay together and remain useful data.
    for original_split in ["validation", "train"]:
        source_rows, url, input_sha256 = _load_split(original_split)
        input_checksums[original_split] = input_sha256
        for index, row in enumerate(source_rows):
            passage = row["passage"].strip()
            group = hashlib.sha256(" ".join(passage.lower().split()).encode()).hexdigest()
            if original_split == "validation":
                test_groups.add(group)
            elif group in test_groups:
                counts["cross_split_passages"] += 1
                continue
            question = row["question"].strip()
            answer = int(row["answer"])
            if answer not in (0, 1):
                raise ValueError(f"BoolQ {original_split} row {index}: answer is not binary")
            fingerprint = (group, " ".join(question.lower().split()))
            if fingerprint in seen_inputs:
                if seen_inputs[fingerprint] != answer:
                    raise ValueError(f"BoolQ {original_split} row {index}: identical input has conflicting labels")
                counts["duplicates"] += 1
                continue
            seen_inputs[fingerprint] = answer
            # Explicitly bounded short-context pilot subset; no input truncation.
            if len((passage + " " + question).split()) > 150:
                counts["length_filtered"] += 1
                continue
            if original_split == "validation":
                split = "test"
            else:
                value = int(group[:8], 16) % 10
                split = "calibration" if value == 0 else "validation" if value == 1 else "train"
                if split == "train" and len(buckets[split]) >= max_train:
                    counts["train_cap"] += 1
                    continue
            original_id = f"boolq-{original_split}-{index}"
            buckets[split].append({
                "id": original_id, "group_id": "boolq-" + group,
                "split": split, "source": REPO, "state": passage,
                "question": question, "kind": "noul", "options": ["no", "yes"],
                "target": [float(1 - answer), float(answer)],
                "metadata": {"family": "reading_comprehension", "original_split": original_split,
                             "revision": REVISION, "license": "cc-by-sa-3.0", "url": url,
                             "label_provenance": "official_boolq_answer", "target_type": "hard",
                             "provenance": {"type": "import", "input_sha256": input_sha256,
                                            "source_url": url, "license": "cc-by-sa-3.0",
                                            "original_id": original_id, "original_split": original_split,
                                            "revision": REVISION,
                                            "split_policy": "official_validation_test_passage_hash_v1"}},
            })
    all_rows = [r for rows in buckets.values() for r in rows]
    validate_records(all_rows)
    for split, rows in buckets.items():
        (output / f"{split}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    manifest = {"dataset": REPO, "revision": REVISION, "license": "cc-by-sa-3.0",
                "counts": {s: len(r) for s, r in buckets.items()}, "filtered": counts,
                "input_files_sha256": input_checksums,
                "files_sha256": {f"{s}.jsonl": hashlib.sha256((output / f"{s}.jsonl").read_bytes()).hexdigest() for s in buckets},
                "max_train": max_train,
                "policy": "Original validation passages reserved for test; distinct questions retained; passage groups isolated; <=150 whitespace words"}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest))
    return manifest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", required=True)
    p.add_argument("--max-train", type=int, default=3000)
    args = p.parse_args()
    convert(args.output_dir, args.max_train)


if __name__ == "__main__":
    main()
