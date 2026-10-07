"""reproject_raster, extract_band and band_statistics: closed-form fixtures.

The band fixture is built so an off-by-one cannot hide: band 1 holds only 10s
and band 2 only 20s, so a wrong band is not a slightly different number, it is
the other number entirely.
"""

import json
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

rasterio = pytest.importorskip("rasterio")

import numpy as np
from rasterio import warp as rasterio_warp
from rasterio.transform import from_origin

from mapsmith.engines import raster


@pytest.fixture
def two_bands(tmp_path):
    """4x4, two bands of one value each, with a nodata corner in band 1.

    16 cells, 4 of them nodata in band 1: mean over the valid ones is exactly
    10.0 and the masked count is exactly 4.
    """
    path = tmp_path / "bands.tif"
    first = np.full((4, 4), 10.0, dtype="float32")
    first[0, 0] = first[0, 1] = first[1, 0] = first[1, 1] = -9999.0
    second = np.full((4, 4), 20.0, dtype="float32")
    with rasterio.open(
        path, "w", driver="GTiff", height=4, width=4, count=2, dtype="float32",
        crs="EPSG:32632", nodata=-9999.0,
        transform=from_origin(500000.0, 4500000.0, 25.0, 25.0),
    ) as dst:
        dst.write(first, 1)
        dst.write(second, 2)
        dst.set_band_description(1, "red")
        dst.set_band_description(2, "nir")
    return str(path)


def _manifest(result):
    return json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))


def _checks(result):
    return {c["name"]: c["passed"] for c in _manifest(result)["verification"]}


# ------------------------------------------------------------ extract_band


def test_extract_band_writes_only_that_band(two_bands, tmp_path):
    out = str(tmp_path / "b2.tif")
    result = raster.extract_band(two_bands, out, 2)
    with rasterio.open(out) as src:
        assert src.count == 1
        assert sorted(np.unique(src.read(1))) == [20.0]
    assert result["band"] == 2
    assert result["description"] == "nir"
    # Verified by the source's own checksum, not by trusting the index passed in.
    assert _checks(result)["x-mapsmith:band_content_matches_source"] is True


def test_extract_band_keeps_the_band_description(two_bands, tmp_path):
    out = str(tmp_path / "b1.tif")
    raster.extract_band(two_bands, out, 1)
    with rasterio.open(out) as src:
        assert src.descriptions[0] == "red"


@pytest.mark.parametrize("band", [0, 3, -1])
def test_extract_band_refuses_a_band_that_is_not_there(band, two_bands, tmp_path):
    """Refused, not clamped: reading the wrong band returns a valid raster of a
    different quantity, which nothing downstream can detect."""
    with pytest.raises(ValueError, match="band must be between 1 and 2"):
        raster.extract_band(two_bands, str(tmp_path / "x.tif"), band)


# --------------------------------------------------------- band_statistics


def test_band_statistics_excludes_nodata_and_says_how_many(two_bands):
    stats = raster.band_statistics(two_bands)
    assert stats["band_count"] == 2
    first, second = stats["bands"]
    assert first["valid_cells"] == 12
    assert first["masked_cells"] == 4
    assert first["mean"] == pytest.approx(10.0)
    assert first["sum"] == pytest.approx(120.0)
    assert first["std"] == pytest.approx(0.0)
    assert second["valid_cells"] == 16
    assert second["mean"] == pytest.approx(20.0)
    assert second["sum"] == pytest.approx(320.0)


def test_band_statistics_can_read_one_band(two_bands):
    stats = raster.band_statistics(two_bands, band=2)
    assert [row["band"] for row in stats["bands"]] == [2]


def test_band_statistics_says_all_masked_instead_of_a_mean_of_nothing(tmp_path):
    """A mean over an empty selection is not an answer, and numpy would return a
    nan that reads like a value."""
    path = tmp_path / "empty.tif"
    with rasterio.open(
        path, "w", driver="GTiff", height=2, width=2, count=1, dtype="float32",
        crs="EPSG:32632", nodata=-9999.0,
        transform=from_origin(0.0, 0.0, 1.0, 1.0),
    ) as dst:
        dst.write(np.full((2, 2), -9999.0, dtype="float32"), 1)
    row = raster.band_statistics(str(path))["bands"][0]
    assert row["all_masked"] is True
    assert row["valid_cells"] == 0
    assert "mean" not in row


