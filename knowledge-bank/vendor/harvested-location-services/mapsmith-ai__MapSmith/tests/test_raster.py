"""Zonal statistics: exact deterministic values, CRS discipline, provenance."""

import json
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

exactextract = pytest.importorskip("exactextract")
rasterio = pytest.importorskip("rasterio")

import numpy as np
from rasterio.transform import from_origin

from mapsmith.engines import raster


@pytest.fixture()
def dem(tmp_path):
    """10x10 raster, 1-unit pixels, UL corner (0,10), value = row*10+col."""
    data = np.arange(100, dtype=np.float32).reshape(10, 10)
    path = tmp_path / "dem.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype="float32",
        crs="EPSG:32631",
        transform=from_origin(0.0, 10.0, 1.0, 1.0),
    ) as dst:
        dst.write(data, 1)
    return str(path)


@pytest.fixture()
def zone(tmp_path):
    """One zone covering exactly the top-left 5x5 pixel block (values 0..44)."""
    gdf = gpd.GeoDataFrame(
        {"zone_id": ["A"]}, geometry=[box(0.0, 5.0, 5.0, 10.0)], crs="EPSG:32631"
    )
    path = tmp_path / "zones.gpkg"
    gdf.to_file(path)
    return str(path)


def test_zonal_exact_values(dem, zone, tmp_path):
    out = tmp_path / "stats.parquet"
    result = raster.zonal_statistics(dem, zone, str(out), ["count", "mean", "min", "max", "sum"])
    assert result["verified"] is True
    gdf = gpd.read_parquet(out)
    row = gdf.iloc[0]
    # top-left 5x5 block: values r*10+c for r,c in 0..4 → known closed-form results
    assert row["count"] == pytest.approx(25.0)
    assert row["mean"] == pytest.approx(22.0)
    assert row["min"] == pytest.approx(0.0)
    assert row["max"] == pytest.approx(44.0)
    assert row["sum"] == pytest.approx(550.0)
    assert row["zone_id"] == "A"  # original attributes carried through


def test_zonal_crs_realignment_recorded(dem, zone, tmp_path):
    # declare zones in EPSG:4326: the engine must reproject and record the decision
    zones_4326 = gpd.read_file(zone).to_crs("EPSG:4326")
    z_path = tmp_path / "zones4326.gpkg"
    zones_4326.to_file(z_path)
    out = tmp_path / "stats2.parquet"
    result = raster.zonal_statistics(dem, str(z_path), str(out), ["count", "mean"])
    manifest = json.loads((tmp_path / "stats2.parquet.provenance.json").read_text())
    # The zones carry the pixel footprints, so a ballpark here weights the
    # wrong cells — named, with its transformation, rather than described.
    decisions = manifest["crs_decisions"]
    assert decisions["x-mapsmith:inputs_reprojected"] == [
        {"argument": "zones_path", "from": "EPSG:4326"}
    ]
    assert decisions["transformation"]["is_ballpark"] is False
    gdf = gpd.read_parquet(out)
    assert gdf.iloc[0]["mean"] == pytest.approx(22.0, abs=0.5)  # round-trip tolerance
    assert result["feature_count"] == 1


def test_zonal_rejects_unknown_stat(dem, zone, tmp_path):
    with pytest.raises(ValueError, match="stdev"):
        raster.zonal_statistics(dem, zone, str(tmp_path / "x.parquet"), ["std"])


def _weights(tmp_path, data, *, name="w.tif", crs="EPSG:32631", transform=None, nodata=-1.0):
    data = np.asarray(data, dtype=np.float32)
    bands = data if data.ndim == 3 else data[None]
    path = tmp_path / name
    with rasterio.open(
        path, "w", driver="GTiff", height=bands.shape[1], width=bands.shape[2],
        count=bands.shape[0], dtype="float32", crs=crs,
        transform=transform or from_origin(0.0, 10.0, 1.0, 1.0), nodata=nodata,
    ) as dst:
        dst.write(bands)
    return str(path)


def _column_weights():
    """weight = column + 1, so the right of the zone counts more than the left."""
    return np.tile(np.arange(1, 11, dtype=np.float32), (10, 1))


