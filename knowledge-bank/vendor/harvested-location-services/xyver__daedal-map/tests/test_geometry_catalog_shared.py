from geometry_catalog_shared import (
    build_geometry_capability_summary,
    build_published_geometry_catalog,
    public_geometry_catalog_records,
    published_geometry_catalog_records,
)


def test_capability_summary_exposes_only_global_baseline_and_admitted_enrichment() -> None:
    catalog = {
        "generated_at": "2026-08-24T00:00:00Z",
        "global_admin_baseline": [
            {"country_code": "BRA", "max_admin_level": 2},
            {"country_code": "AUS", "max_admin_level": 2},
            {"country_code": "FRA", "max_admin_level": 2},
        ],
        "country_profiles": [{"country_code": "AUS", "profile_id": "australia"}],
        "country_family_coverage": [
            {
                "country_code": "AUS",
                "label": "Australia",
                "active_admin_depth": 6,
                "available_family_ids": ["administrative"],
            },
            {
                "country_code": "BRA",
                "label": "Brazil",
                "active_admin_depth": 2,
                "candidate_admin_depth": 4,
                "candidate_admin_status": "blocked",
                "available_family_ids": ["administrative"],
            },
            {
                "country_code": "FRA",
                "label": "France",
                "active_admin_depth": 2,
                "candidate_admin_depth": 4,
                "candidate_admin_status": "preparing",
                "available_family_ids": ["administrative"],
            },
        ],
    }

    summary = build_geometry_capability_summary(catalog)

    assert summary["global_baseline"]["geographic_entity_count"] == 3
    assert summary["global_baseline"]["max_admin_depth"] == 2
    assert summary["enhanced_country_codes"] == ["AUS"]
    assert "candidate_countries" not in summary
    assert "country_programs" not in summary
    assert "same geography tools work" in summary["public_claim"].lower()


def test_additional_reference_family_counts_as_enrichment() -> None:
    summary = build_geometry_capability_summary({
        "global_admin_baseline": [{"country_code": "GBR", "max_admin_level": 2}],
        "country_family_coverage": [{
            "country_code": "GBR",
            "label": "United Kingdom",
            "active_admin_depth": 2,
            "available_family_ids": ["administrative", "place_or_municipality"],
        }],
    })

    assert summary["enhanced_country_codes"] == ["GBR"]
    assert summary["enhanced_countries"][0]["enrichment_reasons"] == ["additional_reference_families"]


def test_country_appears_when_usable_depth_improves_not_when_candidate_is_prepared() -> None:
    baseline = [{"country_code": "FRA", "max_admin_level": 2}]
    prepared = build_geometry_capability_summary({
        "global_admin_baseline": baseline,
        "country_family_coverage": [{
            "country_code": "FRA",
            "label": "France",
            "active_admin_depth": 2,
            "candidate_admin_depth": 4,
            "candidate_admin_status": "prepared_unadmitted",
            "available_family_ids": ["administrative"],
        }],
    })
    admitted = build_geometry_capability_summary({
        "global_admin_baseline": baseline,
        "country_family_coverage": [{
            "country_code": "FRA",
            "label": "France",
            "active_admin_depth": 4,
            "candidate_admin_depth": 5,
            "candidate_admin_status": "preparing",
            "available_family_ids": ["administrative", "place_or_municipality"],
        }],
    })

    assert prepared["enhanced_country_codes"] == []
    assert admitted["enhanced_country_codes"] == ["FRA"]
    assert admitted["enhanced_countries"][0]["active_admin_depth"] == 4
    assert "candidate_admin_depth" not in admitted["enhanced_countries"][0]
    assert "France" in admitted["public_claim"]


def test_public_records_hide_wip_but_keep_admitted_candidate_pass() -> None:
    rows = public_geometry_catalog_records({"geometry_products": [
        {"product_id": "published", "release_state": "published"},
        {"product_id": "admitted", "release_state": "candidate_pass"},
        {"product_id": "wip", "release_state": "candidate_blocked"},
    ]}, "geometry_products")

    assert [item["product_id"] for item in rows] == ["published", "admitted"]


