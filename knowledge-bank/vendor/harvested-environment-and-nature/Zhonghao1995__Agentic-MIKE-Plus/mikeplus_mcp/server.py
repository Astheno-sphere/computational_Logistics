"""Single MCP server for MIKE+. Exposes auto-discovered tools over stdio.

Run:  python -m mikeplus_mcp.server        (cwd = repo root, venv python)

The server itself imports neither mikeplus nor mikeio — every tool runs its work
in an isolated worker subprocess (see runtime/worker.py).
"""
from __future__ import annotations

import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from .registry import discover_tools

_TOOLS = {t.name: t for t in discover_tools()}

server = Server("mike-plus")


def _safe_invoke(tool, arguments: dict | None) -> dict:
    """Run a tool handler, coercing any failure to the same {ok:false} shape the
    handlers already use for logic errors. Without this, infrastructure failures
    (worker timeout / no result / missing worker) would surface as a protocol-level
    exception, so the agent would see two different failure shapes."""
    try:
        return tool.handler(arguments or {})
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


@server.list_tools()
async def _list_tools() -> list[types.Tool]:
    return [
        types.Tool(name=t.name, description=t.description, inputSchema=t.input_schema)
        for t in _TOOLS.values()
    ]


@server.call_tool()
async def _call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    tool = _TOOLS.get(name)
    if tool is None:
        raise ValueError(f"Unknown tool: {name}")
    # handlers spawn a subprocess (blocking) — run off the event loop
    result = await asyncio.to_thread(_safe_invoke, tool, arguments)
    text = json.dumps(result, ensure_ascii=False, default=str, indent=2)
    return [types.TextContent(type="text", text=text)]


async def _main() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def run() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    run()
