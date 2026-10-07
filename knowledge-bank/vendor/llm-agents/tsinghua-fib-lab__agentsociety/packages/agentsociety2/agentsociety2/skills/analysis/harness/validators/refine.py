from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from agentsociety2.skills.analysis.harness.validators._helpers import (
    ValidationResult,
    blocked,
    issue,
    passed,
)

if TYPE_CHECKING:
    from agentsociety2.skills.analysis.harness.models import HypothesisAnalysisState


def validate_refine(
    state: HypothesisAnalysisState,
    workspace: Path,
    hypothesis_id: str,
) -> ValidationResult:
    """Holistic refine gate: contracts and chart outputs on disk."""
    issues = []
    pres = workspace / "presentation" / f"hypothesis_{hypothesis_id}"
    assets = pres / "assets"
    charts_dir = pres / "charts"

    if not state.figure_contracts:
        issues.append(
            issue(
                "refine_no_contracts",
                phase="refine",
                message="No figure contracts recorded",
                fix_hint="Record a figure contract for each report-facing chart or figure",
            )
        )

    if state.chart_count < 1:
        issues.append(
            issue(
                "refine_no_validated_charts",
                phase="refine",
                message="No validated chart or figure files recorded",
                fix_hint="Run validate-chart --chart-path for each contract output",
            )
        )

    for contract in state.figure_contracts:
        if not contract.output_files:
            issues.append(
                issue(
                    "refine_contract_empty_outputs",
                    phase="refine",
                    message=f"Contract {contract.contract_id} has no output_files",
                    fix_hint="Set output_files to generated chart/figure paths",
                )
            )
            continue
        for rel in contract.output_files:
            candidates = [
                pres / rel,
                assets / Path(rel).name,
                charts_dir / Path(rel).name,
                Path(rel),
            ]
            if not any(p.exists() and p.is_file() for p in candidates):
                issues.append(
                    issue(
                        "refine_output_missing",
                        phase="refine",
                        message=f"Missing output for {contract.contract_id}: {rel}",
                        fix_hint="Generate chart then validate-chart --chart-path",
                    )
                )

    if issues:
        return blocked(issues)
    return passed()
