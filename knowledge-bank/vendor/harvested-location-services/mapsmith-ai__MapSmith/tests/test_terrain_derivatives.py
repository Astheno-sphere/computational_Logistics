"""Closed-form tests for slope and aspect (Whitebox engine).

The fixture is an inclined plane: z rises 10 m per 10 m cell eastward, so the
gradient is exactly 1 — slope 45 degrees / 100 percent, and the downslope
azimuth is exactly west (270). Whitebox approximates the outermost TWO cell
rings (measured on 2.0.6: ring 0 and ring 1 carry clamped-window values), so
the assertions read the grid from the third ring inward, where the plane
admits no tolerance: either the numbers are exact or something changed.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("whitebox_workflows")
rasterio = pytest.importorskip("rasterio")

from mapsmith.engines import whitebox_engine


def _write_dem(path: Path, data: np.ndarray, crs: str = "EPSG:32632", origin=(500_000, 5_000_000), cell=10.0) -> str:
    from rasterio.transform import from_origin

    with rasterio.open(
        path, "w", driver="GTiff",
        height=data.shape[0], width=data.shape[1], count=1, dtype="float32",
        crs=crs, transform=from_origin(*origin, cell, cell), nodata=-9999.0,
    ) as ds:
        ds.write(data.astype("float32"), 1)
    return str(path)


def _tilted() -> np.ndarray:
    """z = 10 * column on a 10 m grid: gradient exactly 1, rising eastward."""
    return np.tile(np.arange(10) * 10.0, (10, 1))


def _core(path: Path) -> np.ndarray:
    """The grid from the third ring inward, past the measured edge halo."""
    with rasterio.open(path) as ds:
        return ds.read(1)[2:-2, 2:-2]


def test_slope_of_a_unit_gradient_plane_is_exactly_45_degrees(tmp_path):
    dem = _write_dem(tmp_path / "tilted.tif", _tilted())
    out = tmp_path / "slope.tif"
    result = whitebox_engine.slope(dem, str(out))
    assert result["verified"] is True
    assert np.allclose(_core(out), 45.0, atol=1e-4)
    manifest = json.loads(Path(f"{out}.provenance.json").read_text(encoding="utf-8"))
    assert manifest["operation"] == "slope"
    assert manifest["parameters"]["units"] == "degrees"
    assert "projected" in manifest["crs_decisions"]["reason"]


def test_slope_in_percent_is_exactly_100(tmp_path):
    dem = _write_dem(tmp_path / "tilted.tif", _tilted())
    out = tmp_path / "slope_pct.tif"
    whitebox_engine.slope(dem, str(out), units="percent")
    assert np.allclose(_core(out), 100.0, atol=1e-4)


def test_aspect_of_an_east_rising_plane_faces_exactly_west(tmp_path):
    dem = _write_dem(tmp_path / "tilted.tif", _tilted())
    out = tmp_path / "aspect.tif"
    result = whitebox_engine.aspect(dem, str(out))
    assert result["verified"] is True
    # 270 = downslope azimuth. This pins the convention as much as the number:
    # if aspect ever starts meaning the UPSLOPE direction (90), this fails.
    assert np.allclose(_core(out), 270.0, atol=1e-4)


def test_aspect_flat_cells_are_minus_one_not_nodata(tmp_path):
    dem = _write_dem(tmp_path / "flat.tif", np.full((10, 10), 100.0))
    out = tmp_path / "aspect_flat.tif"
    whitebox_engine.aspect(dem, str(out))
    with rasterio.open(out) as ds:
        values = ds.read(1)
    # -1 everywhere, edges included: the flat marker is a VALUE, not nodata,
    # which is exactly why the tool docs tell callers to mask it.
    assert np.all(values == -1.0)


def test_a_geographic_crs_dem_is_refused(tmp_path):
    dem = _write_dem(
        tmp_path / "geo.tif", _tilted(), crs="EPSG:4326", origin=(12.0, 42.0), cell=0.001
    )
    with pytest.raises(ValueError, match="geographic"):
        whitebox_engine.slope(dem, str(tmp_path / "slope.tif"))
    with pytest.raises(ValueError, match="geographic"):
        whitebox_engine.aspect(dem, str(tmp_path / "aspect.tif"))


def test_unknown_slope_units_are_refused_with_the_valid_set(tmp_path):
    dem = _write_dem(tmp_path / "tilted.tif", _tilted())
    with pytest.raises(ValueError, match="degrees.*percent.*radians|units"):
        whitebox_engine.slope(dem, str(tmp_path / "slope.tif"), units="gradians")
