"""What was searched for, and what was run — recorded locally, off by default.

The discovery layer gets better by measurement, and the measurement it has comes
from 155 requests written by two language models. The best labels available are
not those: they are the ones a real caller produces every time it searches the
catalogue and then runs something, because that pairing is a decision made with
the context we do not have.

**This records those pairings. It does not learn from them.** The distinction is
the whole design and it is deliberate:

- A ranker that learns from what callers pick amplifies its own ordering. What
  they picked was shaped by what it showed them, so the operation ranked first
  gets picked more, gets learned as correct, gets ranked first harder. That is a
  confident answer nothing contradicts — the failure this product exists to
  measure, applied to itself.
- A model that learns changes its answer over time for the same query, and a
  manifest that says "this operation was chosen" stops being explicable six
  months later. `MODEL_REVISION` is pinned and a golden-vector test holds it
  there on purpose.

So the output of this module is not weights. It is **rows for the benchmark**:
`benchmarks/log_to_cases.py` turns them into candidate cases in the same shape as
`tests/data/discovery_queries.json`, and the improvement then happens in the
catalogue text — `distinguishes`, `phrasings`, the facets — in git, with a diff
somebody can read and revert. That is learning with provenance, which is the only
kind this product can afford. It is also not the weak version: the same loop took
found@3 from 18% to 57% and delivery to 97% in one afternoon.

## Switching it on

    MAPSMITH_DISCOVERY_LOG=/data/discovery.jsonl

Unset, nothing is written and nothing is kept in memory. The path is guarded like
any other: under a workspace it must be inside it. One JSON object per line,
append-only, plain text — meant to be read, edited and pruned by hand before any
of it becomes a test case.

**It contains the caller's queries verbatim.** A geospatial question carries
project names, places and intent, so the file stays where it was written and
never leaves the machine: nothing in MapSmith reads it back or sends it anywhere.
Deleting it costs nothing and loses nothing that was promised.
"""

from __future__ import annotations

import atexit
import json
import os
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: How many searches are held waiting for a run to attribute to them. Small on
#: purpose: the further back a search is, the less a later run says about it.
WINDOW = 5

_lock = threading.Lock()
_pending: list[dict[str, Any]] = []

#: Resolved destinations by the raw value that produced them, so the guard runs
#: once per configuration rather than once per record — and so its refusal is
#: reported once rather than on every search.
_resolved: dict[str, Path | None] = {}


def destination() -> Path | None:
    """The log path, validated, or None when the feature is off or refused.

    A refused path disables the log for the rest of the process and says so on
    stderr. Both halves are deliberate: a logging feature must not turn every
    search into an error, and a caller who set the variable and gets no file
    deserves to be told why rather than left to guess.
    """
    raw = os.environ.get("MAPSMITH_DISCOVERY_LOG", "").strip()
    if not raw:
        return None
    if raw in _resolved:
        return _resolved[raw]
    from . import workspace

    # Guarded like a tool argument: this writes a file, and "write anywhere the
    # process can reach" is not a thing a discovery log gets to be.
    try:
        workspace.guard(raw, "MAPSMITH_DISCOVERY_LOG")
        path: Path | None = Path(raw)
    except ValueError as refusal:
        print(
            f"MAPSMITH_DISCOVERY_LOG names a path MapSmith will not write to, so "
            f"discovery is not being recorded: {refusal}",
            file=sys.stderr,
        )
        path = None
    _resolved[raw] = path
    return path


def _write(record: dict[str, Any]) -> None:
    path = destination()
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def record_search(
    query: str,
    declared: dict[str, Any],
    engine: str | None,
    delivered: list[str],
    status: str,
) -> None:
    """Remember a search until something is run, or until it falls out of the window.

    Never raises: a logging failure must not turn a working search into an error.
    """
    if destination() is None or not query.strip():
        return
    try:
        entry = {
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "query": query,
            "declared": {k: v for k, v in declared.items() if v is not None},
            "engine": engine,
            "status": status,
            "delivered": delivered,
            "chose": None,
            "position_of_choice": None,
            "searches_ago": None,
            "matched_by": None,
        }
        with _lock:
            _pending.append(entry)
            while len(_pending) > WINDOW:
                _write(_pending.pop(0))
    except Exception:  # noqa: BLE001,S110 - see the module docstring: a log is
        pass  # never worth turning a working call into an error


def record_run(operation: str) -> None:
    """Attribute a run to the most recent search that offered this operation.

    The rule is written into every record rather than assumed, because it is a
    heuristic and a reader has to be able to discount it: a caller that searched,
    did three unrelated things and then ran something will be attributed to the
    wrong search. `searches_ago` says how far back the match was, and 0 is the
    only value that is beyond argument.
    """
    if destination() is None:
        return
    try:
        with _lock:
            for distance, entry in enumerate(reversed(_pending)):
                if operation in entry["delivered"]:
                    entry["chose"] = operation
                    entry["position_of_choice"] = entry["delivered"].index(operation) + 1
                    entry["searches_ago"] = distance
                    entry["matched_by"] = (
                        "most recent search whose delivered set held this operation"
                    )
                    _pending.remove(entry)
                    _write(entry)
                    return
    except Exception:  # noqa: BLE001,S110 - a log is never worth an error
        pass


def flush() -> None:
    """Write the searches nothing was run after. They are data too — a search
    that led nowhere is a request the catalogue did not serve."""
    try:
        with _lock:
            while _pending:
                _write(_pending.pop(0))
    except Exception:  # noqa: BLE001,S110 - a log is never worth an error
        pass


atexit.register(flush)
