"""Map previews: exact GeoJSON counts, capping, PNG validity, provenance summary."""

import base64
import struct
import zlib

import geopandas as gpd
import pytest
from shapely.geometry import Point

from mapsmith import preview
from mapsmith.engines import vector


@pytest.fixture()
def points_layer(tmp_path):
    gdf = gpd.GeoDataFrame(
        {"name": ["a", "b", "c"]},
        geometry=[Point(9.19, 45.46), Point(9.20, 45.47), Point(9.21, 45.48)],
        crs="EPSG:4326",
    )
    path = tmp_path / "pts.parquet"
    gdf.to_parquet(path)
    return str(path)


def test_vector_preview_exact_counts_and_bounds(points_layer):
    result = preview.vector_preview(points_layer)
    assert result["kind"] == "vector"
    assert result["feature_count"] == 3
    assert result["truncated"] is False
    assert len(result["geojson"]["features"]) == 3
    minx, miny, maxx, maxy = result["bounds"]
    assert (minx, miny, maxx, maxy) == (9.19, 45.46, 9.21, 45.48)
    assert result["provenance"] is None  # hand-made file: no manifest


def test_vector_preview_caps_features(points_layer):
    result = preview.vector_preview(points_layer, max_features=2)
    assert result["truncated"] is True
    assert result["feature_count"] == 3  # total is still reported
    assert len(result["geojson"]["features"]) == 2


def test_vector_preview_reprojects_to_4326(points_layer, tmp_path):
    utm = gpd.read_parquet(points_layer).to_crs("EPSG:32632")
    utm_path = tmp_path / "pts_utm.parquet"
    utm.to_parquet(utm_path)
    result = preview.vector_preview(str(utm_path))
    assert result["crs_original"] == "EPSG:32632"
    lon = result["geojson"]["features"][0]["geometry"]["coordinates"][0]
    assert lon == pytest.approx(9.19, abs=0.01)


def test_vector_preview_rejects_missing_crs(tmp_path):
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(0, 0)], crs=None)
    path = tmp_path / "nocrs.gpkg"
    gdf.to_file(path)
    with pytest.raises(ValueError, match="no CRS"):
        preview.vector_preview(str(path))


def test_provenance_summary_reads_real_manifest(points_layer, tmp_path):
    out = tmp_path / "buffered.parquet"
    vector.buffer(points_layer, 100.0, str(out))
    result = preview.vector_preview(str(out))
    prov = result["provenance"]
    assert prov["operation"] == "buffer_layer"
    assert prov["engine"] == "geopandas"
    assert prov["verified"] is True
    assert prov["checks_total"] > 0
    assert "UTM" in prov["crs_reason"]


def test_png_encoder_produces_valid_gray_alpha_png():
    # 3x2 image: gray gradient, all opaque -> rows are (gray, alpha) interleaved
    row = bytes([0, 255, 128, 255, 255, 255])
    png = preview._png_gray_alpha([row, row], 3, 2)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", png[16:24])
    assert (width, height) == (3, 2)
    assert png[24] == 8  # bit depth
    assert png[25] == 4  # color type 4 = grayscale + alpha
    # IDAT decompresses to exactly (1 filter byte + 2*width) * height
    idat_start = png.index(b"IDAT") + 4
    idat_len = struct.unpack(">I", png[png.index(b"IDAT") - 4 : png.index(b"IDAT")])[0]
    raw = zlib.decompress(png[idat_start : idat_start + idat_len])
    assert raw == b"\x00" + row + b"\x00" + row


def test_vector_preview_rejects_empty_dataset(tmp_path):
    empty = gpd.GeoDataFrame({"a": []}, geometry=[], crs="EPSG:4326")
    path = tmp_path / "empty.parquet"
    empty.to_parquet(path)
    with pytest.raises(ValueError, match="no features"):
        preview.vector_preview(str(path))