def test_weighted_mean_and_sum_in_closed_form(dem, zone, tmp_path):
    """Values r*10+c, weights c+1, the 5x5 block: sum(w) = 5*15 = 75 and
    sum(x*w) = sum_r(10r*15) + 5*sum_c(c(c+1)) = 1500 + 200 = 1700."""
    weights = _weights(tmp_path, _column_weights())
    out = tmp_path / "w.parquet"
    result = raster.zonal_statistics(
        dem, zone, str(out), ["mean", "weighted_mean", "weighted_sum"], weights_path=weights
    )
    row = gpd.read_parquet(out).iloc[0]
    assert row["mean"] == pytest.approx(22.0)
    assert row["weighted_mean"] == pytest.approx(1700 / 75)
    assert row["weighted_sum"] == pytest.approx(1700.0)
    manifest = json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))
    assert [i["path"].rsplit("/", 1)[-1] for i in manifest["inputs"]] == [
        "dem.tif", "zones.gpkg", "w.tif"
    ]
    assert manifest["parameters"]["weight_of_a_cell_with_no_weight"] == 0.0
    # By name, not only by position: inputs[] order is not significant (schema).
    assert manifest["parameters"]["weights_path"].endswith("/w.tif")
    check = next(
        c for c in manifest["verification"]
        if c["name"] == "x-mapsmith:every_valued_cell_has_a_weight"
    )
    assert check["passed"] is True


def test_a_cell_with_no_weight_counts_zero_and_the_zone_is_named(dem, zone, tmp_path):
    """exactextract's own default turns the whole zone's weighted statistics
    into NaN for ONE nodata weight (measured). The cell (0,0) has value 0 and
    weight 1: without it sum(w) = 74 and sum(x*w) is still 1700."""
    data = _column_weights()
    data[0, 0] = -1.0
    weights = _weights(tmp_path, data)
    out = tmp_path / "hole.parquet"
    result = raster.zonal_statistics(
        dem, zone, str(out), ["weighted_mean"], weights_path=weights
    )
    assert gpd.read_parquet(out).iloc[0]["weighted_mean"] == pytest.approx(1700 / 74)
    manifest = json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))
    check = next(
        c for c in manifest["verification"]
        if c["name"] == "x-mapsmith:every_valued_cell_has_a_weight"
    )
    assert check["passed"] is False and check["critical"] is False
    assert "rows [0]" in check["detail"]


@pytest.mark.parametrize(
    "case, match",
    [
        ("other_grid", "its grid is"),
        ("other_crs", "is in EPSG:32632"),
        ("two_bands", "2 bands"),
        ("negative", "negative weight"),
    ],
)
def test_weights_off_the_value_grid_are_refused(dem, zone, tmp_path, case, match):
    """exactextract accepts a coarser weights grid and repeats each coarse cell
    in every fine one -- a weighted_sum inflated k*k times for a count -- and
    never compares the two CRSs. Refused, with how to align them."""
    if case == "other_grid":
        weights = _weights(
            tmp_path, np.ones((5, 5)), transform=from_origin(0.0, 10.0, 2.0, 2.0)
        )
    elif case == "other_crs":
        weights = _weights(tmp_path, _column_weights(), crs="EPSG:32632")
    elif case == "two_bands":
        weights = _weights(tmp_path, np.stack([_column_weights(), _column_weights()]))
    else:
        data = _column_weights()
        data[3, 3] = -5.0
        weights = _weights(tmp_path, data, nodata=-9999.0)
    with pytest.raises(ValueError, match=match):
        raster.zonal_statistics(
            dem, zone, str(tmp_path / "x.parquet"), ["weighted_mean"], weights_path=weights
        )


def test_a_nan_weight_is_a_missing_weight_and_does_not_hide_a_negative(dem, zone, tmp_path):
    """Measured by the 0.6.2 pre-release review on the first version, which
    read the band with numpy: one NaN made the minimum NaN, `nan < 0` was
    false, and a -5 weight went through to a plausible wrong mean. And the
    check passed a zone that had lost a NaN-weighted cell."""
    data = _column_weights()
    data[0, 0] = np.nan  # value 0, weight 1: out of the weighted statistics
    weights = _weights(tmp_path, data, name="nan.tif", nodata=-9999.0)
    out = tmp_path / "nan.parquet"
    result = raster.zonal_statistics(dem, zone, str(out), ["weighted_mean"], weights_path=weights)
    assert gpd.read_parquet(out).iloc[0]["weighted_mean"] == pytest.approx(1700 / 74)
    manifest = json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))
    check = next(
        c for c in manifest["verification"]
        if c["name"] == "x-mapsmith:every_valued_cell_has_a_weight"
    )
    assert check["passed"] is False and "rows [0]" in check["detail"]

    data[3, 3] = -5.0
    weights = _weights(tmp_path, data, name="nanneg.tif", nodata=-9999.0)
    with pytest.raises(ValueError, match="negative weights"):
        raster.zonal_statistics(
            dem, zone, str(tmp_path / "nn.parquet"), ["weighted_mean"], weights_path=weights
        )


