from __future__ import annotations

import json
import unittest
from pathlib import Path

from mapmover.runtime.loc_id_identity_doctrine import (
    DESIGNATION_ORACLE_FIELDS,
    STEWARDSHIP_ORACLE_FIELDS,
    DOCTRINE_RULE_KEYS,
    DOCTRINE_PROFILES,
    compare_doctrine_cases,
    compare_doctrine_rules,
    corpus_audit,
    doctrine_manifest,
    doctrine_decisions,
    doctrine_scorecard,
    evaluate_dual_mode_case,
    evaluate_dual_mode_cases,
    evaluate_designation_cases,
    evaluate_identity_case,
    evaluate_identity_cases,
    evaluate_stewardship_cases,
    registry_audit,
    stewardship_ablation_report,
)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "loc_id_wind_tunnel_samples.json"


class LocIdWindTunnelSampleTests(unittest.TestCase):
    maxDiff = None

    def test_sample_fixture_emits_diagnostic_categories(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        results = evaluate_identity_cases(cases)
        signals = {result["signal"] for result in results}
        self.assertIn("pass", signals)
        self.assertIn("unexpected_issue", signals)

    def test_sample_fixture_preserves_at_least_one_design_finding(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        results = evaluate_identity_cases(cases)
        findings = [
            result
            for result in results
            if result["signal"] in {"known_issue", "unexpected_issue"}
        ]
        self.assertGreaterEqual(len(findings), 1)

    def test_unexpected_failures_are_report_findings_not_suite_failures(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        results = evaluate_identity_cases(cases)
        unexpected = [result for result in results if result["signal"] == "unexpected_issue"]
        self.assertGreaterEqual(len(unexpected), 1)
        self.assertTrue(all(result["unexpected_issues"] for result in unexpected))

    def test_dual_mode_reports_raw_declared_deltas(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        results = evaluate_dual_mode_cases(cases)
        signals = {result["signal"] for result in results}
        self.assertIn("raw_declared_delta", signals)
        self.assertIn("oracle_failure", signals)
        self.assertTrue(any(result["deltas"] for result in results))
        self.assertTrue(all(result["raw"]["signal"] == "unscored" for result in results))

    def test_doctrine_profiles_produce_comparison_deltas(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        by_doctrine = {
            doctrine: evaluate_dual_mode_cases(cases, doctrine=doctrine)
            for doctrine in DOCTRINE_PROFILES
        }
        compared = compare_doctrine_cases(cases, left="present_system", right="proposed_changes")
        self.assertTrue(by_doctrine)
        self.assertTrue(all(len(results) == len(cases) for results in by_doctrine.values()))
        self.assertEqual(len(compared), len(cases))
        self.assertTrue(any(result["deltas"] for result in compared))

    def test_every_doctrine_runs_against_the_same_fixture_corpus(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        case_names = [case["case"] for case in cases]
        for doctrine in DOCTRINE_PROFILES:
            with self.subTest(doctrine=doctrine):
                results = evaluate_dual_mode_cases(cases, doctrine=doctrine)
                self.assertEqual([result["case"] for result in results], case_names)

    def test_containing_loc_id_profile_adds_placement_deltas(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        compared = compare_doctrine_cases(cases, left="proposed_changes", right="containing_loc_id")
        joined_deltas = "\n".join(delta for result in compared for delta in result["deltas"])
        self.assertIn("placement_semantics", joined_deltas)

    def test_scorecards_use_the_same_independent_oracle(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        scorecards = {
            doctrine: doctrine_scorecard(cases, doctrine=doctrine)
            for doctrine in DOCTRINE_PROFILES
        }
        assertion_counts = {
            scorecard["declared"]["oracle_assertions"]
            for scorecard in scorecards.values()
        }
        oracle_fingerprints = {
            scorecard["oracle_fingerprint"] for scorecard in scorecards.values()
        }
        doctrine_fingerprints = {
            scorecard["doctrine_fingerprint"] for scorecard in scorecards.values()
        }

        self.assertEqual(len(assertion_counts), 1)
        self.assertEqual(len(oracle_fingerprints), 1)
        self.assertEqual(len(doctrine_fingerprints), len(DOCTRINE_PROFILES))
        self.assertEqual(scorecards["solidified_sibling_layer"]["raw"]["scored_cases"], 0)
        self.assertGreaterEqual(len(doctrine_decisions("solidified_sibling_layer")), 5)
        self.assertGreaterEqual(len(doctrine_decisions("stewarded_release_graph")), 8)

    def test_every_doctrine_exposes_a_complete_executable_manifest(self) -> None:
        for doctrine in DOCTRINE_PROFILES:
            with self.subTest(doctrine=doctrine):
                manifest = doctrine_manifest(doctrine)
                self.assertEqual(set(manifest["rules"]), set(DOCTRINE_RULE_KEYS))
                self.assertTrue(manifest["registry"])
                self.assertTrue(all(entry["rule_id"] for entry in manifest["registry"]))
                self.assertEqual(len(manifest["fingerprint"]), 64)

        differences = compare_doctrine_rules("proposed_changes", "containing_loc_id")
        self.assertEqual(
            [difference["rule"] for difference in differences],
            ["placement_policy"],
        )

        designation_differences = compare_doctrine_rules(
            "solidified_sibling_layer", "designation_reference_graph"
        )
        changed_policy_rules = {
            difference["rule"]
            for difference in designation_differences
            if difference["kind"] == "policy"
        }
        self.assertEqual(changed_policy_rules, set(DESIGNATION_ORACLE_FIELDS.values()) - {"membership_set_representation"})
        self.assertTrue(
            any(
                difference["rule"] == "designation_membership_set"
                for difference in designation_differences
            )
        )

        stewardship_differences = compare_doctrine_rules(
            "designation_reference_graph", "stewarded_release_graph"
        )
        changed_stewardship_rules = {
            difference["rule"]
            for difference in stewardship_differences
            if difference["kind"] == "policy"
        }
        self.assertEqual(
            changed_stewardship_rules,
            set(STEWARDSHIP_ORACLE_FIELDS.values()),
        )

        durable_differences = compare_doctrine_rules(
            "designation_reference_graph", "durable_public_identity"
        )
        durable_rules = {
            difference["rule"]
            for difference in durable_differences
            if difference["kind"] == "policy"
        }
        self.assertEqual(
            durable_rules,
            {
                "authority_scope_separation",
                "family_admission_posture",
                "identity_publication_separation",
                "persistent_public_resolution",
                "temporal_identifier_network",
                "admin_water_world_partition",
                "customer_world_branching",
                "family_authority_selection",
                "multiaxial_time_provenance",
                "artifact_referent_separation",
            },
        )
        remaining_differences = compare_doctrine_rules(
            "durable_public_identity", "stewarded_release_graph"
        )
        remaining_rules = {
            difference["rule"]
            for difference in remaining_differences
            if difference["kind"] == "policy"
        }
        self.assertEqual(
            remaining_rules,
            set(STEWARDSHIP_ORACLE_FIELDS.values()) - durable_rules,
        )
        reproducible_differences = compare_doctrine_rules(
            "designation_reference_graph", "reproducible_relationship_graph"
        )
        reproducible_rules = {
            difference["rule"]
            for difference in reproducible_differences
            if difference["kind"] == "policy"
        }
        self.assertFalse(durable_rules & reproducible_rules)
        self.assertEqual(
            durable_rules | reproducible_rules,
            set(STEWARDSHIP_ORACLE_FIELDS.values()),
        )
        self.assertEqual(reproducible_rules, remaining_rules)

    def test_doctrine_specific_expected_answers_are_open_policy_not_oracle(self) -> None:
        result = evaluate_identity_case(
            {
                "case": "relationship policy experiment",
                "id": "NHGIS-XWALK-TRACT-1990-2020",
                "family_id": "relationship",
                "oracle": {
                    "declared": {
                        "status": "provisional",
                        "open_policy_fields": ["role"],
                        "policy_options": {
                            "role": {
                                "baseline": "source_alias",
                                "by_doctrine": {
                                    "solidified_sibling_layer": "relationship_id",
                                },
                            }
                        },
                    }
                },
            },
            doctrine="solidified_sibling_layer",
        )

        self.assertFalse(result["oracle"]["scored"])
        self.assertIn("role", result["oracle"]["open_policy_fields"])
        self.assertEqual(result["role"], "relationship_id")
        self.assertEqual(result["signal"], "unscored")

    def test_raw_mode_is_scored_only_with_an_explicit_raw_oracle(self) -> None:
        case = {
            "case": "raw grid",
            "id": "H3-872830828FFFFFF",
            "family_id": "grid",
            "expected_role": "grid_id",
        }
        unscored = evaluate_dual_mode_case(case)
        self.assertFalse(unscored["raw"]["oracle"]["scored"])

        case["oracle"] = {
            "raw": {
                "status": "verified",
                "role": "grid_id",
                "first_segment_scope": "grid_scope",
            }
        }
        scored = evaluate_dual_mode_case(case)
        self.assertTrue(scored["raw"]["oracle"]["scored"])
        self.assertEqual(scored["raw"]["oracle_assertions_passed"], 2)

    def test_known_issue_is_debt_not_a_required_output(self) -> None:
        case = {
            "case": "known broad fallback defect",
            "id": "NHC-CONE-AL092022-2022092800",
            "expected_role": "event_id",
            "expected_issues": ["role mismatch: expected event_id, got loc_id"],
        }
        present = evaluate_identity_case(case, doctrine="present_system")
        proposed = evaluate_identity_case(case, doctrine="proposed_changes")

        self.assertEqual(present["signal"], "known_issue")
        self.assertTrue(present["ok"])
        self.assertEqual(proposed["signal"], "pass")
        self.assertIn(case["expected_issues"][0], proposed["resolved_known_issues"])

    def test_registry_audit_reports_precedence_collisions(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        audit = registry_audit(cases, doctrine="designation_reference_graph")
        corpus = corpus_audit(cases)
        self.assertEqual(audit["case_count"], len(cases))
        self.assertGreater(audit["overlap_count"], 0)
        self.assertGreater(audit["specific_collision_count"], 0)
        self.assertFalse(audit["unused_namespace_rules"])
        self.assertTrue(corpus["valid"])
        self.assertEqual(corpus["oracle_coverage"]["explicit_declared_cases"], len(cases))
        self.assertEqual(corpus["oracle_coverage"]["raw_scored_cases"], 0)
        self.assertEqual(corpus["legacy_doctrine_override_case_count"], 0)
        self.assertEqual(corpus["legacy_expectation_case_count"], 0)
        expected_stewardship_cases = sum(
            "stewardship" in (case.get("oracle") or {}) for case in cases
        )
        self.assertEqual(
            corpus["oracle_coverage"]["explicit_stewardship_cases"],
            expected_stewardship_cases,
        )
        self.assertGreaterEqual(expected_stewardship_cases, 11)

    def test_designation_cases_score_capabilities_separately(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        solidified = evaluate_designation_cases(cases, doctrine="solidified_sibling_layer")
        designation = evaluate_designation_cases(cases, doctrine="designation_reference_graph")
        self.assertGreaterEqual(len(designation), 13)
        self.assertEqual(len(solidified), len(designation))
        self.assertTrue(any(result["signal"] == "oracle_failure" for result in solidified))
        self.assertTrue(all(result["signal"] == "pass" for result in designation))

        score = doctrine_scorecard(cases, doctrine="designation_reference_graph")
        self.assertEqual(
            score["designation"]["oracle_assertions"],
            score["designation"]["oracle_assertions_passed"],
        )
        self.assertEqual(score["designation"]["assertion_accuracy"], 1.0)

    def test_designation_corpus_spans_multiple_governance_systems(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        designation_cases = [case for case in cases if "designation" in (case.get("oracle") or {})]
        identifiers = {case["id"] for case in designation_cases}
        for prefix in ("USA-", "EC-", "AUS-", "BRA-", "IND-", "RPA-"):
            with self.subTest(prefix=prefix):
                self.assertTrue(any(identifier.startswith(prefix) for identifier in identifiers))

    def test_stewardship_cases_score_public_contract_separately(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        designation = evaluate_stewardship_cases(
            cases, doctrine="designation_reference_graph"
        )
        stewarded = evaluate_stewardship_cases(
            cases, doctrine="stewarded_release_graph"
        )
        self.assertGreaterEqual(len(stewarded), 11)
        self.assertEqual(len(designation), len(stewarded))
        self.assertTrue(all(result["signal"] == "oracle_failure" for result in designation))
        self.assertTrue(all(result["signal"] == "pass" for result in stewarded))

        score = doctrine_scorecard(cases, doctrine="stewarded_release_graph")
        self.assertGreaterEqual(score["stewardship"]["oracle_assertions"], 28)
        self.assertEqual(
            score["stewardship"]["oracle_assertions"],
            score["stewardship"]["oracle_assertions_passed"],
        )
        self.assertEqual(score["stewardship"]["assertion_accuracy"], 1.0)

    def test_durable_public_identity_is_a_partial_stewardship_ablation(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        score = doctrine_scorecard(cases, doctrine="durable_public_identity")
        total = score["stewardship"]["oracle_assertions"]
        passed = score["stewardship"]["oracle_assertions_passed"]
        self.assertGreaterEqual(total, 28)
        self.assertGreater(passed, 0)
        self.assertLess(passed, total)
        self.assertEqual(score["stewardship"]["assertion_accuracy"], round(passed / total, 6))
        self.assertEqual(
            score["complexity"]["enabled_stewardship_capability_count"], 10
        )

    def test_reproducible_relationship_graph_is_the_complementary_ablation(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        score = doctrine_scorecard(cases, doctrine="reproducible_relationship_graph")
        total = score["stewardship"]["oracle_assertions"]
        passed = score["stewardship"]["oracle_assertions_passed"]
        self.assertGreaterEqual(total, 28)
        self.assertGreater(passed, 0)
        self.assertLess(passed, total)
        self.assertEqual(score["stewardship"]["assertion_accuracy"], round(passed / total, 6))
        self.assertEqual(
            score["complexity"]["enabled_stewardship_capability_count"], 9
        )

    def test_single_rule_stewardship_ablation_attributes_unique_contribution(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        report = stewardship_ablation_report(cases)
        self.assertTrue(report["baseline"]["gate_ok"])
        self.assertGreaterEqual(report["baseline"]["oracle_assertions_passed"], 28)
        self.assertEqual(len(report["mutations"]), len(STEWARDSHIP_ORACLE_FIELDS))
        self.assertTrue(report["all_rules_have_observed_contribution"])
        self.assertFalse(report["capabilities_below_two_supporting_cases"])
        self.assertEqual(
            sum(mutation["assertion_loss"] for mutation in report["mutations"]),
            report["baseline"]["oracle_assertions_passed"],
        )

        by_capability = {
            mutation["capability"]: mutation for mutation in report["mutations"]
        }
        provenance = by_capability["preserves_relationship_provenance"]
        self.assertGreaterEqual(provenance["assertion_loss"], 8)
        provenance_cases = {
            failure["case"] for failure in provenance["failure_cases"]
        }
        self.assertEqual(provenance["failure_case_count"], len(provenance_cases))
        self.assertTrue(
            {
                "NHGIS 1990-to-2020 tract crosswalk",
                "RPA megaregions static display membership set",
                "Statistics Canada 2016-to-2021 dissemination-area correspondence",
                "ABS 2016-to-2021 local-government-area correspondence",
                "Rejected same_as between H3 cell and administrative area",
                "Ambiguous succession remains a candidate relationship set",
                "H3 logical parent rejected as geometric containment proof",
                "Raster cells sharing a center rejected as same_as",
            }
            <= provenance_cases
        )

    def test_pressure_cases_are_fixture_sized_and_international(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        by_id = {case["id"]: case for case in cases}
        expected_ids = {
            "OCHA-PCODE-ID94",
            "OS-UPRN-906483712",
            "ONS-XWALK-CODE-HISTORY-2026-08-FIXTURE",
            "STATCAN-XWALK-DA-2016-2021-FIXTURE",
            "ABS-XWALK-LGA-2016-2021-FIXTURE",
            "CLAIM-WESTERN-SAHARA-UN-NSGT",
            "CLAIM-ESSEQUIBO-ICJ-171",
        }
        self.assertTrue(expected_ids <= set(by_id))
        for identifier in expected_ids:
            with self.subTest(identifier=identifier):
                self.assertIn("source_url", by_id[identifier])
                self.assertNotIn("geometry", by_id[identifier])

    def test_grid_tile_and_raster_cases_preserve_required_context(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        by_id = {case["id"]: case for case in cases}
        grid_ids = {
            "H3-872830828FFFFFF",
            "OGC-TILE-WEBMERCATORQUAD-Z10-R395-C163",
            "RASTER-ERA5-ATM-025D-LAT37750-LONM122250",
            "RASTER-ERA5-WAVE-100D-LAT37750-LONM122250",
            "RASTER-OISST-V21-025D-LAT33750-LONM120250",
        }
        for identifier in grid_ids:
            with self.subTest(identifier=identifier):
                case = by_id[identifier]
                self.assertEqual(case["family_id"], "grid")
                self.assertEqual(case["oracle"]["declared"]["role"], "grid_id")
                self.assertFalse(case["should_persist_as_loc_id"])

        tile_context = by_id["OGC-TILE-WEBMERCATORQUAD-Z10-R395-C163"][
            "grid_context"
        ]
        self.assertEqual(tile_context["tile_matrix_set_id"], "WebMercatorQuad")
        self.assertEqual(tile_context["content_identity"], "separate_artifact")

        quarter = by_id["RASTER-ERA5-ATM-025D-LAT37750-LONM122250"][
            "grid_context"
        ]
        one_degree = by_id["RASTER-ERA5-WAVE-100D-LAT37750-LONM122250"][
            "grid_context"
        ]
        self.assertEqual(
            (quarter["center_lon"], quarter["center_lat"]),
            (one_degree["center_lon"], one_degree["center_lat"]),
        )
        self.assertNotEqual(
            quarter["cell_width_degrees"], one_degree["cell_width_degrees"]
        )

    def test_negative_pressure_cases_encode_the_rejected_inference(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        negative_cases = [case for case in cases if case.get("negative_test")]
        self.assertGreaterEqual(len(negative_cases), 8)
        rejected = {
            value
            for case in negative_cases
            for value in case["negative_test"].get("rejects", [])
        }
        self.assertTrue(
            {
                "same_as",
                "single_successor",
                "unversioned_public_persistence",
                "artifact_hash_as_geographic_identity",
                "bare_zxy_as_global_identity",
                "logical_parent_as_geometric_contains",
                "same_center_as_same_cell",
                "zero_to_360_as_normalized_EPSG4326_bbox",
            }
            <= rejected
        )

    def test_temporal_identifier_network_handles_aliases_and_code_reuse(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        by_id = {case["id"]: case for case in cases}
        one_referent = by_id["ONS-XWALK-CODE-HISTORY-2026-08-FIXTURE"]["stewardship"][
            "identifier_assertions"
        ]
        reused_identifier = by_id["OCHA-PCODE-REUSE-MUTANT-101"]["stewardship"][
            "identifier_assertions"
        ]

        self.assertGreater(len({row["identifier"] for row in one_referent}), 1)
        self.assertEqual(len({row["referent_id"] for row in one_referent}), 1)
        self.assertEqual(len({row["identifier"] for row in reused_identifier}), 1)
        self.assertGreater(len({row["referent_id"] for row in reused_identifier}), 1)
        self.assertLess(reused_identifier[0]["valid_to"], reused_identifier[1]["valid_from"])
        self.assertTrue(
            all(
                "valid_to" in row and row["assertion_source"]
                for row in one_referent + reused_identifier
            )
        )

    def test_official_world_partition_separates_land_and_water(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        by_id = {case["id"]: case for case in cases}
        land = by_id["REL-REVIEW-WORLD-LAND-PARTITION"]["stewardship"]["world_partition"]
        water = by_id["REL-REVIEW-WORLD-WATER-PARTITION"]["stewardship"]["world_partition"]

        self.assertEqual(land["surface_class"], "land")
        self.assertTrue(land["admin_path"])
        self.assertTrue(land["strict_parentage"])
        self.assertEqual(land["null_tiers"], [3, 4, 5])
        self.assertEqual(water["surface_class"], "water")
        self.assertFalse(water["admin_path"])
        self.assertFalse(water["fabricated_admin_descendants"])
        self.assertTrue(all(row["gap_count"] == row["overlap_count"] == 0 for row in (land, water)))

    def test_non_shaped_presentation_scale_hints_never_affect_identity(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        by_id = {case["id"]: case for case in cases}
        water = by_id["REL-REVIEW-SCALE-WATER-RELEASE"]["stewardship"]["scale_hint"]
        raster = by_id["REL-REVIEW-SCALE-RASTER-RESOLUTION"]["stewardship"]["scale_hint"]

        self.assertNotEqual(water["prior_hint"], water["derived_hint"])
        self.assertEqual(water["subject_id"], "IHO1953-240001002")
        self.assertEqual(raster["source_native_level"], "0.25_degree_cell")
        self.assertTrue(all(row["field_status"] == "derived" for row in (water, raster)))
        self.assertTrue(all(row["affects_identity"] is False for row in (water, raster)))
        self.assertTrue(all(row["input_release_id"] and row["output_release_id"] for row in (water, raster)))

    def test_shaped_sibling_area_depth_affects_canonical_ancestry(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        by_id = {case["id"]: case for case in cases}
        large = by_id["REL-REVIEW-AREA-DEPTH-LARGE-CITY"]["stewardship"][
            "sibling_area_depth"
        ]
        straddler = by_id["REL-REVIEW-AREA-DEPTH-SMALL-STRADDLER"]["stewardship"][
            "sibling_area_depth"
        ]

        self.assertEqual(large["selected_reference_level"], "label_2")
        self.assertEqual(straddler["selected_reference_level"], "label_4")
        self.assertLess(
            len(large["sibling_anchor_loc_id"].split("-")),
            len(straddler["sibling_anchor_loc_id"].split("-")),
        )
        self.assertTrue(straddler["crosses_same_depth_siblings"])
        self.assertFalse(straddler["boundary_crossing_affects_depth"])
        self.assertTrue(straddler["other_intersections_retained_as_bridges"])
        self.assertTrue(all(row["affects_identity"] is True for row in (large, straddler)))
        self.assertTrue(
            all(
                row["canonical_loc_id"].startswith(f'{row["country_owner_iso3"]}-')
                for row in (large, straddler)
            )
        )

    def test_canada_area_depth_suffix_is_not_mistaken_for_admin_depth(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        case = next(
            row for row in cases if row["id"] == "CAN-BC-5915-PLACE-5900001"
        )
        result = evaluate_dual_mode_case(case)
        stewardship = evaluate_stewardship_cases([case], doctrine="reproducible_relationship_graph")[0]

        self.assertEqual(result["raw"]["namespace"], "country_shaped_sibling_area_depth")
        self.assertEqual(result["raw"]["role"], "loc_id")
        self.assertEqual(result["raw"]["first_segment_scope"], "country_reference_scope")
        self.assertFalse(result["raw"]["may_encode_admin_hierarchy"])
        self.assertIsNone(result["raw"]["reference_level"])
        self.assertEqual(result["raw"]["parent_semantics"], "context_or_bridge_only")
        self.assertEqual(stewardship["signal"], "pass")

    def test_canada_point_only_name_does_not_acquire_area_depth(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        case = next(
            row
            for row in cases
            if row["id"] == "CGNDB-00000118CCC54AB8BC2083A146C45EAD"
        )
        result = evaluate_dual_mode_case(case)

        self.assertEqual(result["raw"]["namespace"], "external_source_alias")
        self.assertEqual(result["raw"]["role"], "source_alias")
        self.assertFalse(result["declared"]["may_encode_admin_hierarchy"])
        self.assertFalse(result["raw"]["may_encode_admin_hierarchy"])
        self.assertIsNone(result["declared"]["reference_level"])
        self.assertIsNone(result["raw"]["reference_level"])
        self.assertNotIn("stewardship", case)

    def test_customer_worlds_are_isolated_until_reviewed_promotion(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        by_id = {case["id"]: case for case in cases}
        isolated = by_id["REL-REVIEW-WORLD-BRANCH-ISOLATION"]["stewardship"]["world_branch"]
        promotion = by_id["REL-REVIEW-WORLD-BRANCH-PROMOTION"]["stewardship"]["world_branch"]

        self.assertFalse(isolated["collision_probe"]["cross_world_resolution"])
        self.assertFalse(isolated["collision_probe"]["same_referent"])
        self.assertEqual(promotion["target_world_id"], "daedalmap-official")
        self.assertEqual(promotion["promotion_status"], "blocked_pending_review")
        self.assertEqual(
            set(promotion["required_reviews"]),
            {"identity", "authority", "license", "provenance", "geometry", "lifecycle"},
        )
        self.assertTrue(all(row["official_unchanged"] for row in (isolated, promotion)))

    def test_official_authority_is_selected_and_pinned_per_family(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        by_id = {case["id"]: case for case in cases}
        country = by_id["REL-REVIEW-AUTHORITY-COUNTRY-FAMILY"]["stewardship"][
            "authority_selection"
        ]
        water = by_id["REL-REVIEW-AUTHORITY-WATER-FAMILY"]["stewardship"][
            "authority_selection"
        ]

        self.assertNotEqual(country["family_id"], water["family_id"])
        self.assertNotEqual(country["authority_id"], water["authority_id"])
        self.assertTrue(all(row["official_view_deterministic"] for row in (country, water)))
        self.assertTrue(all(row["alternates_preserved"] for row in (country, water)))
        self.assertTrue(all(row["latest_wins"] is False for row in (country, water)))
        self.assertTrue(all(row["authority_release_id"] and row["source_artifact_id"] for row in (country, water)))

    def test_geometry_packages_declare_distribution_separately_from_data(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        by_id = {case["id"]: case for case in cases}
        public = by_id["REL-REVIEW-GEOMETRY-PACKAGE-PUBLIC"]["stewardship"][
            "geometry_distribution"
        ]
        customer = by_id["REL-REVIEW-GEOMETRY-PACKAGE-CUSTOMER"]["stewardship"][
            "geometry_distribution"
        ]

        self.assertEqual(public["access_posture"], "public")
        self.assertEqual(customer["access_posture"], "customer_world")
        self.assertNotEqual(public["generalization_method"], customer["generalization_method"])
        self.assertEqual(customer["world_id"], "customer-world-alpha")
        self.assertTrue(all(row["profile"] == "geometry" for row in (public, customer)))
        self.assertTrue(all(row["data_profile_inherited"] is False for row in (public, customer)))

    def test_confidence_and_supersession_are_typed_and_reproducible(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as handle:
            cases = json.load(handle)

        by_id = {case["id"]: case for case in cases}
        candidate = by_id["REL-REVIEW-CONFIDENCE-CANDIDATE-SUCCESSOR"]["stewardship"][
            "confidence_supersession"
        ]
        confirmed = by_id["REL-REVIEW-CONFIDENCE-CONFIRMED-SUCCESSOR"]["stewardship"][
            "confidence_supersession"
        ]

        self.assertEqual(candidate["supersession_status"], "candidate")
        self.assertIsInstance(candidate["score"], float)
        self.assertGreater(len(candidate["successor_ids"]), 1)
        self.assertEqual(confirmed["supersession_status"], "confirmed")
        self.assertIsNone(confirmed["score"])
        self.assertEqual(len(confirmed["successor_ids"]), 1)
        self.assertTrue(all(row["default_score_used"] is False for row in (candidate, confirmed)))
        self.assertTrue(all(row["algorithm_version"] and row["threshold_version"] for row in (candidate, confirmed)))

    def test_corpus_audit_requires_evidence_for_stewardship_capabilities(self) -> None:
        audit = corpus_audit(
            [
                {
                    "case": "missing public-resolution evidence",
                    "id": "TEST-STEWARDSHIP-1",
                    "stewardship": {"identity_promise": "durable"},
                    "oracle": {
                        "stewardship": {
                            "status": "verified",
                            "preserves_public_resolution": True,
                        }
                    },
                }
            ]
        )

        self.assertFalse(audit["valid"])
        self.assertIn(
            "MISSING_STEWARDSHIP_EVIDENCE",
            {error["code"] for error in audit["errors"]},
        )

    def test_corpus_audit_rejects_non_boolean_designation_capability(self) -> None:
        audit = corpus_audit(
            [
                {
                    "case": "invalid designation capability",
                    "id": "TEST-DESIG-1",
                    "designation": {"authority": "test"},
                    "oracle": {
                        "designation": {
                            "status": "verified",
                            "represents_membership_set": "yes",
                        }
                    },
                }
            ]
        )

        self.assertFalse(audit["valid"])
        self.assertIn(
            "INVALID_DESIGNATION_CAPABILITY_VALUE",
            {error["code"] for error in audit["errors"]},
        )

    def test_corpus_audit_requires_evidence_for_designation_capabilities(self) -> None:
        audit = corpus_audit(
            [
                {
                    "case": "missing designation clock evidence",
                    "id": "TEST-DESIG-2",
                    "family_id": "membership_set",
                    "designation": {"authority": "test", "status": "active"},
                    "oracle": {
                        "designation": {
                            "status": "verified",
                            "preserves_independent_clocks": True,
                        }
                    },
                }
            ]
        )

        self.assertFalse(audit["valid"])
        self.assertIn(
            "MISSING_DESIGNATION_EVIDENCE",
            {error["code"] for error in audit["errors"]},
        )

    def test_corpus_audit_rejects_an_asserted_open_policy_field(self) -> None:
        audit = corpus_audit(
            [
                {
                    "case": "invalid open policy oracle",
                    "id": "TEST-OPEN-1",
                    "oracle": {
                        "declared": {
                            "status": "provisional",
                            "role": "loc_id",
                            "open_policy_fields": ["role"],
                        }
                    },
                }
            ]
        )

        self.assertFalse(audit["valid"])
        self.assertIn("OPEN_POLICY_FIELD_ASSERTED", {error["code"] for error in audit["errors"]})


if __name__ == "__main__":
    unittest.main()
