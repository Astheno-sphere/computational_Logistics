"""Export only the seven frozen, reviewed Open-Jev corpora for Hugging Face."""
import argparse
import collections
import gzip
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from restore_original_mixture import restore, sha256


SPLITS = ("train", "calibration", "validation", "test", "ood")
COUNTS = {
    "release-v2": (80816, 4761, 3792, 10532, 15920),
    "browser-drone-expansion-v1": (110324, 6883, 5562, 14902, 25379),
    "citation-control-v1": (2520, 200, 180, 300, 800),
    "entity-alignment-control-v1": (6944, 728, 280, 1008, 2240),
    "amount-extraction-control-v1": (32984, 2232, 992, 3472, 9920),
    "email-selection-control-v1": (3618, 81, 189, 432, 1080),
    "phone-extraction-control-v1": (12350, 855, 380, 1615, 3800),
}
EXCLUSIONS = dict(zip(SPLITS, (1700, 89, 69, 176, 219)))
EXTRAS = {
    "citation-control-v1": ("documents.jsonl", "cases.jsonl"),
    "entity-alignment-control-v1": ("families.jsonl", "cases.jsonl"),
    "amount-extraction-control-v1": ("families.jsonl", "cases.jsonl"),
    "email-selection-control-v1": ("families.jsonl", "cases.jsonl"),
    "phone-extraction-control-v1": ("families.jsonl", "cases.jsonl"),
}
SUPPLEMENTAL = {
    "case-customer": ("manifest.json", "workflow_cases.jsonl", "target-statistics.json"),
    "painting-geometry-v1": ("manifest.json",),
    "games-v1": ("manifest.json",),
    "control-games-v1": ("manifest.json",),
    "doom-basic-v1": ("manifest.json", "replay-report.json"),
    "workflow-controls-v1": ("manifest.json", "workflow_cases.jsonl"),
    "reasoning-control-v1": ("manifest.json",),
    "browser-v1": ("manifest.json", "cases.jsonl"),
    "drone-control-v1": ("manifest.json", "cases.jsonl"),
}
SCHEMA = pa.schema([
    ("id", pa.string()), ("group_id", pa.string()), ("split", pa.string()),
    ("source", pa.string()), ("kind", pa.string()), ("question", pa.string()),
    ("options", pa.list_(pa.string())), ("target", pa.list_(pa.float64())),
    ("state_json", pa.string()), ("metadata_json", pa.string()),
    ("record_json", pa.string()), ("original_line_number", pa.int64()),
])
FIELDS = {"id", "group_id", "split", "source", "kind", "question", "options", "target", "state", "metadata"}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def compress_file(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as original, destination.open("wb") as compressed:
        with gzip.GzipFile(filename="", fileobj=compressed, mode="wb", mtime=0) as out:
            shutil.copyfileobj(original, out)
    return {"original_sha256": sha256(source), "compressed_sha256": sha256(destination),
            "original_bytes": source.stat().st_size, "compressed_bytes": destination.stat().st_size}


def export_split(source, name, split, output, original_manifest, group_splits, ids):
    filtered = name in ("release-v2", "browser-drone-expansion-v1")
    config = name + "-redistributable" if filtered else name
    raw_path = Path("raw") / config / f"{split}.jsonl.gz"
    parquet_path = Path("data") / config / f"{split}-00000-of-00001.parquet"
    raw_file, parquet_file = output / raw_path, output / parquet_path
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    parquet_file.parent.mkdir(parents=True, exist_ok=True)
    source_hash, public_hash = hashlib.sha256(), hashlib.sha256()
    sources, kinds, excluded = collections.Counter(), collections.Counter(), []
    total, kept, batch = 0, 0, []
    with source.open("rb") as stream, raw_file.open("wb") as compressed:
        with gzip.GzipFile(filename="", fileobj=compressed, mode="wb", mtime=0) as raw:
            with pq.ParquetWriter(parquet_file, SCHEMA, compression="zstd") as writer:
                for total, line in enumerate(stream, 1):
                    source_hash.update(line)
                    row = json.loads(line)
                    assert set(row) == FIELDS, (name, split, set(row) ^ FIELDS)
                    assert row["split"] == split
                    if row["source"] == "wikispeedia-v1":
                        assert filtered
                        excluded.append(total)
                        continue
                    assert row["id"] not in ids, (name, row["id"])
                    ids.add(row["id"])
                    key = (row["source"], row["group_id"])
                    assert group_splits.setdefault(key, split) == split, (name, key)
                    assert row["target"] and all(isinstance(x, (int, float)) for x in row["target"])
                    sources[row["source"]] += 1
                    kinds[row["kind"]] += 1
                    raw.write(line)
                    public_hash.update(line)
                    parsed = {k: row[k] for k in ("id", "group_id", "split", "source", "kind", "question", "options", "target")}
                    parsed.update(state_json=json.dumps(row["state"], ensure_ascii=False),
                                  metadata_json=json.dumps(row["metadata"], ensure_ascii=False),
                                  record_json=line.decode("utf-8").rstrip("\n"), original_line_number=total)
                    batch.append(parsed)
                    kept += 1
                    if len(batch) == 1024:
                        writer.write_table(pa.Table.from_pylist(batch, schema=SCHEMA))
                        batch = []
                if batch:
                    writer.write_table(pa.Table.from_pylist(batch, schema=SCHEMA))
    frozen_hash = original_manifest.get("sha256", {}).get(split) or original_manifest["files_sha256"][f"{split}.jsonl"]
    assert source_hash.hexdigest() == frozen_hash, (name, split, "frozen hash mismatch")
    assert total == COUNTS[name][SPLITS.index(split)]
    assert len(excluded) == (EXCLUSIONS[split] if filtered else 0)
    assert pq.ParquetFile(parquet_file).metadata.num_rows == kept
    # Verify every Parquet record exactly recovers the published raw source line.
    verified_hash, verified_count = hashlib.sha256(), 0
    with gzip.open(raw_file, "rb") as original:
        for batch in pq.ParquetFile(parquet_file).iter_batches():
            for row in batch.to_pylist():
                line = original.readline()
                assert (row["record_json"] + "\n").encode() == line
                decoded = json.loads(line)
                assert json.loads(row["state_json"]) == decoded["state"]
                assert json.loads(row["metadata_json"]) == decoded["metadata"]
                assert row["target"] == decoded["target"]
                verified_hash.update(line)
                verified_count += 1
        assert not original.readline()
    assert verified_count == kept and verified_hash.hexdigest() == public_hash.hexdigest()
    return {"original_count": total, "count": kept, "excluded_count": len(excluded),
            "excluded_original_line_numbers": excluded,
            "original_sha256": source_hash.hexdigest(), "raw_uncompressed_sha256": public_hash.hexdigest(),
            "raw_path": raw_path.as_posix(), "parquet_path": parquet_path.as_posix(),
            "sources": dict(sources), "kinds": dict(kinds)}


def build(repo, output, report_dir):
    if output.exists():
        raise FileExistsError(f"Use a fresh staging directory: {output}")
    output.mkdir(parents=True)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    manifest = {"schema_version": 1, "repo_id": "ZefanCai/Open-Jev", "code_repository": "https://github.com/Zefan-Cai/Open-Jev-Dev",
                "code_checkout_head_at_export": revision,
                "scope": "Seven separate frozen corpora; mixtures are redistributable projections, not exact original training data.",
                "overlap": "release-v2-redistributable is contained in browser-drone-expansion-v1-redistributable; config totals must not be summed as unique data.",
                "filter": {"source": "wikispeedia-v1", "reason": "No verified separate redistribution license for upstream graph/path archive.",
                           "source_url": "https://snap.stanford.edu/data/wikispeedia.html",
                           "archive_url": "https://snap.stanford.edu/data/wikispeedia/wikispeedia_paths-and-graph.tar.gz",
                           "archive_sha256": "97697096f5d2dcb77aa69e3992305c6c561de89edb9fb10b5ad9feaf8ba534d5"},
                "configs": {}, "supplemental_artifacts": {}, "source_code_sha256": {}}
    for name in COUNTS:
        frozen = json.loads((repo / "data" / name / "manifest.json").read_text())
        filtered = name in ("release-v2", "browser-drone-expansion-v1")
        config = name + "-redistributable" if filtered else name
        original_manifest_path = f"provenance/original-manifests/{name}.json"
        (output / original_manifest_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / "data" / name / "manifest.json", output / original_manifest_path)
        details = {"original_dataset": name, "filtered": filtered, "original_manifest_path": original_manifest_path,
                   "training_status": "Original release-v2 used by released 2B/9B checkpoints" if name == "release-v2" else
                       ("Original expansion mixture used by an in-progress 27B experiment; no completed-result claim" if filtered else "Prepared and audited; no training or model inference performed"),
                   "splits": {}, "extra_artifacts": {}}
        groups, ids = {}, set()
        for split in SPLITS:
            details["splits"][split] = export_split(repo / "data" / name / f"{split}.jsonl", name, split, output, frozen, groups, ids)
            print(f"verified {config}/{split}: {details['splits'][split]['count']}", flush=True)
        details["total"] = sum(s["count"] for s in details["splits"].values())
        details["group_count"] = len(groups)
        for filename in EXTRAS.get(name, ()):
            source = repo / "data" / name / filename
            assert sha256(source) == frozen["files_sha256"][filename]
            dest = f"artifacts/{name}/{filename}.gz"
            details["extra_artifacts"][dest] = compress_file(source, output / dest)
        for filename, digest in frozen.get("configuration", {}).get("source_files_sha256", {}).items():
            assert sha256(repo / "jev" / filename) == digest, (name, filename, "generator changed")
        manifest["configs"][config] = details
    for name, filenames in SUPPLEMENTAL.items():
        for filename in filenames:
            source = repo / "data" / name / filename
            dest = f"provenance/component-artifacts/{name}/{filename}"
            if filename.endswith(".jsonl"):
                dest += ".gz"
                info = compress_file(source, output / dest)
            else:
                (output / dest).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, output / dest)
                info = {"original_sha256": sha256(source), "bytes": source.stat().st_size}
            manifest["supplemental_artifacts"][dest] = info
    shutil.copyfile(repo / "data/wikiracing/manifest.json", output / "provenance/original-manifests/wikiracing.json")
    # Original MIT source only; no dataset, credentials, game assets or benchmark payload.
    for source in sorted((repo / "jev").glob("*.py")):
        dest = output / "reproduce/source-code/jev" / source.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        manifest["source_code_sha256"][f"jev/{source.name}"] = sha256(source)
    for filename in ("pyproject.toml", "LICENSE"):
        shutil.copyfile(repo / filename, output / "reproduce/source-code" / filename)
    shutil.copyfile(repo / "THIRD_PARTY_NOTICES.md", output / "THIRD_PARTY_NOTICES.md")
    shutil.copyfile(repo / "LICENSE", output / "LICENSE-CODE-MIT")
    shutil.copyfile(report_dir / "restore_original_mixture.py", output / "reproduce/restore_original_mixture.py")
    shutil.copyfile(report_dir / "build_release.py", output / "reproduce/build_release.py")
    shutil.copyfile(report_dir / "dataset-card.md", output / "README.md")
    shutil.copyfile(report_dir / "reproduction.md", output / "REPRODUCTION.md")
    (output / "reproduce/source-code/README.md").write_text("Exact source snapshot for Open-Jev data reproduction. See ../../REPRODUCTION.md. Original code is MIT licensed.\n")
    (output / "LICENSE-DATA").write_text("Original generated Open-Jev records are dedicated under CC0 1.0 Universal.\nhttps://creativecommons.org/publicdomain/zero/1.0/legalcode\nThis dedication does not relicense upstream wording, sources, game assets, model weights, or code. See README.md and THIRD_PARTY_NOTICES.md.\n")
    write_json(output / "export-manifest.json", manifest)
    restoration = {}
    for config in list(manifest["configs"])[:2]:
        destination = output.parent / "restoration-audit" / config
        restoration[config] = restore(output, config, repo / "data/wikiracing", destination)
    write_json(report_dir / "local-verification.json", {"all_35_splits_verified": True,
        "original_manifest_hashes_verified": True, "parquet_raw_exact_roundtrip": True,
        "within_config_ids_unique": True, "within_config_groups_disjoint_between_splits": True,
        "wiki_restoration_exact_original_hashes": restoration,
        "configs": {c: {"count": d["total"], "splits": {s: x["count"] for s, x in d["splits"].items()}} for c, d in manifest["configs"].items()}})
    manifest["published_files"] = {p.relative_to(output).as_posix(): {"sha256": sha256(p), "bytes": p.stat().st_size}
                                   for p in sorted(output.rglob("*")) if p.is_file() and p.name != "export-manifest.json"}
    write_json(output / "export-manifest.json", manifest)
    write_json(report_dir / "export-summary.json", {"configs": {k: {"total": v["total"], "filtered": v["filtered"]} for k, v in manifest["configs"].items()},
        "files": len(manifest["published_files"]) + 1, "bytes": sum(x["bytes"] for x in manifest["published_files"].values()),
        "export_manifest_sha256": sha256(output / "export-manifest.json")})
    print("All seven frozen corpora exported and verified.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.repo, args.output, Path(__file__).resolve().parent)
