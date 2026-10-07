from mapmover.runtime.geometry_inventory import (
    build_depth_index,
    public_geometry_inventory_payload,
)


def test_candidate_product_cannot_raise_active_depth() -> None:
    catalog = {
        "country_family_coverage": [],
        "geometry_products": [{
            "product_group": "admin_spine",
            "scope": "BRA",
            "admin_coverage": {"max_admin_level": 5},
        }],
        "global_admin_baseline": [{
            "country_code": "BRA",
            "max_admin_level": 2,
        }],
    }

    index, _global = build_depth_index(catalog)

    assert index["BRA"]["max_admin_level"] == 2
    assert index["BRA"]["depth_source"] == "shared_bank_baseline"


def test_active_and_candidate_depths_remain_separate() -> None:
    catalog = {
        "country_family_coverage": [{
            "country_code": "GBR",
            "max_admin_level": 2,
            "active_admin_depth": 2,
            "candidate_admin_depth": 3,
            "candidate_admin_status": "blocked_spatial_qa",
            "families": [{
                "family_id": "administrative",
                "max_admin_level": 2,
                "active_admin_depth": 2,
                "candidate_admin_depth": 3,
                "candidate_admin_status": "blocked_spatial_qa",
            }],
        }],
        "global_admin_baseline": [{
            "country_code": "GBR",
            "max_admin_level": 2,
        }],
    }

    index, _global = build_depth_index(catalog)

    assert index["GBR"]["max_admin_level"] == 2
    assert index["GBR"]["candidate_admin_depth"] == 3
    assert index["GBR"]["candidate_admin_status"] == "blocked_spatial_qa"
    assert index["GBR"]["program"]["active_admin_depth"] == 2
    assert index["GBR"]["program"]["candidate_admin_depth"] == 3


def test_public_payload_shows_capability_without_candidate_or_workflow_state() -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": []},
            "properties": {
                "loc_id": "FRA",
                "name": "France",
                "max_admin_level": 2,
                "candidate_admin_depth": 4,
                "candidate_admin_status": "prepared_unadmitted",
                "depth_color": "#5b8db8",
                "depth_source": "country_program",
                "coverage_matrix_status": "internal review",
                "families": [
                    {"family_id": "administrative", "label": "Administrative", "available": True, "state": "published"},
                    {"family_id": "postal", "label": "Postal", "available": False, "state": "staged", "gap_or_disposition": "WIP"},
                ],
            },
        }],
        "legend": [],
        "catalog": {"schema_version": "1", "generated_at": "now", "catalog_fingerprint": "secret"},
    }

    public = public_geometry_inventory_payload(payload)
    properties = public["features"][0]["properties"]

    assert properties["max_admin_level"] == 2
    assert properties["coverage_basis"] == "enhanced_country_coverage"
    assert properties["catalog_view"] == "public"
    assert public["view"] == "public"
    assert properties["families"] == [{
        "family_id": "administrative",
        "label": "Administrative",
        "available": True,
    }]
    serialized = str(public)
    assert "candidate" not in serialized
    assert "prepared_unadmitted" not in serialized
    assert "internal review" not in serialized
    assert "catalog_fingerprint" not in serialized
