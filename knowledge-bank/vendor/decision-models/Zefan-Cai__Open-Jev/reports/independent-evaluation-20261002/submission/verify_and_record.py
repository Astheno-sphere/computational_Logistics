"""Verify downloaded checkpoint bytes and record runtime, without inference."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys

root = Path(__file__).resolve().parent
manifest = json.loads((root / "submission.json").read_text())
checkpoint = root / "model/package/checkpoint"
digest = hashlib.sha256()
for file in sorted(checkpoint.rglob("*")):
    if file.is_symlink():
        raise SystemExit("Checkpoint symlinks are not accepted")
    if file.is_file():
        digest.update(file.relative_to(checkpoint).as_posix().encode() + b"\0")
        with file.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
if digest.hexdigest() != manifest["identity"]["checkpoint_sha256"]:
    raise SystemExit("Checkpoint tree checksum differs from the published release")
model = json.loads((checkpoint / "model.json").read_text())
temperature = json.loads((checkpoint / "temperature.json").read_text())["temperature"]
if (model["model_id"] != manifest["identity"]["model"]
        or model["revision"] != manifest["identity"]["base_revision"]
        or temperature != manifest["identity"]["temperature"]):
    raise SystemExit("Checkpoint model, base revision or temperature differs")
actual_commit = subprocess.check_output(
    ["git", "-C", str(root / "loader"), "rev-parse", "HEAD"], text=True).strip()
dirty = subprocess.check_output(
    ["git", "-C", str(root / "loader"), "status", "--porcelain"], text=True)
if actual_commit != manifest["identity"]["code_commit"] or dirty:
    raise SystemExit("Evaluator loader must be the pinned clean checkout")
packages = {}
for name in ("torch", "transformers", "peft", "accelerate", "safetensors", "huggingface-hub"):
    try:
        packages[name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        packages[name] = None
try:
    gpu = subprocess.check_output([
        "nvidia-smi", "--query-gpu=index,name,memory.total,driver_version",
        "--format=csv,noheader"], text=True, stderr=subprocess.DEVNULL).strip().splitlines()
except (OSError, subprocess.CalledProcessError):
    gpu = []
report = {"checkpoint_verified": True, "loader_commit": actual_commit,
          "python": sys.version.split()[0], "platform": platform.platform(),
          "packages": packages, "gpu_inventory": gpu,
          "hardware_test_status": "not_measured", "inference_performed": False,
          "sealed_result_status": "pending_independent_evaluator"}
(root / "runtime.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
