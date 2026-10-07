"""Closed-form tests for band_math.

Scene fixture: red = 3000 and NIR = 5000 stored as uint16, with scale 0.0001
and offset -0.1 declared on both bands. The physical values are therefore 0.2
and 0.4, and NDVI = 0.2 / 0.6 = 1/3 exactly. Skip the declared calibration and
the same formula gives (5000-3000)/(5000+3000) = 0.25 — a perfectly ordinary
NDVI, and the reason this class of error survives: without an offset the scale
cancels in the ratio, so code that ignored both was right until Sentinel-2
introduced a non-zero offset in January 2022.
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


def _write(path, bands, dtype, scales=None, offsets=None):
    with rasterio.open(
        path, "w", driver="GTiff", height=4, width=4, count=len(bands), dtype=dtype,
        crs=CRS, transform=from_origin(500000, 4600000, 10, 10),
    ) as ds:
        for index, value in enumerate(bands, start=1):
            ds.write(np.full((4, 4), value, dtype=dtype), index)
        if scales:
            ds.scales = scales
        if offsets:
            ds.offsets = offsets
    return str(path)


def _manifest(output: Path) -> dict:
    return json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))


@pytest.fixture
def scene(tmp_path):
    return _write(
        tmp_path / "scene.tif", (3000, 5000), "uint16",
        scales=(0.0001, 0.0001), offsets=(-0.1, -0.1),
    )


def test_ndvi_uses_the_declared_scale_and_offset(scene, tmp_path):
    out = tmp_path / "ndvi.tif"
    result = raster.band_math(scene, str(out), "(b2 - b1) / (b2 + b1)")
    assert result["mean"] == pytest.approx(1 / 3, abs=1e-6)
    assert result["bands_used"] == [1, 2]
    assert result["scale_offset_applied"] == [
        "b1: value * 0.0001 + -0.1",
        "b2: value * 0.0001 + -0.1",
    ]
    manifest = _manifest(out)
    assert any("scale and offset applied" in note for note in manifest["notes"])
    # The number the same formula gives on the stored values, for contrast.
    assert result["mean"] != pytest.approx(0.25, abs=1e-6)


def test_a_scene_without_calibration_is_taken_at_face_value(tmp_path):
    plain = _write(tmp_path / "phys.tif", (0.2, 0.6), "float32")
    out = tmp_path / "ndvi_plain.tif"
    result = raster.band_math(plain, str(out), "(b2 - b1) / (b2 + b1)")
    assert result["mean"] == pytest.approx(0.5, abs=1e-6)
    assert "scale_offset_applied" not in result
    assert any("no band declares" in note for note in _manifest(out)["notes"])


def test_integer_subtraction_does_not_wrap_around(tmp_path):
    """b1 - b2 on uint16 where b1 < b2 wraps to ~65535 in numpy, silently.
    Closed form: 3000 - 5000 must be -2000, not 63536."""
    scene = _write(tmp_path / "raw.tif", (3000, 5000), "uint16")
    out = tmp_path / "diff.tif"
    result = raster.band_math(scene, str(out), "b1 - b2")
    assert result["mean"] == pytest.approx(-2000.0, abs=1e-6)
    with rasterio.open(out) as ds:
        assert ds.dtypes[0] == "float32"


def test_an_index_is_not_rounded_into_an_integer_band(tmp_path):
    """The input is uint16; inheriting its dtype would store an NDVI of 1/3
    as 0. The output profile is float by construction."""
    scene = _write(tmp_path / "raw.tif", (3000, 5000), "uint16")
    out = tmp_path / "ndvi_int.tif"
    result = raster.band_math(scene, str(out), "(b2 - b1) / (b2 + b1)")
    assert result["mean"] == pytest.approx(0.25, abs=1e-6)
    with rasterio.open(out) as ds:
        assert ds.dtypes[0] == "float32"
        assert float(ds.read(1).min()) == pytest.approx(0.25, abs=1e-6)
    manifest = _manifest(out)
    assert [c["name"] for c in manifest["verification"] if not c["passed"]] == []


def test_division_by_zero_becomes_nodata_and_is_counted(tmp_path):
    scene = _write(tmp_path / "zeros.tif", (0, 0), "int16")
    out = tmp_path / "zero.tif"
    result = raster.band_math(scene, str(out), "(b2 - b1) / (b2 + b1)")
    assert result["nodata_cells"] == 16
    checks = {w["check"] for w in result.get("warnings", [])}
    assert "result_not_empty" in checks


def test_only_arithmetic_over_bands_is_accepted(scene, tmp_path):
    # ** is allowed on purpose (an index that squares a band is ordinary);
    # names, calls and attribute access are what must not get through.
    assert raster.band_math(scene, str(tmp_path / "sq.tif"), "b1 ** 2")["verified"]
    for bad in ("__import__(chr(111))", "b1 + x", "open(f)", "b1 % 2", "b1; b2"):
        with pytest.raises(ValueError, match="may only contain band references"):
            raster.band_math(scene, str(tmp_path / "x.tif"), bad)
    with pytest.raises(ValueError, match="references no band"):
        raster.band_math(scene, str(tmp_path / "x.tif"), "42")
    with pytest.raises(ValueError, match="has 2 band"):
        raster.band_math(scene, str(tmp_path / "x.tif"), "b9 - b1")


def test_reachable_through_run_operation(scene, tmp_path):
    from mapsmith.server import run_operation

    result = run_operation(
        "band_math",
        {
            "input_path": scene,
            "output_path": str(tmp_path / "via_ro.tif"),
            "expression": "(b2 - b1) / (b2 + b1)",
        },
    )
    assert result["ran"] is True
    assert result["status"] == "ok"


def test_a_power_tower_is_refused_before_the_file_is_opened(tmp_path):
    """`b1*0+9**9**9**9` passed every check and hung the host.

    The character whitelist allows it — only digits, `b`, and operators — and it
    references a band, so both gates said yes. Then CPython was asked for an
    integer power with about 370 million digits in the exponent, and the process
    stopped responding before a single pixel was read. One call, one machine.
    Preexisting: identical in 0.3.0.

    The rule is not "no exponentiation": an index that squares a band is
    ordinary. It is that the **exponent must be a plain small number**, which is
    what separates `(b1 - b2) ** 2` from a tower — `**` is right-associative, so
    the outer exponent of `9**9**9**9` is itself an expression.

    Refused at parse time, so the raster argument here is never opened; the test
    passes a path that does not exist to prove exactly that.
    """
    import pytest

    from mapsmith.engines import raster

    absent = str(tmp_path / "never-opened.tif")
    with pytest.raises(ValueError, match="not a plain number"):
        raster.band_math(absent, str(tmp_path / "out.tif"), "b1*0+9**9**9**9")
    assert not (tmp_path / "out.tif").exists()

    # The legitimate shapes still work, and are the reason this is a cap and
    # not a ban.
    raster._refuse_unevaluable_expression("(b1 - b2) / (b1 + b2)")
    raster._refuse_unevaluable_expression("(b1 - b2) ** 2")
    raster._refuse_unevaluable_expression("-b1 + 3.5")

    # Chained small powers multiply into a large one, so the count is capped too.
    with pytest.raises(ValueError, match="exponentiations"):
        raster._refuse_unevaluable_expression("((((b1**8)**8)**8)**8)**8")
