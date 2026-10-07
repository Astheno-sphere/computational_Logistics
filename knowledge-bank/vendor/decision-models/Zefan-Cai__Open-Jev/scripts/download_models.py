#!/usr/bin/env python3
"""Download the three pinned JEV starting models into an isolated HF cache."""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import traceback
from huggingface_hub import snapshot_download

ROOT = Path("/mnt/localssd/jev-qwen")
CACHE = "/mnt/localssd/jev-hf-cache"
STATUS = ROOT / "state/model-download-status.json"
MODELS = [
    ("Qwen/Qwen3.5-2B", "15852e8c16360a2fea060d615a32b45270f8a8fc"),
    ("Qwen/Qwen3.5-9B", "c202236235762e1c871ad0ccb60c8ee5ba337b9a"),
    ("Qwen/Qwen3.8-27B", "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"),
]
PATTERNS = ["config.json", "generation_config.json", "tokenizer*", "vocab*", "merges*", "*.safetensors", "*.index.json"]
state = {"pid": os.getpid(), "status": "running", "models": []}

def now():
    return datetime.now(timezone.utc).isoformat()

def save():
    state["updated_at"] = now()
    temp = STATUS.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2) + "\n")
    temp.replace(STATUS)

save()
for repo_id, revision in MODELS:
    record = {"repo_id": repo_id, "revision": revision, "status": "downloading", "started_at": now()}
    state["models"].append(record)
    save()
    print(json.dumps({"event": "download_start", **record}), flush=True)
    try:
        path = snapshot_download(repo_id=repo_id, revision=revision, cache_dir=CACHE, allow_patterns=PATTERNS, max_workers=4)
        snapshot = Path(path)
        weights = list(snapshot.glob("*.safetensors"))
        if not (snapshot / "config.json").is_file() or not weights:
            raise RuntimeError("Downloaded snapshot has no config or safetensors")
        record.update(status="complete", snapshot=str(snapshot), weight_shards=len(weights), weight_bytes=sum(p.stat().st_size for p in weights), completed_at=now())
        print(json.dumps({"event": "download_complete", **record}), flush=True)
    except Exception as exc:
        record.update(status="failed", error_type=type(exc).__name__, failed_at=now())
        state["status"] = "failed"
        save()
        traceback.print_exc()
        raise
    save()
state["status"] = "complete"
save()
print(json.dumps({"event": "all_downloads_complete", "completed_at": now()}), flush=True)