def test_a_negative_weight_outside_every_zone_changes_nothing_and_is_not_refused(
    dem, zone, tmp_path
):
    data = _column_weights()
    data[9, 9] = -5.0  # the zone is the top-left 5x5 block
    weights = _weights(tmp_path, data, nodata=-9999.0)
    out = tmp_path / "far.parquet"
    raster.zonal_statistics(dem, zone, str(out), ["weighted_mean"], weights_path=weights)
    assert gpd.read_parquet(out).iloc[0]["weighted_mean"] == pytest.approx(1700 / 75)


def test_a_cell_with_neither_value_nor_weight_is_not_a_lost_cell(zone, tmp_path):
    """The other half of what the first check got wrong: a NaN VALUE with a
    missing weight on the same cell was reported as a cell lost to the
    weights, when it had no value to lose."""
    data = np.arange(100, dtype=np.float32).reshape(10, 10)
    data[0, 0] = np.nan
    values = tmp_path / "nanvalues.tif"
    with rasterio.open(
        values, "w", driver="GTiff", height=10, width=10, count=1, dtype="float32",
        crs="EPSG:32631", transform=from_origin(0.0, 10.0, 1.0, 1.0),
    ) as dst:
        dst.write(data, 1)
    weights_data = _column_weights()
    weights_data[0, 0] = -1.0
    weights = _weights(tmp_path, weights_data)
    result = raster.zonal_statistics(
        str(values), zone, str(tmp_path / "both.parquet"), ["weighted_mean"], weights_path=weights
    )
    manifest = json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))
    check = next(
        c for c in manifest["verification"]
        if c["name"] == "x-mapsmith:every_valued_cell_has_a_weight"
    )
    assert check["passed"] is True, check["detail"]


@pytest.mark.parametrize("case, match", [
    ("same_shape_other_origin", "its grid is"),
    ("finer_degrees", "its grid is"),
    ("no_crs", "declares no CRS"),
])
def test_the_grid_comparison_catches_what_shape_alone_does_not(dem, zone, tmp_path, case, match):
    """The first grid test changed the shape too, so the transform comparison
    was never exercised on its own; and its tolerance was an absolute 1e-5,
    which accepted a 1.8e-5 degree grid beside a 9e-6 one."""
    if case == "same_shape_other_origin":
        weights = _weights(tmp_path, _column_weights(), transform=from_origin(0.5, 10.0, 1.0, 1.0))
    elif case == "finer_degrees":
        values = tmp_path / "deg.tif"
        with rasterio.open(
            values, "w", driver="GTiff", height=10, width=10, count=1, dtype="float32",
            crs="EPSG:4326", transform=from_origin(12.0, 42.0, 9e-6, 9e-6),
        ) as dst:
            dst.write(np.ones((10, 10), dtype=np.float32), 1)
        dem = str(values)
        gpd.GeoDataFrame(
            geometry=[box(12.0, 42.0 - 9e-5, 12.0 + 9e-5, 42.0)], crs="EPSG:4326"
        ).to_file(tmp_path / "degzone.gpkg")
        zone = str(tmp_path / "degzone.gpkg")
        weights = _weights(
            tmp_path, _column_weights(), crs="EPSG:4326",
            transform=from_origin(12.0, 42.0, 1.8e-5, 1.8e-5),
        )
    else:
        weights = _weights(tmp_path, _column_weights(), crs=None)
    with pytest.raises(ValueError, match=match):
        raster.zonal_statistics(
            dem, zone, str(tmp_path / "g.parquet"), ["weighted_mean"], weights_path=weights
        )


def test_point_registered_weights_on_the_same_grid_are_the_same_weights(dem, zone, tmp_path):
    """Refused until 2026-09-25 as "one is point-registered and the other
    area-registered". On the same geotransform the two have their samples in
    the same places -- GDAL has already folded the tag into the transform
    (D-096) -- so refusing them refused two grids that line up."""
    area = _weights(tmp_path, _column_weights())
    point = tmp_path / "point_weights.tif"
    point.write_bytes(Path(area).read_bytes())
    with rasterio.open(point, "r+") as dst:
        dst.update_tags(AREA_OR_POINT="Point")
    means = []
    for weights in (area, str(point)):
        out = tmp_path / f"{Path(weights).stem}.parquet"
        raster.zonal_statistics(dem, zone, str(out), ["weighted_mean"], weights_path=weights)
        means.append(gpd.read_parquet(out)["weighted_mean"].iloc[0])
    assert means[0] == pytest.approx(means[1])


