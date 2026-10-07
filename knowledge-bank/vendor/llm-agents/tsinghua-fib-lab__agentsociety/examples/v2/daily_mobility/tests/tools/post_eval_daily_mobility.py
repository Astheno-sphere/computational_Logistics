#!/usr/bin/env python3
"""Daily Mobility post-evaluation CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval_metrics import compute_metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily Mobility CLI post-eval")
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--eval-config", type=Path, default=None)
    args = parser.parse_args()

    tools = Path(__file__).resolve().parent
    exp = tools.parent
    run_dir = (args.run_dir or (exp / "run")).resolve()
    eval_path = (args.eval_config or (exp / "eval_config.json")).resolve()
    cfg = json.loads(eval_path.read_text(encoding="utf-8"))
    gt_dir = (exp / str(cfg.get("groundtruth_data", "groundtruth"))).resolve()

    init_cfg = json.loads((exp / "init_config.json").read_text(encoding="utf-8"))
    agent_ids = [a["agent_id"] for a in init_cfg["agents"]]
    results = compute_metrics(run_dir, gt_dir, agent_ids)

    out_path = run_dir / "scores.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"scores written to {out_path}")
    for key, value in results.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
