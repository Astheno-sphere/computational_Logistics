"""The result tables in both READMEs are transcribed from committed JSON; this keeps them in step."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
READMES = ["README.md", "README.zh-CN.md"]
TACIT = ROOT / "bench/results_tacit/2026-10-06"
L0 = ROOT / "bench/results_v01/2026-09-22/Qwen__Qwen3-8B.json"


def cells(line):
    return [c.strip().replace("**", "") for c in line.strip().strip("|").split("|")]


def expected(res):
    n = res["n"]
    one = "%.3f" % (res["one_forward"]["correct"] / n)
    if not res["settings"]["adaptive"]:
        return one, "—"
    a = res["adaptive"]
    return one, "%.3f <sub>%.1f%%</sub>" % (a["correct"] / n, 100 * a["escalated"] / n)


@pytest.mark.parametrize("readme", READMES)
def test_tacit_table_matches_its_json(readme):
    rows = [cells(x) for x in (ROOT / readme).read_text().splitlines() if x.startswith("| [Tacit-")]
    assert len(rows) == 5
    for row in rows:
        name = re.match(r"\[(Tacit-[\w.]+)\]", row[0]).group(1)
        for col, task in ((2, "jevbench"), (4, "bev")):
            res = json.loads((TACIT / ("%s.%s.json" % (name, task))).read_text())
            assert res["model"] == "morriszjm/" + name
            assert (row[col], row[col + 1]) == expected(res), (readme, name, task)


@pytest.mark.parametrize("readme", READMES)
def test_raw_vs_l0_table_matches_its_json(readme):
    task = next(t for t in json.loads(L0.read_text())["tasks"] if t["task"] == "banking20")["levels"]
    text = (ROOT / readme).read_text().replace("**", "")
    for metric in ("flip", "acc", "ece"):
        want = "| %.3f | %.3f |" % (task["raw"][metric], task["L0"][metric])
        assert want in text, (readme, metric, want)
    cov = "| %.1f%% | %.1f%% |" % (100 * task["raw"]["cov@5%"], 100 * task["L0"]["cov@5%"])
    assert cov in text, (readme, cov)
