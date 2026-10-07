"""Concatenate already split datasets, then enforce cross-source group checks."""
import argparse
import hashlib
import json
from pathlib import Path

from .data import SPLITS, read_jsonl, validate_records


def mix(inputs, output_dir):
    output = Path(output_dir)
    for source in inputs:
        if not Path(source).is_dir():
            raise ValueError(f"Input dataset directory does not exist: {source}")
    all_rows, counts = [], {}
    for split in SPLITS:
        rows = []
        for source in inputs:
            path = Path(source) / f"{split}.jsonl"
            if path.exists():
                for row in read_jsonl(path):
                    if row.get("split") != split:
                        raise ValueError(f"{path}: row {row.get('id', '?')} has split {row.get('split')!r}, expected {split!r}")
                    rows.append(row)
        all_rows.extend(rows)
        counts[split] = len(rows)
    summary = validate_records(all_rows)
    output.mkdir(parents=True, exist_ok=True)
    for split in counts:
        rows = [r for r in all_rows if r["split"] == split]
        (output / f"{split}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    manifest = {"counts": counts, "sources": [str(source) for source in inputs], "summary": summary,
                "sha256": {s: hashlib.sha256((output / f"{s}.jsonl").read_bytes()).hexdigest() for s in counts}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    manifest = mix(args.inputs, args.output_dir)
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
