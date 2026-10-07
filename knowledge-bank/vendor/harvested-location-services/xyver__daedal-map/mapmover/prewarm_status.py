"""Process-local status for asynchronous runtime pre-warm tasks.

The normal /health endpoint intentionally reports container health immediately.
This module supports /health/ready, which stays non-ready until the expensive
startup warm work has completed in the current process.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone


_LOCK = threading.Lock()
_STATE: dict[str, object] = {
    "state": "not_started",
    "started_at": None,
    "completed_at": None,
    "tasks": {},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def begin_prewarm(tasks: list[str]) -> None:
    """Start a new readiness generation with the named tasks marked running."""
    with _LOCK:
        _STATE["state"] = "warming"
        _STATE["started_at"] = _now()
        _STATE["completed_at"] = None
        _STATE["tasks"] = {str(task): {"state": "running"} for task in tasks}


def complete_prewarm_task(task: str, error: Exception | None = None) -> None:
    """Mark one task complete or failed and settle aggregate readiness."""
    with _LOCK:
        tasks = _STATE.setdefault("tasks", {})
        if not isinstance(tasks, dict):
            tasks = {}
            _STATE["tasks"] = tasks
        tasks[str(task)] = {
            "state": "failed" if error else "ready",
            **({"error": str(error)[:240]} if error else {}),
        }
        states = [entry.get("state") for entry in tasks.values() if isinstance(entry, dict)]
        if any(state == "failed" for state in states):
            _STATE["state"] = "failed"
            _STATE["completed_at"] = _now()
        elif states and all(state == "ready" for state in states):
            _STATE["state"] = "ready"
            _STATE["completed_at"] = _now()


def run_prewarm_task(task: str, func, *args, **kwargs) -> None:
    """Run a task while reliably recording completion for readiness probes."""
    try:
        func(*args, **kwargs)
    except Exception as exc:
        complete_prewarm_task(task, exc)
        raise
    else:
        complete_prewarm_task(task)


def prewarm_readiness() -> dict[str, object]:
    with _LOCK:
        tasks = _STATE.get("tasks", {})
        return {
            "state": _STATE.get("state"),
            "started_at": _STATE.get("started_at"),
            "completed_at": _STATE.get("completed_at"),
            "tasks": {name: dict(value) for name, value in tasks.items()} if isinstance(tasks, dict) else {},
        }
