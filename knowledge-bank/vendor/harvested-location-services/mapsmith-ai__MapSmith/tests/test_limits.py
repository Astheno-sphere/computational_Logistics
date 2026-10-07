"""The sample limit: counted from the lengths, refused before anything is allocated."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")

import geopandas as gpd
from rasterio.transform import from_origin
from shapely.geometry import LineString

from mapsmith import limits
from mapsmith.engines import linework, sampling


@pytest.fixture
def line(tmp_path) -> str:
    path = tmp_path / "line.gpkg"
    gpd.GeoDataFrame(geometry=[LineString([(0, 50), (1000, 50)])], crs="EPSG:32632").to_file(path)
    return str(path)


@pytest.fixture
def dem(tmp_path) -> str:
    path = tmp_path / "dem.tif"
    with rasterio.open(
        path, "w", driver="GTiff", height=10, width=110, count=1, dtype="float32",
        crs="EPSG:32632", transform=from_origin(-50.0, 100.0, 10.0, 10.0),
    ) as dst:
        dst.write(np.ones((1, 10, 110), dtype="float32"))
    return str(path)


def test_a_profile_over_the_limit_is_refused_with_the_count(monkeypatch, dem, line, tmp_path):
    """1000 m at 10 m is 101 points plus one for the end: over a limit of 50."""
    monkeypatch.setenv(limits.MAX_SAMPLES_ENV, "50")
    out = tmp_path / "p.parquet"
    with pytest.raises(ValueError, match=r"about 102 points, over this server's limit of 50"):
        sampling.elevation_profile(dem, line, str(out), spacing=10.0)
    assert not out.exists()


def test_under_the_limit_nothing_changes(monkeypatch, dem, line, tmp_path):
    monkeypatch.setenv(limits.MAX_SAMPLES_ENV, "200")
    result = sampling.elevation_profile(dem, line, str(tmp_path / "p.parquet"), spacing=10.0)
    assert result["points"] == 101


def test_points_along_lines_is_limited_too(monkeypatch, line, tmp_path):
    monkeypatch.setenv(limits.MAX_SAMPLES_ENV, "50")
    with pytest.raises(ValueError, match="points_along_lines .* over this server's limit"):
        linework.points_along_lines(line, str(tmp_path / "pts.parquet"), spacing=10.0)


def test_the_default_admits_an_ordinary_profile_and_stops_a_micrometre_spacing(dem, line, tmp_path):
    with pytest.raises(ValueError, match="MAPSMITH_MAX_SAMPLES"):
        sampling.elevation_profile(dem, line, str(tmp_path / "p.parquet"), spacing=1e-6)


@pytest.mark.parametrize("raw", ["lots", "0", "-3"])
def test_a_limit_that_is_not_a_positive_whole_number_is_refused(monkeypatch, raw):
    monkeypatch.setenv(limits.MAX_SAMPLES_ENV, raw)
    with pytest.raises(ValueError, match=limits.MAX_SAMPLES_ENV):
        limits.max_samples()


@pytest.mark.parametrize("spacing", [float("nan"), float("inf")])
def test_points_along_lines_refuses_a_spacing_that_is_not_finite(line, tmp_path, spacing):
    with pytest.raises(ValueError, match="positive finite"):
        linework.points_along_lines(line, str(Path(tmp_path) / "pts.parquet"), spacing=spacing)
