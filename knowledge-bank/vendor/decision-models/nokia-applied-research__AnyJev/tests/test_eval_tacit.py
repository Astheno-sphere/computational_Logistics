"""scripts/eval_tacit.py maps JevBench records to Tacit requests the way the published evaluation did."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("eval_tacit", ROOT / "scripts/eval_tacit.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def test_jevbench_mapping(tmp_path):
    d = tmp_path / "datasets/public"
    d.mkdir(parents=True)
    recs = [
        {"id": "n1", "state": {"log": "x"}, "expected": "no",
         "question": {"type": "noul", "instructions": "Escalate?", "criteria": {"true": "yes, page", "false": "no"}}},
        {"id": "s1", "state": "S", "expected": 2,
         "question": {"type": "score", "instructions": "Severity?", "criteria": ["none", "low", "high"]}},
        {"id": "c1", "state": "S", "expected": "refund",
         "question": {"type": "choice", "instructions": "Route?", "criteria": {"track": "where is it", "refund": ""}}},
    ]
    (d / "easy.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    noul, score, choice = ev.jevbench_items(str(tmp_path), expected=None)
    assert noul["kind"] == "yes_no" and noul["y"] == 1 and noul["state"] == '{"log": "x"}'
    assert noul["question"].endswith('rubric: {"no": "no", "yes": "yes, page"}')
    assert score["kind"] == "score" and score["first_level"] == 0 and score["options"] == ["none", "low", "high"]
    assert score["y"] == 2
    assert choice["options"] == ["track", "refund"] and choice["y"] == 1 and "first_level" not in choice
    assert choice["question"].endswith('rubric: {"track": "where is it", "refund": "refund"}')
