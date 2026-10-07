import json

from conftest import ROOT
import tree_diagnose as td

DUMP = json.loads((ROOT / "skills/gh-datatree/examples/probe_example.json").read_text())


def codes(component):
    return {f["code"] for f in td.diagnose(DUMP) if f["component"] == component}


def test_graft_against_flat_list_is_caught_with_its_flag():
    c = codes("Line")
    assert {"CROSS_PRODUCT", "PARAM_FLAGS"} <= c


def test_nulls_empty_branches_runtime_and_deep_paths():
    c = codes("Route crv")
    assert {"RUNTIME", "NULLS", "DEEP_PATHS"} <= c
    assert "CROSS_PRODUCT" not in c          # list access: one curve per branch is expected


def test_clean_component_has_no_warnings():
    ok = [{"component": "Ok", "messages": [], "outputs": [], "inputs": [
        {"name": "A", "access": "item", "mapping": "none", "branches": [{"path": "{0}", "n": 4}]},
        {"name": "B", "access": "item", "mapping": "none", "branches": [{"path": "{0}", "n": 4}]}]}]
    assert [f for f in td.diagnose(ok) if f["severity"] != "info"] == []


def test_report_lists_errors_first():
    text = td.report(td.diagnose(DUMP))
    assert text.index("WARNING") < text.index("INFO")
