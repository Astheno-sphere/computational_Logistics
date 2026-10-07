"""Closed-form tests for measure_area.

Fixtures and their arithmetic, all on paper:
- a 100 x 100 m square in EPSG:32632 → planar 10000 m² exactly;
- a 1000 x 1000 US-survey-foot square in EPSG:2229 → 10⁶ ft² × (1200/3937)²
  = 92903.4116 m², which is what a unit-aware planar measurement must return
  and 10⁶ is what an assume-metres one returns;
- a 120 x 100 rectangle in EPSG:3857 at 41.86°N → planar 12000 m², ground
  6651.34 m² (ratio 1.80): the distortion warning must fire;
- the same shape in EPSG:3035, an equal-area projection → planar 10000 m²,
  ground 10000.000005 m²: the warning must NOT fire;
- a bowtie (self-intersecting ring) → the raw shoelace differs from the
  repaired area, and the repair is recorded before the measurement.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon, box

from mapsmith.engines import vector


def _manifest(output: Path) -> dict:
    return json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))


def _layer(tmp_path, name, geometry, crs):
    path = tmp_path / f"{name}.parquet"
    gpd.GeoDataFrame({"id": ["P-1"]}, geometry=[geometry], crs=crs).to_parquet(path)
    return str(path)


def test_planar_area_in_metric_crs_is_exact(tmp_path):
    source = _layer(tmp_path, "utm", box(0, 0, 100, 100), "EPSG:32632")
    out = tmp_path / "utm_area.parquet"
    result = vector.measure_area(source, str(out), method="planar")
    assert result["total_area_m2"] == 10000.0
    assert float(gpd.read_parquet(out)["area_m2"].iloc[0]) == 10000.0
    manifest = _manifest(out)
    assert manifest["operation"] == "measure_area"
    assert "metre" in manifest["crs_decisions"]["reason"]


def test_planar_area_converts_us_survey_feet(tmp_path):
    # The trap this closes: 10^6 square feet reported as 10^6 square metres.
    source = _layer(tmp_path, "feet", box(0, 0, 1000, 1000), "EPSG:2229")
    out = tmp_path / "feet_area.parquet"
    result = vector.measure_area(source, str(out), method="planar")
    assert result["total_area_m2"] == pytest.approx(92903.4116, abs=1e-3)
    manifest = _manifest(out)
    assert "US survey foot" in manifest["crs_decisions"]["reason"]


def test_geodesic_area_is_the_ground_area(tmp_path):
    source = _layer(tmp_path, "merc", box(1380000, 5140000, 1380120, 5140100), "EPSG:3857")
    out = tmp_path / "merc_ground.parquet"
    result = vector.measure_area(source, str(out))  # geodesic is the default
    assert result["total_area_m2"] == pytest.approx(6651.335, abs=0.01)
    manifest = _manifest(out)
    assert "ellipsoid" in manifest["crs_decisions"]["reason"]
    assert "WGS 84" in manifest["crs_decisions"]["analysis_crs"]


def test_planar_on_web_mercator_warns_with_the_ratio(tmp_path):
    source = _layer(tmp_path, "merc", box(1380000, 5140000, 1380120, 5140100), "EPSG:3857")
    out = tmp_path / "merc_planar.parquet"
    result = vector.measure_area(source, str(out), method="planar")
    assert result["total_area_m2"] == 12000.0
    assert result["ground_area_m2"] == pytest.approx(6651.335, abs=0.01)
    # 12000 / 6651.335 = 1.8038: the plane reports 1.8x the land it covers.
    warnings = result.get("warnings", [])
    assert any("x-mapsmith:planar_area_matches_ground" in str(w) or "ground area" in str(w)
               for w in warnings), warnings
    checks = {c["name"]: c for c in _manifest(out)["verification"]}
    assert checks["x-mapsmith:planar_area_matches_ground"]["passed"] is False
    assert "1.80" in checks["x-mapsmith:planar_area_matches_ground"]["detail"]


def test_planar_on_an_equal_area_crs_does_not_warn(tmp_path):
    source = _layer(tmp_path, "laea", box(4532000, 2050000, 4532100, 2050100), "EPSG:3035")
    out = tmp_path / "laea_planar.parquet"
    result = vector.measure_area(source, str(out), method="planar")
    assert result["total_area_m2"] == 10000.0
    assert result["ground_area_m2"] == pytest.approx(10000.0, abs=0.01)
    checks = {c["name"]: c for c in _manifest(out)["verification"]}
    assert checks["x-mapsmith:planar_area_matches_ground"]["passed"] is True


def test_invalid_geometry_is_repaired_before_measuring_and_recorded(tmp_path):
    bowtie = Polygon([(0, 0), (100, 0), (0, 60), (100, 60)])
    assert not bowtie.is_valid
    source = _layer(tmp_path, "bowtie", bowtie, "EPSG:32632")
    out = tmp_path / "bowtie_area.parquet"
    result = vector.measure_area(source, str(out), method="planar")
    # The repaired area is the two triangles: 2 x (100 x 30 / 2) = 3000.
    assert result["total_area_m2"] == 3000.0
    # The repair must be where the rest of the system looks for repairs, in
    # the manifest AND in the tool result — not buried in a free-text note.
    assert result["repairs"] == [{
        "check": "x-mapsmith:input_geometry_valid",
        "action": result["repairs"][0]["action"],
        "resolved": True,
    }]
    assert "BEFORE measuring" in result["repairs"][0]["action"]
    manifest = _manifest(out)
    assert manifest["repairs"][0]["check"] == "x-mapsmith:input_geometry_valid"
    assert manifest["repairs"][0]["resolved"] is True


def test_points_measure_zero_and_say_so(tmp_path):
    source = _layer(tmp_path, "point", Point(500000, 4500000), "EPSG:32632")
    out = tmp_path / "point_area.parquet"
    result = vector.measure_area(source, str(out), method="planar")
    assert result["total_area_m2"] == 0.0
    checks = {c["name"]: c for c in _manifest(out)["verification"]}
    assert checks["x-mapsmith:area_is_measurable"]["passed"] is False
    assert checks["x-mapsmith:area_is_measurable"]["critical"] is False


def test_measure_area_refuses_planar_on_geographic_and_bad_method(tmp_path):
    source = _layer(tmp_path, "geo", box(12.4, 41.9, 12.41, 41.91), "EPSG:4326")
    with pytest.raises(ValueError, match="square degrees"):
        vector.measure_area(source, str(tmp_path / "x.parquet"), method="planar")
    with pytest.raises(ValueError, match="method must be"):
        vector.measure_area(source, str(tmp_path / "y.parquet"), method="spherical")
    # geodesic on the same geographic layer is exactly what it is for
    out = tmp_path / "geo_ground.parquet"
    assert vector.measure_area(source, str(out))["total_area_m2"] > 0


def test_measure_area_refuses_a_crs_less_input(tmp_path):
    naked = tmp_path / "naked.parquet"
    gpd.GeoDataFrame({"i": [1]}, geometry=[box(0, 0, 1, 1)], crs=None).to_parquet(naked)
    with pytest.raises(ValueError, match="no CRS"):
        vector.measure_area(str(naked), str(tmp_path / "x.parquet"))


def test_a_courtyard_is_subtracted_on_the_ellipsoid_too(tmp_path):
    """The bug Argleton's trap 011 found, the day after measure_area shipped.

    `Geod.geometry_area_perimeter` returns a signed value whose sign follows
    ring orientation, so taking abs() of the whole geometry added the hole
    instead of subtracting it: a 10000 m2 parcel with a 1600 m2 courtyard came
    back as 11609 on the geodesic path while the planar path said 8400. The
    two disagreeing by 38% is what the distortion check noticed.

    Closed form: outer 100x100 = 10000, courtyard 40x40 = 1600, so 8400 planar.
    On the ellipsoid at this latitude the same parcel is 8406.7 — the UTM zone's
    own 0.08% scale, which is the only difference there should ever be here.
    """
    import geopandas as gpd
    from shapely.geometry import Polygon

    from mapsmith.engines import vector

    east, north = 500_000.0, 5_030_000.0
    parcel = tmp_path / "courtyard.parquet"
    gpd.GeoDataFrame(
        {"id": [1]},
        geometry=[
            Polygon(
                [(east, north), (east + 100, north), (east + 100, north + 100),
                 (east, north + 100)],
                [[(east + 30, north + 30), (east + 70, north + 30),
                  (east + 70, north + 70), (east + 30, north + 70)]],
            )
        ],
        crs="EPSG:32632",
    ).to_parquet(parcel)

    planar = vector.measure_area(str(parcel), str(tmp_path / "p.parquet"), method="planar")
    assert planar["total_area_m2"] == pytest.approx(8400.0, abs=0.01)

    geodesic = vector.measure_area(str(parcel), str(tmp_path / "g.parquet"))
    assert geodesic["total_area_m2"] == pytest.approx(8406.7, abs=0.5)
    # Not 11609: that is the two rings added, which is the whole point.
    assert geodesic["total_area_m2"] < 10000.0
    # And with the paths agreeing to 0.08%, the distortion check stays quiet.
    assert not geodesic.get("warnings")
