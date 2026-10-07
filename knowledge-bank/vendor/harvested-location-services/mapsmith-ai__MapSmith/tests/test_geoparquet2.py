"""GeoParquet 2.0 storage: geometry in Parquet's own logical types (issue #23).

2.0 (`v2.0.0-rc.1`, 2026-07-19) drops the WKB-in-a-plain-binary-column layout
and requires Parquet's native `GEOMETRY`/`GEOGRAPHY` logical types, with the
`geo` metadata key demoted to optional. So a valid Parquet file full of geometry
may carry no `geo` key at all, and MapSmith used to treat exactly that file as
CRS-less — while `run_sql` read it happily, because DuckDB understands the native
types. One tool refusing what another accepts, on the same file, is the failure
this module pins down.

The fixtures are written by DuckDB rather than vendored: `geoparquet_version
'NONE'` writes the native type with no `geo` key, and `'BOTH'` writes both
layers. That keeps the expected values in the test instead of in a binary blob.
"""

import pytest

from mapsmith import verify

duckdb = pytest.importorskip("duckdb")
gpd = pytest.importorskip("geopandas")


def _write(path, sql, version, crs_clause=""):
    con = duckdb.connect()
    con.execute("LOAD spatial")
    con.execute(
        f"COPY ({sql}) TO '{str(path).replace(chr(92), '/')}' "
        f"(FORMAT parquet, geoparquet_version '{version}')"
    )
    return path


def test_native_geometry_is_recognised_without_geo_metadata(tmp_path):
    import pyarrow.parquet as pq

    target = _write(tmp_path / "native.parquet", "SELECT 1 AS a, ST_Point(9, 45) AS geom", "NONE")
    assert b"geo" not in (pq.read_schema(target).metadata or {}), "fixture should have no geo key"

    found = verify.native_geometry_column(str(target))
    assert found is not None, "the native logical type was not detected"
    assert found[0] == "geom"


def test_the_crs_probe_no_longer_reports_unknown(tmp_path):
    """The regression that mattered: a file that states its CRS was read as
    CRS-less, so the CRS precondition refused valid work for a wrong reason."""
    source = tmp_path / "utm.parquet"
    gpd.GeoDataFrame(
        {"a": [1]}, geometry=gpd.GeoSeries.from_wkt(["POINT (500000 5000000)"]), crs="EPSG:32632"
    ).to_parquet(source)
    target = _write(
        tmp_path / "native_utm.parquet",
        f"SELECT * FROM read_parquet('{str(source).replace(chr(92), '/')}')",
        "NONE",
    )
    assert verify.probe_crs(str(target)) == "EPSG:32632"


def test_describe_reads_a_native_file(tmp_path):
    """`describe_dataset` used to surface a raw GeoPandas ValueError here."""
    from mapsmith.engines import vector

    target = _write(
        tmp_path / "native.parquet",
        "SELECT * FROM (VALUES (1, ST_Point(9, 45)), (2, ST_Point(10, 46))) t(a, geom)",
        "NONE",
    )
    described = vector.describe(str(target))
    assert described["feature_count"] == 2
    assert described["geometry_types"] == ["Point"]
    assert described["extent"]["minx"] == pytest.approx(9.0)
    assert described["extent"]["maxy"] == pytest.approx(46.0)


def test_both_layers_are_read_the_old_way(tmp_path):
    """`geoparquet_version 'BOTH'` carries native types *and* `geo` metadata.
    The 1.x path must keep winning there, so the two layers cannot disagree."""
    import pyarrow.parquet as pq

    target = _write(tmp_path / "both.parquet", "SELECT ST_Point(9, 45) AS geom", "BOTH")
    assert b"geo" in (pq.read_schema(target).metadata or {})
    assert verify.native_geometry_column(str(target)) is not None
    assert verify.probe_crs(str(target)) != verify.UNKNOWN_CRS


