"""An HTTP gateway for Tacit decisions in front of a running `vllm serve`.

    vllm serve morriszjm/Tacit-9B --host 127.0.0.1 --port 8000
    python -m anyjev.serve --model morriszjm/Tacit-9B --upstream http://127.0.0.1:8000/v1 --adaptive
    curl -s 127.0.0.1:8100/v1/decide -H 'Content-Type: application/json' \\
        -d '{"state": "Customer: my package has not arrived.", "question": "What does the customer want?",
             "options": ["track_order", "refund"]}'

One `Tacit` serves every client, so the escalation cap (`max_cot_share` over the last `cot_window`
decisions) is shared. POST /v1/decide takes one decision ({"state", "question", "options", "kind"})
or a batch ({"items": [...]}); GET /v1/stats and GET /health. Standard library only; it listens on
127.0.0.1 unless told otherwise and has no authentication of its own.
"""
from __future__ import annotations

import argparse
import http.server
import json
from typing import Optional, Sequence

from anyjev.tacit import Tacit


def make_server(tacit: Tacit, host: str = "127.0.0.1", port: int = 8100) -> http.server.ThreadingHTTPServer:
    """A threading HTTP server answering with `tacit`; call `.serve_forever()` on it."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                return self._send(200, {"ok": True})
            if self.path == "/v1/stats":
                return self._send(200, tacit.stats)
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/v1/decide":
                return self._send(404, {"error": "not found"})
            try:
                req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                if "items" in req:
                    return self._send(200, {"decisions": tacit.decide_batch(req["items"])})
                return self._send(200, tacit.decide_batch([req])[0])
            except (ValueError, KeyError, TypeError) as e:
                return self._send(400, {"error": str(e)})
            except RuntimeError as e:                    # the vLLM server failed or is unreachable
                return self._send(502, {"error": str(e)})

        def log_message(self, fmt, *args):
            pass

    return http.server.ThreadingHTTPServer((host, port), Handler)


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m anyjev.serve",
                                 description="Tacit decisions over HTTP, in front of a running `vllm serve`.")
    ap.add_argument("--model", required=True, help="the repo vLLM serves, e.g. morriszjm/Tacit-9B")
    ap.add_argument("--upstream", default="http://127.0.0.1:8000/v1", help="the vLLM server's URL (root or /v1)")
    ap.add_argument("--served-model", default=None, help="vLLM's --served-model-name, if it was set")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--adaptive", action="store_true", help="send low-confidence decisions to reasoning")
    ap.add_argument("--tau", type=float, default=0.5)
    ap.add_argument("--max-cot-share", type=float, default=0.2, help="a negative value removes the cap")
    ap.add_argument("--cot-window", type=int, default=1000, help="0 counts every decision since start")
    ap.add_argument("--cot-max-tokens", type=int, default=8192)
    a = ap.parse_args(argv)
    tacit = Tacit.from_pretrained(a.model, engine="server", base_url=a.upstream, served_model=a.served_model,
                                  adaptive=a.adaptive, tau=a.tau,
                                  max_cot_share=None if a.max_cot_share < 0 else a.max_cot_share,
                                  cot_window=a.cot_window or None, cot_max_tokens=a.cot_max_tokens)
    server = make_server(tacit, a.host, a.port)
    print("Tacit gateway: http://%s:%d/v1/decide -> %s (%s)" % (a.host, a.port, a.upstream, a.model), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
