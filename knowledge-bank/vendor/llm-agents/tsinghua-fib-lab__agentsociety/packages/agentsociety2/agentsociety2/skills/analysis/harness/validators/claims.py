from __future__ import annotations

from agentsociety2.skills.analysis.harness.models import (
    ClaimMode,
    ClaimsDocument,
    ValidationResult,
)
from agentsociety2.skills.analysis.harness.validators._helpers import (
    blocked,
    issue,
    passed,
)


def validate_claims(doc: ClaimsDocument) -> ValidationResult:
    issues = []
    if not doc.claims:
        issues.append(
            issue(
                "no_claims",
                phase="claims",
                message="claims.json has no entries",
                fix_hint="Use record-claim for each finding",
            )
        )
    confirmatory = [c for c in doc.claims if c.mode == ClaimMode.confirmatory]
    if not confirmatory:
        issues.append(
            issue(
                "no_confirmatory_claim",
                phase="claims",
                message="No confirmatory claims in claims.json",
            )
        )
    elif not any(c.approved for c in confirmatory):
        issues.append(
            issue(
                "no_approved_confirmatory_claim",
                phase="claims",
                message="No confirmatory claim has approved=true",
                fix_hint="Have the user approve at least one confirmatory claim before refine",
            )
        )
    for claim in doc.claims:
        if not claim.statement.strip():
            issues.append(
                issue(
                    "empty_claim_statement",
                    phase="claims",
                    message=f"Claim {claim.claim_id} has empty statement",
                )
            )
        if not claim.evidence.strip():
            issues.append(
                issue(
                    "empty_claim_evidence",
                    phase="claims",
                    message=f"Claim {claim.claim_id} has empty evidence",
                )
            )

    if issues:
        return blocked(issues, recommended_next_step="Fix claims.json structure")
    return passed()
