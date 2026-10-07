"""What the validation gate actually caught, from an arm's results file.

Arm A records the same audit without acting on it, so running this on both
arms shows whether the two runs produced defective plans on the same tasks.

Usage: python gate_stats.py <repN.jsonl>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if len(sys.argv) < 2:
    raise SystemExit("usage: python gate_stats.py <repN.jsonl>")
records = [
    json.loads(line)
    for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
]

caught = repaired = 0
for record in records:
    audit = record.get("gate_audit") or {}
    rounds = audit.get("rounds", [])
    if rounds and rounds[0]["issues"]:
        caught += 1
        codes = sorted({i["code"] for i in rounds[0]["issues"]})
        print(f"  task {record['task_id']}: {len(rounds[0]['issues'])} issue(s) "
              f"({', '.join(codes)}) -> rounds: {len(rounds)}, "
              f"residual: {audit.get('final_issue_count')}")
    if len(rounds) > 1:
        repaired += 1
print(f"tasks: {len(records)} | plans defective on first attempt: {caught} | "
      f"repair rounds run: {repaired}")