def test_band_statistics_refuses_a_band_out_of_range(two_bands):
    with pytest.raises(ValueError, match="band must be between 1 and 2"):
        raster.band_statistics(two_bands, band=5)


# -------------------------------------------------------- reproject_raster


def test_reproject_raster_lands_in_the_requested_crs(two_bands, tmp_path):
    out = str(tmp_path / "wgs84.tif")
    result = raster.reproject_raster(two_bands, out, "EPSG:4326", "nearest")
    with rasterio.open(out) as src:
        assert src.crs.to_epsg() == 4326
        assert src.count == 2
    assert _checks(result)["crs_matches"] is True
    decisions = _manifest(result)["crs_decisions"]
    assert decisions["source_crs"] == "EPSG:32632"
    assert decisions["target_crs"] == "EPSG:4326"


def test_reproject_raster_requires_the_resampling_method(two_bands, tmp_path):
    """No default, because the right choice depends on whether the values are a
    surface or class codes — and getting it wrong is silent."""
    with pytest.raises(TypeError):
        raster.reproject_raster(two_bands, str(tmp_path / "x.tif"), "EPSG:4326")
    with pytest.raises(ValueError, match="resampling must be one of"):
        raster.reproject_raster(two_bands, str(tmp_path / "x.tif"), "EPSG:4326", "magic")


def test_reproject_raster_refuses_a_raster_without_a_crs(tmp_path):
    path = tmp_path / "nocrs.tif"
    with rasterio.open(
        path, "w", driver="GTiff", height=2, width=2, count=1, dtype="float32",
        transform=from_origin(0.0, 0.0, 1.0, 1.0),
    ) as dst:
        dst.write(np.ones((2, 2), dtype="float32"), 1)
    with pytest.raises(ValueError, match="declares no CRS"):
        raster.reproject_raster(str(path), str(tmp_path / "x.tif"), "EPSG:4326", "nearest")


@pytest.fixture
def class_codes(tmp_path):
    """A categorical raster: three codes, no intermediate values anywhere.

    INTEGER dtype on purpose. `_distinct_values` calls a raster categorical when
    it has an integer dtype and few distinct values, and says in its own
    docstring that this is a heuristic — a float raster of codes 1, 3, 5 is not
    recognised as one, so the invented-code check does not run on it. Writing
    this fixture as float32 first and expecting the check to fire was assuming
    the opposite of what the code states.
    """
    path = tmp_path / "classes.tif"
    data = np.tile(np.array([1, 1, 1, 1, 3, 3, 3, 3], dtype="int16"), (8, 1))
    with rasterio.open(
        path, "w", driver="GTiff", height=8, width=8, count=1, dtype="int16",
        crs="EPSG:32632", nodata=0,
        transform=from_origin(500000.0, 4500000.0, 25.0, 25.0),
    ) as dst:
        dst.write(data, 1)
    return str(path)


def test_an_interpolating_method_on_class_codes_is_flagged(class_codes, tmp_path):
    """'bilinear' averages neighbours, so a raster of codes 1 and 3 comes back
    holding a 2 that means nothing, and every count and area for it is fabricated.

    The target is EPSG:2263 rather than EPSG:4326, and the reason is worth
    knowing: this operation keeps the source's pixel COUNT, so a warp between two
    metre CRSs maps roughly cell to cell and barely interpolates at all -- with
    EPSG:4326 as the target, bilinear on this fixture invents nothing. A target
    whose unit is the US survey foot changes the ground size of a cell by a
    factor of three, which forces real sub-pixel sampling. So the hazard is not
    "reprojection" in general: it is reprojection that actually resamples, and
    changing the unit guarantees it.
    """
    out = str(tmp_path / "bad.tif")
    result = raster.reproject_raster(class_codes, out, "EPSG:2263", "bilinear")
    assert _checks(result)["x-mapsmith:no_invented_class_codes"] is False
    assert result["invented_values"] == [2.0]
    hint = next(
        w["hint"] for w in result["warnings"]
        if w["check"] == "x-mapsmith:no_invented_class_codes"
    )
    assert "nearest or mode" in hint
    # It is a warning, not a refusal: the raster is valid and the caller is told.
    assert result["verified"] is True


def test_a_metre_to_metre_warp_of_the_same_codes_invents_nothing(class_codes, tmp_path):
    """The other half of the statement above, so it cannot rot into folklore:
    the same fixture and the same interpolating method, into a CRS whose unit is
    also the metre, comes back with only the source's codes."""
    out = str(tmp_path / "same_unit.tif")
    result = raster.reproject_raster(class_codes, out, "EPSG:4326", "bilinear")
    assert result.get("invented_values") is None
    with rasterio.open(out) as src:
        assert set(np.unique(src.read(1))) <= {0, 1, 3}


