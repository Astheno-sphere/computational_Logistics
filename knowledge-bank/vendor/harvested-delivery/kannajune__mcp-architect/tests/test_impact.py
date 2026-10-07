"""Tests for change-impact (blast radius) analysis."""
from pathlib import Path

import pytest

from mcp_architect.analysis import analyze_impact


@pytest.fixture
def chain(tmp_path: Path) -> Path:
    """a → b → c  (a imports b, b imports c)."""
    pkg = tmp_path / "app"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "c.py").write_text("VALUE = 1\n")
    (pkg / "b.py").write_text("from app.c import VALUE\n")
    (pkg / "a.py").write_text("from app.b import VALUE\n")
    return tmp_path


def test_direct_and_transitive(chain: Path):
    d = analyze_impact(chain, "app/c.py")
    assert d["found"]
    assert "app.b" in d["direct_importers"]          # b imports c directly
    assert set(d["transitive_importers"]) >= {"app.a", "app.b"}  # a reaches c via b
    assert d["transitive_count"] >= 2


def test_resolve_by_module_name(chain: Path):
    d = analyze_impact(chain, "app.c")
    assert d["found"] and d["target"] == "app.c"


def test_resolve_by_leaf(chain: Path):
    d = analyze_impact(chain, "c")
    assert d["found"] and d["target"] == "app.c"


def test_leaf_has_no_importers(chain: Path):
    d = analyze_impact(chain, "app/a.py")  # nothing imports a
    assert d["found"]
    assert d["direct_count"] == 0
    assert d["transitive_count"] == 0


def test_not_found_returns_suggestions(chain: Path):
    d = analyze_impact(chain, "totally.missing")
    assert d["found"] is False
    assert "suggestions" in d


def test_empty_target_is_graceful(chain: Path):
    # An empty target must not raise — the server tool turns this into guidance.
    d = analyze_impact(chain, "")
    assert d["found"] is False
