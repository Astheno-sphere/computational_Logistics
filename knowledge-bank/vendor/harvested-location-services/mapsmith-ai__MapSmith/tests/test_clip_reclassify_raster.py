"""Closed-form tests for clip_raster and reclassify_raster.

Fixture: a 4x4 grid of 10 m cells in EPSG:32633 holding the values 0..15 in
reading order, so every cell is identifiable by its value. The north-west
quadrant is exactly the cells 0, 1, 4, 5 — a clip to that quadrant either
returns those four numbers or it is wrong, with nothing to interpret.

Reclassify: 16 cells, 0..15. The intervals [0,8) and [8,16) split them exactly
in half, and the boundary cell (8) belongs to the second — which is the whole
contract of half-open ranges, and the off-by-one this operation is built to
make explicit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

rasterio = pytest.importorskip("rasterio")

import geopandas as gpd
import numpy as np
from rasterio.transform import from_origin
from shapely.geometry import box

from mapsmith.engines import raster

CRS = "EPSG:32633"
ORIGIN_X, ORIGIN_Y, CELL = 500000.0, 4600000.0, 10.0


@pytest.fixture
def grid(tmp_path):
    path = tmp_path / "grid.tif"
    with rasterio.open(
        path, "w", driver="GTiff", height=4, width=4, count=1, dtype="int16",
        crs=CRS, transform=from_origin(ORIGIN_X, ORIGIN_Y, CELL, CELL), nodata=-9999,
    ) as ds:
        ds.write(np.arange(16, dtype="int16").reshape(4, 4), 1)
    return str(path)


@pytest.fixture
def quadrant(tmp_path):
    """The north-west 2x2 cells: values 0, 1, 4, 5."""
    path = tmp_path / "mask.gpkg"
    gpd.GeoDataFrame(
        {"i": [1]},
        geometry=[box(ORIGIN_X, ORIGIN_Y - 2 * CELL, ORIGIN_X + 2 * CELL, ORIGIN_Y)],
        crs=CRS,
    ).to_file(path, driver="GPKG")
    return str(path)


def _manifest(output: Path) -> dict:
    return json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))


def test_clip_returns_exactly_the_masked_cells(grid, quadrant, tmp_path):
    out = tmp_path / "clip.tif"
    result = raster.clip_raster(grid, quadrant, str(out))
    assert result["shape"] == [2, 2]
    assert result["valid_cells"] == 4
    with rasterio.open(out) as ds:
        assert ds.read(1).tolist() == [[0, 1], [4, 5]]
        assert ds.crs.to_epsg() == 32633
    manifest = _manifest(out)
    assert manifest["operation"] == "clip_raster"
    # Nothing moved, and the record says so by carrying no `inputs_reprojected`
    # rather than by being empty — those are different claims.
    decisions = manifest["crs_decisions"]
    assert "nothing was reprojected" in decisions["reason"]
    assert "x-mapsmith:inputs_reprojected" not in decisions


def test_clip_reprojects_the_mask_and_records_it(grid, quadrant, tmp_path):
    """rasterio.mask never checks the CRS: two systems that overlap numerically
    clip the wrong area in silence. The mask is moved here, on purpose."""
    geographic = tmp_path / "mask4326.gpkg"
    gpd.read_file(quadrant).to_crs("EPSG:4326").to_file(geographic, driver="GPKG")
    out = tmp_path / "clip_geo.tif"
    result = raster.clip_raster(grid, str(geographic), str(out))
    manifest = _manifest(out)
    # Which input moved and how. `rasterio.mask` does not check CRS, so a
    # ballpark here clips the wrong area and says nothing.
    decisions = manifest["crs_decisions"]
    assert decisions["x-mapsmith:inputs_reprojected"] == [
        {"argument": "mask_path", "from": "EPSG:4326"}
    ]
    assert decisions["transformation"]["is_ballpark"] is False
    # The round trip through degrees costs a fraction of a cell at the edges,
    # so the clip may keep one extra row or column — never a different area.
    assert result["shape"][0] <= 3 and result["shape"][1] <= 3
    with rasterio.open(out) as ds:
        values = set(ds.read(1, masked=True).compressed().tolist())
    assert {0, 1, 4, 5} <= values


def test_clip_refuses_a_raster_without_a_crs(quadrant, tmp_path):
    naked = tmp_path / "naked.tif"
    with rasterio.open(
        naked, "w", driver="GTiff", height=4, width=4, count=1, dtype="int16",
        transform=from_origin(0, 0, CELL, CELL),
    ) as ds:
        ds.write(np.arange(16, dtype="int16").reshape(4, 4), 1)
    with pytest.raises(ValueError, match="declares no CRS"):
        raster.clip_raster(str(naked), quadrant, str(tmp_path / "x.tif"))


def test_clip_notes_a_missing_nodata_value(quadrant, tmp_path):
    """Without a declared nodata, rasterio fills the outside with 0 — a legal
    elevation. The manifest has to say so."""
    no_nodata = tmp_path / "no_nodata.tif"
    with rasterio.open(
        no_nodata, "w", driver="GTiff", height=4, width=4, count=1, dtype="int16",
        crs=CRS, transform=from_origin(ORIGIN_X, ORIGIN_Y, CELL, CELL),
    ) as ds:
        ds.write(np.arange(16, dtype="int16").reshape(4, 4), 1)
    out = tmp_path / "clip_nonodata.tif"
    raster.clip_raster(str(no_nodata), quadrant, str(out))
    assert any("no nodata value" in note for note in _manifest(out)["notes"])


def test_reclassify_splits_exactly_in_half(grid, tmp_path):
    out = tmp_path / "rc.tif"
    result = raster.reclassify(grid, str(out), ["0:8:1", "8:16:2"])
    assert result["codes"] == [1.0, 2.0]
    assert result["unmapped_cells"] == 0
    with rasterio.open(out) as ds:
        data = ds.read(1)
    assert int((data == 1).sum()) == 8  # values 0..7
    assert int((data == 2).sum()) == 8  # values 8..15
    manifest = _manifest(out)
    assert manifest["parameters"]["bounds"] == "low inclusive, high exclusive"


def test_the_boundary_value_belongs_to_the_upper_interval(grid, tmp_path):
    """Half-open by contract: a cell of exactly 8 is in [8, 16), not [0, 8)."""
    out = tmp_path / "rc_boundary.tif"
    raster.reclassify(grid, str(out), ["0:8:10", "8:9:20", "9:16:30"])
    with rasterio.open(out) as ds:
        data = ds.read(1)
    assert int((data == 20).sum()) == 1  # the single cell whose value is 8


def test_unmapped_cells_become_nodata_and_are_counted(grid, tmp_path):
    out = tmp_path / "rc_partial.tif"
    result = raster.reclassify(grid, str(out), ["0:8:1"])
    assert result["unmapped_cells"] == 8
    with rasterio.open(out) as ds:
        band = ds.read(1, masked=True)
    assert int(band.count()) == 8  # only the mapped half carries data
    assert any("outside every interval" in note for note in _manifest(out)["notes"])


def test_overlapping_and_malformed_intervals_are_refused(grid, tmp_path):
    with pytest.raises(ValueError, match="overlap"):
        raster.reclassify(grid, str(tmp_path / "x.tif"), ["0:10:1", "5:20:2"])
    with pytest.raises(ValueError, match="must be 'low:high:new'"):
        raster.reclassify(grid, str(tmp_path / "x.tif"), ["0-10-1"])
    with pytest.raises(ValueError, match="low must be less than high"):
        raster.reclassify(grid, str(tmp_path / "x.tif"), ["10:10:1"])
    with pytest.raises(ValueError, match="non-numeric"):
        raster.reclassify(grid, str(tmp_path / "x.tif"), ["a:b:1"])


def test_both_are_reachable_through_run_operation(grid, quadrant, tmp_path):
    from mapsmith.server import run_operation

    clipped = run_operation(
        "clip_raster",
        {
            "raster_path": grid,
            "mask_path": quadrant,
            "output_path": str(tmp_path / "via_ro.tif"),
        },
    )
    assert clipped["ran"] is True
    reclassified = run_operation(
        "reclassify_raster",
        {
            "input_path": grid,
            "output_path": str(tmp_path / "via_ro_rc.tif"),
            "intervals": ["0:8:1", "8:16:2"],
        },
    )
    assert reclassified["ran"] is True
