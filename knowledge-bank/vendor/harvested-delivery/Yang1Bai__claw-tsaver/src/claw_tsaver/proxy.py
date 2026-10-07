"""MCP proxy server.

Aggregates tools from a configurable set of downstream MCP servers, exposes
them under ``<server_name>__<tool_name>`` to the upstream client (OpenClaw),
and transparently compresses oversized tool results behind a handle that the
client can later resolve via the built-in ``expand_content`` tool.
"""

from __future__ import annotations

import json
import sys
import time
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

import tiktoken
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from claw_tsaver import store

CONFIG_DIR = Path.home() / ".claw-tsaver"
CONFIG_PATH = CONFIG_DIR / "config.json"
LOG_PATH = CONFIG_DIR / "log.jsonl"
PREFIX_SEP = "__"
PREVIEW_CHARS = 100

DEFAULT_CONFIG: dict[str, Any] = {
    "downstream_servers": [],
    "compression_threshold_tokens": 500,
}


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _eprint(*args: Any, **kwargs: Any) -> None:
    """Print to stderr so it can't pollute the stdio MCP channel on stdout."""
    print(*args, file=sys.stderr, **kwargs)


def load_config() -> dict[str, Any]:
    """Load ``config.json``; if missing, write a stub and return its values."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(
            json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8"
        )
        _eprint(
            f"[claw-tsaver] Created stub config at {CONFIG_PATH}. "
            "Edit downstream_servers and re-run."
        )
        return dict(DEFAULT_CONFIG)
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _count_tokens(text: str, encoder: tiktoken.Encoding) -> int:
    return len(encoder.encode(text, disallowed_special=()))


def _stringify_content(content: list[Any]) -> str:
    """Flatten a list of MCP content blocks into a single string."""
    parts: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
        else:
            parts.append(str(block))
    return "\n".join(parts)


def _log_call(entry: dict[str, Any]) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        _eprint(f"[claw-tsaver] failed to write log: {e}")


def _compressed_payload(
    full_text: str, tool_name: str, original_tokens: int
) -> str:
    """Build the JSON envelope that replaces a too-large tool return value."""
    head = full_text[:PREVIEW_CHARS]
    tail = full_text[-PREVIEW_CHARS:] if len(full_text) > PREVIEW_CHARS else ""
    handle = store.save_expansion(tool_name, full_text)
    envelope = {
        "compressed": True,
        "preview_head": head,
        "preview_tail": tail,
        "full_token_count": original_tokens,
        "expand_handle": handle,
        "hint": (
            f"Call expand_content with handle '{handle}' "
            "to retrieve full content."
        ),
    }
    return json.dumps(envelope, ensure_ascii=False)


# ---------------------------------------------------------------------------
# downstream server registry
# ---------------------------------------------------------------------------
class DownstreamRegistry:
    """Holds live ``ClientSession``s for every configured downstream server
    and records which prefixed tool name maps to which session."""

    def __init__(self, exit_stack: AsyncExitStack) -> None:
        self._exit_stack = exit_stack
        self._sessions: dict[str, ClientSession] = {}
        self._tools: list[Tool] = []
        # prefixed_name -> (server_name, original_tool_name)
        self._routes: dict[str, tuple[str, str]] = {}

    async def add_server(
        self, name: str, command: str, args: list[str]
    ) -> None:
        params = StdioServerParameters(command=command, args=args)
        try:
            read, write = await self._exit_stack.enter_async_context(
                stdio_client(params)
            )
            session = await self._exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
        except Exception as e:
            _eprint(f"[claw-tsaver] failed to spawn '{name}': {e}")
            return
        self._sessions[name] = session
        try:
            listed = await session.list_tools()
        except Exception as e:
            _eprint(f"[claw-tsaver] list_tools failed for '{name}': {e}")
            return
        for tool in listed.tools:
            prefixed = f"{name}{PREFIX_SEP}{tool.name}"
            self._routes[prefixed] = (name, tool.name)
            self._tools.append(
                Tool(
                    name=prefixed,
                    description=tool.description,
                    inputSchema=tool.inputSchema,
                )
            )
        _eprint(
            f"[claw-tsaver] connected to '{name}' "
            f"({len(listed.tools)} tools)"
        )

    @property
    def tools(self) -> list[Tool]:
        return list(self._tools)

    def route(
        self, prefixed_name: str
    ) -> tuple[ClientSession, str] | None:
        info = self._routes.get(prefixed_name)
        if info is None:
            return None
        server_name, original = info
        session = self._sessions.get(server_name)
        if session is None:
            return None
        return session, original


# ---------------------------------------------------------------------------
# built-in tool
# ---------------------------------------------------------------------------
EXPAND_TOOL = Tool(
    name="expand_content",
    description=(
        "Retrieve the full content of a previously compressed tool result. "
        "Pass the expand_handle returned in the compressed envelope."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "handle": {
                "type": "string",
                "description": "The expand_handle from a compressed result.",
            }
        },
        "required": ["handle"],
    },
)


# ---------------------------------------------------------------------------
# server entry point
# ---------------------------------------------------------------------------
async def serve() -> None:
    """Run the claw-tsaver MCP proxy on stdio."""
    store.init_db()
    config = load_config()
    threshold = int(config.get("compression_threshold_tokens", 500))
    encoder = tiktoken.get_encoding("cl100k_base")

    server: Server = Server("claw-tsaver")

    async with AsyncExitStack() as stack:
        registry = DownstreamRegistry(stack)
        for entry in config.get("downstream_servers", []):
            await registry.add_server(
                name=entry["name"],
                command=entry["command"],
                args=list(entry.get("args", [])),
            )

        @server.list_tools()
        async def _list_tools() -> list[Tool]:
            return [EXPAND_TOOL, *registry.tools]

        @server.call_tool()
        async def _call_tool(
            name: str, arguments: dict[str, Any] | None
        ) -> list[Any]:
            args = arguments or {}

            # built-in: expand a stored handle
            if name == "expand_content":
                handle = str(args.get("handle", ""))
                full = store.get_expansion(handle)
                if full is None:
                    return [
                        TextContent(
                            type="text",
                            text=f"No expansion found for handle '{handle}'.",
                        )
                    ]
                return [TextContent(type="text", text=full)]

            # downstream proxy
            route = registry.route(name)
            if route is None:
                return [
                    TextContent(type="text", text=f"Unknown tool '{name}'.")
                ]
            session, original_name = route
            try:
                result = await session.call_tool(original_name, args)
            except Exception as e:
                return [
                    TextContent(
                        type="text", text=f"Downstream error: {e}"
                    )
                ]

            content = list(result.content or [])
            full_text = _stringify_content(content)
            original_tokens = _count_tokens(full_text, encoder)

            if original_tokens <= threshold:
                _log_call(
                    {
                        "ts": int(time.time()),
                        "tool": name,
                        "original_tokens": original_tokens,
                        "returned_tokens": original_tokens,
                        "saved": 0,
                        "compressed": False,
                    }
                )
                return content

            envelope = _compressed_payload(full_text, name, original_tokens)
            returned_tokens = _count_tokens(envelope, encoder)
            _log_call(
                {
                    "ts": int(time.time()),
                    "tool": name,
                    "original_tokens": original_tokens,
                    "returned_tokens": returned_tokens,
                    "saved": original_tokens - returned_tokens,
                    "compressed": True,
                }
            )
            return [TextContent(type="text", text=envelope)]

        async with stdio_server() as (read, write):
            await server.run(
                read, write, server.create_initialization_options()
            )