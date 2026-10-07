import pandas as pd

from mapmover.runtime.family_admin_crosswalk import (
    resolve_admin_ids_to_family,
    resolve_family_ids_to_admin,
    resolve_family_to_admin,
)


def test_identity_crosswalk_without_overlap_metrics_is_supported(tmp_path) -> None:
    crosswalk_path = tmp_path / "identity_crosswalk.parquet"
    pd.DataFrame([{
        "source_family": "ibge_municipality",
        "source_loc_id": "3550308",
        "source_name": "Sao Paulo",
        "target_family": "admin",
        "target_admin_level": "admin_2",
        "target_loc_id": "BRA-EXAMPLE",
        "target_name": "Sao Paulo",
        "is_primary": True,
        "primary_policy": "representative_point",
        "relationship_vintage": "2022",
    }]).to_parquet(crosswalk_path, index=False)

    payload = resolve_family_to_admin(
        "3550308",
        source_family="ibge_municipality",
        target_admin_level="admin_2",
        iso3="BRA",
        crosswalk_path=crosswalk_path,
    )

    assert payload["ok"] is True
    assert payload["primary_match"]["match_loc_id"] == "BRA-EXAMPLE"
    assert payload["primary_match"]["source_area_share"] is None


def test_batch_crosswalk_reads_support_both_directions(tmp_path) -> None:
    crosswalk_path = tmp_path / "batch_crosswalk.parquet"
    pd.DataFrame([
        {
            "source_family": "postal",
            "source_loc_id": "POSTAL-A",
            "source_name": "A",
            "target_family": "admin",
            "target_admin_level": "admin_2",
            "target_loc_id": "USA-AA-001",
            "target_name": "One",
            "source_area_share": 1.0,
            "target_area_share": 0.6,
            "intersection_area": 10.0,
            "is_primary": True,
        },
        {
            "source_family": "postal",
            "source_loc_id": "POSTAL-B",
            "source_name": "B",
            "target_family": "admin",
            "target_admin_level": "admin_2",
            "target_loc_id": "USA-AA-001",
            "target_name": "One",
            "source_area_share": 0.8,
            "target_area_share": 0.4,
            "intersection_area": 8.0,
            "is_primary": False,
        },
    ]).to_parquet(crosswalk_path, index=False)

    forward = resolve_family_ids_to_admin(
        ["POSTAL-A", "POSTAL-B"],
        source_family="postal",
        target_admin_level="admin_2",
        crosswalk_path=crosswalk_path,
    )
    reverse = resolve_admin_ids_to_family(
        ["USA-AA-001"],
        source_family="postal",
        target_admin_level="admin_2",
        crosswalk_path=crosswalk_path,
    )

    assert set(forward) == {"POSTAL-A", "POSTAL-B"}
    assert forward["POSTAL-A"]["primary_match"]["match_loc_id"] == "USA-AA-001"
    assert [row["match_loc_id"] for row in reverse["USA-AA-001"]["overlaps"]] == ["POSTAL-A", "POSTAL-B"]
