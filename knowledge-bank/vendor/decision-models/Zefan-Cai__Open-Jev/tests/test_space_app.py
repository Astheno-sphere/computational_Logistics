"""CPU-only HTTP boundary tests using explicit fixtures, never model inference."""
from contextlib import redirect_stderr
from http.client import HTTPConnection
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest


APP_PATH = Path(__file__).resolve().parents[1] / "deploy/huggingface-space/app.py"
SPEC = importlib.util.spec_from_file_location("open_jev_space_app_under_test", APP_PATH)
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


class ExplicitFixturePredictor:
    """Deterministic response for transport tests; this is not a trained model."""
    model_name = "explicit-http-test-fixture"
    method = "fixture_not_model_inference"

    def __init__(self, *, entered=None, release=None, error=None):
        self.entered, self.release, self.error = entered, release, error
        self.calls = []

    def predict(self, request):
        self.calls.append(request)
        if self.entered:
            self.entered.set()
        if self.release and not self.release.wait(5):
            raise RuntimeError("Test fixture was not released")
        if self.error:
            raise self.error
        return {"answers": {"category": {"type": "choice", "choice": "退款",
                "probabilities": {"退款": 0.75, "其他": 0.25}}},
                "metadata": {"test_fixture_only": True}}


def classification_request():
    return {"state": "请帮我退款。", "questions": {"category": {
        "type": "choice", "instructions": "按主要诉求选择类别。",
        "criteria": {"退款": None, "其他": None}}}}


class SpaceHTTPTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.files = {"index.html": '<link href="./styles.css"><script type="module" src="./app.js"></script>',
                      "app.js": 'import {parseCategories} from "./logic.mjs";',
                      "logic.mjs": 'export function parseCategories() { return {}; }',
                      "styles.css": "body { color: black; }"}
        for name, content in self.files.items():
            (self.root / name).write_text(content, encoding="utf-8")
        (self.root / "not-public.txt").write_text("not an allowed asset")
        self.state = app.ModelState()
        self.server = app.make_server(self.state, host="127.0.0.1", port=0,
                                      workbench=self.root / "index.html")
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(3)

    def request(self, path="/health", *, payload=None, raw=None, headers=None):
        if payload is not None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request("POST" if raw is not None else "GET", path, body=raw,
                               headers={"Content-Type": "application/json", **(headers or {})})
            response = connection.getresponse()
            return response.status, response.read(), dict(response.getheaders())
        finally:
            connection.close()

    def ready(self, predictor=None):
        predictor = predictor or ExplicitFixturePredictor()
        with self.state.lock:
            self.state.predictor = predictor
            self.state.status = "ready"
        return predictor

    def test_canonical_page_assets_and_developer_link(self):
        status, _, headers = self.request("/")
        self.assertEqual(status, 307)
        self.assertEqual(headers["Location"], "/examples/workbench/index.html")
        for name, expected in self.files.items():
            prefixes = ("/examples/workbench/",) if name == "index.html" else ("/", "/examples/workbench/")
            for prefix in prefixes:
                with self.subTest(path=prefix + name):
                    status, body, headers = self.request(prefix + name)
                    self.assertEqual(status, 200)
                    self.assertEqual(body.decode(), expected)
                    mime = "text/html" if name.endswith("html") else "text/css" if name.endswith("css") else "text/javascript"
                    self.assertEqual(headers["Content-Type"], mime + "; charset=utf-8")
                    self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        status, _, headers = self.request("/examples/index.html")
        self.assertEqual(status, 307)
        self.assertEqual(headers["Location"], "https://github.com/Zefan-Cai/Open-Jev/blob/main/README.md#typed-decisions")
        for path in ("/not-public.txt", "/examples/workbench/not-public.txt", "/examples/workbench/../not-public.txt"):
            self.assertEqual(self.request(path)[0], 404)

    def test_loading_and_error_do_not_claim_ready_or_infer(self):
        status, body, _ = self.request()
        health = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(health["status"], "loading")
        self.assertEqual(health["limits"], app.LIMITS)
        self.assertNotIn("method", health)
        self.assertEqual(self.request("/v1/systemone", payload=classification_request())[0], 503)
        with self.state.lock:
            self.state.status = "error"
        health = json.loads(self.request()[1])
        self.assertEqual(health["status"], "error")
        self.assertNotIn("model", health)
        self.assertEqual(self.request("/v1/systemone", payload=classification_request())[0], 503)

    def test_plain_category_names_reach_fixture(self):
        predictor = self.ready()
        payload = classification_request()
        status, body, _ = self.request("/v1/systemone", payload=payload)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["metadata"]["test_fixture_only"])
        self.assertEqual(predictor.calls, [payload])
        self.assertEqual(json.loads(self.request()[1])["method"], "fixture_not_model_inference")

    def test_blank_instructions_and_invalid_categories_never_reach_fixture(self):
        predictor = self.ready()
        for instructions in (None, "", " \n\t", "x" * 1001):
            payload = classification_request()
            payload["questions"]["category"]["instructions"] = instructions
            self.assertEqual(self.request("/v1/systemone", payload=payload)[0], 422)
        for description in (5, [], "x" * 501):
            payload = classification_request()
            payload["questions"]["category"]["criteria"]["退款"] = description
            self.assertEqual(self.request("/v1/systemone", payload=payload)[0], 422)
        self.assertEqual(predictor.calls, [])

    def test_busy_rejects_second_request_while_health_works(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        predictor = self.ready(ExplicitFixturePredictor(entered=entered, release=release))
        first = []
        worker = threading.Thread(target=lambda: first.append(
            self.request("/v1/systemone", payload=classification_request())))
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            health = json.loads(self.request()[1])
            self.assertEqual(health["status"], "ready")
            self.assertTrue(health["busy"])
            status, _, headers = self.request("/v1/systemone", payload=classification_request())
            self.assertEqual(status, 429)
            self.assertEqual(headers["Retry-After"], "5")
            self.assertEqual(len(predictor.calls), 1)
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(first[0][0], 200)
        self.assertFalse(self.state.inference_lock.locked())

    def test_errors_do_not_echo_input_or_raw_exception(self):
        marker = "PRIVATE_FIXTURE_INPUT_MUST_NOT_APPEAR"
        predictor = self.ready(ExplicitFixturePredictor(error=RuntimeError(marker)))
        payload = classification_request()
        payload["state"] = marker
        logs = io.StringIO()
        with redirect_stderr(logs):
            status, body, _ = self.request("/v1/systemone", payload=payload)
        self.assertEqual(status, 500)
        self.assertNotIn(marker, body.decode())
        self.assertNotIn(marker, logs.getvalue())
        self.assertNotIn("answers", json.loads(body))
        self.assertEqual(len(predictor.calls), 1)
        self.assertFalse(self.state.inference_lock.locked())

    def test_request_limits_and_origin_guard(self):
        predictor = self.ready()
        payload = classification_request()
        self.assertEqual(self.request("/v1/systemone", payload=payload,
                                      headers={"Origin": "https://outside.invalid"})[0], 403)
        self.assertEqual(self.request("/v1/systemone", raw=b" " * (app.MAX_BODY_BYTES + 1))[0], 413)
        payload["state"] = "x" * 4001
        self.assertEqual(self.request("/v1/systemone", payload=payload)[0], 422)
        self.assertEqual(self.request("/v1/systemone", raw=b'{"state":1,"state":2}')[0], 422)
        self.assertEqual(predictor.calls, [])


if __name__ == "__main__":
    unittest.main()
