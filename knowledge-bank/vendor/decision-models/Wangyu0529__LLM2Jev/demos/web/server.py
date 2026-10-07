"""Serve the web demo and proxy requests to an LLM2Jev HTTP server."""

from __future__ import annotations

import argparse
import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEMO_DIR = Path(__file__).resolve().parent
PROXY_PATHS = {
    "/api/models": ("GET", "/v1/models"),
    "/api/systemone": ("POST", "/v1/systemone"),
}


class DemoHandler(SimpleHTTPRequestHandler):
    api_base = "http://127.0.0.1:30000"
    api_key: str | None = None

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(DEMO_DIR), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] == "/assets/llm2jev-banner.jpeg":
            self._serve_asset()
            return
        if self.path.split("?", 1)[0] == "/api/models":
            self._proxy()
            return
        super().do_GET()

    def _serve_asset(self) -> None:
        asset = (DEMO_DIR.parent.parent / unquote(self.path.split("?", 1)[0].lstrip("/"))).resolve()
        if asset != (DEMO_DIR.parent.parent / "assets/llm2jev-banner.jpeg").resolve() or not asset.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = asset.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] == "/api/systemone":
            self._proxy()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _proxy(self) -> None:
        path = self.path.split("?", 1)[0]
        expected_method, upstream_path = PROXY_PATHS[path]
        if self.command != expected_method:
            self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)
            return

        body = None
        if self.command == "POST":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"detail": "Invalid Content-Length"})
                return
            body = self.rfile.read(length)

        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request = Request(
            f"{self.api_base}{upstream_path}",
            data=body,
            headers=headers,
            method=self.command,
        )
        try:
            with urlopen(request, timeout=300) as response:
                self._send_response(response.status, response.read(), response.headers.get_content_type())
        except HTTPError as error:
            self._send_response(error.code, error.read(), error.headers.get_content_type())
        except URLError as error:
            self._send_json(
                HTTPStatus.BAD_GATEWAY,
                {"detail": f"Could not reach LLM2Jev server: {error.reason}"},
            )

    def _send_json(self, status: int, payload: object) -> None:
        self._send_response(
            status,
            json.dumps(payload, ensure_ascii=False).encode(),
            "application/json",
        )

    def _send_response(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--api-base", default="http://127.0.0.1:30000")
    parser.add_argument("--api-key", default=os.environ.get("LLM2JEV_API_KEY"))
    args = parser.parse_args()

    DemoHandler.api_base = args.api_base.rstrip("/")
    DemoHandler.api_key = args.api_key
    server = ThreadingHTTPServer((args.host, args.port), DemoHandler)
    print(f"LLM2Jev web demo: http://{args.host}:{args.port}")
    print(f"Proxying model requests to {DemoHandler.api_base}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