def test_vector_preview_serializes_datetime_columns(tmp_path):
    import pandas as pd

    gdf = gpd.GeoDataFrame(
        {"when": pd.to_datetime(["2026-01-01", "2026-06-15"])},
        geometry=[Point(9.0, 45.0), Point(9.1, 45.1)],
        crs="EPSG:4326",
    )
    path = tmp_path / "dated.parquet"
    gdf.to_parquet(path)
    result = preview.vector_preview(str(path))
    props = result["geojson"]["features"][0]["properties"]
    assert "2026-01-01" in str(props["when"])


def test_truncated_preview_keeps_full_bounds(tmp_path):
    spread = gpd.GeoDataFrame(
        {"i": [1, 2, 3]},
        geometry=[Point(9.0, 45.0), Point(10.0, 46.0), Point(12.5, 41.9)],
        crs="EPSG:4326",
    )
    path = tmp_path / "spread.parquet"
    spread.to_parquet(path)
    result = preview.vector_preview(str(path), max_features=1)
    assert result["truncated"] is True
    assert len(result["geojson"]["features"]) == 1
    # bounds cover ALL 3 features, not just the one shown
    assert result["bounds"] == pytest.approx([9.0, 41.9, 12.5, 46.0])


def test_budget_never_raises_user_feature_cap(tmp_path):
    many = gpd.GeoDataFrame(
        {"i": range(200)},
        geometry=[Point(9 + i * 1e-3, 45) for i in range(200)],
        crs="EPSG:4326",
    )
    path = tmp_path / "many10.parquet"
    many.to_parquet(path)
    payload = preview.map_preview([str(path)], max_features=10, max_payload_chars=500)
    assert len(payload["layers"][0]["geojson"]["features"]) <= 10


def test_provenance_summary_survives_malformed_manifest(tmp_path, points_layer):
    import shutil

    path = tmp_path / "copy.parquet"
    shutil.copy(points_layer, path)
    (tmp_path / "copy.parquet.provenance.json").write_text(
        '{"operation": "x", "verification": [{}], "engine": null}', encoding="utf-8"
    )
    result = preview.vector_preview(str(path))
    assert result["provenance"]["verified"] is False  # no KeyError, honest default


def test_raster_preview_closed_form(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    import numpy as np
    from rasterio.transform import from_origin

    data = np.arange(100, dtype=np.float32).reshape(10, 10)  # values 0..99
    data[0, 0] = np.nan  # a stray NaN must not poison the declared-nodata mask
    path = tmp_path / "grid.tif"
    with rasterio.open(
        path, "w", driver="GTiff", height=10, width=10, count=1, dtype="float32",
        crs="EPSG:4326", transform=from_origin(9.0, 46.0, 0.01, 0.01),
        nodata=-1.0,
    ) as dst:
        dst.write(data, 1)
    result = preview.raster_preview(str(path))
    assert result["kind"] == "raster"
    assert result["value_range"] == [1.0, 99.0]  # NaN excluded; 0 was overwritten
    assert result["bounds"] == pytest.approx([9.0, 45.9, 9.1, 46.0])
    assert result["png_data_uri"].startswith("data:image/png;base64,")
    png = base64.b64decode(result["png_data_uri"].split(",", 1)[1])
    assert png.startswith(b"\x89PNG")


def test_map_preview_merges_bounds(points_layer, tmp_path):
    other = gpd.GeoDataFrame(
        {"n": [1]}, geometry=[Point(12.49, 41.89)], crs="EPSG:4326"  # Rome
    )
    other_path = tmp_path / "rome.parquet"
    other.to_parquet(other_path)
    result = preview.map_preview([points_layer, str(other_path)])
    assert len(result["layers"]) == 2
    minx, miny, maxx, maxy = result["bounds"]
    assert (minx, miny) == (9.19, 41.89)
    assert (maxx, maxy) == (12.49, 45.48)


def test_map_preview_rejects_empty_list():
    with pytest.raises(ValueError, match="at least one"):
        preview.map_preview([])
