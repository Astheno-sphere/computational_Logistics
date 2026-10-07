from __future__ import annotations

import hashlib
from pathlib import Path

from agentsociety2.skills.analysis.harness.json_io import (
    load_model_from_file,
    save_model_to_file,
)
from agentsociety2.skills.analysis.harness.models import ValidationResult
from agentsociety2.skills.analysis.harness.paths import (
    hypothesis_report_review_path,
    synthesis_report_review_path,
)
from agentsociety2.skills.analysis.harness.schemas import (
    ReportQualityReview,
    ReviewVerdict,
    SynthesisQualityReview,
)
from agentsociety2.skills.analysis.harness.validators._helpers import (
    ValidationIssue,
    blocked,
    issue,
    passed,
)

MIN_PASS_SCORE = 4
MIN_DIMENSION_SCORE = 3

REPORT_DIMENSION_KEYS: tuple[str, ...] = (
    "evidence_traceability",
    "narrative_clarity",
    "limitations_honesty",
    "bilingual_parity",
    "chart_integration",
)

SYNTHESIS_DIMENSION_KEYS = (
    "cross_hypothesis_integration",
    "tension_surfaced",
    "limitations_honesty",
    "bilingual_parity",
)


def report_content_fingerprint(presentation_dir: Path) -> str:
    parts: list[bytes] = []
    for name in (
        "report_zh.md",
        "report_en.md",
        "report_zh.html",
        "report_en.html",
    ):
        path = presentation_dir / name
        if path.exists():
            parts.append(path.read_bytes())
    digest = hashlib.sha256(b"".join(parts)).hexdigest()
    return digest[:24]


def synthesis_content_fingerprint(synthesis_dir: Path) -> str:
    parts: list[bytes] = []
    for name in (
        "synthesis_report_zh.md",
        "synthesis_report_en.md",
        "synthesis_report_zh.html",
        "synthesis_report_en.html",
    ):
        path = synthesis_dir / name
        if path.exists():
            parts.append(path.read_bytes())
    return hashlib.sha256(b"".join(parts)).hexdigest()[:24]


def save_report_review(
    workspace: Path, hypothesis_id: str, review: ReportQualityReview
) -> Path:
    path = hypothesis_report_review_path(workspace, hypothesis_id)
    save_model_to_file(path, review)
    return path


def save_synthesis_review(workspace: Path, review: SynthesisQualityReview) -> Path:
    path = synthesis_report_review_path(workspace)
    save_model_to_file(path, review)
    return path


def load_report_review(
    workspace: Path, hypothesis_id: str
) -> ReportQualityReview | None:
    path = hypothesis_report_review_path(workspace, hypothesis_id)
    if not path.exists():
        return None
    return load_model_from_file(path, ReportQualityReview)


def load_synthesis_review(workspace: Path) -> SynthesisQualityReview | None:
    path = synthesis_report_review_path(workspace)
    if not path.exists():
        return None
    return load_model_from_file(path, SynthesisQualityReview)


def validate_report_review(
    workspace: Path,
    hypothesis_id: str,
    presentation_dir: Path,
) -> ValidationResult:
    issues: list[ValidationIssue] = []
    path = hypothesis_report_review_path(workspace, hypothesis_id)
    if not path.exists():
        issues.append(
            issue(
                "report_review_missing",
                phase="produce",
                message="report_review.json not found",
                fix_hint="Dispatch report-reviewer subagent, then record-report-review",
            )
        )
        return blocked(issues)

    try:
        review = load_model_from_file(path, ReportQualityReview)
    except ValueError as exc:
        issues.append(
            issue(
                "report_review_invalid",
                phase="produce",
                message=str(exc),
                fix_hint="Run `ags.py analysis payload-template --name report_review` for payload shape",
            )
        )
        return blocked(issues)

    current_fp = report_content_fingerprint(presentation_dir)
    if review.report_fingerprint != current_fp:
        issues.append(
            issue(
                "report_review_stale",
                phase="produce",
                message="Independent review is stale (reports changed after review)",
                fix_hint="Re-run report-reviewer and record-report-review",
            )
        )

    if review.verdict != ReviewVerdict.PASS:
        issues.append(
            issue(
                "report_review_not_pass",
                phase="produce",
                message=f"Reviewer verdict is {review.verdict.value}, not PASS",
                fix_hint="Address revision_instructions; re-dispatch report-producer",
            )
        )
    if review.overall_score < MIN_PASS_SCORE:
        issues.append(
            issue(
                "report_review_score_low",
                phase="produce",
                message=f"overall_score {review.overall_score} < {MIN_PASS_SCORE}",
                fix_hint="Revise reports until independent reviewer scores ≥ 4",
            )
        )
    if review.blocking_issues:
        issues.append(
            issue(
                "report_review_blocking_issues",
                phase="produce",
                message=f"{len(review.blocking_issues)} blocking issue(s) remain",
                fix_hint=(
                    review.revision_instructions[0]
                    if review.revision_instructions
                    else "Fix blocking_issues"
                ),
            )
        )
    for key in REPORT_DIMENSION_KEYS:
        score = review.dimensions.get(key)
        if score is None or score < MIN_DIMENSION_SCORE:
            issues.append(
                issue(
                    "report_review_dimension_low",
                    phase="produce",
                    message=f"Review dimension {key} missing or score < {MIN_DIMENSION_SCORE}",
                    fix_hint="Re-review after substantive report revision",
                )
            )

    if issues:
        return blocked(
            issues,
            recommended_next_step="REVISE: report-producer → report-reviewer → record-report-review",
        )
    return passed()


def validate_synthesis_review(workspace: Path, synthesis_dir: Path) -> ValidationResult:
    issues: list[ValidationIssue] = []
    path = synthesis_report_review_path(workspace)
    if not path.exists():
        issues.append(
            issue(
                "synthesis_review_missing",
                phase="synthesis",
                message="synthesis_review.json not found",
                fix_hint="Dispatch synthesis-reviewer, then record-synthesis-review",
            )
        )
        return blocked(issues)

    try:
        review = load_model_from_file(path, SynthesisQualityReview)
    except ValueError as exc:
        return blocked(
            [
                issue(
                    "synthesis_review_invalid",
                    phase="synthesis",
                    message=str(exc),
                )
            ]
        )

    current_fp = synthesis_content_fingerprint(synthesis_dir)
    if review.report_fingerprint != current_fp:
        issues.append(
            issue(
                "synthesis_review_stale",
                phase="synthesis",
                message="Synthesis review stale after report edits",
                fix_hint="Re-run synthesis-reviewer and record-synthesis-review",
            )
        )
    if review.verdict != ReviewVerdict.PASS or review.overall_score < MIN_PASS_SCORE:
        issues.append(
            issue(
                "synthesis_review_not_pass",
                phase="synthesis",
                message=f"verdict={review.verdict.value} score={review.overall_score}",
                fix_hint="Revise synthesis reports per revision_instructions",
            )
        )
    if review.blocking_issues:
        issues.append(
            issue(
                "synthesis_review_blocking",
                phase="synthesis",
                message="Blocking issues listed in synthesis_review.json",
            )
        )
    for key in SYNTHESIS_DIMENSION_KEYS:
        if review.dimensions.get(key, 0) < MIN_DIMENSION_SCORE:
            issues.append(
                issue(
                    "synthesis_review_dimension_low",
                    phase="synthesis",
                    message=f"Dimension {key} below bar",
                )
            )

    if issues:
        return blocked(issues)
    return passed()
