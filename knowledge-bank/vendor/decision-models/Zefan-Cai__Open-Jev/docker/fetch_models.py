#!/usr/bin/env python3
"""Bake the pinned Open-Jev checkpoint package and its base weights into the image.

The published checkpoint is a LoRA adapter plus a scalar decision head; it only
loads together with the exact upstream base revision named in its model.json.
This script downloads both, then verifies that pairing and the published file
digests, so a build fails here rather than at container start.
"""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

OUTPUT = Path(os.environ.get("JEV_MODEL_ROOT", "/weights"))
BASE_MODEL = os.environ["JEV_BASE_MODEL"]
BASE_REVISION = os.environ["JEV_BASE_REVISION"]
PACKAGE_REPO = os.environ["JEV_PACKAGE_REPO"]
PACKAGE_REVISION = os.environ["JEV_PACKAGE_REVISION"]

# Weight formats the Open-Jev loader never reads; skipping them keeps the layer small.
IGNORE = ["*.pth", "*.bin", "*.gguf", "*.msgpack", "*.h5", "*.onnx", "original/*"]


def token():
    """Both repositories are public; a token is only used when one is supplied."""
    secret = Path("/run/secrets/hf_token")
    if secret.is_file():
        value = secret.read_text().strip()
        if value:
            return value
    return os.environ.get("HF_TOKEN") or None


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def fail(message):
    print(json.dumps({"event": "fetch_failed", "error": message}), flush=True)
    sys.exit(1)


package_dir = OUTPUT / PACKAGE_REPO.split("/")[-1]
hub_cache = OUTPUT / "hub"
print(json.dumps({"event": "fetch_start", "package": PACKAGE_REPO, "revision": PACKAGE_REVISION,
                  "base": BASE_MODEL, "base_revision": BASE_REVISION}), flush=True)

snapshot_download(repo_id=PACKAGE_REPO, revision=PACKAGE_REVISION, local_dir=package_dir,
                  token=token(), max_workers=4)
shutil.rmtree(package_dir / ".cache", ignore_errors=True)

checkpoint = package_dir / "package" / "checkpoint"
if not (checkpoint / "model.json").is_file():
    fail(f"checkpoint metadata missing under {checkpoint}")

config = json.loads((checkpoint / "model.json").read_text())
if config["model_id"] != BASE_MODEL or config["revision"] != BASE_REVISION:
    fail("checkpoint requires base %s@%s but the build pins %s@%s"
         % (config["model_id"], config["revision"], BASE_MODEL, BASE_REVISION))

# The package ships its own manifest; verify what was downloaded against it.
manifest_path = package_dir / "package" / "manifest.json"
verified = 0
if manifest_path.is_file():
    manifest = json.loads(manifest_path.read_text())
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        fail("package verification manifest has no file entries")
    for name, entry in sorted(files.items()):
        candidate = package_dir / "package" / name
        if not candidate.is_file():
            fail(f"package file listed in manifest is missing: {name}")
        if candidate.stat().st_size != entry["bytes"] or digest(candidate) != entry["sha256"]:
            fail(f"package file does not match the published manifest: {name}")
        verified += 1
else:
    fail(f"package verification manifest missing: {manifest_path}")

snapshot = Path(snapshot_download(repo_id=BASE_MODEL, revision=BASE_REVISION, cache_dir=hub_cache,
                                  ignore_patterns=IGNORE, token=token(), max_workers=4))
weights = sorted(snapshot.glob("*.safetensors"))
if not (snapshot / "config.json").is_file() or not weights:
    fail("base snapshot has no config.json or safetensors shard")
if not any((snapshot / name).is_file() for name in ("tokenizer.json", "tokenizer_config.json")):
    fail("base snapshot has no tokenizer files")

# Paths are relative to this file's directory, which the image mounts elsewhere.
record = {
    "package_repo": PACKAGE_REPO,
    "package_revision": PACKAGE_REVISION,
    "package_files_verified": verified,
    "checkpoint": checkpoint.relative_to(OUTPUT).as_posix(),
    "base_model": BASE_MODEL,
    "base_revision": BASE_REVISION,
    "base_snapshot": snapshot.relative_to(OUTPUT).as_posix(),
    "base_weight_shards": len(weights),
    "base_weight_bytes": sum(path.stat().st_size for path in weights),
    "max_length": config["max_length"],
    "lora_rank": config["lora_rank"],
    "method": config["method"],
}
(OUTPUT / "BUILD.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({"event": "fetch_complete", **record}), flush=True)
