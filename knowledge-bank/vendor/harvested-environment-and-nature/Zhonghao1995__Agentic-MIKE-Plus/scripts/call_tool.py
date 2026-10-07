"""CLI to invoke one MIKE+ MCP tool by name (for agents / testing, no MCP client needed).

Usage:
  python scripts/call_tool.py --list
  python scripts/call_tool.py <tool_name> '<json-args>'
Examples:
  python scripts/call_tool.py mike_model_info "{\"sqlite\": \"C:/path/model.sqlite\"}"
  python scripts/call_tool.py mike_get_values "{\"sqlite\":\"...\",\"table\":\"msm_Link\",\"columns\":[\"Diameter\"],\"muids\":[\"C14154801.2\"]}"
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mikeplus_mcp.registry import discover_tools  # noqa: E402


def main() -> int:
    tools = {t.name: t for t in discover_tools()}

    if len(sys.argv) < 2 or sys.argv[1] in ("--list", "-l"):
        for t in discover_tools():
            req = t.input_schema.get("required", [])
            print(f"{t.name:22} required={req}")
            print(f"  {t.description}")
        return 0

    name = sys.argv[1]
    try:
        args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": f"bad JSON args: {exc}"}))
        return 2
    if name not in tools:
        print(json.dumps({"ok": False, "error": f"unknown tool {name!r}; try --list"}))
        return 2

    result = tools[name].handler(args)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
