"""Restore an original frozen mixture using separately obtained Wikispeedia rows."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def restore(release_root, config, wiki_dir, output_dir):
    release_root, wiki_dir, output_dir = map(Path, (release_root, wiki_dir, output_dir))
    manifest = json.loads((release_root / "export-manifest.json").read_text())
    details = manifest["configs"][config]
    if not details["filtered"]:
        raise ValueError("Select one of the two redistributable mixture configs")
    wiki_manifest = json.loads((release_root / "provenance/original-manifests/wikiracing.json").read_text())
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for split, info in details["splits"].items():
        wiki_path = wiki_dir / f"{split}.jsonl"
        if sha256(wiki_path) != wiki_manifest["files_sha256"][f"{split}.jsonl"]:
            raise ValueError(f"Wikispeedia frozen source hash mismatch: {split}")
        wiki_rows = iter(json.loads(line) for line in wiki_path.read_text().splitlines())
        excluded = set(info["excluded_original_line_numbers"])
        target_path = output_dir / f"{split}.jsonl"
        if target_path.exists():
            raise FileExistsError(target_path)
        with gzip.open(release_root / info["raw_path"], "rb") as public, target_path.open("wb") as out:
            for number in range(1, info["original_count"] + 1):
                if number in excluded:
                    row = next(wiki_rows)
                    if row["source"] != "wikispeedia-v1" or row["split"] != split:
                        raise ValueError("Unexpected source or split in Wiki input")
                    # Exactly jev.mix_data.mix's serialization, including key order.
                    line = (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
                else:
                    line = public.readline()
                    if not line:
                        raise ValueError("Public projection ended early")
                out.write(line)
            if public.readline() or next(wiki_rows, None) is not None:
                raise ValueError("Unexpected extra source rows")
        actual = sha256(target_path)
        if actual != info["original_sha256"]:
            raise ValueError(f"Restored frozen hash mismatch: {split}")
        results[split] = {"count": info["original_count"], "sha256": actual}
    original_manifest = release_root / details["original_manifest_path"]
    (output_dir / "manifest.json").write_bytes(original_manifest.read_bytes())
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--wiki-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(restore(args.release_root, args.config, args.wiki_dir, args.output_dir), indent=2))