def test_nearest_on_class_codes_invents_nothing(class_codes, tmp_path):
    out = str(tmp_path / "good.tif")
    result = raster.reproject_raster(class_codes, out, "EPSG:2263", "nearest")
    # nearest is not checked for invented codes because it cannot invent any:
    # every output value is some input value by construction.
    assert "invented_values" not in result
    with rasterio.open(out) as src:
        values = set(np.unique(src.read(1)))
    assert values <= {0, 1, 3}


def test_reprojection_is_not_expected_to_preserve_the_shape(two_bands, tmp_path):
    """A warped grid has a new shape and new corners, so the check is on the CRS
    and on emptiness — asserting the shape would fail for the right reason and
    be reported as the wrong one."""
    out = str(tmp_path / "shape.tif")
    result = raster.reproject_raster(two_bands, out, "EPSG:4326", "nearest")
    names = set(_checks(result))
    assert "crs_matches" in names and "result_not_empty" in names
    assert "shape_preserved" not in names


def test_a_clip_layer_is_not_needed_for_any_of_this(two_bands, tmp_path):
    """Guard against a fixture drifting into something that needs a vector: all
    three operations here are raster-only."""
    unused = gpd.GeoDataFrame(
        geometry=[Polygon([(0, 0), (1, 0), (1, 1)])], crs="EPSG:32632"
    )
    assert len(unused) == 1
    assert raster.band_statistics(two_bands)["band_count"] == 2


def test_a_requested_cell_size_is_the_cell_size_delivered(tmp_path):
    """The number the caller named, on disk, on a grid that does not divide evenly.

    A 100 m extent asked to become 30 m cells used to deliver 33.333 m —
    `round(extent / resolution)` cells across the same ground — while the
    manifest recorded `"resolution": 30.0` and a check called
    `shape_matches_resolution` passed, because it compared the shape on disk to
    the shape we had computed rather than to the resolution in its own name.
    An 11% cell error is a 23% area error for anyone multiplying by cell size.

    Chosen so the extent does NOT divide evenly: 100/30 is 3.33, so the grid has
    to grow to 4 cells and 120 m rather than shrink the cells to fit.
    """
    import json

    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    source = tmp_path / "source.tif"
    with rasterio.open(
        source, "w", driver="GTiff", height=10, width=10, count=1,
        dtype="float32", crs="EPSG:32632", transform=from_origin(0, 100, 10, 10),
    ) as dst:
        dst.write(np.arange(100, dtype="float32").reshape(10, 10), 1)

    out = tmp_path / "out.tif"
    raster.resample(str(source), str(out), resolution=30.0, resampling="bilinear")

    with rasterio.open(out) as ds:
        assert ds.transform.a == pytest.approx(30.0, abs=1e-9)
        assert -ds.transform.e == pytest.approx(30.0, abs=1e-9)
        assert (ds.height, ds.width) == (4, 4), (
            "100 m of ground at 30 m per cell is four cells, not three: rounding "
            "down is how the cell size started bending to fit the extent"
        )

    manifest = json.loads((tmp_path / "out.tif.provenance.json").read_text(encoding="utf-8"))
    named = {c["name"]: c["passed"] for c in manifest["verification"]}
    assert named["x-mapsmith:cell_size_is_what_was_asked"] is True
    assert any("does not divide evenly" in note for note in manifest.get("notes", [])), (
        "the output covers more ground than the input and the manifest does not "
        "say so, which is the sort of silence that turns up in someone's area total"
    )


def test_an_evenly_dividing_extent_gains_no_phantom_cell(tmp_path):
    """`ceil` with no tolerance would add a column to floating-point noise.

    100 m at 25 m is exactly four cells. If `(right - left) / resolution` lands
    on 4.0000000001 the grid should still be four wide.
    """
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    source = tmp_path / "even.tif"
    with rasterio.open(
        source, "w", driver="GTiff", height=10, width=10, count=1,
        dtype="float32", crs="EPSG:32632", transform=from_origin(0, 100, 10, 10),
    ) as dst:
        dst.write(np.ones((10, 10), dtype="float32"), 1)

    out = tmp_path / "even_out.tif"
    raster.resample(str(source), str(out), resolution=25.0, resampling="bilinear")
    with rasterio.open(out) as ds:
        assert (ds.height, ds.width) == (4, 4)
        assert ds.transform.a == pytest.approx(25.0, abs=1e-9)


