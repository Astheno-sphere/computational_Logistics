"""Turn a discovery log into benchmark rows a person can accept or throw away.

    MAPSMITH_DISCOVERY_LOG=/data/discovery.jsonl   # then use MapSmith for a while
    python benchmarks/log_to_cases.py /data/discovery.jsonl

The 155 requests in `tests/data/discovery_queries.json` were written by two
language models from work scenarios. They are the best we could make without
users; they are not what users ask. A real caller's query carries the file it
actually has, the words its domain actually uses, and the ambiguity a generator
smooths away — and the operation it ran afterwards is a label produced with
context no annotator had.

So this reads the log and prints candidate rows in exactly the shape of that
file, with `label` set to what was run and `generated_by` recording the machine
that produced it. **It prints; it does not write.** Every row is a guess about
intent from a temporal coincidence, and the ones worth keeping are chosen by
somebody reading them — which is also the point at which queries that name real
places and real projects get looked at before they enter a public repository.

**A recorded choice can be the caller's mistake, and the first one was.** The
session that shook this loose asked for *"one label point per parcel"* and ran
`centroid_layer`, which our ranking had put fourth. The ranking was right: a
centroid can fall outside its own polygon, which is
[Argleton](https://argleton.org) trap 014, and `point_on_surface` is the
operation for that request. Taken as a label, that row would have taught the
catalogue to recommend the defect our own suite measures — so a `NOT TOP-RANKED`
flag is a question about the ranking, never a verdict on it, and the reader has
to decide which of the two was wrong.

Two flags of the output are worth more than the rows themselves:

* `NOT TOP-RANKED` — the caller was shown the operation and picked one our
  ranking had further down. That is the ranking being wrong with the answer in
  hand, and it is the cheapest correction available: usually a missing phrasing
  or a `distinguishes` that does not distinguish.
* `NOTHING RUN` — a search nothing followed. Either the caller found no
  operation, or found one and did something else with it. A cluster of these on
  similar queries is a gap in the catalogue, not a ranking problem.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mapsmith import catalog  # noqa: E402


def read(path: Path) -> list[dict[str, Any]]:
    """Every well-formed line. A truncated last line is normal — the log is
    appended to by a running process — and is skipped rather than fatal."""
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"# skipped an unreadable line: {line[:60]}...", file=sys.stderr)
    return records


def to_case(record: dict[str, Any]) -> dict[str, Any]:
    """One log record as a benchmark row.

    `label` is what was run, and `label_claude`/`label_gemini` stay absent: this
    row has one label from one source, and filling the other two fields with it
    would manufacture the agreement the ceiling is measured from.
    """
    return {
        "query": record["query"],
        "scenario": "recorded from use",
        "generated_by": "discovery log",
        "split": "tune",
        "label": record["chose"],
        "declared": record["declared"],
        "delivered_position": record["position_of_choice"],
        "searches_ago": record["searches_ago"],
    }


def main(argv: list[str]) -> int:
    # This prints em dashes and non-ASCII query text on a Windows console whose
    # default codepage is cp1252, where the write raises rather than degrades.
    # Redirected to a file it stays UTF-8, which is what the rows have to be.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(argv) != 2:
        print(__doc__)
        return 2
    path = Path(argv[1])
    if not path.exists():
        print(f"no log at {path}. Set MAPSMITH_DISCOVERY_LOG and use MapSmith first.")
        return 1

    records = read(path)
    known = {op["name"] for op in catalog.OPERATIONS}
    ran = [r for r in records if r.get("chose")]
    nothing = [r for r in records if not r.get("chose")]
    # Attribution is a heuristic, and the further back the match the weaker it
    # is. Rows are printed in the order that makes the doubtful ones easy to
    # drop: certain first.
    ran.sort(key=lambda r: (r.get("searches_ago") or 0, r.get("position_of_choice") or 0))

    cases = []
    for record in ran:
        if record["chose"] not in known:
            continue
        flag = ""
        if record.get("position_of_choice", 1) > 1:
            flag = f"  # NOT TOP-RANKED — shown at {record['position_of_choice']}"
        if record.get("searches_ago"):
            flag += f"  # attributed {record['searches_ago']} searches back — check it"
        cases.append((to_case(record), flag))

    print(f"# {len(records)} records, {len(ran)} with a run attributed, "
          f"{len(nothing)} with nothing run")
    print("# Read these. Paste the ones that are true into "
          "tests/data/discovery_queries.json.")
    print()
    for case, flag in cases:
        print(json.dumps(case, ensure_ascii=False) + "," + flag)

    misranked = [r for r in ran if (r.get("position_of_choice") or 1) > 1]
    if misranked:
        print()
        print(f"# {len(misranked)} of {len(ran)} runs chose something our ranking did "
              "not put first. Each is a phrasing or a `distinguishes` to fix:")
        for record in misranked:
            print(f"#   {record['chose']} at position {record['position_of_choice']} "
                  f"of {len(record['delivered'])} — {record['query'][:70]}")

    if nothing:
        print()
        print(f"# {len(nothing)} searches nothing was run after. Recurring shapes here "
              "are missing capability, not bad ranking:")
        for query, count in Counter(r["query"] for r in nothing).most_common(10):
            print(f"#   {count}x  {query[:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
