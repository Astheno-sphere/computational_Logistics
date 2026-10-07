from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

from agentsociety2.skills.analysis.harness.json_io import load_model_from_file
from agentsociety2.skills.analysis.harness.models import ClaimMode, ValidationResult
from agentsociety2.skills.analysis.harness.schemas import AnalysisSummary
from agentsociety2.skills.analysis.harness.state import load_claims
from agentsociety2.skills.analysis.harness.validators._helpers import (
    blocked,
    issue,
    passed,
)

MIN_REPORT_WORDS = 25
MIN_LIMITATIONS_CHARS = 8
MIN_SECTION_HEADERS = 3
MIN_KEY_FINDING_CHARS = 12

FLUFF_PATTERNS = (
    re.compile(r"有趣的模式|interesting patterns?", re.IGNORECASE),
    re.compile(r"结果(表明|显示).{0,12}(显著|明显)(?!.*\d)", re.IGNORECASE),
    re.compile(r"further research is needed", re.IGNORECASE),
    re.compile(r"呈现出(一定|较为)?(的)?(多样|复杂|丰富)", re.IGNORECASE),
)

FIGURE_LINE_RE = re.compile(r"!\[[^\]]*\]\(assets/([^)]+)\)")
SECTION_RE = re.compile(r"^##\s+.+", re.MULTILINE)
MARKDOWN_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
MARKDOWN_TABLE_SEPARATOR_RE = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$",
    re.MULTILINE,
)
EMPTY_EDA_MESSAGES = (
    "暂无交互式 EDA。请运行 run-eda --type bundle。",
    "No interactive EDA yet. Run run-eda --type bundle.",
)


class _ReportHTMLAuditParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.id_counts: dict[str, int] = {}
        self.data_section_found = False
        self.data_section_depth = 0
        self.data_text: list[str] = []
        self.data_table_count = 0
        self._ignored_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = {name.lower(): value for name, value in attrs}
        element_id = attributes.get("id")
        if element_id:
            self.id_counts[element_id] = self.id_counts.get(element_id, 0) + 1

        normalized_tag = tag.lower()
        if normalized_tag == "section":
            if self.data_section_depth:
                self.data_section_depth += 1
            elif (element_id or "").lower() == "data":
                self.data_section_found = True
                self.data_section_depth = 1
        if not self.data_section_depth:
            return
        if normalized_tag in {"script", "style"}:
            self._ignored_depth += 1
        elif normalized_tag == "table" and not self._ignored_depth:
            self.data_table_count += 1

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if self.data_section_depth and normalized_tag in {"script", "style"}:
            self._ignored_depth = max(0, self._ignored_depth - 1)
        if self.data_section_depth and normalized_tag == "section":
            self.data_section_depth -= 1
            if not self.data_section_depth:
                self._ignored_depth = 0

    def handle_data(self, data: str) -> None:
        if self.data_section_depth and not self._ignored_depth:
            self.data_text.append(data)


def _audit_html(text: str) -> _ReportHTMLAuditParser:
    parser = _ReportHTMLAuditParser()
    parser.feed(text)
    parser.close()
    return parser


def _word_count(text: str) -> int:
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", text)
    return len(tokens)


def _figure_refs(text: str) -> list[str]:
    return FIGURE_LINE_RE.findall(text)


def _caption_lines_after_figures(text: str) -> list[bool]:
    lines = text.splitlines()
    ok: list[bool] = []
    for i, line in enumerate(lines):
        if FIGURE_LINE_RE.search(line):
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            ok.append(len(next_line) >= 4 and not FIGURE_LINE_RE.search(next_line))
    return ok


def _duplicate_html_ids(text: str) -> list[str]:
    audit = _audit_html(text)
    return sorted(
        element_id for element_id, count in audit.id_counts.items() if count > 1
    )


def _markdown_data_section(text: str) -> str:
    headings = list(MARKDOWN_HEADING_RE.finditer(text))
    for index, heading in enumerate(headings):
        title = re.sub(r"^\d+(?:\.\d+)*[.)]?\s*", "", heading.group(1)).lower()
        if "data" not in title and "数据" not in title:
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        return text[heading.end() : end].strip()
    return ""


def _data_parity_issues(markdown: str, report_html: str) -> tuple[str, ...]:
    markdown_data = _markdown_data_section(markdown)
    if len(re.sub(r"\W+", "", markdown_data)) < 40:
        return ()

    audit = _audit_html(report_html)
    if not audit.data_section_found:
        return ("missing_html_data_section",)

    parity_issues: list[str] = []
    if MARKDOWN_TABLE_SEPARATOR_RE.search(markdown_data) and not audit.data_table_count:
        parity_issues.append("markdown_data_table_missing_from_html")

    plain_html_data = re.sub(r"\s+", " ", " ".join(audit.data_text)).strip()
    for message in EMPTY_EDA_MESSAGES:
        plain_html_data = plain_html_data.replace(message, "")
    plain_html_data = re.sub(
        r"^(?:数据与探索|Data exploration|Interactive exploration|交互式探索)\s*",
        "",
        plain_html_data,
        flags=re.IGNORECASE,
    )
    if len(re.sub(r"\W+", "", plain_html_data)) < 24:
        parity_issues.append("html_data_section_contains_only_eda_empty_state")
    return tuple(parity_issues)


