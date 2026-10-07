"""Terrain results must be correct whatever the input GeoTIFF's encoding.

whitebox_workflows 2.x decompresses DEFLATE/LZW rasters without undoing the
TIFF predictor (tag 317), so anything it computes from such a file is garbage —
while still having the right CRS, shape and value range, and still looking like
terrain. PREDICTOR=2 is the standard recommendation for integer rasters, so
this is a normal encoding, not an exotic one.

Correctness is checked against an independent reference rather than by
comparing two runs: two wrong answers agreeing would pass.
"""


import numpy as np
import pytest

# importorskip, not a plain import: CONTRIBUTING documents `pip install -e .[test]`
# and pytest collects every file before running anything, so a module-level
# `import rasterio` here broke the whole suite for a contributor without the
# raster extra — including the tests that need neither.
rasterio = pytest.importorskip("rasterio")
wb = pytest.importorskip("whitebox_workflows")

from rasterio.transform import from_origin

from mapsmith.engines import whitebox_engine

SIZE = 300
RES = 20.0
# (dtype, compression, predictor, tiled) — predictor 3 is float-only
ENCODINGS = [
    ("int16", None, None, False),
    ("int16", None, None, True),
    ("int16", "deflate", 1, False),
    ("int16", "deflate", 2, False),
    ("int16", "deflate", 2, True),
    ("int16", "lzw", 2, False),
    ("float32", "deflate", 1, False),
    ("float32", "deflate", 2, False),
    ("float32", "deflate", 3, False),
    ("float32", "deflate", 3, True),
    ("float32", "lzw", 3, False),
]


def _dem() -> np.ndarray:
    x, y = np.meshgrid(np.arange(SIZE, dtype="float64"), np.arange(SIZE, dtype="float64"))
    return 40 * np.sin(x / 11) * np.cos(y / 13) + 18 * np.sin(x / 29 + 0.7) + 0.5 * (SIZE - y) + 500


def _reference_hillshade(z: np.ndarray) -> np.ndarray:
    """Horn's method, azimuth 315 and altitude 30 — our tool's defaults."""
    dzdx = (np.roll(z, -1, 1) - np.roll(z, 1, 1)) / (2 * RES)
    dzdy = (np.roll(z, -1, 0) - np.roll(z, 1, 0)) / (2 * RES)
    slope = np.arctan(np.hypot(dzdx, dzdy))
    aspect = np.arctan2(dzdy, -dzdx)
    az, alt = np.radians(360 - 315 + 90), np.radians(30)
    shade = np.cos(alt) * np.cos(slope) + np.sin(alt) * np.sin(slope) * np.cos(az - aspect)
    return shade[2:-2, 2:-2].ravel()


def _write(path, data, dtype, compress, predictor, tiled):
    profile = {
        "driver": "GTiff", "height": SIZE, "width": SIZE, "count": 1, "dtype": dtype,
        "crs": "EPSG:32632", "transform": from_origin(500000, 5000000, RES, RES),
        "nodata": -32768.0, "tiled": tiled,
    }
    if tiled:
        profile.update(blockxsize=256, blockysize=256)
    if compress:
        profile["compress"] = compress
    if predictor:
        profile["predictor"] = predictor
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data.astype(dtype), 1)


@pytest.mark.parametrize(
    "dtype,compress,predictor,tiled", ENCODINGS,
    ids=[f"{d}-{c or 'raw'}-pred{p or 0}-{'tiled' if t else 'striped'}"
         for d, c, p, t in ENCODINGS],
)
def test_hillshade_is_correct_for_every_encoding(tmp_path, dtype, compress, predictor, tiled):
    data = _dem()
    src, out = tmp_path / "dem.tif", tmp_path / "hs.tif"
    _write(src, data, dtype, compress, predictor, tiled)
    with rasterio.open(src) as ds:
        assert np.array_equal(ds.read(1), data.astype(dtype)), "the file itself must be faithful"

    whitebox_engine.hillshade(str(src), str(out))

    with rasterio.open(out) as ds:
        got = ds.read(1).astype("float64")[2:-2, 2:-2].ravel()
    r = float(np.corrcoef(got, _reference_hillshade(data.astype(dtype).astype("float64")))[0, 1])
    assert r > 0.95, (
        f"hillshade of a {dtype} {compress or 'uncompressed'} predictor={predictor} "
        f"{'tiled' if tiled else 'striped'} DEM correlates only {r:.3f} with the "
        "reference: the engine was handed an encoding it mishandles"
    )


