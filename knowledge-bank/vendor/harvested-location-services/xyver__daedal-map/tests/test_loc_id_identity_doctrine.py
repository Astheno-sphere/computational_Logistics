from __future__ import annotations

import json
import unittest
from pathlib import Path

from mapmover.runtime.loc_id_identity_doctrine import (
    evaluate_identity_case,
    evaluate_identity_cases,
    infer_first_segment_scope,
    infer_identity_role,
)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "loc_id_weird_cases.json"


def load_weird_cases() -> list[dict]:
    with FIXTURE_PATH.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    assert isinstance(payload, list)
    return payload


class LocIdIdentityDoctrineTests(unittest.TestCase):
    def test_weird_case_fixture_matches_declared_doctrine(self) -> None:
        results = evaluate_identity_cases(load_weird_cases())
        failures = [result for result in results if not result["ok"]]
        self.assertEqual(failures, [])

    def test_sidechain_admin_level_is_rejected_as_fake_spine_depth(self) -> None:
        result = evaluate_identity_case(
            {
                "case": "bad zcta fake admin depth",
                "id": "USA-Z-00601",
                "family_id": "overlay_zcta",
                "expected_role": "loc_id",
                "admin_level": 3,
            }
        )

        self.assertFalse(result["ok"])
        self.assertIn("non-admin families must not expose admin_level as spine depth", result["issues"])

    def test_sidechain_parent_id_is_rejected_as_fake_hierarchy(self) -> None:
        result = evaluate_identity_case(
            {
                "case": "bad zcta fake parent",
                "id": "USA-Z-00601",
                "family_id": "overlay_zcta",
                "expected_role": "loc_id",
                "parent_id": "USA-PR-001",
            }
        )

        self.assertFalse(result["ok"])
        self.assertIn("non-admin parent_id must be represented as context or bridge metadata", result["issues"])

    def test_contested_parentage_requires_claim_records(self) -> None:
        result = evaluate_identity_case(
            {
                "case": "bad contested parent",
                "id": "ESH",
                "family_id": "admin_0",
                "expected_role": "loc_id",
                "parent_status": "contested",
            }
        )

        self.assertFalse(result["ok"])
        self.assertIn("contested parentage requires parent_claims", result["issues"])

    def test_supersession_rule_requires_successor_or_predecessor(self) -> None:
        result = evaluate_identity_case(
            {
                "case": "bad retired id",
                "id": "USA-CT-003",
                "family_id": "admin_local",
                "expected_role": "loc_id",
                "temporal_rule": "supersession_required",
            }
        )

        self.assertFalse(result["ok"])
        self.assertIn("supersession_required needs superseded_by or supersedes", result["issues"])

    def test_first_segment_scope_distinguishes_country_and_source_universes(self) -> None:
        self.assertEqual(infer_first_segment_scope("USA-Z-00601", family_id="overlay_zcta"), "country_reference_scope")
        self.assertEqual(infer_first_segment_scope("IHO1953-240001002", family_id="water_body"), "source_family_scope")
        self.assertEqual(infer_first_segment_scope("USA-VA-059", family_id="admin_local"), "admin_hierarchy")

    def test_identity_role_keeps_non_location_objects_out_of_loc_id(self) -> None:
        self.assertEqual(infer_identity_role("FIRE-413706", family_id="event"), "event_id")
        self.assertEqual(infer_identity_role("ROUTE-USA-I95", family_id="route"), "route_id")
        self.assertEqual(infer_identity_role("H3-872830828ffffff", family_id="grid"), "grid_id")


if __name__ == "__main__":
    unittest.main()
