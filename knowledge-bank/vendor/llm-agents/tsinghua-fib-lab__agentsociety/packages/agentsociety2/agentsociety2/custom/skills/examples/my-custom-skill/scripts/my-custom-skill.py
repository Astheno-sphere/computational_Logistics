"""Example custom skill script (subprocess mode).

This script demonstrates Pattern B: deterministic computation via subprocess.
It receives args via --args-json, does computation, and outputs JSON to stdout.

Usage:
    python my-custom-skill.py --args-json '{"tick": 1, "profile": {...}}'

Environment variables available:
    SKILL_NAME     - Name of this skill
    SKILL_DIR      - Path to the skill directory (where SKILL.md lives)
    AGENT_WORK_DIR - Path to the agent's workspace directory (cwd)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--args-json", default="{}")
    ns = parser.parse_args()
    args = json.loads(ns.args_json or "{}")

    cwd = Path.cwd()  # This is AGENT_WORK_DIR

    # Example: read existing state
    state_path = cwd / "custom_state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        state = {"count": 0}

    # Example: do some computation
    state["count"] += 1
    state["last_tick"] = args.get("tick")

    # Example: write state back
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Output result as JSON to stdout (this is what the agent sees)
    print(
        json.dumps(
            {
                "ok": True,
                "message": f"Custom skill ran successfully (count={state['count']})",
                "state": state,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
