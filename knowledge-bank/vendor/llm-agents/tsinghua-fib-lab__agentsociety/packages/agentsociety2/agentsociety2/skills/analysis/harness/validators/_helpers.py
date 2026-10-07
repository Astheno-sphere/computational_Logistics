from __future__ import annotations

import re

from agentsociety2.skills.analysis.harness.models import (
    ValidationIssue,
    ValidationResult,
)


def blocked(
    issues: list[ValidationIssue],
    *,
    recommended_next_step: str = "",
) -> ValidationResult:
    step = recommended_next_step
    if not step and issues:
        step = issues[0].fix_hint or issues[0].message
    return ValidationResult(status="BLOCKED", issues=issues, recommended_next_step=step)


def passed() -> ValidationResult:
    return ValidationResult(status="PASS", issues=[], recommended_next_step="")


def merge_results(*results: ValidationResult) -> ValidationResult:
    issues: list[ValidationIssue] = []
    for result in results:
        issues.extend(result.issues)
    if issues:
        return blocked(issues)
    return passed()


def issue(
    code: str,
    *,
    severity: str = "fatal",
    phase: str = "",
    message: str = "",
    fix_hint: str = "",
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        severity=severity,
        phase=phase,
        message=message,
        fix_hint=fix_hint,
    )


CHART_NAME_RE = re.compile(r"^chart_\d{2}_[a-z0-9_-]+\.(png|svg)$", re.IGNORECASE)
FIGURE_NAME_RE = re.compile(r"^figure_\d{2}_[a-z0-9_-]+\.(png|svg)$", re.IGNORECASE)
