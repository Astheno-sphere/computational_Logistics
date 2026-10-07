"""Closed-form tests for resample_raster.

Fixture: a 2x2 land-cover grid at 20 m in EPSG:32633, west column class 1
(forest), east column class 3 (water). The extent is 40x40 m, so resampling to
10 m gives exactly 4x4 cells, and nearest neighbour gives exactly two columns
of 1 and two of 3 — arithmetic, not approximation.

The interesting number is the wrong one: bilinear interpolates the cell centres
that fall between the old ones, producing the value 2 — a class that is not in
the file, and in a real legend means something else entirely (4 cells of
"urban" appearing on the boundary between forest and water). Nothing in the
raster stack says so, which is why the operation says so itself.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

rasterio = pytest.importorskip("rasterio")

import numpy as np
from rasterio.transform import from_origin

from mapsmith.engines import raster

CRS = "EPSG:32633"


@pytest.fixture
def landcover(tmp_path):
    path = tmp_path / "landcover.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=2,
        width=2,
        count=1,
        dtype="uint8",
        crs=CRS,
        transform=from_origin(500000, 4600000, 20, 20),
    ) as ds:
        ds.write(np.array([[1, 3], [1, 3]], dtype="uint8"), 1)
    return str(path)


def _manifest(output: Path) -> dict:
    return json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))


def test_nearest_keeps_the_class_codes_and_the_closed_form_shape(landcover, tmp_path):
    out = tmp_path / "near.tif"
    result = raster.resample(landcover, str(out), 10, "nearest")
    assert result["shape"] == [4, 4]  # 40 m extent / 10 m cells
    assert "invented_values" not in result
    with rasterio.open(out) as ds:
        data = ds.read(1)
        assert ds.crs.to_epsg() == 32633
        assert sorted(np.unique(data).tolist()) == [1, 3]
        assert int((data == 3).sum()) == 8  # two of four columns, four rows
    manifest = _manifest(out)
    assert manifest["operation"] == "resample_raster"
    assert manifest["parameters"]["resampling"] == "nearest"
    assert manifest["parameters"]["target_shape"] == [4, 4]


def test_bilinear_on_class_codes_reports_the_class_it_invented(landcover, tmp_path):
    out = tmp_path / "bilin.tif"
    result = raster.resample(landcover, str(out), 10, "bilinear")
    # The operation succeeds — the result is a valid raster — and says what it did.
    assert result["verified"] is True
    assert result["invented_values"] == [2.0]
    checks = {w["check"] for w in result["warnings"]}
    assert "x-mapsmith:no_invented_class_codes" in checks
    hint = next(w["hint"] for w in result["warnings"] if w["check"] == "x-mapsmith:no_invented_class_codes")
    assert "nearest or mode" in hint
    with rasterio.open(out) as ds:
        data = ds.read(1)
    assert int((data == 2).sum()) == 4  # one whole column of a class that never existed
    manifest = _manifest(out)
    failed = [c for c in manifest["verification"] if not c["passed"]]
    assert [c["name"] for c in failed] == ["x-mapsmith:no_invented_class_codes"]


def test_mode_is_treated_as_categorical_and_invents_nothing(landcover, tmp_path):
    out = tmp_path / "mode.tif"
    result = raster.resample(landcover, str(out), 10, "mode")
    assert "invented_values" not in result
    with rasterio.open(out) as ds:
        assert sorted(np.unique(ds.read(1)).tolist()) == [1, 3]


def test_a_continuous_raster_is_not_second_guessed(tmp_path):
    """The check exists for class codes. A float DEM resampled with bilinear is
    the correct thing to do, and must not collect a warning for doing it."""
    dem = tmp_path / "dem.tif"
    with rasterio.open(
        dem, "w", driver="GTiff", height=2, width=2, count=1, dtype="float32",
        crs=CRS, transform=from_origin(500000, 4600000, 20, 20),
    ) as ds:
        ds.write(np.array([[100.0, 300.0], [100.0, 300.0]], dtype="float32"), 1)
    result = raster.resample(str(dem), str(tmp_path / "dem10.tif"), 10, "bilinear")
    assert "invented_values" not in result
    assert not result.get("warnings")


def test_the_method_is_required_and_checked(landcover, tmp_path):
    with pytest.raises(ValueError, match="resampling must be one of"):
        raster.resample(landcover, str(tmp_path / "x.tif"), 10, "nonsense")
    # q1 exists in rasterio's enum but only works when warping: read() raises
    # ResamplingAlgorithmError. The refusal must name that, not leak the error.
    with pytest.raises(ValueError, match="valid only for warping"):
        raster.resample(landcover, str(tmp_path / "x.tif"), 10, "q1")
    with pytest.raises(ValueError, match="resolution must be positive"):
        raster.resample(landcover, str(tmp_path / "x.tif"), 0, "nearest")


def test_a_raster_without_a_crs_is_refused(tmp_path):
    naked = tmp_path / "naked.tif"
    with rasterio.open(
        naked, "w", driver="GTiff", height=2, width=2, count=1, dtype="uint8",
        transform=from_origin(0, 0, 20, 20),
    ) as ds:
        ds.write(np.array([[1, 3], [1, 3]], dtype="uint8"), 1)
    with pytest.raises(ValueError, match="declares no CRS"):
        raster.resample(str(naked), str(tmp_path / "x.tif"), 10, "nearest")


def test_run_operation_reaches_an_operation_that_has_no_tool(landcover, tmp_path):
    """resample_raster is the first operation with `tool: None` — the whole
    point of that field is that it is still callable."""
    from mapsmith.server import run_operation

    out = tmp_path / "via_run_operation.tif"
    result = run_operation(
        "resample_raster",
        {
            "input_path": landcover,
            "output_path": str(out),
            "resolution": 10,
            "resampling": "nearest",
        },
    )
    assert result["ran"] is True
    assert result["status"] == "ok"
    assert Path(f"{out}.provenance.json").exists()
