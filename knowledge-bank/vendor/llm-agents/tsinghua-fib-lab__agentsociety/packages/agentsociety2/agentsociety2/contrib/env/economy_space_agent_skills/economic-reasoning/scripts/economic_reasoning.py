"""economic-reasoning skill (subprocess mode)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ECONOMIC_KEYWORDS = (
    "currency",
    "price",
    "income",
    "tax",
    "product",
    "job",
    "wage",
    "economy",
    "market",
    "cost",
    "buy",
    "sell",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--args-json", default="{}")
    ns = parser.parse_args()
    args = json.loads(ns.args_json or "{}")

    observation = str(args.get("observation", ""))
    financial_info = args.get("financial_info", "")
    obs_lower = observation.lower()
    has_economic_context = any(kw in obs_lower for kw in ECONOMIC_KEYWORDS)

    result = {
        "ok": True,
        "has_economic_context": has_economic_context,
        "summary": "",
        "financial_info": financial_info,
    }

    if has_economic_context:
        result["summary"] = "EconomicReasoning: analyzed financial state"
    else:
        result["summary"] = "EconomicReasoning: no economic context"

    Path("economic_reasoning.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    Path("economic_reasoning.txt").write_text(result["summary"], encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
