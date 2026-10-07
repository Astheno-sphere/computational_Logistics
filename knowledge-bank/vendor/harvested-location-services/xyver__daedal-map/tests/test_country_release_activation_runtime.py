from pathlib import Path
from unittest.mock import patch

import pandas as pd

from mapmover.runtime import geometry_catalog, reference_graph


def test_cloud_geometry_catalog_follows_selected_active_lane() -> None:
    with patch.object(geometry_catalog, "read_artifact_json", return_value={"schema_version": "1.1.1"}) as reader:
        assert geometry_catalog._fetch_geometry_catalog_from_s3() == {"schema_version": "1.1.1"}
    reader.assert_called_once_with("geometry/geometry_catalog.json", lane="active")


def test_cloud_reference_graph_discovery_is_catalog_owned(tmp_path: Path) -> None:
    catalog = {"country_profiles": [{
        "country_code": "GBR",
        "release_status": "published",
        "release_id": "gbr_geometry_1_0_0",
        "reference_graph_manifest": (
            "geometry/countries/GBR/releases/geometry/gbr_geometry_1_0_0/"
            "runtime/reference_graph/manifest.json"
        ),
    }]}
    with (
        patch.object(reference_graph, "load_geometry_catalog", return_value=catalog),
        patch.object(reference_graph, "_missing_graph_files", return_value=()),
    ):
        roots = reference_graph._discover_roots(str(tmp_path), "", True)
    assert roots == ((
        "GBR",
        str((tmp_path / "geometry/countries/GBR/reference/gbr_geometry_1_0_0").resolve()),
    ),)


def test_cloud_reference_graph_does_not_scan_legacy_roots(tmp_path: Path) -> None:
    legacy = tmp_path / "geometry/countries/GBR/reference_graph"
    legacy.mkdir(parents=True)
    with patch.object(reference_graph, "load_geometry_catalog", return_value={"country_profiles": []}):
        assert reference_graph._discover_roots(str(tmp_path), "", True) == ()


def test_explicit_operator_graph_override_wins_in_cloud_mode(tmp_path: Path) -> None:
    override = tmp_path / "isolated/GBR/reference_graph"
    override.mkdir(parents=True)
    with patch.object(reference_graph, "_country_for_root", return_value="GBR"):
        assert reference_graph._discover_roots(str(tmp_path), str(override), True) == (
            ("GBR", str(override.resolve())),
        )


def test_cloud_partition_index_is_read_through_shared_artifact_seam(tmp_path: Path) -> None:
    root = tmp_path / "geometry/countries/GBR/reference/r"
    source = "geometry/countries/GBR/relationships/f/identities.parquet"
    current = "geometry/countries/GBR/reference/f/1.0.0/identities.parquet"
    partition = tmp_path / current
    digest = "a" * 64
    frame = pd.DataFrame({"path": [source], "sha256": [digest]})
    with (
        patch.object(reference_graph, "DATA_ROOT", tmp_path),
        patch.object(reference_graph, "is_cloud_mode", return_value=True),
        patch.object(reference_graph, "select_rows", return_value=frame) as reader,
        patch.object(reference_graph, "_country_release_paths", return_value={digest: (current,)}),
    ):
        paths = reference_graph._partition_paths(root, "identities")
    assert paths == [partition]
    reader.assert_called_once_with(root / "identity_partitions.parquet", columns=["path", "sha256"])


def test_cloud_exact_identity_route_avoids_partition_index_fanout(tmp_path: Path) -> None:
    root = tmp_path / "geometry/countries/USA/releases/geometry/r/runtime/reference_graph"
    partition = tmp_path / "geometry/countries/USA/relationships/wbd/identity_versions.parquet"
    frame = pd.DataFrame({"path": [str(partition.relative_to(tmp_path)).replace("\\", "/")]})
    with (
        patch.object(reference_graph, "DATA_ROOT", tmp_path),
        patch.object(reference_graph, "is_cloud_mode", return_value=True),
        patch.object(reference_graph, "select_rows", return_value=frame) as reader,
    ):
        paths = reference_graph._route_paths(
            root, reference_graph.IDENTITY_ROUTE_INDEX, "loc_id", ["USA-WBD-HUC12-010100020101"],
        )
    assert paths == [partition]
    reader.assert_called_once_with(
        root / "identity_routes.parquet",
        columns=["path"],
        in_filters={"loc_id": ["USA-WBD-HUC12-010100020101"]},
    )


def test_relationship_route_selects_only_matching_endpoint_family(tmp_path: Path) -> None:
    root = tmp_path / "graph"
    root.mkdir()
    pd.DataFrame([
        {"source_family": "watershed", "target_family": "admin_2", "path": "wbd_county.parquet"},
        {"source_family": "protected_area", "target_family": "admin_2", "path": "forest_county.parquet"},
    ]).to_parquet(root / "relationship_partitions.parquet", index=False)
    with patch.object(reference_graph, "DATA_ROOT", tmp_path):
        paths = reference_graph._relationship_route_paths(root, "watershed", "source_family")
    assert paths == [tmp_path / "wbd_county.parquet"]


def test_cloud_reference_family_discovery_is_catalog_owned(tmp_path: Path) -> None:
    root = tmp_path / "geometry/countries/NZL/releases/geometry/r/runtime/reference_graph"
    frame = pd.DataFrame({
        "family": ["place_or_municipality", "unpublished_internal_family"],
        "row_count": [123, 999],
    })
    catalog = {"country_family_coverage": [{
        "country_code": "NZL",
        "available_family_ids": ["administrative", "place_or_municipality"],
    }]}
    with (
        patch.object(reference_graph, "load_geometry_catalog", return_value=catalog),
        patch.object(reference_graph, "reference_graph_roots", return_value={"NZL": root}),
        patch.object(reference_graph, "global_reference_graph_root", return_value=None),
        patch.object(reference_graph, "is_cloud_mode", return_value=True),
        patch.object(reference_graph, "select_rows", return_value=frame) as reader,
    ):
        families = reference_graph.reference_graph_families()

    assert families == [
        {
            "family": "administrative", "identity_count": 0,
            "available_country_codes": ["NZL"], "complete_country_codes": [],
            "partial_country_codes": ["NZL"],
        },
        {
            "family": "place_or_municipality", "identity_count": 123,
            "available_country_codes": ["NZL"], "complete_country_codes": [],
            "partial_country_codes": ["NZL"],
        },
    ]
    reader.assert_called_once_with(root / "identity_partitions.parquet", columns=["family", "row_count"])


def test_identities_fail_closed_before_duckdb_when_graph_has_no_partitions() -> None:
    with (
        patch.object(reference_graph, "reference_graph_available", return_value=True),
        patch.object(reference_graph, "_table_source", return_value=""),
        patch.object(reference_graph, "_connection") as connection,
    ):
        assert reference_graph.identities(["AUS-NSW-117-03"]) == []
    connection.assert_not_called()