@pytest.mark.parametrize(
    ("declaration", "expected"),
    [
        # The label is the authority string, not the display name: it is exact,
        # it round-trips through CRS.from_user_input, and it keeps CRS84 visibly
        # distinct from EPSG:4326 — same datum, opposite axis order, and pyproj
        # refuses to give CRS84 that code. Flattening the two would be the
        # axis-order bug that eats a working pipeline once the coordinates leave
        # this file.
        ("", "OGC:CRS84"),
        ("OGC:CRS84", "OGC:CRS84"),
        ("EPSG:3857", "EPSG:3857"),
        # NOT resolved on purpose: the spec defines srid:<n> as a numeric
        # identifier and names no authority, so EPSG:<n> would be a guess
        # recorded as fact — the 0.2.1 `crs: null` bug in a new costume
        ("srid:5070", verify.UNKNOWN_CRS),
        ("projjson:absent_key", verify.UNKNOWN_CRS),
    ],
)
def test_crs_declaration_forms(tmp_path, declaration, expected):
    target = _write(tmp_path / "x.parquet", "SELECT ST_Point(9, 45) AS geom", "NONE")
    assert verify.native_crs_declaration(str(target), declaration) == expected


def test_an_inline_projjson_declaration_resolves(tmp_path):
    """What DuckDB actually writes is not a `projjson:key` reference but the
    whole document inline, which the first draft of the resolver did not expect."""
    import json

    import pyarrow.parquet as pq

    source = tmp_path / "utm.parquet"
    gpd.GeoDataFrame(
        {"a": [1]}, geometry=gpd.GeoSeries.from_wkt(["POINT (500000 5000000)"]), crs="EPSG:32632"
    ).to_parquet(source)
    target = _write(
        tmp_path / "inline.parquet",
        f"SELECT * FROM read_parquet('{str(source).replace(chr(92), '/')}')",
        "NONE",
    )
    schema = pq.ParquetFile(target).schema
    declaration = next(
        json.loads(schema.column(i).logical_type.to_json()).get("crs")
        for i in range(len(schema))
        if json.loads(schema.column(i).logical_type.to_json()).get("Type") in verify.NATIVE_GEO_TYPES
    )
    assert declaration.lstrip().startswith("{"), "expected an inline PROJJSON document"
    assert verify.native_crs_declaration(str(target), declaration) == "EPSG:32632"


def test_our_own_output_carries_both_layers(tmp_path):
    """What MapSmith writes through DuckDB must satisfy a 2.0 reader and a 1.x
    one at once, and the CRS must survive in both places. The flavour is stated
    in the COPY rather than inherited: DuckDB 1.4 wrote native types by default
    and 1.5 went back to 1.x, so the installed engine was choosing the canonical
    output format of a provenance product."""
    import json

    import pyarrow.parquet as pq

    from mapsmith.engines import duckdb_engine

    source = tmp_path / "utm.parquet"
    gpd.GeoDataFrame(
        {"a": [1]}, geometry=gpd.GeoSeries.from_wkt(["POINT (500000 5000000)"]), crs="EPSG:32632"
    ).to_parquet(source)
    target = tmp_path / "out.parquet"
    duckdb_engine.run_sql(
        f"SELECT * FROM read_parquet('{str(source).replace(chr(92), '/')}')", str(target)
    )

    # the 2.0 layer
    native = verify.native_geometry_column(str(target))
    assert native is not None, "no native geometry logical type in our own output"
    assert verify.native_crs_declaration(str(target), native[1]) == "EPSG:32632"
    # the 1.x layer
    geo = json.loads((pq.read_schema(target).metadata or {})[b"geo"])
    assert geo["columns"][geo["primary_column"]]["crs"] is not None
    # and a 1.x-only reader still opens it
    assert gpd.read_parquet(target).crs.to_epsg() == 32632


def test_a_plain_parquet_without_geometry_keeps_its_original_error(tmp_path):
    """The fallback must not turn "this file has no geometry" into a confusing
    success or a different exception."""
    from mapsmith.engines import vector

    target = tmp_path / "tabular.parquet"
    duckdb.connect().execute(
        f"COPY (SELECT 1 AS a) TO '{str(target).replace(chr(92), '/')}' (FORMAT parquet)"
    )
    with pytest.raises(ValueError, match="geo metadata"):
        vector.describe(str(target))


