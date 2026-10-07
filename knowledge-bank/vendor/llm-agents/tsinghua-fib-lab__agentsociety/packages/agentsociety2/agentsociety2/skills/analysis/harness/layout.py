from __future__ import annotations

import shutil
from pathlib import Path

from agentsociety2.skills.analysis.models import DIR_HYPOTHESIS_PREFIX, DIR_PRESENTATION
from agentsociety2.skills.analysis.utils import _sanitize_id

DIR_DOT_AGENTSOCIETY = ".agentsociety"
DIR_HARNESS_WORKSPACE = "analysis"
DIR_SYNTHESIS_HARNESS = "synthesis"

FILE_STATE = "state.yaml"
FILE_PLAN = "analysis_plan.yaml"
FILE_CLAIMS = "claims.json"

HARNESS_ONLY_FILES = frozenset({FILE_STATE, FILE_PLAN, FILE_CLAIMS})

PRESENTATION_FORBIDDEN_DIRS = frozenset({"analysis", "figures", "eda"})
PRESENTATION_ALLOWED_DIRS = frozenset({"data", "charts", "assets"})


def hypothesis_presentation_dir(workspace: Path, hypothesis_id: str) -> Path:
    hid = _sanitize_id(hypothesis_id)
    return (
        Path(workspace).resolve() / DIR_PRESENTATION / f"{DIR_HYPOTHESIS_PREFIX}{hid}"
    )


def hypothesis_harness_dir(workspace: Path, hypothesis_id: str) -> Path:
    hid = _sanitize_id(hypothesis_id)
    return (
        Path(workspace).resolve()
        / DIR_DOT_AGENTSOCIETY
        / DIR_HARNESS_WORKSPACE
        / f"{DIR_HYPOTHESIS_PREFIX}{hid}"
    )


def synthesis_harness_dir(workspace: Path) -> Path:
    return (
        Path(workspace).resolve()
        / DIR_DOT_AGENTSOCIETY
        / DIR_HARNESS_WORKSPACE
        / DIR_SYNTHESIS_HARNESS
    )


def legacy_hypothesis_harness_dir(workspace: Path, hypothesis_id: str) -> Path:
    return hypothesis_presentation_dir(workspace, hypothesis_id) / "analysis"


def migrate_legacy_hypothesis_harness(workspace: Path, hypothesis_id: str) -> list[str]:
    old = legacy_hypothesis_harness_dir(workspace, hypothesis_id)
    new = hypothesis_harness_dir(workspace, hypothesis_id)
    if not old.is_dir():
        return []
    new.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []
    for name in HARNESS_ONLY_FILES:
        src = old / name
        if not src.is_file():
            continue
        dest = new / name
        if dest.exists():
            continue
        shutil.move(str(src), str(dest))
        moved.append(name)
    return moved


def list_presentation_layout_issues(presentation_dir: Path) -> list[str]:
    issues: list[str] = []
    if not presentation_dir.is_dir():
        return issues
    for name in PRESENTATION_FORBIDDEN_DIRS:
        path = presentation_dir / name
        if path.exists():
            issues.append(
                f"Remove presentation/{presentation_dir.name}/{name}/ — "
                f"use data/ (EDA), charts/ (plots), and .agentsociety/analysis/ (harness state)"
            )
    legacy = presentation_dir / "analysis"
    if legacy.is_dir():
        if any((legacy / f).exists() for f in HARNESS_ONLY_FILES):
            issues.append(
                f"Move harness files from {legacy} to "
                f".agentsociety/analysis/{presentation_dir.name}/ (run analysis intake)"
            )
        for report in legacy.glob("report_*.*"):
            if report.suffix in {".md", ".html"}:
                issues.append(
                    f"Move {report.name} from {legacy} to {presentation_dir}/ (hypothesis root)"
                )
    return issues
