"""Parse the MIKE 1D engine log into a structured QA gate.

The engine writes a per-run ``.log`` next to the model and prints the same text to
stdout. A successful run ends with ``Simulation done`` and reports per-phase issues
like ``WARNING: 4 issue(s) found during validate (0 error(s))``. We distil that into
``{completed, errors, warnings, issues, status}`` so a runner skill can gate on it
instead of eyeballing a log tail.

Pure module — stdlib only (no mikeplus / mikeio), so it is unit-testable offline.
"""
from __future__ import annotations

import re
from pathlib import Path

_ERROR_SUMMARY = re.compile(r"(\d+)\s+error\(s\)")
_ISSUE_SUMMARY = re.compile(r"(\d+)\s+issue\(s\)\s+found")
_WARNING_MSG = re.compile(r"WARNING:\s*(.*)")
_ERROR_LINE = re.compile(r"ERROR:")
_DONE = "Simulation done"


def parse_engine_log(text: str) -> dict:
    """Distil an engine log (full text or just its tail) into QA fields.

    - ``completed``: the run reached ``Simulation done``.
    - ``errors``: the engine's own error tally (max of the ``(N error(s))``
      summaries and any ``ERROR:`` lines).
    - ``warnings``: ``WARNING:`` lines, excluding the ``N issue(s) found`` roll-ups.
    - ``issues``: total issues the engine reported across phases.
    - ``status``: ``ok`` | ``completed_with_warnings`` | ``completed_with_errors`` | ``incomplete``.
    """
    text = text or ""
    completed = _DONE in text
    summary_errors = sum(int(n) for n in _ERROR_SUMMARY.findall(text))
    errors = max(summary_errors, len(_ERROR_LINE.findall(text)))
    warnings = sum(1 for m in _WARNING_MSG.findall(text) if "issue(s) found" not in m)
    issues = sum(int(n) for n in _ISSUE_SUMMARY.findall(text))

    if not completed:
        status = "incomplete"
    elif errors > 0:
        status = "completed_with_errors"
    elif warnings > 0:
        status = "completed_with_warnings"
    else:
        status = "ok"

    return {
        "completed": completed,
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "status": status,
    }


def read_run_log(model_dir, since_mtime: float = 0.0) -> dict:
    """Find the newest ``*.log`` in ``model_dir`` written at/after ``since_mtime`` and parse it.

    Returns the ``parse_engine_log`` fields plus ``log_file``. When no log is found
    (e.g. the engine wrote none), returns ``status="unknown"`` with null fields so the
    run result stays uniform.
    """
    try:
        logs = [p for p in Path(model_dir).glob("*.log") if _mtime(p) >= since_mtime]
    except OSError:
        logs = []

    if not logs:
        return {"log_file": None, "completed": None, "errors": None,
                "warnings": None, "issues": None, "status": "unknown"}

    newest = max(logs, key=_mtime)
    qa = parse_engine_log(newest.read_text(encoding="utf-8", errors="replace"))
    qa["log_file"] = str(newest)
    return qa


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0