# --- #28: one reader, and a declared CRS that survives the trip -------------
#
# 0.2.2 taught two of the six read paths to open a 2.0-native file and left the
# other four raising `Missing geo metadata` on it — the exact error the work
# said it had eliminated. These tests go through the TOOLS, not the resolver,
# because that is where the halves diverged.


def _native_utm(tmp_path, name="native.parquet", wkt="POINT (500000 5000000)", rows=1):
    """A 2.0-native file (no `geo` key) that declares EPSG:32632 inline."""
    source = tmp_path / f"src_{name}"
    gpd.GeoDataFrame(
        {"a": list(range(rows))},
        geometry=gpd.GeoSeries.from_wkt([wkt] * rows),
        crs="EPSG:32632",
    ).to_parquet(source)
    return _write(
        tmp_path / name,
        f"SELECT * FROM read_parquet('{str(source).replace(chr(92), '/')}')",
        "NONE",
    )


def test_every_vector_read_goes_through_the_one_reader():
    """The guard that keeps this fix from being half-applied again.

    #28 happened because "open a vector file" was six copies of the same
    decision. Adding a seventh copy is the only way to reintroduce it, so the
    seventh copy is what fails here — not the symptom.
    """
    import re
    from pathlib import Path

    import mapsmith

    package = Path(mapsmith.__file__).parent  # not the CWD: pytest may start anywhere
    readers = package / "readers.py"
    pattern = re.compile(
        r"\b(?:gpd|geopandas)\.read_(?:parquet|file)\s*\(|\bpyogrio\.read_dataframe\s*\("
    )
    offenders, scanned = [], 0
    for module in package.rglob("*.py"):
        if module == readers:
            continue
        scanned += 1
        for number, line in enumerate(module.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                where = module.relative_to(package).as_posix()
                offenders.append(f"{where}:{number}: {line.strip()}")
    assert scanned > 10, f"only {scanned} modules scanned — the guard checked nothing"
    assert not offenders, (
        "vector reads outside mapsmith/readers.py — route them through "
        "readers.read_vector so the GeoParquet 2.0 branch cannot be half-applied:\n"
        + "\n".join(offenders)
    )


def test_a_multi_layer_input_is_refused_as_every_other_component_sees_it(tmp_path):
    """A container with no chosen layer is refused everywhere at once (#29).

    The old contract was "everyone consistently takes GDAL's first layer",
    which was consistent and wrong: Argleton's trap 006 measured describe
    answering about a layer nobody asked for, silently. The new contract is
    refusal with the layers named — and probe_crs reports `unknown` for the
    same case, so the dispatcher and the plan validator never inspect a layer
    no operation will read. Outputs are the opposite case (MapSmith wrote and
    named them), so the verification reader still prefers the stem.
    """
    from mapsmith import readers, verify

    container = tmp_path / "roads.gpkg"
    gpd.GeoDataFrame(
        {"a": [1, 2, 3]}, geometry=gpd.GeoSeries.from_wkt(["POINT (0 0)"] * 3), crs="EPSG:4326"
    ).to_file(container, layer="aaa_scratch", driver="GPKG")
    gpd.GeoDataFrame(
        {"a": [9]}, geometry=gpd.GeoSeries.from_wkt(["POINT (9 45)"]), crs="EPSG:32632"
    ).to_file(container, layer="roads", driver="GPKG")

    with pytest.raises(ValueError, match="aaa_scratch.*roads|roads.*aaa_scratch"):
        readers.read_vector(str(container))
    with pytest.raises(ValueError, match="no layer was chosen"):
        readers.read_vector_capped(str(container), 10)
    assert verify.probe_crs(str(container)) == verify.UNKNOWN_CRS
    # verification, on the other hand, must see the layer MapSmith named
    assert readers.read_vector_or_table(str(container)).crs.to_epsg() == 32632


def test_a_raster_crs_can_be_labelled(tmp_path):
    """`crs_label` is handed rasterio CRSs as well as pyproj ones, and rasterio's
    `to_authority` takes a different keyword name. Getting that wrong crashed
    `preview_map` on every raster whose CRS has no EPSG code."""
    rasterio = pytest.importorskip("rasterio")
    import numpy as np

    from mapsmith import preview, verify

    cases = (
        (rasterio.crs.CRS.from_epsg(32632), "EPSG:32632"),
        (rasterio.crs.CRS.from_proj4(
            "+proj=laea +lat_0=52 +lon_0=10 +datum=WGS84 +units=m +no_defs"), None),
    )
    for index, (crs, expected) in enumerate(cases):
        target = tmp_path / f"r{index}.tif"
        with rasterio.open(
            target, "w", driver="GTiff", height=2, width=2, count=1, dtype="float32",
            crs=crs, transform=rasterio.transform.from_origin(0, 10, 5, 5),
        ) as ds:
            ds.write(np.ones((2, 2), dtype="float32"), 1)
        assert verify.crs_label(crs) != verify.UNKNOWN_CRS
        if expected:
            assert verify.crs_label(crs) == expected
        with rasterio.open(target) as ds:
            stored = ds.crs
        assert preview.raster_preview(str(target))["crs_original"] == verify.crs_label(stored)
        # GDAL renormalises the WKT it stores, so the digest of a CRS handed to
        # the writer and of the same CRS read back can differ. That is the safe
        # direction — an unnecessary reprojection, never a skipped one — and it
        # is why identity is `same_crs`, not string equality.
        assert verify.same_crs(crs, stored)


def test_preview_map_opens_a_native_file(tmp_path):
    from mapsmith import preview

    payload = preview.vector_preview(str(_native_utm(tmp_path, "prev.parquet")))
    assert payload["feature_count"] == 1
    assert payload["crs_original"] == "EPSG:32632"


def test_zonal_statistics_accepts_native_zones(tmp_path):
    """`zones_path` is agent-supplied, so a third-party 2.0 file reaches it."""
    pytest.importorskip("exactextract")
    rasterio = pytest.importorskip("rasterio")
    import numpy as np

    from mapsmith.engines import raster

    dem = tmp_path / "dem.tif"
    with rasterio.open(
        dem, "w", driver="GTiff", height=4, width=4, count=1, dtype="float32",
        crs="EPSG:32632", transform=rasterio.transform.from_origin(499990, 5000010, 5, 5),
    ) as ds:
        ds.write(np.full((4, 4), 7.0, dtype="float32"), 1)

    zones = _native_utm(tmp_path, "zones.parquet", "POLYGON ((499995 4999995, 500005 4999995, "
                        "500005 5000005, 499995 5000005, 499995 4999995))")
    result = raster.zonal_statistics(str(dem), str(zones), str(tmp_path / "zs.parquet"),
                                     stats=["mean"])
    assert result["feature_count"] == 1
    # closed form: the whole raster is 7.0, so the mean over any zone is 7.0
    assert gpd.read_parquet(tmp_path / "zs.parquet")["mean"].tolist() == [7.0]


def test_watershed_accepts_native_pour_points(tmp_path):
    """Only the read is under test: a bad read raises before any hydrology runs."""
    pytest.importorskip("whitebox_workflows")
    from mapsmith.engines import whitebox_engine

    points = _native_utm(tmp_path, "pour.parquet")
    with pytest.raises(Exception) as caught:
        whitebox_engine.watershed(str(tmp_path / "absent.tif"), str(points),
                                  str(tmp_path / "ws.tif"))
    assert "geo metadata" not in str(caught.value).lower()


def test_verification_does_not_read_a_native_file_as_geometryless(tmp_path):
    """The worst of the four: it did not fail, it *misread*.

    A 2.0-native file fell through to the zero-row branch and produced a frame
    whose geometry was all None — reported as `2/2 invalid geometries`, which
    is a critical failure, which triggers the repair that rewrites the file
    with `os.replace`. The repair would have destroyed the output it was
    called to fix.
    """
    frame = verify._read_vector(str(_native_utm(tmp_path, "ver.parquet", rows=2)))
    assert len(frame) == 2
    assert frame.geometry.notna().all(), "geometry was dropped on the verification path"
    assert frame.crs is not None and frame.crs.to_epsg() == 32632


def test_a_crs_named_unknown_is_not_read_as_no_crs(tmp_path):
    """`crs_label` returns a *label*; feeding it back in as a CRS lost real ones.

    pyproj names a PROJJSON document with no authority `unknown`, which is the
    literal value of the UNKNOWN_CRS sentinel — so a file that states its CRS
    read as CRS-less, the same class of bug as #23 wearing a different coat.
    """
    from pyproj import CRS

    from mapsmith import readers

    # A LAEA with a custom origin: no EPSG code to fall back on, and pyproj
    # names it "unknown" all by itself. This is what DuckDB writes.
    unnamed = CRS.from_proj4(
        "+proj=laea +lat_0=52 +lon_0=10 +x_0=4321000 +y_0=3210000 "
        "+datum=WGS84 +units=m +no_defs"
    )
    assert unnamed.name == "unknown" and unnamed.to_epsg() is None, "fixture assumption"

    assert verify.crs_label(unnamed) != verify.UNKNOWN_CRS
    resolved, reason = readers.native_crs(str(tmp_path / "x.parquet"), unnamed.to_json())
    assert reason is None
    assert resolved is not None and resolved.equals(unnamed)


def test_two_different_unnamed_crs_do_not_collapse_to_one_label():
    """Labels are compared, not only printed: `left != right` decides whether an
    overlay reprojects. Two unlike CRSs sharing a label is a wrong answer, not
    an ugly manifest."""
    from pyproj import CRS

    first = CRS.from_proj4("+proj=laea +lat_0=52 +lon_0=10 +datum=WGS84 +units=m +no_defs")
    second = CRS.from_proj4("+proj=laea +lat_0=45 +lon_0=9 +datum=WGS84 +units=m +no_defs")
    assert first.name == second.name == "unknown", "fixture assumption"
    assert verify.crs_label(first) != verify.crs_label(second)

    # And the same two under a shared *name*, which is the common case in the
    # wild (desktop GIS tools hand out "Custom LAEA" and "WGS_1984_Albers"
    # freely).
    # The name branch used to answer first, so the digest never ran.
    named = [
        CRS.from_json_dict(crs.to_json_dict() | {"name": "Custom LAEA"})
        for crs in (first, second)
    ]
    assert named[0].name == named[1].name and not named[0].equals(named[1])
    assert verify.crs_label(named[0]) != verify.crs_label(named[1])
    assert verify.crs_label(first) != verify.crs_label(second)


def test_an_srid_declaration_says_which_one_it_refused(tmp_path):
    """Refusing is right; refusing silently is not. The agent was told the file
    has no CRS, about a file whose schema visibly carries a `crs` field."""
    from mapsmith import readers

    target = _write(tmp_path / "srid.parquet", "SELECT ST_Point(9, 45) AS geom", "NONE")
    crs, reason = readers.native_crs(str(target), "srid:5070")
    assert crs is None
    assert reason is not None
    assert "srid:5070" in reason
    assert "5070" in reason and "authority" in reason.lower()

    frame = gpd.GeoDataFrame({"a": [1]}, geometry=gpd.GeoSeries.from_wkt(["POINT (9 45)"]))
    frame.attrs[readers.CRS_REASON] = reason
    check = next(
        c for c in verify.verify_loaded_inputs("buffer_layer", input_path=frame)
        if c.name == "input_crs_present"
    )
    assert not check.passed
    assert "srid:5070" in check.hint


def test_an_unreadable_declaration_gives_our_message_not_pyprojs(tmp_path):
    """A raw `pyproj.CRSError` beating MapSmith's own message is the failure the
    precondition ordering exists to prevent."""
    from mapsmith import readers

    target = _write(tmp_path / "bad.parquet", "SELECT ST_Point(9, 45) AS geom", "NONE")
    crs, reason = readers.native_crs(str(target), "EPSG:not-a-code")
    assert crs is None
    assert reason and "EPSG:not-a-code" in reason
    crs, reason = readers.native_crs(str(target), '{"not": "a projjson document"}')
    assert crs is None
    assert reason and "PROJJSON" in reason
