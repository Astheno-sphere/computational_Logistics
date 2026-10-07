from __future__ import annotations

from pathlib import Path

from agentsociety2.skills.analysis.harness.models import AnalysisPlan, ValidationResult
from agentsociety2.skills.analysis.harness.validators._helpers import (
    blocked,
    issue,
    passed,
)


def validate_plan(
    plan: AnalysisPlan, *, plan_path: Path | None = None
) -> ValidationResult:

    issues = []
    if not plan.research_question.strip():
        issues.append(
            issue(
                "missing_research_question",
                phase="frame",
                message="analysis_plan.research_question is empty",
                fix_hint="Set research_question in analysis_plan.yaml via write-plan",
            )
        )
    if not plan.primary_metrics:
        issues.append(
            issue(
                "missing_primary_metrics",
                phase="frame",
                message="analysis_plan.primary_metrics is empty",
                fix_hint="Add at least one primary metric to analysis_plan.yaml",
            )
        )
    if not plan.target_tables:
        issues.append(
            issue(
                "missing_target_tables",
                phase="frame",
                message="analysis_plan.target_tables is empty",
                fix_hint="List tables to analyze in analysis_plan.yaml",
            )
        )
    if not plan.confirmatory_claims:
        issues.append(
            issue(
                "missing_confirmatory_claims",
                phase="frame",
                message="analysis_plan.confirmatory_claims is empty",
                fix_hint="Add planned confirmatory claims before exploration",
            )
        )
    if plan_path is not None and not plan_path.exists():
        issues.append(
            issue(
                "plan_file_missing",
                phase="frame",
                message=f"analysis plan file not found: {plan_path}",
                fix_hint="Run write-plan to create analysis_plan.yaml",
            )
        )
    if issues:
        return blocked(issues, recommended_next_step="Run write-plan and validate-plan")
    return passed()