def test_conversion_happens_only_when_a_predictor_is_present(tmp_path):
    """The workaround must be narrow: compression and tiling on their own are
    handled correctly, and converting them anyway would be wasted I/O."""
    import json

    data = _dem()
    cases = {
        "pred2": ("int16", "deflate", 2, True),
        "deflate_only": ("int16", "deflate", None, True),
        "plain": ("int16", None, None, False),
    }
    converted = {}
    for name, (dtype, compress, predictor, tiled) in cases.items():
        src, out = tmp_path / f"{name}.tif", tmp_path / f"{name}_hs.tif"
        _write(src, data, dtype, compress, predictor, tiled)
        whitebox_engine.hillshade(str(src), str(out))
        notes = json.loads((tmp_path / f"{name}_hs.tif.provenance.json")
                           .read_text(encoding="utf-8"))["notes"]
        converted[name] = bool(notes)
        if notes:
            assert "predictor 2" in notes[0]

    assert converted == {"pred2": True, "deflate_only": False, "plain": False}


def test_flow_accumulation_agrees_across_encodings(tmp_path):
    """Flow routing carries a bad cell downstream, so an encoding defect here
    is not confined to a few pixels."""
    data = _dem()
    plain, predicted = tmp_path / "plain.tif", tmp_path / "pred.tif"
    _write(plain, data, "float32", None, None, False)
    _write(predicted, data, "float32", "deflate", 3, True)

    whitebox_engine.flow_accumulation(str(plain), str(tmp_path / "a.tif"))
    whitebox_engine.flow_accumulation(str(predicted), str(tmp_path / "b.tif"))
    with rasterio.open(tmp_path / "a.tif") as x, rasterio.open(tmp_path / "b.tif") as y:
        assert np.array_equal(x.read(1), y.read(1))


def test_no_temporary_copies_are_left_behind(tmp_path):
    data = _dem()
    src = tmp_path / "dem.tif"
    _write(src, data, "int16", "deflate", 2, True)
    whitebox_engine.hillshade(str(src), str(tmp_path / "hs.tif"))
    assert [p.name for p in tmp_path.rglob("*no-predictor*")] == []


def test_the_engine_reads_predictor_files_wrongly_and_our_copy_fixes_it(tmp_path):
    """The defect at its root, with no terrain tool in the way: whitebox hands
    back the undifferenced values, and cumsum reconstructs the truth. This is
    what the conversion exists for, and it is far cheaper to check here than
    through a hillshade."""
    data = _dem()
    src = tmp_path / "pred2.tif"
    _write(src, data, "int16", "deflate", 2, False)

    assert whitebox_engine._needs_plain_copy(str(src)) == "stored with TIFF predictor 2"

    wbe = wb.WbEnvironment()
    wbe.verbose = False
    with rasterio.open(src) as ds:
        truth = ds.read(1)

    as_read = wbe.read_raster(str(src)).to_numpy()
    assert not np.array_equal(as_read, truth), "if this passes, upstream fixed the bug"
    assert np.array_equal(np.cumsum(as_read, axis=1).astype("int16"), truth), (
        "the returned values are the horizontal differences, unsummed"
    )

    converted = whitebox_engine._plain_copy(str(src), tmp_path)
    assert whitebox_engine._needs_plain_copy(converted) is None
    assert np.array_equal(wbe.read_raster(converted).to_numpy(), truth)
