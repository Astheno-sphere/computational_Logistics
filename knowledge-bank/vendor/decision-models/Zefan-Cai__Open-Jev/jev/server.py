"""Local HTTP service for Open-Jev; no cloud keys or generated JSON required."""
import argparse
import json
import mimetypes
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .api import compile_request
from .serving import load_predictor


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("non-finite JSON number")
    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)


def make_server(predictor, host="127.0.0.1", port=8791, *, static_root=None,
                max_body_bytes=4 * 1024 * 1024):
    root = Path(static_root or Path(__file__).resolve().parent.parent / "examples").resolve()
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(30)

        def log_message(self, *args):
            pass  # Do not log request bodies, prompts, or credentials.

        def send(self, status, data, content_type="application/json"):
            payload = json.dumps(data, ensure_ascii=False, allow_nan=False).encode() if isinstance(data, dict) else data
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/" and static_root is None:
                self.send_response(302)
                self.send_header("Location", "/examples/workbench/index.html")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if path == "/health":
                return self.send(200, {"status": "ready", "model": predictor.model_name, "method": predictor.method})
            if path == "/v1/models":
                return self.send(200, {"models": [{"id": predictor.model_name, "name": predictor.model_name,
                                                   "description": "Open-Jev local " + predictor.method,
                                                   "release_date": "2026-09-19", "method": predictor.method}],
                                       "aliases": ["open-jev", "jev-latest"]})
            if path == "/examples.json":
                files = []
                for candidate in root.rglob("*.json"):
                    if not candidate.resolve().is_relative_to(root):
                        continue
                    try:
                        request = strict_json(candidate.read_bytes())
                        if not isinstance(request, dict) or not {"state", "questions"} <= request.keys():
                            continue
                        compile_request(request["state"], request["questions"])
                    except (OSError, ValueError, KeyError, TypeError):
                        continue
                    files.append(str(candidate.relative_to(root)))
                return self.send(200, {"files": sorted(files)})
            relative = "index.html" if path == "/" else path.removeprefix("/examples/").lstrip("/")
            if relative.endswith("/"):
                relative += "index.html"
            target = (root / relative).resolve()
            if not target.is_relative_to(root) or not target.is_file():
                return self.send(404, {"error": "not found"})
            return self.send(200, target.read_bytes(), mimetypes.guess_type(str(target))[0] or "application/octet-stream")

        def do_POST(self):
            if urlsplit(self.path).path not in ("/v1/inference", "/v1/systemone", "/api/jev"):
                return self.send(404, {"error": "not found"})
            origin = self.headers.get("Origin")
            if origin and urlsplit(origin).netloc != self.headers.get("Host"):
                return self.send(403, {"error": "cross-origin requests are disabled"})
            if self.headers.get_content_type() != "application/json":
                return self.send(415, {"error": "Content-Type must be application/json"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > max_body_bytes:
                    return self.send(413, {"error": "request body size is outside server limits"})
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValueError("incomplete request body")
                request = strict_json(body)
                with lock:
                    response = predictor.predict(request)
                return self.send(200, response)
            except (ValueError, KeyError, TypeError, UnicodeError) as error:
                return self.send(422, {"error": str(error)})
            except Exception as error:
                # Never substitute a fake/oracle answer when model inference fails.
                return self.send(500, {"error": "model inference failed", "error_type": type(error).__name__})

    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--checkpoint")
    group.add_argument("--model", dest="model_id")
    parser.add_argument("--revision")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--max-length", type=int)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--backend", choices=("torch", "triton-tail", "fast-cuda"), default="torch",
                        help="Experimental CUDA acceleration; default torch is unchanged")
    parser.add_argument("--fused-final-head", action=argparse.BooleanOptionalAction, default=True,
                        help="Fuse final RMSNorm and scalar scoring in fast-cuda (default on)")
    parser.add_argument("--prefix-cache", action=argparse.BooleanOptionalAction, default=False,
                        help="Enable request-local token-prefix reuse; default off pending full-checkpoint BF16 validation")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8791)
    args = vars(parser.parse_args())
    host, port = args.pop("host"), args.pop("port")
    predictor = load_predictor(**args)
    server = make_server(predictor, host, port)
    print(json.dumps({"url": f"http://{host}:{server.server_port}", "model": predictor.model_name,
                      "method": predictor.method}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