def validate_report_quality(
    presentation_dir: Path,
    *,
    workspace: Path | None = None,
    hypothesis_id: str | None = None,
) -> ValidationResult:
    issues: list = []
    report_zh = presentation_dir / "report_zh.md"
    report_en = presentation_dir / "report_en.md"
    html_zh = presentation_dir / "report_zh.html"
    html_en = presentation_dir / "report_en.html"
    summary_path = presentation_dir / "data" / "analysis_summary.json"

    missing = [
        label
        for path, label in (
            (report_zh, "report_zh.md"),
            (report_en, "report_en.md"),
            (html_zh, "report_zh.html"),
            (html_en, "report_en.html"),
        )
        if not path.exists() or not path.read_text(encoding="utf-8").strip()
    ]
    if missing:
        issues.append(
            issue(
                "report_quality_missing_files",
                phase="produce",
                message=f"Bilingual MD + HTML required before quality check: {', '.join(missing)}",
                fix_hint="Write all four report files; run `ags.py analysis guidance --topic reports`",
            )
        )
        return blocked(issues)

    zh_text = report_zh.read_text(encoding="utf-8")
    en_text = report_en.read_text(encoding="utf-8")
    zh_html_text = html_zh.read_text(encoding="utf-8")
    en_html_text = html_en.read_text(encoding="utf-8")

    for path, text, label in (
        (report_zh, zh_text, "report_zh.md"),
        (report_en, en_text, "report_en.md"),
    ):
        wc = _word_count(text)
        if wc < MIN_REPORT_WORDS:
            issues.append(
                issue(
                    "report_too_short",
                    phase="produce",
                    message=f"{label} has only ~{wc} words (minimum {MIN_REPORT_WORDS})",
                    fix_hint="Expand claim-backed narrative sections with metrics, evidence, and caveats",
                )
            )
        if len(SECTION_RE.findall(text)) < MIN_SECTION_HEADERS:
            issues.append(
                issue(
                    "report_sections_sparse",
                    phase="produce",
                    message=f"{label} needs at least {MIN_SECTION_HEADERS} `##` sections",
                    fix_hint="Use overview, data, findings, conclusions structure",
                )
            )
        for pat in FLUFF_PATTERNS:
            if pat.search(text):
                issues.append(
                    issue(
                        "report_fluff_phrase",
                        phase="produce",
                        message=f"{label} contains generic filler matching {pat.pattern!r}",
                        fix_hint="Replace with specific metrics, tables, or claim-backed statements",
                    )
                )
        captions = _caption_lines_after_figures(text)
        if captions and not all(captions):
            issues.append(
                issue(
                    "figure_caption_missing",
                    phase="produce",
                    message=f"{label}: every `![](assets/...)` needs a one-line caption below",
                    fix_hint="Add a concise caption directly below each figure embed",
                )
            )

    for markdown, report_html, label in (
        (zh_text, zh_html_text, "report_zh.html"),
        (en_text, en_html_text, "report_en.html"),
    ):
        duplicate_ids = _duplicate_html_ids(report_html)
        if duplicate_ids:
            issues.append(
                issue(
                    "report_html_duplicate_ids",
                    phase="produce",
                    message=f"{label} contains duplicate HTML id(s): {', '.join(duplicate_ids)}",
                    fix_hint="Keep one authoritative section id and use id-free child fragments for embedded EDA",
                )
            )
        parity_issues = _data_parity_issues(markdown, report_html)
        if parity_issues:
            issues.append(
                issue(
                    "report_data_section_parity",
                    phase="produce",
                    message=f"{label} does not preserve its Markdown data section: {', '.join(parity_issues)}",
                    fix_hint="Regenerate the HTML data section from the Markdown, then embed EDA only inside the child markers",
                )
            )

    zh_figs = set(_figure_refs(zh_text))
    en_figs = set(_figure_refs(en_text))
    if zh_figs != en_figs:
        issues.append(
            issue(
                "bilingual_figure_mismatch",
                phase="produce",
                message="Chinese and English reports reference different asset sets",
                fix_hint="Mirror figure embeds across report_zh.md and report_en.md",
            )
        )

    if summary_path.exists():
        try:
            summary = load_model_from_file(summary_path, AnalysisSummary)
            if len((summary.limitations or "").strip()) < MIN_LIMITATIONS_CHARS:
                issues.append(
                    issue(
                        "limitations_too_short",
                        phase="produce",
                        message="analysis_summary.json limitations field is empty or trivial",
                        fix_hint="State simulation external-validity caveats explicitly",
                    )
                )
            weak = [
                f
                for f in summary.key_findings
                if len(str(f).strip()) < MIN_KEY_FINDING_CHARS
            ]
            if not summary.key_findings or weak:
                issues.append(
                    issue(
                        "key_findings_weak",
                        phase="produce",
                        message="analysis_summary.json key_findings must be substantive bullets",
                        fix_hint="Each finding should be a testable sentence with evidence",
                    )
                )
        except ValueError as exc:
            issues.append(
                issue(
                    "analysis_summary_invalid",
                    phase="produce",
                    message=str(exc),
                )
            )

    if workspace and hypothesis_id:
        claims_doc = load_claims(workspace, hypothesis_id)
        confirmatory = [
            c for c in claims_doc.claims if c.mode == ClaimMode.confirmatory
        ]
        for claim in confirmatory[:8]:
            needle = (claim.statement or claim.claim_id or "").strip()
            if needle and needle[:12] not in zh_text and claim.claim_id not in zh_text:
                issues.append(
                    issue(
                        "confirmatory_claim_not_in_report",
                        phase="produce",
                        message=f"Confirmatory claim not reflected in report_zh.md: {claim.claim_id or needle[:40]}",
                        fix_hint="Add a findings subsection per claim; see claims.json",
                    )
                )

    if issues:
        return blocked(
            issues,
            recommended_next_step="Revise reports with report-producer, then re-run validate-report-quality",
        )
    return passed()
