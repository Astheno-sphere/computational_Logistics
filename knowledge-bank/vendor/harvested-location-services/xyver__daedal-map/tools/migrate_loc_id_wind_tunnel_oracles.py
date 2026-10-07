from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mapmover.runtime.loc_id_identity_doctrine import ORACLE_FIELDS, corpus_audit

DEFAULT_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "loc_id_wind_tunnel_samples.json"


def migrate_case(case: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Move legacy flat expectations into an explicit doctrine-neutral oracle."""
    migrated = dict(case)
    oracle_root = dict(migrated.get("oracle") or {})
    if isinstance(oracle_root.get("declared"), dict):
        return migrated, False

    declared: dict[str, Any] = {}
    open_policy_fields: list[str] = []
    policy_options: dict[str, Any] = {}
    for result_field, legacy_field in ORACLE_FIELDS.items():
        has_baseline = legacy_field in migrated
        baseline = migrated.pop(legacy_field, None)
        override_field = f"{legacy_field}_by_doctrine"
        by_doctrine = migrated.pop(override_field, None)
        if by_doctrine:
            open_policy_fields.append(result_field)
            policy_options[result_field] = {
                "baseline": baseline if has_baseline else None,
                "by_doctrine": by_doctrine,
            }
        elif has_baseline:
            declared[result_field] = baseline

    known_issues = migrated.pop("expected_issues", None)
    if known_issues:
        declared["known_issues"] = known_issues
    known_issue_codes = migrated.pop("expected_issue_codes", None)
    if known_issue_codes:
        declared["known_issue_codes"] = known_issue_codes
    issues_by_doctrine = migrated.pop("expected_issues_by_doctrine", None)
    if issues_by_doctrine:
        policy_options["known_issues_by_doctrine"] = issues_by_doctrine

    if open_policy_fields:
        declared["open_policy_fields"] = sorted(open_policy_fields)
    if policy_options:
        declared["policy_options"] = policy_options
    asserted_fields = [field for field in ORACLE_FIELDS if field in declared]
    declared["status"] = "provisional" if asserted_fields else "open"

    # Put status first for readability without sorting the entire fixture.
    declared = {"status": declared.pop("status"), **declared}
    oracle_root["declared"] = declared
    migrated["oracle"] = oracle_root
    return migrated, True


def migrate_cases(cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    migrated_cases = []
    changed = 0
    for case in cases:
        migrated, case_changed = migrate_case(case)
        migrated_cases.append(migrated)
        changed += int(case_changed)
    return migrated_cases, changed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate legacy loc_id wind-tunnel expectations into explicit declared oracles."
    )
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--write", action="store_true", help="Rewrite the fixture after validation.")
    args = parser.parse_args()

    with args.fixture.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError(f"{args.fixture} must contain a JSON list")

    migrated, changed = migrate_cases(payload)
    audit = corpus_audit(migrated)
    summary = {
        "fixture": str(args.fixture),
        "case_count": len(migrated),
        "changed_cases": changed,
        "valid": audit["valid"],
        "oracle_fingerprint": audit["oracle_fingerprint"],
        "oracle_coverage": audit["oracle_coverage"],
        "legacy_expectation_case_count": audit["legacy_expectation_case_count"],
        "legacy_doctrine_override_case_count": audit["legacy_doctrine_override_case_count"],
        "errors": audit["errors"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not audit["valid"]:
        return 1
    if args.write and changed:
        args.fixture.write_text(json.dumps(migrated, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
