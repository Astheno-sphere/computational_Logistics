from __future__ import annotations

import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_research_skills_package_no_longer_exports_deleted_paper_module() -> None:
    skills = importlib.import_module("agentsociety2.skills")

    assert "paper" not in skills.__all__
    assert not hasattr(skills, "paper")
    skills_file = skills.__file__
    assert skills_file is not None
    skills_root = Path(skills_file).resolve().parent
    paper_dir = skills_root / "paper"
    py_files = list(paper_dir.rglob("*.py")) if paper_dir.is_dir() else []
    assert py_files == []


def test_workspace_launcher_no_longer_dispatches_deleted_paper_skills() -> None:
    text = (REPO_ROOT / "extension/runtime/agentsociety/bin/ags.py").read_text(
        encoding="utf-8"
    )

    assert "agentsociety-paper-orchestrator" not in text
    assert "agentsociety-paper-adapter" not in text
    assert '"paper-orchestrator"' not in text
    assert '"paper-adapter"' not in text


def test_research_workflow_docs_route_paper_work_to_external_toolkit() -> None:
    checked_files = [
        REPO_ROOT / "extension/skills/agentsociety-research-pipeline/v1.0.0/SKILL.md",
        REPO_ROOT / "extension/src/workspaceManager.ts",
        REPO_ROOT / "packages/agentsociety2/docs/skills.rst",
        REPO_ROOT / "packages/agentsociety2/docs/api/skills.rst",
    ]

    for path in checked_files:
        text = path.read_text(encoding="utf-8")
        assert "agentsociety-paper-orchestrator" not in text
        assert "agentsociety-paper-adapter" not in text
        assert "agentsociety2.skills.paper" not in text

    pipeline_text = checked_files[0].read_text(encoding="utf-8")
    assert "paper-toolkit" in pipeline_text
