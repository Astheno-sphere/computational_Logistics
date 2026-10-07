"""Closed-form tests for the multi-layer container contract (issue #29).

The fixture mirrors Argleton's trap 006: `zones` written first (4 polygons,
which made it GDAL's silent default), `wells` second (31 points). The old
behaviour answered 4 to a question about wells, with no trace; these tests pin
the new contract — operations refuse with the layers named, inspection
describes every layer so the caller can choose.
"""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

from mapsmith import readers
from mapsmith.engines import vector

N_ZONES = 4
N_WELLS = 31


@pytest.fixture
def container(tmp_path):
    path = tmp_path / "project.gpkg"
    gpd.GeoDataFrame(
        {"zone_id": [f"Z-{i}" for i in range(N_ZONES)]},
        geometry=[
            Polygon([(i * 10, 0), (i * 10 + 8, 0), (i * 10 + 8, 8), (i * 10, 8)])
            for i in range(N_ZONES)
        ],
        crs="EPSG:32632",
    ).to_file(path, layer="zones", driver="GPKG")
    gpd.GeoDataFrame(
        {"well_id": [f"W-{i}" for i in range(N_WELLS)]},
        geometry=[Point(i, 100 + i) for i in range(N_WELLS)],
        crs="EPSG:32632",
    ).to_file(path, layer="wells", driver="GPKG")
    return str(path)


def test_operations_refuse_the_container_and_name_the_layers(container, tmp_path):
    with pytest.raises(ValueError) as excinfo:
        vector.buffer(container, 10.0, str(tmp_path / "out.parquet"))
    message = str(excinfo.value)
    assert "zones" in message and "wells" in message
    assert "describe_dataset" in message  # the message says where to look next


def test_describe_lists_every_layer_with_its_own_count(container):
    info = vector.describe(container)
    assert info["kind"] == "vector-container"
    assert info["layer_count"] == 2
    counts = {entry["layer"]: entry["feature_count"] for entry in info["layers"]}
    assert counts == {"zones": N_ZONES, "wells": N_WELLS}
    for entry in info["layers"]:
        assert entry["crs"] and "32632" in entry["crs"]


def test_a_single_layer_container_is_untouched_by_the_refusal(tmp_path):
    path = tmp_path / "wells.gpkg"
    gpd.GeoDataFrame(
        {"well_id": [1, 2, 3]},
        geometry=[Point(i, i) for i in range(3)],
        crs="EPSG:32632",
    ).to_file(path, layer="anything", driver="GPKG")
    assert len(readers.read_vector(str(path))) == 3
    assert vector.describe(str(path))["feature_count"] == 3
