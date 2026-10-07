import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from jev.api import compile_request, format_response
from scripts import jevbench_open_development as development
from scripts import jevbench_openjev as legacy


IDENTITY = {"model": "Qwen/Qwen3.5-2B", "method": "lora_decision_head",
            "base_revision": "1" * 40, "checkpoint_sha256": "2" * 64,
            "temperature": 1.25, "code_commit": "3" * 40, "max_length": 16384}


def fixtures():
    tasks, tiers = [], {}
    for family in (*development.PRIORITY_FAMILIES, "ordinal", "policy", "intent", "routing"):
        for index in range(16):
            kind = ("noul", "choice", "score")[index % 3]
            labels = ["no", "yes"] if kind == "noul" else ["0", "1", "2"]
            question = {"type": kind, "instructions": "Synthetic test fixture only."}
            if kind != "noul":
                question["criteria"] = list(labels) if kind == "score" else {label: label for label in labels}
            ident = f"fixture-{family}-{index}"
            tasks.append(SimpleNamespace(id=ident, family=family, state="Fixture content.", question=question,
                                         labels=labels, expected=1 if kind == "score" else labels[0],
                                         split="public", provenance={"gold_sentinel": "PRIVATE_GOLD"}))
            tiers[ident] = "hard" if family in development.PRIORITY_FAMILIES else "standard"
    def validate(probs, task):
        valid = set(probs) == set(task.labels) and abs(sum(probs.values()) - 1) <= .001
        predicted = min(probs, key=lambda key: (-probs[key], key)) if valid else None
        return {"valid": valid, "probs": probs if valid else None,
                "correct": predicted == str(task.expected)}
    return SimpleNamespace(tasks=tasks, tiers=tiers,
                           base=SimpleNamespace(build_question=lambda task: copy.deepcopy(task.question)),
                           scoring=SimpleNamespace(score_task=validate))


class PublicDevelopmentTest(unittest.TestCase):
    def test_selection_never_consults_gold_state_or_predictions(self):
        source = fixtures()
        selected = development.select_tasks(source, 64)
        larger = development.select_tasks(source, 128)
        self.assertEqual([t.id for t in selected], [t.id for t in larger[:64]])
        self.assertEqual(sum(t.family in development.PRIORITY_FAMILIES for t in selected), 32)
        self.assertEqual(len({t.id for t in selected}), 64)
        altered = copy.deepcopy(source)
        for task in altered.tasks:
            task.expected, task.state, task.provenance = "changed gold", "changed state", {"correct": False}
        self.assertEqual([t.id for t in selected], [t.id for t in development.select_tasks(altered, 64)])
        with self.assertRaises(ValueError):
            development.select_tasks(source, 63)

    def test_prepared_requests_exclude_gold_and_changed_freeze_fails(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(development, "load_upstream", return_value=fixtures()):
            path = Path(tmp) / "prepared"
            manifest = development.prepare("unused", path)
            raw = (path / "requests.json").read_bytes()
            self.assertNotIn(b"PRIVATE_GOLD", raw)
            self.assertNotIn(b'"expected"', raw)
            self.assertNotIn(b'"provenance"', raw)
            self.assertEqual(manifest["sealed_items_read"], 0)
            development.verify_preparation(fixtures(), path)
            (path / "requests.json").write_bytes(raw + b"\n")
            with self.assertRaisesRegex(ValueError, "selection changed"):
                development.verify_preparation(fixtures(), path)

    def test_noul_inclusive_boundaries_and_abstention_count_wrong(self):
        task = SimpleNamespace(question={"type": "noul"}, labels=["no", "yes"], expected="yes")
        upstream = fixtures()
        for p, abstain, correct in ((.2, False, False), (.200001, True, False),
                                    (.799999, True, False), (.8, False, True)):
            row = development.score(task, {"no": 1 - p, "yes": p}, upstream)
            self.assertEqual((row["abstained"], row["correct"]), (abstain, correct))
        row = development.score(task, {"no": .5, "yes": .5}, upstream)
        metrics = development.metrics([row])
        self.assertEqual(metrics["competence"], -100)
        self.assertEqual(metrics["coverage"], 0)

    def test_score_expected_position_is_not_argmax_accuracy(self):
        task = SimpleNamespace(question={"type": "score"}, labels=["0", "1", "2"], expected=1)
        row = development.score(task, {"0": .4, "1": 0, "2": .6}, fixtures())
        self.assertFalse(row["correct"])
        self.assertAlmostEqual(row["normalized_mae"], .1)
        result = development.metrics([row])
        self.assertAlmostEqual(result["competence"], 70)
        self.assertEqual(result["argmax_accuracy_auxiliary"], 0)
        invalid = development.score(task, {}, fixtures())
        self.assertIsNone(development.metrics([invalid])["competence"])

    def test_durable_collection_and_replay_bind_current_scope_and_counts(self):
        upstream = fixtures()
        with tempfile.TemporaryDirectory() as tmp, patch.object(development, "load_upstream", return_value=upstream):
            root = Path(tmp)
            development.prepare("unused", root / "prepared")
            requests = json.loads((root / "prepared/requests.json").read_bytes())["workloads"]
            received = []
            for row in requests:
                records = compile_request(row["request"]["state"], row["request"]["questions"])
                n = len(records[0]["answer_keys"])
                response = format_response(records, [[1 / n] * n])
                response.update(model=IDENTITY["model"], usage={"input_tokens": 42},
                                metadata={**{k: v for k, v in IDENTITY.items() if k != "model"},
                                          "prefix_cache": {"enabled": False}})
                raw = legacy.json_bytes(response)
                received.append(SimpleNamespace(status=200, read=lambda raw=raw: raw))
            with patch.object(legacy.http.client, "HTTPConnection") as http:
                http.return_value.getresponse.side_effect = received
                report = development.collect("unused", root / "prepared", "http://127.0.0.1:8791/v1/systemone",
                                             IDENTITY, root / "run")
            self.assertEqual(report["upstream_commit"], development.UPSTREAM_COMMIT)
            self.assertEqual(report["scope"], development.SCOPE)
            summary = development.summarize("unused", root / "run")
            self.assertEqual(summary["n"], 64)
            self.assertIn("official I_open", summary["not_computed"])
            trained = copy.deepcopy(summary)
            trained["expected_identity"]["checkpoint_sha256"] = "4" * 64
            comparison = development.compare(summary, trained)
            self.assertEqual(comparison["subset_competence_delta"], 0)
            trained["input_sha256"] = "5" * 64
            with self.assertRaisesRegex(ValueError, "same frozen public sample"):
                development.compare(summary, trained)
            report["successful_requests"] = 63
            (root / "run/report.json").write_bytes(legacy.json_bytes(report))
            with self.assertRaisesRegex(ValueError, "counts differ"):
                development.summarize("unused", root / "run")


if __name__ == "__main__":
    unittest.main()
