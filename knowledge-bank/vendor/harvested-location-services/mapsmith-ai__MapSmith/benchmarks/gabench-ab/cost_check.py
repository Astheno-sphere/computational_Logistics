"""Token spend of a run, from GABench's llm_usage.jsonl.

Prices are per million tokens and depend on the model you ran: pass them
explicitly rather than trusting a default that silently goes stale.

Usage: python cost_check.py <usage.jsonl> [input-price] [output-price]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if len(sys.argv) < 2:
    raise SystemExit("usage: python cost_check.py <usage.jsonl> [in-price] [out-price]")
path = Path(sys.argv[1])
in_price = float(sys.argv[2]) if len(sys.argv) > 2 else None
out_price = float(sys.argv[3]) if len(sys.argv) > 3 else None

metrics = []
with path.open(encoding="utf-8") as fh:
    for line in fh:
        entry = json.loads(line)
        if "metrics" in entry:
            metrics.append(entry["metrics"])

inp = sum(m.get("input_tokens", 0) for m in metrics)
out = sum(m.get("output_tokens", 0) for m in metrics)
print(f"calls: {len(metrics)}  input: {inp:,}  output: {out:,}")
if in_price is not None and out_price is not None:
    print(f"cost: USD {inp / 1e6 * in_price + out / 1e6 * out_price:.2f}")
