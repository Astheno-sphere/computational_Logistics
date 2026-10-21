"""The proposal's motion plate: its data file agrees with the study it is drawn from."""
import json

from conftest import ROOT

PROP = ROOT / "docs" / "proposal"


def test_motion_data_matches_the_study():
    m = json.loads((PROP / "motion.json").read_text())
    s = json.loads((PROP / "study.json").read_text())
    n, ny = m["n"], len(m["years"])
    assert m["best"] == s["best"] and m["target"] == s["target"]
    for name, rows in m["states"].items():
        assert len(rows) == n and all(len(r) == ny and set(r) <= set("0123") for r in rows), name
    assert len(m["home"]) == n
    for t, j in m["home"]:
        assert j < len(m["towns"][t]["pts"])
    hit = lambda k: sum(line[-1] <= m["target"] for line in m["fans"][k])   # noqa: E731
    assert (hit("no_policy"), hit(m["best"])) == (4, 41)   # the numbers the proposal text states
    for t in m["towns"]:
        assert t["path"].startswith("M") and t["w"] > 0 and t["h"] > 0 and t["span_m"] > 0


def test_motion_plate_is_embedded_in_the_built_proposal():
    html = (PROP / "index.html").read_text()
    assert 'id="mp"' in html and "/*MOTION*/" not in html and "/*MOTION_JS*/" not in html
