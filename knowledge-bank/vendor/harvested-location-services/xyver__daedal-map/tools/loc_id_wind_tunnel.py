from __future__ import annotations

import argparse
from collections import Counter
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mapmover.runtime.loc_id_identity_doctrine import (
    DOCTRINE_PROFILES,
    compare_doctrine_cases,
    compare_doctrine_rules,
    corpus_audit,
    doctrine_manifest,
    doctrine_decisions,
    doctrine_scorecard,
    evaluate_designation_cases,
    evaluate_stewardship_cases,
    evaluate_dual_mode_cases,
    evaluate_identity_cases,
    registry_audit,
    stewardship_ablation_report,
)

DEFAULT_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "loc_id_wind_tunnel_samples.json"


def _load_cases(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    return payload


def _md(value: Any) -> str:
    return str(value if value is not None else "-").replace("|", "\\|").replace("\r", " ").replace("\n", "<br>")


def _render_policy_rules(doctrine: str) -> list[str]:
    manifest = doctrine_manifest(doctrine)
    lines = [
        f"Doctrine: `{doctrine}` — {_md(manifest['description'])}",
        "",
        f"Doctrine fingerprint: `{manifest['fingerprint']}`",
        "",
        "| Executable rule | Value |",
        "|---|---|",
    ]
    for key, value in manifest["rules"].items():
        lines.append(f"| {_md(key)} | {_md(value)} |")
    lines.extend(["", "| Harness contract | Value |", "|---|---|"])
    for key, value in manifest["harness_contract"].items():
        lines.append(f"| {_md(key)} | {_md(value)} |")
    complexity = manifest["complexity"]
    lines.extend(
        [
            "",
            "Complexity: "
            f"{complexity['policy_rule_count']} policy rules; "
            f"{complexity['nonbaseline_policy_rule_count']} nonbaseline rules; "
            f"{complexity['enabled_designation_capability_count']} enabled designation capabilities; "
            f"{complexity['enabled_stewardship_capability_count']} enabled stewardship capabilities; "
            f"{complexity['namespace_rule_count']} namespace rules; "
            f"~{complexity['regex_alternative_terms_estimate']} regex alternatives; "
            f"{complexity['pattern_characters']} pattern characters.",
            "",
        ]
    )
    return lines


def _render_markdown(results: list[dict[str, Any]], doctrine: str) -> str:
    lines = [
        "# loc_id Wind Tunnel Report",
        "",
        *_render_policy_rules(doctrine),
        "| Signal | Case | System | Role | Scope | Level | Placement | Issues | Design questions |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        issues = "<br>".join(_md(value) for value in result.get("issues") or []) or "-"
        questions = "<br>".join(_md(value) for value in result.get("design_questions") or []) or "-"
        lines.append(
            "| {signal} | {case} | {system} | {role} | {scope} | {level} | {placement} | {issues} | {questions} |".format(
                signal=_md(result.get("signal")),
                case=_md(result.get("case")),
                system=_md(result.get("source_system")),
                role=_md(result.get("role")),
                scope=_md(result.get("first_segment_scope")),
                level=_md(result.get("reference_level")),
                placement=_md(result.get("placement_semantics")),
                issues=issues,
                questions=questions,
            )
        )
    return "\n".join(lines) + "\n"


def _render_dual_markdown(results: list[dict[str, Any]], doctrine: str) -> str:
    lines = [
        "# loc_id Wind Tunnel Raw/Declared Report",
        "",
        *_render_policy_rules(doctrine),
        "Raw results are unscored unless a case supplies `oracle.raw`.",
        "",
        "| Signal | Case | System | Declared | Raw | Deltas |",
        "|---|---|---|---|---|---|",
    ]
    for result in results:
        declared = result.get("declared") or {}
        raw = result.get("raw") or {}
        deltas = "<br>".join(_md(value) for value in result.get("deltas") or []) or "-"
        lines.append(
            "| {signal} | {case} | {system} | {declared_role}/{declared_scope}/{declared_level}/{declared_placement} | {raw_role}/{raw_scope}/{raw_level}/{raw_placement} | {deltas} |".format(
                signal=result.get("signal"),
                case=result.get("case"),
                system=result.get("source_system") or "-",
                declared_role=declared.get("role"),
                declared_scope=declared.get("first_segment_scope"),
                declared_level=declared.get("reference_level") or "-",
                declared_placement=declared.get("placement_semantics") or "-",
                raw_role=raw.get("role"),
                raw_scope=raw.get("first_segment_scope"),
                raw_level=raw.get("reference_level") or "-",
                raw_placement=raw.get("placement_semantics") or "-",
                deltas=deltas,
            )
        )
    return "\n".join(lines) + "\n"


def _render_designation_markdown(results: list[dict[str, Any]], doctrine: str) -> str:
    lines = [
        "# loc_id Wind Tunnel Designation Report",
        "",
        *_render_policy_rules(doctrine),
        "Designation assertions test doctrine capabilities against independent program evidence.",
        "",
        "| Signal | Case | System | Assertions | Passed | Missing capabilities |",
        "|---|---|---|---:|---:|---|",
    ]
    for result in results:
        lines.append(
            "| {signal} | {case} | {system} | {assertions} | {passed} | {failed} |".format(
                signal=_md(result["signal"]),
                case=_md(result["case"]),
                system=_md(result.get("source_system")),
                assertions=result["oracle_assertions"],
                passed=result["oracle_assertions_passed"],
                failed=_md(", ".join(result["failed_capabilities"]) or "none"),
            )
        )
    return "\n".join(lines) + "\n"


def _render_stewardship_markdown(results: list[dict[str, Any]], doctrine: str) -> str:
    lines = [
        "# loc_id Wind Tunnel Stewardship Report",
        "",
        *_render_policy_rules(doctrine),
        "Stewardship assertions test durability, provenance, and reproducibility against independent evidence.",
        "",
        "| Signal | Case | System | Assertions | Passed | Missing capabilities |",
        "|---|---|---|---:|---:|---|",
    ]
    for result in results:
        lines.append(
            "| {signal} | {case} | {system} | {assertions} | {passed} | {failed} |".format(
                signal=_md(result["signal"]),
                case=_md(result["case"]),
                system=_md(result.get("source_system")),
                assertions=result["oracle_assertions"],
                passed=result["oracle_assertions_passed"],
                failed=_md(", ".join(result["failed_capabilities"]) or "none"),
            )
        )
    return "\n".join(lines) + "\n"


def _render_ablation_markdown(cases: list[dict[str, Any]], doctrine: str) -> str:
    report = stewardship_ablation_report(cases, doctrine=doctrine)
    baseline = report["baseline"]
    lines = [
        "# loc_id Wind Tunnel Stewardship Ablation",
        "",
        f"Doctrine: `{doctrine}`",
        "",
        f"Doctrine fingerprint: `{report['doctrine_fingerprint']}`",
        "",
        f"Oracle fingerprint: `{report['oracle_fingerprint']}`",
        "",
        f"Baseline: {baseline['oracle_assertions_passed']}/{baseline['oracle_assertions']} assertions across {baseline['case_count']} cases.",
        "",
        f"Every stewardship rule has observed contribution: {report['all_rules_have_observed_contribution']}",
        "",
        "Capabilities with fewer than two supporting cases: "
        + (
            ", ".join(report["capabilities_below_two_supporting_cases"])
            or "none"
        ),
        "",
        "Evidence concentration: "
        + "; ".join(
            f"{case}={count}" for case, count in report["case_concentration"].items()
        ),
        "",
        "| Capability disabled | Executable rule | Assertion loss | Failing cases | Cases |",
        "|---|---|---:|---:|---|",
    ]
    for mutation in report["mutations"]:
        cases_text = ", ".join(
            str(failure["case"]) for failure in mutation["failure_cases"]
        ) or "none"
        lines.append(
            "| {capability} | {rule} | {loss} | {case_count} | {cases} |".format(
                capability=_md(mutation["capability"]),
                rule=_md(mutation["rule"]),
                loss=mutation["assertion_loss"],
                case_count=mutation["failure_case_count"],
                cases=_md(cases_text),
            )
        )
    return "\n".join(lines) + "\n"


def _render_compare_markdown(results: list[dict[str, Any]], left: str, right: str) -> str:
    rule_differences = compare_doctrine_rules(left, right)
    left_manifest = doctrine_manifest(left)
    right_manifest = doctrine_manifest(right)
    lines = [
        "# loc_id Wind Tunnel Doctrine Comparison",
        "",
        f"Comparing `{left}` to `{right}`.",
        "",
        f"Rule fingerprints: `{left_manifest['fingerprint'][:12]}` to `{right_manifest['fingerprint'][:12]}`.",
        "",
        "## Executable rule differences",
        "",
        "| Kind | Rule | Left | Right |",
        "|---|---|---|---|",
    ]
    for difference in rule_differences:
        lines.append(
            f"| {_md(difference['kind'])} | {_md(difference['rule'])} | "
            f"{_md(difference['left'])} | {_md(difference['right'])} |"
        )
    if not rule_differences:
        lines.append("| - | No executable differences | - | - |")
    lines.extend(
        [
        "",
        "## Case output differences",
        "",
        "| Signal | Case | System | Deltas |",
        "|---|---|---|---|",
        ]
    )
    for result in results:
        deltas = "<br>".join(_md(value) for value in result.get("deltas") or []) or "-"
        lines.append(
            "| {signal} | {case} | {system} | {deltas} |".format(
                signal=result.get("signal"),
                case=result.get("case"),
                system=result.get("source_system") or "-",
                deltas=deltas,
            )
        )
    return "\n".join(lines) + "\n"


def _render_matrix_markdown(cases: list[dict[str, Any]]) -> str:
    doctrines = tuple(DOCTRINE_PROFILES)
    corpus = corpus_audit(cases)
    lines = [
        "# loc_id Wind Tunnel Doctrine Matrix",
        "",
        f"Shared fixture cases: {len(cases)}",
        "",
        f"Shared oracle fingerprint: `{corpus['oracle_fingerprint']}`",
        "",
        "Doctrine-specific expected answers are excluded. Raw cases are unscored until they declare `oracle.raw`.",
        "",
        "| Doctrine | Rule ID | Declared assertions | Passed | Accuracy | Clean scored cases | Known issue cases | Unexpected cases | Open-policy cases | Designation assertions | Passed | Accuracy | Active designation capabilities | Stewardship assertions | Passed | Accuracy | Active stewardship capabilities | Raw scored | Raw deltas | Overlaps | Specific collisions | Namespace rules | Regex terms |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for doctrine in doctrines:
        score = doctrine_scorecard(cases, doctrine=doctrine)
        declared = score["declared"]
        raw = score["raw"]
        designation = score["designation"]
        stewardship = score["stewardship"]
        complexity = score["complexity"]
        lines.append(
            "| {doctrine} | `{rule_id}` | {assertions} | {passed} | {accuracy} | {clean} | {known} | {unexpected} | {open_policy} | {designation_assertions} | {designation_passed} | {designation_accuracy} | {designation_capabilities} | {stewardship_assertions} | {stewardship_passed} | {stewardship_accuracy} | {stewardship_capabilities} | {raw_scored} | {raw_deltas} | {overlaps} | {specific_collisions} | {namespace_rules} | {regex_terms} |".format(
                doctrine=doctrine,
                rule_id=score["doctrine_fingerprint"][:12],
                assertions=declared["oracle_assertions"],
                passed=declared["oracle_assertions_passed"],
                accuracy=declared["assertion_accuracy"],
                clean=declared["clean_scored_cases"],
                known=declared["known_issue_cases"],
                unexpected=declared["unexpected_issue_cases"],
                open_policy=declared["open_policy_case_count"],
                designation_assertions=designation["oracle_assertions"],
                designation_passed=designation["oracle_assertions_passed"],
                designation_accuracy=designation["assertion_accuracy"],
                designation_capabilities=complexity["enabled_designation_capability_count"],
                stewardship_assertions=stewardship["oracle_assertions"],
                stewardship_passed=stewardship["oracle_assertions_passed"],
                stewardship_accuracy=stewardship["assertion_accuracy"],
                stewardship_capabilities=complexity["enabled_stewardship_capability_count"],
                raw_scored=raw["scored_cases"],
                raw_deltas=raw["declared_delta_cases"],
                overlaps=score["registry"]["overlap_count"],
                specific_collisions=score["registry"]["specific_collision_count"],
                namespace_rules=complexity["namespace_rule_count"],
                regex_terms=complexity["regex_alternative_terms_estimate"],
            )
        )

    lines.extend(
        [
            "",
            "| Left | Right | Same output | Doctrine delta | Oracle failure | Rule differences |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for left, right in zip(doctrines, doctrines[1:]):
        compared = compare_doctrine_cases(cases, left=left, right=right)
        counts = Counter(str(result.get("signal")) for result in compared)
        lines.append(
                "| {left} | {right} | {passed} | {delta} | {failure} | {rule_differences} |".format(
                left=left,
                right=right,
                passed=counts.get("pass", 0),
                delta=counts.get("doctrine_delta", 0),
                    failure=counts.get("oracle_failure", 0),
                    rule_differences=len(compare_doctrine_rules(left, right)),
                )
        )
    return "\n".join(lines) + "\n"


def _render_rules_markdown(doctrine: str) -> str:
    manifest = doctrine_manifest(doctrine)
    lines = ["# loc_id Doctrine Rules", "", *_render_policy_rules(doctrine)]
    lines.extend(
        [
            "| Order | Rule ID | Pattern | Role | Family | Scope | Public promise | Admin fallback |",
            "|---:|---|---|---|---|---|---|---|",
        ]
    )
    for entry in manifest["registry"]:
        lines.append(
            "| {order} | {rule_id} | `{pattern}` | {role} | {family} | {scope} | {promise} | {fallback} |".format(
                order=entry["order"],
                rule_id=_md(entry["rule_id"]),
                pattern=_md(entry["pattern"]),
                role=_md(entry.get("identity_role")),
                family=_md(entry.get("family_id")),
                scope=_md(entry.get("scope_type")),
                promise=_md(entry.get("public_promise")),
                fallback=_md(entry.get("is_admin_fallback")),
            )
        )
    return "\n".join(lines) + "\n"


def _render_audit_markdown(cases: list[dict[str, Any]], doctrine: str) -> str:
    audit = registry_audit(cases, doctrine=doctrine)
    corpus = corpus_audit(cases)
    oracle = corpus["oracle_coverage"]
    lines = [
        "# loc_id Registry Audit",
        "",
        *_render_policy_rules(doctrine),
        "## Corpus and oracle audit",
        "",
        f"Corpus valid: {corpus['valid']}",
        "",
        f"Oracle fingerprint: `{corpus['oracle_fingerprint']}`",
        "",
        f"Explicit declared oracles: {oracle['explicit_declared_cases']}; "
        f"explicit raw oracles: {oracle['explicit_raw_cases']}; "
        f"explicit designation oracles: {oracle['explicit_designation_cases']}; "
        f"explicit stewardship oracles: {oracle['explicit_stewardship_cases']}; "
        f"declared scored cases: {oracle['declared_scored_cases']}; "
        f"raw scored cases: {oracle['raw_scored_cases']}; "
        f"designation scored cases: {oracle['designation_scored_cases']}; "
        f"stewardship scored cases: {oracle['stewardship_scored_cases']}.",
        "",
        f"Legacy doctrine-specific expectation cases excluded from scoring: {corpus['legacy_doctrine_override_case_count']}",
        "",
        "## Registry audit",
        "",
        f"Recognized: {audit['recognized_cases']}/{audit['case_count']}",
        "",
        f"Overlapping cases: {audit['overlap_count']}",
        "",
        "Unexercised namespace rules: " + (", ".join(audit["unexercised_namespace_rules"]) or "none"),
        "",
        "Shadowed namespace rules: " + (", ".join(audit["shadowed_namespace_rules"]) or "none"),
        "",
        f"Specific-rule collisions: {audit['specific_collision_count']}",
        "",
        "| Case | ID | Matching rules | Specific collision | Selected |",
        "|---|---|---|---|---|",
    ]
    for overlap in audit["overlap_cases"]:
        lines.append(
            f"| {_md(overlap['case'])} | {_md(overlap['id'])} | "
            f"{_md(', '.join(overlap['matches']))} | {_md(overlap['has_specific_collision'])} | "
            f"{_md(overlap['selected'])} |"
        )
    if not audit["overlap_cases"]:
        lines.append("| - | - | none | - | - |")
    return "\n".join(lines) + "\n"


def _render_decisions_markdown() -> str:
    lines = [
        "# loc_id Doctrine Decisions",
        "",
        "| Doctrine | Decision ID | Decision | Effect |",
        "|---|---|---|---|",
    ]
    for doctrine in DOCTRINE_PROFILES:
        decisions = doctrine_decisions(doctrine)
        if not decisions:
            lines.append(f"| {doctrine} | - | - | - |")
        for decision in decisions:
            lines.append(
                "| {doctrine} | {id} | {decision} | {effect} |".format(
                    doctrine=doctrine,
                    id=decision.get("id") or "-",
                    decision=decision.get("decision") or "-",
                    effect=decision.get("effect") or "-",
                )
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate sampled geography identifiers against loc_id doctrine.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument(
        "--mode",
        choices=("single", "dual", "designation", "stewardship", "ablation", "compare", "matrix", "rules", "audit", "decisions"),
        default="single",
    )
    doctrine_choices = tuple(DOCTRINE_PROFILES)
    parser.add_argument("--doctrine", choices=doctrine_choices, default="proposed_changes")
    parser.add_argument("--left-doctrine", choices=doctrine_choices, default="present_system")
    parser.add_argument("--right-doctrine", choices=doctrine_choices, default="proposed_changes")
    parser.add_argument("--fail-on-unexpected", action="store_true")
    args = parser.parse_args()

    cases = _load_cases(args.fixture)
    if args.mode in {"matrix", "rules", "audit", "ablation", "decisions"}:
        results = []
    elif args.mode == "compare":
        results = compare_doctrine_cases(cases, left=args.left_doctrine, right=args.right_doctrine)
    elif args.mode == "dual":
        results = evaluate_dual_mode_cases(cases, doctrine=args.doctrine)
    elif args.mode == "designation":
        results = evaluate_designation_cases(cases, doctrine=args.doctrine)
    elif args.mode == "stewardship":
        results = evaluate_stewardship_cases(cases, doctrine=args.doctrine)
    else:
        results = evaluate_identity_cases(cases, doctrine=args.doctrine)
    if args.mode == "rules":
        manifest = doctrine_manifest(args.doctrine)
        if args.format == "json":
            print(json.dumps(manifest, indent=2, sort_keys=True))
        else:
            print(_render_rules_markdown(args.doctrine), end="")
    elif args.mode == "audit":
        audit = {
            "corpus": corpus_audit(cases),
            "registry": registry_audit(cases, doctrine=args.doctrine),
        }
        if args.format == "json":
            print(json.dumps(audit, indent=2, sort_keys=True))
        else:
            print(_render_audit_markdown(cases, args.doctrine), end="")
    elif args.mode == "decisions":
        if args.format == "json":
            payload = {
                doctrine: doctrine_decisions(doctrine)
                for doctrine in DOCTRINE_PROFILES
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(_render_decisions_markdown(), end="")
    elif args.mode == "ablation":
        report = stewardship_ablation_report(cases, doctrine=args.doctrine)
        if args.format == "json":
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(_render_ablation_markdown(cases, args.doctrine), end="")
    elif args.mode == "matrix":
        if args.format == "json":
            payload = {
                doctrine: {
                    "manifest": doctrine_manifest(doctrine),
                    "scorecard": doctrine_scorecard(cases, doctrine=doctrine),
                    "registry_audit": registry_audit(cases, doctrine=doctrine),
                }
                for doctrine in DOCTRINE_PROFILES
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(_render_matrix_markdown(cases), end="")
    elif args.format == "json":
        if args.mode == "compare":
            payload = {
                "left_manifest": doctrine_manifest(args.left_doctrine),
                "right_manifest": doctrine_manifest(args.right_doctrine),
                "rule_differences": compare_doctrine_rules(args.left_doctrine, args.right_doctrine),
                "left_scorecard": doctrine_scorecard(cases, doctrine=args.left_doctrine),
                "right_scorecard": doctrine_scorecard(cases, doctrine=args.right_doctrine),
                "cases": results,
            }
        else:
            payload = {
                "manifest": doctrine_manifest(args.doctrine),
                "scorecard": doctrine_scorecard(cases, doctrine=args.doctrine),
                "cases": results,
            }
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.mode == "compare":
        print(_render_compare_markdown(results, args.left_doctrine, args.right_doctrine), end="")
    elif args.mode == "dual":
        print(_render_dual_markdown(results, args.doctrine), end="")
    elif args.mode == "designation":
        print(_render_designation_markdown(results, args.doctrine), end="")
    elif args.mode == "stewardship":
        print(_render_stewardship_markdown(results, args.doctrine), end="")
    else:
        print(_render_markdown(results, args.doctrine), end="")

    if args.fail_on_unexpected:
        if args.mode == "matrix":
            if any(
                not doctrine_scorecard(cases, doctrine=doctrine)["gate_ok"]
                for doctrine in DOCTRINE_PROFILES
            ):
                return 1
        elif args.mode in {"single", "dual", "designation", "stewardship", "compare"} and any(
            result.get("gate_ok") is False for result in results
        ):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