def test_reproject_with_a_resolution_delivers_square_cells_of_that_size(tmp_path):
    """Reprojection derived the cell size from the reprojected extent, so a
    requested 30 arrived as 33.24 by 33.47 — not even square, under a manifest
    that said 30."""
    import json

    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    source = tmp_path / "src.tif"
    with rasterio.open(
        source, "w", driver="GTiff", height=10, width=10, count=1,
        dtype="float32", crs="EPSG:32632", transform=from_origin(0, 100, 10, 10),
    ) as dst:
        dst.write(np.arange(100, dtype="float32").reshape(10, 10), 1)

    out = tmp_path / "reprojected.tif"
    raster.reproject_raster(
        str(source), str(out), target_crs="EPSG:3857",
        resampling="bilinear", resolution=30.0,
    )
    with rasterio.open(out) as ds:
        assert ds.transform.a == pytest.approx(30.0, abs=1e-9)
        assert -ds.transform.e == pytest.approx(30.0, abs=1e-9)

    manifest = json.loads(
        (tmp_path / "reprojected.tif.provenance.json").read_text(encoding="utf-8")
    )
    named = {c["name"]: c["passed"] for c in manifest["verification"]}
    assert named["x-mapsmith:cell_size_is_what_was_asked"] is True


def test_a_warp_that_dies_halfway_leaves_a_manifest_beside_the_partial_file(
    tmp_path, monkeypatch
):
    """Invariant 2 on the path where it is easiest to lose: a crash mid-write.

    `reproject_raster` opens the destination and then warps band by band, so a
    warp that raises on band two leaves a file on disk that is real, plausible
    and partial -- bands two and three zero-filled. It had no
    `audit_on_failure`, so no manifest was written beside it, and "a dataset
    with no lineage beside it did not come from here" became false.

    The `conformita-manifest` agent spotted the missing audit on 2026-09-23 by
    reading the source and said so as an INFERENCE, to be measured before being
    treated as a fact. Measured: a 19608-byte raster on disk, no manifest.

    The same run fixes the other half. `target_crs` and `transformation` said
    where the pixels went, and were written before the warp -- the defect found
    in `reproject_layer` the same day, in the raster twin nobody had looked at.
    """
    src = tmp_path / "three_bands.tif"
    with rasterio.open(
        src, "w", driver="GTiff", height=40, width=40, count=3, dtype="float32",
        crs="EPSG:32632", transform=from_origin(500000, 5000000, 30, 30),
    ) as dst:
        for band in (1, 2, 3):
            dst.write(np.full((40, 40), float(band), dtype="float32"), band)

    real_warp = rasterio_warp.reproject
    calls = {"n": 0}

    def warp_that_dies_on_the_second_band(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("warp failed on band 2")
        return real_warp(*args, **kwargs)

    monkeypatch.setattr(rasterio_warp, "reproject", warp_that_dies_on_the_second_band)

    out = tmp_path / "out.tif"
    with pytest.raises(RuntimeError, match="warp failed on band 2"):
        raster.reproject_raster(str(src), str(out), "EPSG:4326", "nearest")

    assert out.exists(), (
        "the destination was created and partially written, which is the "
        "premise of this test: if it stopped being created before the failure, "
        "there is no orphan to guard against and this test guards nothing"
    )
    manifest_path = Path(f"{out}.provenance.json")
    assert manifest_path.exists(), (
        "a partial raster is on disk with no manifest beside it, which is "
        "invariant 2 broken on exactly the path where the lineage matters most"
    )
    written = json.loads(manifest_path.read_text(encoding="utf-8"))
    for claim in ("target_crs", "transformation"):
        assert claim not in written["crs_decisions"], (
            f"the warp raised and the manifest still reports {claim!r}: it says "
            "where the pixels were put, and they were not put there"
        )
    assert written["crs_decisions"]["source_crs"] == "EPSG:32632", (
        "what was true before the attempt has to survive it: "
        f"{written['crs_decisions']}"
    )
    completed = [
        c for c in written["verification"]
        if c["name"] == "x-mapsmith:operation_completed"
    ]
    assert completed and completed[0]["passed"] is False, (
        "the record has to say the run did not finish, or a consumer reads a "
        f"partial raster as a finished one: {written['verification']}"
    )
