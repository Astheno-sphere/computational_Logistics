"""Bounded public CPU demo; the model loads after the HTTP listener opens."""
import json
from pathlib import Path
import resource
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from jev.api import compile_request
from jev.server import strict_json


MODEL_ID = "ZefanCai/Open-Jev-2B"
MODEL_REVISION = "0c7aa498b1627be8da4acf34c863ff0ee0a92785"
BASE_ID = "Qwen/Qwen3.5-2B"
BASE_REVISION = "15852e8c16360a2fea060d615a32b45270f8a8fc"
LIMITS = {"max_candidates": 8, "max_text_chars": 4000, "max_length": 1024}
MAX_BODY_BYTES = 16 * 1024
WORKBENCH = Path("/opt/open-jev/examples/workbench/index.html")


class ModelState:
    def __init__(self):
        self.lock = threading.Lock()
        self.inference_lock = threading.Lock()
        self.predictor = None
        self.status = "loading"

    def health(self):
        with self.lock:
            result = {"status": self.status, "limits": dict(LIMITS),
                      "checkpoint": MODEL_ID, "checkpoint_revision": MODEL_REVISION,
                      "device": "cpu", "busy": self.inference_lock.locked()}
            if self.predictor is not None:
                result.update(model=self.predictor.model_name, method=self.predictor.method)
            if self.status == "error":
                result["error"] = "Model loading failed; the deployment operator must check the configuration."
            return result

    def load(self):
        started = time.perf_counter()
        try:
            import torch
            from huggingface_hub import snapshot_download
            from jev.serving import load_predictor

            torch.set_num_threads(2)
            torch.set_num_interop_threads(1)
            package = Path(snapshot_download(
                MODEL_ID, revision=MODEL_REVISION,
                allow_patterns=["package/checkpoint/**"], max_workers=2,
            ))
            checkpoint = package / "package/checkpoint"
            print(json.dumps({"event": "checkpoint_downloaded"}), flush=True)
            config = json.loads((checkpoint / "model.json").read_text())
            if (config.get("model_id"), config.get("revision")) != (BASE_ID, BASE_REVISION):
                raise ValueError("Unexpected checkpoint base identity")
            predictor = load_predictor(checkpoint=checkpoint, device="cpu",
                                       max_length=LIMITS["max_length"], batch_size=1,
                                       prefix_cache=False)
            predictor.max_questions = 1
            predictor.max_candidates = LIMITS["max_candidates"]
            print(json.dumps({"event": "weights_loaded", "device": "cpu"}), flush=True)
            # Check that this CPU supports the model's operators before readiness.
            # This fixed startup request is discarded and never shown as a user result.
            predictor.predict({"state": "A customer requests a refund.", "questions": {
                "startup": {"type": "choice", "instructions": "Choose the request type.",
                            "criteria": {"refund": "Refund request", "other": "Another request"}}
            }})
            with self.lock:
                self.predictor = predictor
                self.status = "ready"
            print(json.dumps({"event": "model_ready", "device": "cpu",
                              "checkpoint_revision": MODEL_REVISION,
                              "startup_seconds": time.perf_counter() - started,
                              "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024}), flush=True)
        except Exception as error:
            with self.lock:
                self.status = "error"
            # Do not print exception messages, paths, credentials, or request bodies.
            print(json.dumps({"event": "model_load_failed",
                              "error_type": type(error).__name__}), flush=True)


def validate_request(request):
    if not isinstance(request, dict):
        raise ValueError("Request must be an object")
    state = request.get("state")
    if not isinstance(state, str) or not state.strip() or len(state) > LIMITS["max_text_chars"]:
        raise ValueError("Text must contain 1 to 4000 characters")
    questions = request.get("questions")
    if not isinstance(questions, dict) or len(questions) != 1:
        raise ValueError("The public demo accepts exactly one classification question")
    question_id, question = next(iter(questions.items()))
    if not isinstance(question_id, str) or not 1 <= len(question_id) <= 80:
        raise ValueError("Invalid question identifier")
    if not isinstance(question, dict) or question.get("type") != "choice":
        raise ValueError("The public demo accepts a choice question")
    criteria = question.get("criteria")
    if not isinstance(criteria, dict) or not 2 <= len(criteria) <= LIMITS["max_candidates"]:
        raise ValueError("Define between 2 and 8 categories")
    if any(not isinstance(key, str) or not key.strip() or len(key) > 80
           or (value is not None and (not isinstance(value, str) or len(value) > 500))
           for key, value in criteria.items()):
        raise ValueError("Category names must be 1 to 80 characters; descriptions at most 500")
    instructions = question.get("instructions")
    if not isinstance(instructions, str) or not instructions.strip() or len(instructions) > 1000:
        raise ValueError("Instructions must contain 1 to 1000 characters")
    compile_request(state, questions)


class BoundedHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 8

    def __init__(self, address, handler):
        self.connections = threading.BoundedSemaphore(8)
        super().__init__(address, handler)

    def process_request(self, request, client_address):
        if not self.connections.acquire(blocking=False):
            try:
                request.settimeout(0.5)
                request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\n"
                                b"Retry-After: 5\r\nConnection: close\r\n\r\n")
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.connections.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.connections.release()

    def handle_error(self, request, client_address):
        pass  # Never log submitted data or client addresses.


def make_server(state, *, host="0.0.0.0", port=7860, workbench=WORKBENCH):
    workbench_root = Path(workbench).resolve().parent
    assets = {"index.html": "text/html; charset=utf-8",
              "app.js": "text/javascript; charset=utf-8",
              "logic.mjs": "text/javascript; charset=utf-8",
              "styles.css": "text/css; charset=utf-8"}

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, *args):
            pass

        def send(self, status, data, content_type="application/json; charset=utf-8"):
            payload = (json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
                       if isinstance(data, dict) else data)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if status in (429, 503):
                self.send_header("Retry-After", "5")
            self.end_headers()
            self.wfile.write(payload)

        def redirect(self, target):
            self.send_response(307)
            self.send_header("Location", target)
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/health":
                return self.send(200, state.health())
            if path in ("/", "/index.html", "/examples/workbench/"):
                return self.redirect("/examples/workbench/index.html")
            if path == "/examples/index.html":
                return self.redirect("https://github.com/Zefan-Cai/Open-Jev/blob/main/README.md#typed-decisions")
            name = path.removeprefix("/examples/workbench/") if path.startswith("/examples/workbench/") else path.removeprefix("/")
            if name in assets:
                target = (workbench_root / name).resolve()
                if target.parent != workbench_root:
                    return self.send(404, {"error": "Not found"})
                try:
                    content = target.read_bytes()
                except OSError:
                    return self.send(503, {"error": "Workbench asset is unavailable"})
                return self.send(200, content, assets[name])
            return self.send(404, {"error": "Not found"})

        def do_POST(self):
            if urlsplit(self.path).path != "/v1/systemone":
                return self.send(404, {"error": "Not found"})
            origin = self.headers.get("Origin")
            try:
                cross_origin = origin and urlsplit(origin).netloc != self.headers.get("Host")
            except ValueError:
                cross_origin = True
            if cross_origin:
                return self.send(403, {"error": "Cross-origin requests are disabled"})
            if self.headers.get_content_type() != "application/json":
                return self.send(415, {"error": "Content-Type must be application/json"})
            if self.headers.get("Transfer-Encoding"):
                return self.send(400, {"error": "Transfer-Encoding is not supported"})
            lengths = self.headers.get_all("Content-Length", [])
            try:
                if len(lengths) != 1:
                    raise ValueError("Missing or repeated length")
                length = int(lengths[0])
            except ValueError:
                return self.send(400, {"error": "A single valid Content-Length is required"})
            if not 1 <= length <= MAX_BODY_BYTES:
                return self.send(413, {"error": "Request is larger than the public demo limit"})
            with state.lock:
                predictor = state.predictor if state.status == "ready" else None
            if predictor is None:
                return self.send(503, {"error": "Model is not ready; check the service status"})
            if not state.inference_lock.acquire(blocking=False):
                return self.send(429, {"error": "Another request is running. Try again when it finishes."})
            try:
                body = self.rfile.read(length)
                if len(body) != length:
                    return self.send(400, {"error": "Incomplete request body"})
                try:
                    request = strict_json(body)
                    validate_request(request)
                except (ValueError, KeyError, TypeError, UnicodeError):
                    return self.send(422, {"error": "Invalid input. Use one text of at most 4000 characters and 2 to 8 categories."})
                try:
                    result = predictor.predict(request)
                except (ValueError, KeyError, TypeError):
                    return self.send(422, {"error": "The model rejected this request. Shorten the text or category descriptions; the limit is 1024 tokens per candidate."})
                except Exception:
                    return self.send(500, {"error": "Model inference failed; no result was produced"})
                return self.send(200, result)
            except OSError:
                return
            finally:
                state.inference_lock.release()

    return BoundedHTTPServer((host, port), Handler)


if __name__ == "__main__":
    state = ModelState()
    server = make_server(state)
    threading.Thread(target=state.load, name="model-loader", daemon=True).start()
    print(json.dumps({"event": "http_listening", "port": 7860, "status": "loading"}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
