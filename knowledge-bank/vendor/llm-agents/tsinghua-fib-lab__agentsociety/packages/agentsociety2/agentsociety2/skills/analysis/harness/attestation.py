from __future__ import annotations

from agentsociety2.skills.analysis.harness.models import (
    AttestationStatus,
    PhaseAttestation,
    ValidationIssue,
    ValidationResult,
)
from agentsociety2.skills.analysis.harness.validators._helpers import (
    blocked,
    issue,
    passed,
)

PHASE_RUBRIC_KEYS: dict[str, list[str]] = {
    "frame": ["research_question_confirmed", "success_criteria"],
    "explore": ["tables_inspected", "data_limitations", "eda_takeaway"],
    "claims": ["claims_user_approved", "confirmatory_vs_exploratory_clear"],
    "refine": ["charts_map_to_claims", "visual_message_clear"],
    "produce": [
        "bilingual_reports_reviewed",
        "limitations_stated",
        "independent_review_pass",
    ],
    "synthesis": [
        "scope_sources_integrated",
        "limitations_stated",
        "independent_review_pass",
    ],
}


def validate_attestation(att: PhaseAttestation) -> ValidationResult:
    issues: list[ValidationIssue] = []
    phase = att.phase.strip()
    if phase not in PHASE_RUBRIC_KEYS:
        issues.append(
            issue(
                "unknown_phase",
                phase=phase,
                message=f"Unknown attestation phase: {phase}",
                fix_hint="Use frame|explore|claims|refine|produce|synthesis",
            )
        )
        return blocked(issues)

    if att.status == AttestationStatus.BLOCKED:
        if not att.blocking_reason:
            issues.append(
                issue(
                    "blocking_reason_required",
                    phase=phase,
                    message="BLOCKED attestation requires blocking_reason",
                )
            )
        return blocked(
            issues,
            recommended_next_step=att.recommended_next_step
            or att.blocking_reason
            or "",
        )

    if not att.key_findings:
        issues.append(
            issue(
                "key_findings_required",
                phase=phase,
                message="At least one key_finding is required in phase attestation",
                fix_hint="Summarize what this phase established before advancing",
            )
        )

    for key in PHASE_RUBRIC_KEYS[phase]:
        if key not in att.rubric or att.rubric[key] in (None, "", []):
            issues.append(
                issue(
                    "rubric_field_missing",
                    phase=phase,
                    message=f"Attestation rubric missing: {key}",
                    fix_hint=f"Set rubric.{key} in record-attestation payload (LLM judgment)",
                )
            )

    if issues:
        return blocked(
            issues,
            recommended_next_step="Complete record-attestation with rubric fields filled",
        )
    return passed()
