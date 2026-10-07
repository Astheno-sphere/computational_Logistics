import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from jev.client import Client
from jev.server import make_server, strict_json
from jev.serving import Predictor


class ExplicitTestScorer:
    def __init__(self):
        self.counts = []

    def score(self, records):
        count = sum(1 if r["kind"] == "noul" else len(r["options"]) for r in records)
        self.counts.append(count)
        return [[0.0, 1.0] if r["kind"] == "noul" else
                [float(o.split(":")[0]) for o in r["options"]] for r in records], count * 7


def request():
    return {"state": {"text": "test"}, "questions": {
        "large": {"type": "choice", "instructions": "Choose.", "criteria": {str(i): None for i in range(9)}},
        "binary": {"type": "noul", "instructions": "Yes?"},
        "ordinal": {"type": "score", "instructions": "Rate.", "criteria": ["0", "1", "2"]},
    }}


class ServingTest(unittest.TestCase):
    def test_chunked_choice_is_normalized_after_reassembly(self):
        reference = Predictor(ExplicitTestScorer(), model_name="test", batch_size=100).predict(request())
        for size in (1, 2, 4, 8):
            scorer = ExplicitTestScorer()
            result = Predictor(scorer, model_name="test", batch_size=size).predict(request())
            self.assertEqual(result["answers"], reference["answers"])
            self.assertEqual(result["usage"], {"input_tokens": 91, "output_tokens": 0})
            self.assertLessEqual(max(scorer.counts), size)

    def test_limits_and_unknown_models_fail_before_backend(self):
        scorer = ExplicitTestScorer()
        predictor = Predictor(scorer, model_name="test", max_questions=1)
        with self.assertRaises(ValueError):
            predictor.predict(request())
        with self.assertRaises(ValueError):
            Predictor(scorer, model_name="test").predict({**request(), "model": "other"})
        self.assertEqual(scorer.counts, [])

    def test_invalid_backend_cannot_return_fake_answers(self):
        class Broken:
            def score(self, records):
                return [[float("nan")]], 0
        with self.assertRaises(RuntimeError):
            Predictor(Broken(), model_name="test").predict(request())

    def test_ambiguous_json_is_rejected(self):
        for text in ('{"state":1,"state":2}', '{"state":NaN}', '{"x":Infinity}'):
            with self.assertRaises(ValueError):
                strict_json(text)

    def test_http_client_official_route_and_errors(self):
        server = make_server(Predictor(ExplicitTestScorer(), model_name="test"), port=0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            result = Client(base + "/v1/systemone").ask(**request(), model="jev-latest")
            self.assertEqual(result["answers"]["large"]["choice"], "8")
            self.assertEqual(result["model"], "test")
            with urlopen(base + "/health") as response:
                self.assertEqual(json.load(response)["status"], "ready")
            with urlopen(base + "/") as response:
                self.assertTrue(response.url.endswith("/examples/workbench/index.html"))
                self.assertIn(b'workbench', response.read())
            with urlopen(base + "/examples/workbench/logic.mjs") as response:
                self.assertIn(b'parseCSV', response.read())
            for body, headers, code in [(b'{"state":NaN}', {}, 422),
                                        (json.dumps(request()).encode(), {"Origin": "https://outside.invalid"}, 403)]:
                req = Request(base + "/v1/inference", body,
                              headers={"Content-Type": "application/json", **headers})
                with self.assertRaises(HTTPError) as ctx:
                    urlopen(req)
                self.assertEqual(ctx.exception.code, code)
                ctx.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

    def test_http_inventory_lists_requests_and_keeps_artifacts_fetchable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "examples"
            fixtures = {
                "z-request.json": request(),
                "nested/a-request.json": request(),
                "games/wiki-graph.json": {"nodes": ["start", "goal"], "edges": [["start", "goal"]]},
                "games/trex-state.json": {"score": 0, "obstacles": []},
                "painting/reference.json": {"size": 8, "answers": {}},
                "list.json": [request()],
                "empty-questions.json": {"state": "test", "questions": {}},
                "invalid-question.json": {"state": "test", "questions": {
                    "bad": {"type": "text", "instructions": "Unsupported question type"}}},
                "invalid-state.json": {**request(), "state": None},
            }
            for name, value in fixtures.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
            (root / "malformed.json").write_text("{")
            (root / "duplicate-key.json").write_text('{"state":"a","state":"b","questions":{}}')
            outside = Path(temporary) / "outside.json"
            outside.write_text(json.dumps(request()))
            (root / "outside-link.json").symlink_to(outside)
            scorer = ExplicitTestScorer()
            server = make_server(Predictor(scorer, model_name="test"), port=0, static_root=root)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(base + "/examples.json") as response:
                    self.assertEqual(json.load(response), {"files": ["nested/a-request.json", "z-request.json"]})
                self.assertEqual(scorer.counts, [])
                for name in ("painting/reference.json", "games/wiki-graph.json", "list.json"):
                    with self.subTest(artifact=name), urlopen(base + "/examples/" + name) as response:
                        self.assertEqual(json.load(response), fixtures[name])
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + "/examples/outside-link.json")
                self.assertEqual(error.exception.code, 404)
                error.exception.close()
                with urlopen(base + "/examples/nested/a-request.json") as response:
                    selected = json.load(response)
                result = Client(base + "/v1/systemone").ask(**selected)
                self.assertEqual(result["answers"]["large"]["choice"], "8")
            finally:
                server.shutdown()
                server.server_close()
                worker.join()


if __name__ == "__main__":
    unittest.main()
