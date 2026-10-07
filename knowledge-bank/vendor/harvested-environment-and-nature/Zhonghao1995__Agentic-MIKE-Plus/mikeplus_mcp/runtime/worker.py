"""Run a worker script in an isolated subprocess and collect its JSON result.

Why subprocesses: ``mikeplus`` and ``mikeio`` must NOT share a Python process,
and ``mikeio1d`` must be imported after ``mikeplus``. Each worker imports exactly
one heavy library, so spawning a fresh short-lived process per tool call
sidesteps the conflict entirely.

Contract with workers:
- worker reads a JSON payload from stdin; ``payload["__out"]`` is a temp file path
- worker writes its structured result (a JSON object) to that file
- worker may print logs to stdout/stderr (the MIKE 1D engine prints to stdout);
  the helper captures stdout and returns its tail as ``_log_tail``
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parents[1]   # .../mikeplus_mcp
_PROJECT_ROOT = _PKG_ROOT.parent                  # repo root (makes mikeplus_mcp importable)
_WORKERS = _PKG_ROOT / "workers"

# the interpreter running the server (the venv python) also runs the workers
PYTHON = os.environ.get("MIKE_MCP_PYTHON", sys.executable)


def call_worker(worker: str, payload: dict, timeout: float = 1800.0) -> dict:
    script = _WORKERS / f"{worker}.py"
    if not script.exists():
        raise FileNotFoundError(f"worker not found: {script}")

    fd, out_name = tempfile.mkstemp(suffix=".json", prefix=f"{worker}_")
    os.close(fd)
    out = Path(out_name)

    args = dict(payload)
    args["__out"] = str(out)

    env = dict(os.environ)
    env["PYTHONPATH"] = str(_PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    try:
        proc = subprocess.run(
            [PYTHON, str(script)],
            input=json.dumps(args),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        result = None
        if out.exists() and out.stat().st_size > 0:
            try:
                result = json.loads(out.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                result = None
        if result is None:
            tail = (proc.stderr or proc.stdout or "")[-1500:]
            raise RuntimeError(
                f"worker '{worker}' produced no result (rc={proc.returncode}).\n{tail}"
            )
        log = (proc.stdout or "").strip()
        if log:
            result.setdefault("_log_tail", log[-2000:])
        return result
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"worker '{worker}' timed out after {timeout:.0f}s")
    finally:
        try:
            out.unlink()
        except OSError:
            pass
