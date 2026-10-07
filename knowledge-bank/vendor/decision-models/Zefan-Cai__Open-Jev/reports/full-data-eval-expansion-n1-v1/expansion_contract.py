"""Fixed expansion audit contract and independently implemented CPU helpers."""
import hashlib
import importlib.util
from pathlib import Path, PurePosixPath
import stat

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "0b6e4fcca3306b9fe98b96a08074e78b4674fd16"
TRAINING_COMMIT = "99c5361d83edd5f9dbd11cb3f4bd9f9c54b5973e"
RUN_IDENTITY = "24c861e3a7937db09c8ba68b240600cb33c743d200e91375246b724a062b5bdb"
HOSTNAME = "kwade5342000001"
REMOTE = "/data/zefan/open-jev/evals/expansion-27b-four-gpu-data-v1"
REMOTE_RUN = "/data/zefan/open-jev/runs/browser-drone-expansion-v1-27b-ddp-n1-v1"
REMOTE_DATA = "/data/zefan/open-jev/data/browser-drone-expansion-v1"
PROFILE = "browser-drone-expansion-v1"
MODEL = "Qwen/Qwen3.8-27B"
REVISION = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
PARTITION = "concatenated_test_ood"
STEPS = 27581
SEED = 20260920
CALIBRATION_N = 512
# Ordered selected-ID JSON hash, not a hash of future calibration predictions.
CALIBRATION_IDS_SHA = "a1903776bafb4af05654c91ceaf3dc19a1135f82384186e7216001c76190ddad"
MANIFEST_SHA = "ba001b88787ce21576017897a0cbdedd5917ceb29ad3522b0e1fb7b4836d49df"
COUNTS = {"train": 110324, "calibration": 6883, "validation": 5562, "test": 14902, "ood": 25379}
HASHES = {
    "train": "91a3e3c715abd735509a5a23453161475aff85626f2c47563a8fab4e7dc79239",
    "calibration": "8a366dbb71dbe57b98a25da3071fc858beb7e8567adf4abf952c3d98f79bb94c",
    "validation": "bb49a3ca608dbeb543c56a20ee2f32e75f65be835fcb40ec40014af7351c6c7d",
    "test": "662d5e79da70eba77ad740eb37576b8157e53e5c1d8cd9344c60ec56d3969637",
    "ood": "364992ae82a2d8b6f3f4ed68a0efa06d9a6b9ae469d81113d4165f762eec0a94",
}
SPLITS = ("test", "ood")
SOURCE_FILES = ("scripts/evaluate_checkpoints_parallel.py", "jev/model.py", "jev/api.py",
                "jev/data.py", "jev/metrics.py", "jev/serving.py")
# Public source-snapshot compatibility: exact archived producer bytes from COMMIT.
# The private cluster policy is represented only by its historical SHA-256.
PINNED_SOURCE_HASHES = {'scripts/evaluate_checkpoints_parallel.py': '6a271eae0d1382aa2619b2ec547866db3c16b34cbaa6d43a7a15824410ecf493', 'jev/model.py': 'b8f135ef2da1f1205ba715b02f3dcf3c25962a2bec7e92a335198f59b6083c83', 'jev/api.py': '493f1fb9c3ffccbdc5f07d555791f9d86b3db7e1a53eef278230211cb6883254', 'jev/data.py': '97c1764a5090f60476397baf889a864359e0d59b48d99ddf3b34335d3e1b138e', 'jev/metrics.py': 'cb460c78b877a24708a0a8f8ca6b51f9602491f6ea24cd14e9a828c03d92f78b', 'jev/serving.py': 'e181c7dfaa7d0e2af0e79b77ad82a2264ff80fefe147587b0bae25d0aaa6b958'}
PINNED_POLICY_SHA = '668041118db8b2530e2367e09da72fbe32eea191582d9d4f9e809c0a58b98722'
EVAL_FILES = {"plan.json", "summary.json", "merged-test.jsonl", "merged-ood.jsonl"} | {
    f"shard-{rank}.{suffix}" for rank in range(4) for suffix in ("json", "jsonl", "log")}
WEIGHT_FILES = {"adapter/adapter_config.json", "adapter/adapter_model.safetensors",
                "head.pt", "model.json", "temperature.json"}
RUN_FILES = {"run.json", "summary.json", "training.jsonl", "calibration.jsonl",
             "trained_test.jsonl", "reload_check.jsonl"}
HELPER = ROOT / "reports/full-data-eval-n1-v1/verify.py"
HELPER_SHA = "662b6d7ec9611a98c754f3c51da8ddea8714e779b76c5699ebe242c2d8c8af6a"
if hashlib.sha256(HELPER.read_bytes()).hexdigest() != HELPER_SHA:
    raise ValueError("Historical independent arithmetic helper changed")
_spec = importlib.util.spec_from_file_location("historical_expansion_audit_arithmetic", HELPER)
_helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helper)
require, decode, objsha = _helper.require, _helper.decode, _helper.objsha
distribution, summarize, Comparison = _helper.distribution, _helper.summarize, _helper.Comparison


def safe_file(root, name):
    name = PurePosixPath(name)
    require(not name.is_absolute() and bool(name.parts) and ".." not in name.parts, "Unsafe relative filename")
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), "Missing/symlinked evidence directory")
    path = root
    for part in name.parts:
        path = path / part
        require(not path.is_symlink(), "Symlinked evidence path")
    require(stat.S_ISREG(path.stat().st_mode), "Nonregular evidence file")
    return path


def info(path):
    path = Path(path)
    require(not path.is_symlink() and stat.S_ISREG(path.stat().st_mode), "Nonregular evidence file")
    digest, size = hashlib.sha256(), 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
            size += len(block)
    require(size == path.stat().st_size, "File size changed while hashing")
    return {"sha256": digest.hexdigest(), "bytes": size}


def file_set(root):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), "Missing/symlinked directory")
    files = set()
    for path in root.rglob("*"):
        require(not path.is_symlink(), "Symlinked directory member")
        if not path.is_dir():
            require(stat.S_ISREG(path.stat().st_mode), "Nonregular directory member")
            files.add(path.relative_to(root).as_posix())
    return files


def checkpoint_names(root):
    names = file_set(root)
    require(WEIGHT_FILES <= names <= WEIGHT_FILES | {"adapter/README.md"}, "Incomplete/unexpected checkpoint file set")
    return names


def checkpoint_digest(root):
    digest = hashlib.sha256()
    for name in sorted(checkpoint_names(root)):
        digest.update(name.encode() + b"\0")
        with safe_file(root, name).open("rb") as stream:
            for block in iter(lambda: stream.read(1048576), b""):
                digest.update(block)
    return digest.hexdigest()


def assignments(rows, rank):
    offset, assigned = 0, []
    for split in SPLITS:
        assigned.extend((split, index, row) for index, row in enumerate(rows[split]) if (offset + index) % 4 == rank)
        offset += len(rows[split])
    return assigned


def assignment_identity(assigned, rank):
    return {"partition": PARTITION, "rank": rank, "total_rows": len(assigned),
            "counts": {split: sum(s == split for s, _, _ in assigned) for split in SPLITS},
            "ordered_rows_sha256": objsha([(s, i, row["id"], objsha(row)) for s, i, row in assigned])}
