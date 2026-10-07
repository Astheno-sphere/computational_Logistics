#!/usr/bin/env python3
"""Speak stdio to a client that cannot speak Streamable HTTP, and HTTP to DFX.

DFX is a REMOTE MCP server. That is the right shape for it: there is nothing to
install, nothing to keep updated, and the data behind it moves nightly whether or not
anyone has pulled a new version. Every client that speaks Streamable HTTP should use
the URL directly and skip this file entirely.

This exists for the clients that do not, and there are still many of them. A stdio
client launches a subprocess, writes JSON-RPC to its stdin and reads JSON-RPC from its
stdout, and it has no way to reach a URL at all. For those, this is the whole adapter:
one process, one POST per message, no state.

    python3 dfx_mcp_stdio.py

NO DEPENDENCIES, ON PURPOSE. The same rule the server itself follows. A bridge that
needs a package manager to run is a bridge that fails on the machine of the person who
just wanted to try the thing, and this is the first code a stranger runs.

STDOUT IS THE PROTOCOL CHANNEL AND NOTHING ELSE MAY TOUCH IT. One stray print here
corrupts the stream and the client reports a malformed server rather than a chatty
bridge, so every diagnostic in this file goes to stderr.

A TRANSPORT FAILURE IS ANSWERED, NEVER SWALLOWED. If the endpoint is unreachable or
slow, the client gets a JSON-RPC error carrying the id it sent, because a client that
is waiting on an id waits forever when the bridge simply gives up. The one exception is
a notification, which has no id and by the specification takes no reply: that is
reported on stderr and nowhere else.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

ENDPOINT = os.environ.get("DFX_MCP_URL",
                          "https://exchange-production-9123.up.railway.app/mcp")
# Long enough for the widest question this server answers. Measured against production:
# an unfiltered search over the whole tape is the slowest call on the surface at roughly
# two seconds, and every other shape is well under one. Sixty is not a performance
# claim, it is the difference between a slow answer and a client that reports a dead
# server because it gave up first.
TIMEOUT = float(os.environ.get("DFX_MCP_TIMEOUT", "60"))
# Optional and good manners. It does not authenticate anyone and DFX treats it as a
# claim rather than an identity, which is why it is safe to let a caller set it.
AGENT = os.environ.get("DFX_AGENT_NAME", "dfx-mcp-stdio-bridge")


def _post(payload: bytes) -> str:
    req = urllib.request.Request(
        ENDPOINT, data=payload,
        headers={"Content-Type": "application/json",
                 # Both are advertised. The server answers this one in plain JSON
                 # today; naming the stream type as well means a future that upgrades
                 # to it does not break this file.
                 "Accept": "application/json, text/event-stream",
                 "X-Agent-Name": AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        body = r.read().decode("utf-8", "replace")
        kind = (r.headers.get("Content-Type") or "").lower()
    if "text/event-stream" in kind:
        # An SSE frame is `data: <json>` lines with blank separators. Only the payload
        # lines matter here, and a single response never spans more than one of them.
        for line in body.splitlines():
            if line.startswith("data:"):
                return line[5:].strip()
        return ""
    return body


def _error(rpc_id, code: int, message: str) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": rpc_id,
                       "error": {"code": code, "message": message}})


def main() -> int:
    out = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            # The client sent something that is not JSON. There is no id to answer to
            # and inventing one would put a reply on the stream nobody is waiting for.
            print(f"dfx-bridge: unparseable line from client: {e}", file=sys.stderr)
            continue

        # A notification is any message without an id, and the specification is explicit
        # that it takes no response. Forwarding it and then writing the server's reply
        # would put an unsolicited object on the stream.
        rpc_id = msg.get("id") if isinstance(msg, dict) else None
        is_notification = isinstance(msg, dict) and "id" not in msg

        try:
            reply = _post(line.encode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:200]
            if is_notification:
                print(f"dfx-bridge: HTTP {e.code} on notification: {detail}",
                      file=sys.stderr)
                continue
            reply = _error(rpc_id, -32603, f"DFX returned HTTP {e.code}: {detail}")
        except Exception as e:                                        # noqa: BLE001
            if is_notification:
                print(f"dfx-bridge: {type(e).__name__} on notification: {e}",
                      file=sys.stderr)
                continue
            reply = _error(rpc_id, -32603,
                           f"could not reach DFX at {ENDPOINT}: "
                           f"{type(e).__name__}: {e}")

        if is_notification or not reply:
            continue
        out.write(reply.rstrip("\n") + "\n")
        # FLUSH EVERY MESSAGE. Python buffers a pipe, the client is blocked reading it,
        # and a bridge that answers correctly into a buffer is a bridge that hangs.
        out.flush()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except BrokenPipeError:
        # The client closed the stream. That is how a session ends, not a failure.
        sys.exit(0)
