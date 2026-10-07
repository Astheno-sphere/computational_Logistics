from pathlib import Path

import pytest

from mapmover.runtime.geometry_storage_layout import (
    catalog_artifact_path,
    country_admin_spine_root,
    country_crosswalk_artifact_path,
    country_release_manifest_relative,
    global_admin0_display_relative,
    global_admin0_exact_relative,
    global_admin0_point_relative,
    global_admin0_point_path,
    released_artifact_path,
    released_artifact_paths_by_hash,
)


PROFILE = {"release_id": "usa_geometry_1_3_2", "release_version": "1.3.2"}


def test_global_admin0_high_level_contract_keeps_three_distinct_worldwide_banks() -> None:
    """Exact, Display, and point lookup are separate products, never loose country shards."""
    assert {
        "exact": global_admin0_exact_relative(),
        "display": global_admin0_display_relative(),
        "point": global_admin0_point_relative(),
    } == {
        "exact": "geometry/global/exact/admin_0.parquet",
        "display": "geometry/global/display/admin_0.parquet",
        "point": "geometry/global/runtime/admin_0_point.parquet",
    }


def test_country_paths_come_from_one_contained_layout_contract() -> None:
    assert country_admin_spine_root(Path("data"), "usa", PROFILE) == Path(
        "data/geometry/countries/USA/admin_spine/exact/usa_geometry_1_3_2"
    )


def test_release_owned_crosswalk_uses_local_authoring_fallback(tmp_path: Path) -> None:
    relative = (
        "geometry/countries/USA/crosswalks/usa_geometry_1_3_2/"
        "official/census/zcta_to_county.parquet"
    )
    local = (
        tmp_path / "geometry/countries/USA/crosswalks/official/census/"
        "zcta_to_county.parquet"
    )
    local.parent.mkdir(parents=True)
    local.touch()

    assert country_crosswalk_artifact_path(
        tmp_path, relative, cloud_mode=False,
    ) == local
    assert country_crosswalk_artifact_path(
        tmp_path, relative, cloud_mode=True,
    ) == tmp_path / relative


def test_catalog_artifact_path_rejects_paths_outside_geometry() -> None:
    assert catalog_artifact_path(Path("data"), {"path": "geometry/global/exact/admin_0.parquet"}) == Path(
        "data/geometry/global/exact/admin_0.parquet"
    )
    assert catalog_artifact_path(Path("data"), {"path": "../secret"}) is None
    assert catalog_artifact_path(Path("data"), {"path": "catalog.json"}) is None
    assert country_release_manifest_relative("USA", PROFILE) == (
        "geometry/countries/USA/releases/1.3.2/manifest.json"
    )


def test_embedded_legacy_path_resolves_by_release_hash() -> None:
    digest = "a" * 64
    paths = released_artifact_paths_by_hash({
        "objects": [{"sha256": digest, "source_paths": [
            "geometry/countries/USA/reference/example/1.3.2/aliases.parquet"
        ]}]
    })
    assert released_artifact_path(
        "geometry/countries/USA/relationships/old/aliases.parquet", digest, paths,
    ) == "geometry/countries/USA/reference/example/1.3.2/aliases.parquet"


def test_exact_declared_path_wins_when_projection_has_same_basename() -> None:
    digest = "a" * 64
    release_owned = "geometry/countries/AUS/releases/geometry/aus_geometry_1_2_5/runtime/admin_spine/admin_0_3.parquet"
    stable_projection = "geometry/countries/AUS/admin_spine/exact/aus_geometry_1_2_5/admin_0_3.parquet"
    paths = released_artifact_paths_by_hash({
        "objects": [{
            "sha256": digest,
            "source_paths": [stable_projection, release_owned],
        }],
    })

    assert released_artifact_path(release_owned, digest, paths) == release_owned


def test_legacy_basename_still_fails_closed_when_multiple_paths_match() -> None:
    digest = "a" * 64
    paths = released_artifact_paths_by_hash({
        "objects": [{
            "sha256": digest,
            "source_paths": [
                "geometry/countries/AUS/releases/geometry/v1/runtime/admin_0_3.parquet",
                "geometry/countries/AUS/admin_spine/exact/v1/admin_0_3.parquet",
            ],
        }],
    })

    with pytest.raises(ValueError, match="ambiguous active paths"):
        released_artifact_path("legacy/admin_0_3.parquet", digest, paths)


def test_unknown_hash_fails_closed_without_source_path_fallback() -> None:
    original = "geometry/countries/USA/relationships/old/aliases.parquet"
    with pytest.raises(ValueError, match="absent from the active manifest"):
        released_artifact_path(original, "b" * 64, {})


def test_global_point_path_uses_clean_contract_in_cloud(tmp_path: Path) -> None:
    record = {"path": "geometry/global/runtime/admin_0_point.parquet"}
    assert global_admin0_point_path(tmp_path, record, cloud_mode=True) == (
        tmp_path / "geometry/global/runtime/admin_0_point.parquet"
    )