@pytest.mark.parametrize("sidecars", ["weights_only", "both"])
def test_each_raster_s_georeferencing_facts_stay_with_that_raster(dem, zone, tmp_path, sidecars):
    """Every input's facts used to be merged into one flat `environment`: with
    a sidecar beside the weights only, the record said `internal` next to the
    weights' sidecar name -- two files described as one -- and with a sidecar
    beside both, the weights' disappeared (conformita-manifest review)."""
    weights = _weights(tmp_path, _column_weights())
    agreeing = '<PAMDataset><SRS>EPSG:32631</SRS></PAMDataset>'
    Path(f"{weights}.aux.xml").write_text(agreeing, encoding="utf-8")
    if sidecars == "both":
        Path(f"{dem}.aux.xml").write_text(agreeing, encoding="utf-8")
    result = raster.zonal_statistics(
        dem, zone, str(tmp_path / "e.parquet"), ["weighted_mean"], weights_path=weights
    )
    record = json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))
    # The only shipped path that writes `inputs[].environment`, and the
    # conformance sweep has no fixture with a sidecar: without this line the
    # field reaches records without either implementation of the spec seeing it.
    from conftest import _spec_problems

    assert _spec_problems(record) == []
    # Spec draft.10: each input says which argument read it, so swapping values
    # and weights is visible in the record and not only in the file names.
    assert [i["argument"] for i in record["inputs"]] == [
        "raster_path", "zones_path", "weights_path"
    ]
    on_weights = record["inputs"][2]["environment"]
    assert on_weights["x-mapsmith:georeferencing_sidecar_present"] == "w.tif.aux.xml"
    # With several inputs no FILE fact sits on the record: the format reads the
    # record-level `environment` as true of the whole run, and the order of
    # `inputs` means nothing (draft.10, section 3.8). The DEM's sidecar is on
    # the DEM's own entry, the first one included.
    environment = record.get("environment", {})
    assert not [k for k in environment if k.startswith("x-mapsmith:")], environment
    if sidecars == "weights_only":
        assert "environment" not in record["inputs"][0]
    else:
        on_dem = record["inputs"][0]["environment"]
        assert on_dem["x-mapsmith:georeferencing_sidecar_present"] == "dem.tif.aux.xml"
    assert "x-mapsmith:environment" not in record["inputs"][2]
    # And the history carries both, which it did not: `get_lineage` kept the
    # record-level `environment` and dropped each input's own.
    from mapsmith import lineage

    [step] = lineage.lineage(result["output"], scan_root=tmp_path)["steps"]
    walked = step["inputs"]
    assert [i["argument"] for i in walked] == ["raster_path", "zones_path", "weights_path"]
    assert walked[2]["environment"] == on_weights
    assert "environment" not in walked[1]
    if sidecars == "both":
        assert walked[0]["environment"] == record["inputs"][0]["environment"]


def test_the_unweighted_form_still_writes_a_conforming_record(dem, zone, tmp_path):
    """The conformance sweep exercises the weighted form; the unweighted one
    has code of its own and is checked here, against the vendored validator."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "validator", Path(__file__).parent / "data" / "manifest_spec_validator.py"
    )
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    result = raster.zonal_statistics(dem, zone, str(tmp_path / "u.parquet"), ["mean"])
    record = json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))
    assert validator.problems(record) == []
    assert "weights_path" not in record["parameters"]


def test_a_weighted_statistic_needs_weights_and_weights_need_one(dem, zone, tmp_path):
    with pytest.raises(ValueError, match="need weights_path"):
        raster.zonal_statistics(dem, zone, str(tmp_path / "a.parquet"), ["weighted_mean"])
    weights = _weights(tmp_path, _column_weights())
    with pytest.raises(ValueError, match="would change nothing"):
        raster.zonal_statistics(
            dem, zone, str(tmp_path / "b.parquet"), ["mean"], weights_path=weights
        )


def test_zonal_rejects_zones_without_crs(dem, tmp_path):
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[box(0, 0, 1, 1)], crs=None)
    z = tmp_path / "nocrs.gpkg"
    gdf.to_file(z)
    with pytest.raises(ValueError, match="no CRS"):
        raster.zonal_statistics(dem, str(z), str(tmp_path / "y.parquet"))