def test_public_country_profile_hides_release_lane_and_unavailable_packages() -> None:
    rows = public_geometry_catalog_records({"country_profiles": [{
        "profile_id": "example",
        "release_status": "candidate_pass",
        "release_id": "example_candidate_r1",
        "graph_release_id": "example_graph_candidate",
        "qa_highlights": ["The adopted local spine passes.", "The graph is local and unpublished."],
        "family_coverage": [{"family_id": "administrative", "state": "graph_admitted", "available": True}],
        "package_recipes": [
            {"package_id": "ready", "download_available": True},
            {"package_id": "wip", "download_available": False},
        ],
    }]}, "country_profiles")

    assert len(rows) == 1
    profile = rows[0]
    assert "release_status" not in profile
    assert "release_id" not in profile
    assert profile["qa_highlights"] == ["The maintained spine passes."]
    assert "state" not in profile["family_coverage"][0]
    assert [item["package_id"] for item in profile["package_recipes"]] == ["ready"]


def test_published_records_exclude_every_candidate_lifecycle() -> None:
    rows = published_geometry_catalog_records({"geometry_products": [
        {"product_id": "published", "release_state": "published"},
        {"product_id": "candidate_pass", "release_state": "candidate_pass"},
        {"product_id": "local", "status": "adopted_local_candidate"},
    ]}, "geometry_products")

    assert [item["product_id"] for item in rows] == ["published"]


def test_downloadable_projection_filters_wip_records_and_unavailable_families() -> None:
    catalog = {
        "generated_at": "2026-08-24T00:00:00Z",
        "catalog_fingerprint": "canonical-fingerprint",
        "global_admin_baseline": [{"country_code": "USA", "max_admin_level": 2}],
        "country_profiles": [
            {"country_code": "USA", "release_status": "published"},
            {"country_code": "TST", "release_status": "candidate_pass"},
        ],
        "country_family_coverage": [{
            "country_code": "USA",
            "candidate_admin_depth": 5,
            "families": [
                {
                    "family_id": "administrative", "available": True,
                    "state": "published", "coverage_status": "complete",
                    "coverage_complete": True,
                },
                {"family_id": "watershed", "available": False, "state": "researching"},
            ],
        }],
        "geometry_products": [
            {"product_id": "published", "release_state": "published"},
            {"product_id": "wip", "release_state": "candidate"},
        ],
    }

    published = build_published_geometry_catalog(catalog)

    assert published["source_catalog_fingerprint"] == "canonical-fingerprint"
    assert [item["product_id"] for item in published["geometry_products"]] == ["published"]
    assert [item["country_code"] for item in published["country_profiles"]] == ["USA"]
    coverage = published["country_family_coverage"][0]
    assert coverage["available_family_ids"] == ["administrative"]
    assert coverage["complete_family_ids"] == ["administrative"]
    assert [item["family_id"] for item in coverage["families"]] == ["administrative"]
    assert coverage["families"][0]["coverage_status"] == "complete"
    assert "candidate_admin_depth" not in coverage


def test_downloadable_projection_refers_to_the_crosswalk_catalog() -> None:
    published = build_published_geometry_catalog({
        "crosswalks": [
            {"crosswalk_id": "callable", "publication_status": "published", "callable": True},
            {"crosswalk_id": "relationship-only", "publication_status": "published", "callable": False},
            {"crosswalk_id": "wip", "publication_status": "wip", "callable": True},
        ],
        "reference_systems": [
            {"reference_system_id": "ready", "publication_status": "published", "callable": True},
            {"reference_system_id": "held", "publication_status": "published", "callable": False},
        ],
    })

    assert "crosswalks" not in published
    assert "reference_systems" not in published
    assert published["crosswalk_catalog_path"] == "geometry/crosswalk_catalog.json"


def test_downloadable_projection_does_not_advertise_internal_release_receipts() -> None:
    published = build_published_geometry_catalog({
        "country_profiles": [{
            "country_code": "USA",
            "release_status": "published",
            "active_release": {
                "release_id": "usa_geometry_1_0_0",
                "source_pointer_path": "geometry/countries/USA/releases/geometry/current.json",
                "source_pointer_sha256": "pointer-hash",
                "version_manifest_path": "geometry/countries/USA/releases/geometry/usa_geometry_1_0_0/version.json",
                "version_manifest_sha256": "version-hash",
                "runtime_artifacts": {
                    "query_layout_manifest": "geometry/countries/USA/runtime/admin_spine/manifest.json",
                },
            },
        }],
    })

    assert published["country_profiles"][0]["active_release"] == {
        "release_id": "usa_geometry_1_0_0",
        "runtime_artifacts": {
            "query_layout_manifest": "geometry/countries/USA/runtime/admin_spine/manifest.json",
        },
    }
