"""Surface the files most worth a human's (or AI's) attention.

Combines size, a cheap cyclomatic-complexity proxy, and git churn (how often a
file changes) — the classic signals for "where the risk lives".
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .walk import CODE_EXTS, count_loc, iter_files, read_text, rel

# Tokens that introduce a branch / decision point.
_BRANCH = re.compile(
    r"\b(if|elif|else if|for|while|case|catch|except|&&|\|\||\?\s|switch)\b"
)


def _complexity(text: str) -> int:
    return len(_BRANCH.findall(text)) + 1


def _git_churn(root: Path) -> dict[str, int]:
    if not (root / ".git").exists():
        return {}
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", "--no-merges", "--name-only", "--format="],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return {}
    churn: dict[str, int] = {}
    for line in out.splitlines():
        line = line.strip()
        if line:
            churn[line] = churn.get(line, 0) + 1
    return churn


def find_hotspots(root: str | Path, top: int = 10) -> dict:
    root = Path(root)
    rows = []
    for f in iter_files(root):
        if f.suffix.lower() not in CODE_EXTS:
            continue
        text = read_text(f)
        if not text:
            continue
        rows.append({
            "file": rel(f, root),
            "loc": count_loc(text),
            "complexity": _complexity(text),
        })

    churn = _git_churn(root)
    for r in rows:
        r["changes"] = churn.get(r["file"], 0)

    largest = sorted(rows, key=lambda r: r["loc"], reverse=True)[:top]
    most_complex = sorted(rows, key=lambda r: r["complexity"], reverse=True)[:top]
    most_changed = (
        sorted([r for r in rows if r["changes"]], key=lambda r: r["changes"], reverse=True)[:top]
        if churn else []
    )

    # "Risk" = big AND complex AND frequently changed.
    for r in rows:
        r["risk"] = r["loc"] * 0.4 + r["complexity"] * 2 + r["changes"] * 5
    risky = sorted(rows, key=lambda r: r["risk"], reverse=True)[:top]

    return {
        "root": str(root),
        "files_analyzed": len(rows),
        "git_history_available": bool(churn),
        "largest": [{k: r[k] for k in ("file", "loc")} for r in largest],
        "most_complex": [{k: r[k] for k in ("file", "complexity", "loc")} for r in most_complex],
        "most_changed": [{k: r[k] for k in ("file", "changes")} for r in most_changed],
        "highest_risk": [
            {"file": r["file"], "loc": r["loc"], "complexity": r["complexity"], "changes": r["changes"]}
            for r in risky
        ],
    }
