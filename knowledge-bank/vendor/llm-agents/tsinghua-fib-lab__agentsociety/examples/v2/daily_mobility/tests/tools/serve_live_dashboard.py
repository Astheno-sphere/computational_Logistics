#!/usr/bin/env python3
"""Serve the Daily Mobility interactive live dashboard."""

from __future__ import annotations

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from live_data import build_dashboard_payload  # noqa: E402

STATIC_DIR = TOOLS_DIR / "live_dashboard"


class DashboardHandler(BaseHTTPRequestHandler):
    run_dir: Path
    log_file: Path | None
    agent_id: int

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        if self.path.startswith("/api/"):
            return

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content = path.read_bytes()
        suffix = path.suffix.lower()
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
        }.get(suffix, "application/octet-stream")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        route = parsed.path.rstrip("/") or "/"

        if route == "/api/live-state":
            try:
                qs = parse_qs(parsed.query)
                agent_id = self.agent_id
                if qs.get("agent_id"):
                    try:
                        agent_id = int(qs["agent_id"][0])
                    except ValueError:
                        import logging
                        logging.getLogger(__name__).debug("Malformed agent_id query param; using default")
                payload = build_dashboard_payload(
                    self.run_dir, self.log_file, agent_id=agent_id
                )
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._send_json(payload)
            return

        if route == "/":
            self._send_file(STATIC_DIR / "index.html")
            return

        candidate = (STATIC_DIR / route.lstrip("/")).resolve()
        if not candidate.is_relative_to(STATIC_DIR.resolve()):
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        self._send_file(candidate)


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily Mobility live web dashboard")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--log-file", type=Path, default=None)
    parser.add_argument("--agent-id", type=int, default=1)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    handler = type(
        "BoundDashboardHandler",
        (DashboardHandler,),
        {
            "run_dir": args.run_dir.resolve(),
            "log_file": args.log_file,
            "agent_id": args.agent_id,
        },
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Daily Mobility dashboard: {url}", flush=True)
    print(f"run-dir: {args.run_dir.resolve()}", flush=True)
    print(f"agent-id: {args.agent_id}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
