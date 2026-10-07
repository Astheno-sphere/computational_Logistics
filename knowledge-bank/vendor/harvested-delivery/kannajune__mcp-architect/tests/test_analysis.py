"""Tests for the pure analysis layer (no MCP dependency required)."""
from pathlib import Path

import pytest

from mcp_architect.analysis import (
    explain_module,
    find_hotspots,
    get_dependency_graph,
    get_overview,
)


@pytest.fixture
def sample(tmp_path: Path) -> Path:
    """A tiny multi-file Python project with a deliberate import + a cycle."""
    pkg = tmp_path / "app"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "core.py").write_text(
        "import os\n\n"
        "class Engine:\n"
        "    def run(self, x):\n"
        "        if x:\n"
        "            return 1\n"
        "        for i in range(x):\n"
        "            pass\n"
        "        return 0\n"
    )
    (pkg / "api.py").write_text(
        "from app.core import Engine\n\n"
        "def handler():\n"
        "    return Engine().run(1)\n"
    )
    (tmp_path / "main.py").write_text("from app.api import handler\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="x"\ndependencies=["fastapi"]\n'
    )
    return tmp_path


def test_overview_detects_language_and_framework(sample: Path):
    ov = get_overview(sample)
    assert ov["total_files"] >= 4
    langs = {l["language"] for l in ov["languages"]}
    assert "Python" in langs
    assert "FastAPI" in ov["frameworks"]
    assert "main.py" in ov["entry_points"]


def test_dependency_graph_finds_internal_edges(sample: Path):
    dg = get_dependency_graph(sample, "python")
    assert dg["modules"] >= 3
    assert dg["edges"] >= 2
    hubs = {h["module"] for h in dg["most_depended_upon"]}
    assert any("core" in h for h in hubs)


def test_hotspots_returns_largest(sample: Path):
    hs = find_hotspots(sample, top=5)
    assert hs["files_analyzed"] >= 3
    assert hs["largest"]
    assert hs["largest"][0]["loc"] > 0


def test_explain_module(sample: Path):
    em = explain_module(sample, "app")
    assert em["files"] >= 2
    classes = {c for f in em["file_details"] for c in f["classes"]}
    assert "Engine" in classes


def test_explain_missing_path(sample: Path):
    assert "error" in explain_module(sample, "does/not/exist")
