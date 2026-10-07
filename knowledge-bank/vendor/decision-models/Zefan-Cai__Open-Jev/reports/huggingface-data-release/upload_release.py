"""Publish the audited folder and verify the pinned public Hugging Face release."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from datasets import load_dataset
from huggingface_hub import DatasetCard, HfApi, hf_hub_download

from restore_original_mixture import sha256


REPO_ID = "ZefanCai/Open-Jev"


def main(staging, reports, verify_only=None):
    token = os.environ["HUGGINGFACE_TOKEN"]
    api = HfApi(token=token)
    identity = api.whoami()
    if identity.get("name") != "ZefanCai":
        raise ValueError("Unexpected Hugging Face account")
    manifest = json.loads((staging / "export-manifest.json").read_text())
    local_files = {p.relative_to(staging).as_posix(): p for p in staging.rglob("*") if p.is_file()}
    expected = set(manifest["published_files"]) | {"export-manifest.json"}
    if set(local_files) != expected:
        raise ValueError("Staging contains files outside the audited export manifest")
    for name, info in manifest["published_files"].items():
        if sha256(local_files[name]) != info["sha256"]:
            raise ValueError(f"Staged file changed after audit: {name}")
    DatasetCard.load(staging / "README.md").validate()
    repo = api.repo_info(REPO_ID, repo_type="dataset")
    if repo.private:
        raise ValueError("Expected the explicitly authorized public dataset repository")
    if verify_only:
        revision = verify_only
    else:
        existing = set(api.list_repo_files(REPO_ID, repo_type="dataset", revision=repo.sha))
        if existing - (expected | {".gitattributes"}):
            raise ValueError("Unexpected existing repository files; preserve and review before update")
        result = api.upload_folder(
            repo_id=REPO_ID, repo_type="dataset", folder_path=staging,
            commit_message="Publish seven audited Open-Jev data configs with frozen provenance",
            commit_description="Includes two documented redistributable mixture projections, five prepared control corpora, exact raw records, Parquet splits, original manifests and original-mixture restoration. Excludes Wikispeedia task payload and external evaluation payload.",
            parent_commit=repo.sha,
        )
        revision = result.oid
        (reports / "upload-result.json").write_text(json.dumps({"repo_id": REPO_ID, "repo_type": "dataset",
            "revision": revision, "commit_url": result.commit_url, "public": True}, indent=2) + "\n")
        print(f"Published dataset commit {revision}", flush=True)
    remote_files = {x.path: x for x in api.list_repo_tree(REPO_ID, repo_type="dataset", revision=revision,
                                                        recursive=True, expand=True) if hasattr(x, "blob_id")}
    if set(remote_files) != expected | {".gitattributes"}:
        raise ValueError("Remote file inventory differs from approved release")
    verified = {}
    for name, path in local_files.items():
        remote = remote_files[name]
        if remote.size != path.stat().st_size:
            raise ValueError(f"Remote size mismatch: {name}")
        if remote.lfs:
            actual = remote.lfs.sha256
            correct = sha256(path)
            method = "LFS SHA-256"
        else:
            content = path.read_bytes()
            correct = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
            actual = remote.blob_id
            method = "Git blob SHA-1"
        if actual != correct:
            raise ValueError(f"Remote content hash mismatch: {name}")
        verified[name] = {"hash": actual, "method": method, "bytes": remote.size}
    cache = staging.parent / "remote-verification"
    for name in ("README.md", "export-manifest.json"):
        downloaded = Path(hf_hub_download(REPO_ID, name, repo_type="dataset", revision=revision,
                                         local_dir=cache, token=token, force_download=True))
        if sha256(downloaded) != sha256(staging / name):
            raise ValueError(f"Downloaded remote content mismatch: {name}")
    loaded = {}
    for config, details in manifest["configs"].items():
        dataset = load_dataset(REPO_ID, config, revision=revision, token=token,
                               cache_dir=staging.parent / "datasets-remote-cache")
        if set(dataset) != set(details["splits"]):
            raise ValueError(f"Missing remote split for {config}")
        loaded[config] = {}
        for split, info in details["splits"].items():
            if len(dataset[split]) != info["count"]:
                raise ValueError(f"Remote loaded count mismatch: {config}/{split}")
            sample = dataset[split][0]
            original = json.loads(sample["record_json"])
            assert sample["id"] == original["id"] and original["source"] != "wikispeedia-v1"
            assert json.loads(sample["state_json"]) == original["state"]
            assert json.loads(sample["metadata_json"]) == original["metadata"]
            loaded[config][split] = len(dataset[split])
        print(f"Remote load_dataset verified: {config}", flush=True)
    result = {"repo_id": REPO_ID, "revision": revision, "public": True,
              "all_remote_file_hashes_match": True, "remote_files": verified,
              "all_35_splits_load_from_hub": True, "load_dataset_counts": loaded,
              "export_manifest_sha256": sha256(staging / "export-manifest.json")}
    (reports / "remote-verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"url": f"https://huggingface.co/datasets/{REPO_ID}", "revision": revision,
                      "verified_files": len(verified), "configs_loaded": len(loaded)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--verify-only", help="Already-published commit to verify without a new upload")
    args = parser.parse_args()
    main(args.staging, Path(__file__).resolve().parent, args.verify_only)
