"""Entry point: `python -m atmospore_mcp` or `atmospore-mcp` (script alias)."""

from __future__ import annotations

import os
import sys

from atmospore_mcp.server import build_server


def main() -> None:
    api_key = os.environ.get("ATMOSPORE_API_KEY")
    if not api_key:
        print(
            "ERROR: ATMOSPORE_API_KEY environment variable is required.\n"
            "Get a free API key at https://atmospore.com/account (100 calls/day, no credit card).",
            file=sys.stderr,
        )
        sys.exit(2)

    server = build_server(api_key=api_key)
    server.run()


if __name__ == "__main__":
    main()
