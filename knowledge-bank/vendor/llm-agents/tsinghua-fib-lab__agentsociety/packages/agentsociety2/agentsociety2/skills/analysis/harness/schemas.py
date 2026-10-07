from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ArtifactManifestEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    filename: str
    type: str = ""
    description: str = ""
    finding_number: int | None = None
    included_in_report: bool = True


class ArtifactManifest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hypothesis_id: str = ""
    generated_at: str = ""
    artifacts: list[ArtifactManifestEntry] = Field(default_factory=list)


class ReportOutlineSection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    title: str = ""


class ReportOutlineFigure(BaseModel):
    model_config = ConfigDict(extra="ignore")

    asset: str
    caption: str = ""
    finding_number: int | None = None


class ReportOutline(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hypothesis_id: str = ""
    sections: list[ReportOutlineSection] = Field(default_factory=list)
    figures: list[ReportOutlineFigure] = Field(default_factory=list)


class AnalysisSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str = ""
    key_findings: list[str] = Field(default_factory=list)
    limitations: str = ""
    evidence_index_path: str = "data/evidence_index.json"


EvidenceKind = Literal[
    "eda",
    "sql",
    "chart",
    "figure",
    "contract",
    "claim",
    "summary",
    "other",
]


class EvidenceSource(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: str
    kind: EvidenceKind = "other"
    phase: str = ""
    report_section: str = ""
    label: str = ""
    excerpt: str = ""


class EvidenceIndex(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hypothesis_id: str = ""
    generated_at: str = ""
    sources: list[EvidenceSource] = Field(default_factory=list)
    section_map: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "overview": [],
            "data": [],
            "findings": [],
            "conclusions": [],
            "appendix": [],
        }
    )


class SynthesisBrief(BaseModel):
    model_config = ConfigDict(extra="ignore")

    synthesis_question: str = ""
    scope_hypothesis_ids: list[str] = Field(default_factory=list)
    source_artifacts: list[str] = Field(default_factory=list)
    comparison_mode: Literal["integrative", "cross_hypothesis"] = "integrative"


REPORT_SECTION_IDS = frozenset(
    {"overview", "data", "findings", "conclusions", "appendix"}
)


class ReviewVerdict(str, Enum):
    PASS = "PASS"
    REVISE = "REVISE"
    FAIL = "FAIL"


class ReportQualityReview(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hypothesis_id: str = ""
    reviewer_role: Literal["independent"] = "independent"
    verdict: ReviewVerdict = ReviewVerdict.REVISE
    overall_score: int = Field(ge=1, le=5, default=1)
    dimensions: dict[str, int] = Field(default_factory=dict)
    blocking_issues: list[str] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)
    report_fingerprint: str = ""
    reviewed_artifact_paths: list[str] = Field(default_factory=list)
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SynthesisQualityReview(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reviewer_role: Literal["independent"] = "independent"
    verdict: ReviewVerdict = ReviewVerdict.REVISE
    overall_score: int = Field(ge=1, le=5, default=1)
    dimensions: dict[str, int] = Field(default_factory=dict)
    blocking_issues: list[str] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)
    report_fingerprint: str = ""
    scope_hypothesis_ids: list[str] = Field(default_factory=list)
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
