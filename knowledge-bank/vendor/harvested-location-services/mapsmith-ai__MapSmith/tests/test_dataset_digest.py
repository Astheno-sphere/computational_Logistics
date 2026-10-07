"""The digest a manifest records for a dataset made of several files (spec §3.3, draft.9).

Until 0.7.1 an input shapefile was digested as its `.shp` alone: a record kept
matching a dataset whose attributes (`.dbf`) or CRS (`.prj`) had been rewritten,
while it said `sha256` is "of the bytes". The expected values here are built
from hashlib by hand, so the test does not trust the function it checks.
"""

from __future__ import annotations

import hashlib
import sys

import geopandas as gpd
import pytest
from shapely.geometry import Point

from mapsmith.provenance import InputRecord, dataset_sha256


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def by_hand(lines: list[tuple[str, str]]) -> str:
    return sha("".join(f"{p}\0{s}\n" for p, s in lines).encode("utf-8"))


def test_a_shapefile_digest_is_the_listing_of_its_data_files(tmp_path):
    for ext, content in (
        (".shp", b"geom"), (".shx", b"idx"), (".dbf", b"attrs"), (".prj", b"crs"),
        (".cpg", b"UTF-8"), (".sbn", b"index"), (".shp.xml", b"metadata"),
    ):
        (tmp_path / f"roads{ext}").write_bytes(content)
    # Named by extension, not by file name: renaming a shapefile keeps its digest.
    assert dataset_sha256(tmp_path / "roads.shp") == by_hand([
        (".cpg", sha(b"UTF-8")), (".dbf", sha(b"attrs")), (".prj", sha(b"crs")),
        (".shp", sha(b"geom")), (".shx", sha(b"idx")),
    ])


def test_renaming_a_shapefile_keeps_its_digest(tmp_path):
    for folder, stem in ((tmp_path / "a", "roads"), (tmp_path / "b", "delivered")):
        folder.mkdir()
        for ext in (".shp", ".dbf", ".prj"):
            (folder / f"{stem}{ext}").write_bytes(ext.encode())
    assert dataset_sha256(tmp_path / "a" / "roads.shp") == dataset_sha256(
        tmp_path / "b" / "delivered.shp"
    )


def test_rewriting_the_attributes_of_an_input_shapefile_changes_its_recorded_digest(tmp_path):
    shp = tmp_path / "wells.shp"
    gpd.GeoDataFrame({"depth": [10, 20]}, geometry=[Point(0, 0), Point(1, 1)],
                     crs="EPSG:32633").to_file(shp)
    before = InputRecord.from_path(shp).sha256
    gpd.GeoDataFrame({"depth": [10, 99]}, geometry=[Point(0, 0), Point(1, 1)],
                     crs="EPSG:32633").to_file(shp)
    assert InputRecord.from_path(shp).sha256 != before, (
        "the attributes changed and the digest did not: the record would still match"
    )


def test_a_file_geodatabase_is_digested_without_its_lock_files(tmp_path):
    gdb = tmp_path / "data.gdb"
    gdb.mkdir()
    (gdb / "a00000001.gdbtable").write_bytes(b"one")
    before = dataset_sha256(gdb)
    assert before == by_hand([("a00000001.gdbtable", sha(b"one"))])
    (gdb / "_gdb.HOST.1.2.sr.lock").write_bytes(b"volatile")
    assert dataset_sha256(gdb) == before


def test_a_single_file_keeps_the_plain_sha256(tmp_path):
    f = tmp_path / "a.parquet"
    f.write_bytes(b"abc")
    assert dataset_sha256(f) == sha(b"abc")


def test_a_missing_shapefile_is_an_error_not_an_empty_digest(tmp_path):
    with pytest.raises(FileNotFoundError):
        dataset_sha256(tmp_path / "nothing.shp")


def test_mapsmith_digests_what_the_specification_reference_digests(tmp_path):
    """Three implementations of one rule (spec reference, the ArcGIS Pro emitter,
    MapSmith) are three chances to disagree; this holds MapSmith to the reference."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent / "data"))
    import manifest_spec_multi_file_digest as reference

    shp_dir = tmp_path / "shp"
    shp_dir.mkdir()
    for name, content in (("Roads.SHP", b"g"), ("roads.dbf", b"a"), ("roads.prj", b"c"),
                          ("roads.sbn", b"i"), ("roads.shp.xml", b"m")):
        (shp_dir / name).write_bytes(content)
    gdb = tmp_path / "t.gdb"
    (gdb / "sub").mkdir(parents=True)
    for name, content in (("a.gdbtable", b"1"), ("sub/b.spx", b"2"), ("x.lock", b"v"),
                          (".DS_Store", b"f"), ("Thumbs.db", b"t")):
        (gdb / name).write_bytes(content)
    single = tmp_path / "one.parquet"
    single.write_bytes(b"p")
    for path in (shp_dir / "roads.shp", gdb, single):
        assert dataset_sha256(path) == reference.dataset_sha256(path), path


def test_the_vendored_reference_is_the_published_one():
    """Drift between the copy and upstream is a finding: the test above would then
    hold MapSmith to a rule the specification no longer states."""
    import ast
    from pathlib import Path

    from conftest import spec_checkout

    spec_repo = spec_checkout()

    def body(path: Path) -> list[str]:
        source = path.read_text(encoding="utf-8")
        first = ast.parse(source).body[0]
        return source.splitlines()[first.end_lineno:]

    here = Path(__file__).parent / "data" / "manifest_spec_multi_file_digest.py"
    there = spec_repo / "examples" / "multi_file_digest.py"
    assert body(here) == body(there), "re-vendor the reference digest from manifest-spec"


def test_a_writer_reading_and_writing_shapefiles_records_both_listings(tmp_path):
    """No fixture of the conformance sweep reads or writes a shapefile, so the
    listing rule was checked on hand-made files and never on a real record.
    A real writer here, a shapefile on both sides, and the digests recomputed by
    the specification's reference rather than by the function under test."""
    import json
    import sys
    from pathlib import Path

    from conftest import _spec_problems
    from mapsmith.engines import vector
    from mapsmith.provenance import SPEC_VERSION, declares_listing_rule

    sys.path.insert(0, str(Path(__file__).parent / "data"))
    import manifest_spec_multi_file_digest as reference

    source = tmp_path / "wells.shp"
    gpd.GeoDataFrame({"depth": [10, 20]}, geometry=[Point(0, 0), Point(100, 100)],
                     crs="EPSG:32633").to_file(source)
    out = tmp_path / "wells_10m.shp"
    vector.buffer(str(source), 10.0, str(out))

    record = json.loads(Path(f"{out}.provenance.json").read_text(encoding="utf-8"))
    assert _spec_problems(record) == []
    assert record["spec_version"] == SPEC_VERSION and declares_listing_rule(record)
    assert record["inputs"][0]["sha256"] == reference.dataset_sha256(source)
    assert record["output"]["sha256"] == reference.dataset_sha256(out)
    assert record["output"]["sha256"] != sha(out.read_bytes()), "the .shp alone again"


def test_an_ambiguous_shapefile_output_keeps_its_manifest_without_a_digest(
    tmp_path, monkeypatch
):
    """Section 3.3 forbids a digest when two files match one member. Raising in
    `write_for` would leave the dataset on disk without its manifest, which is
    the one outcome invariant 2 exists to rule out. The case-sensitive
    filesystem that allows `out.dbf` beside `out.DBF` is simulated."""
    import json
    from pathlib import Path

    from mapsmith import provenance
    from mapsmith.provenance import ProvenanceRecord

    out = tmp_path / "out.parquet"
    out.write_bytes(b"data")

    def ambiguous(path):
        raise ValueError("two files match the .dbf member of out.shp")

    monkeypatch.setattr(provenance, "dataset_sha256", ambiguous)
    manifest = ProvenanceRecord(operation="op", parameters={}, inputs=[]).finish().write_for(out)
    record = json.loads(Path(manifest).read_text(encoding="utf-8"))
    assert "output" not in record
    assert any("output digest not recorded" in note for note in record["notes"])


@pytest.mark.skipif(sys.platform != "win32", reason="junctions are a Windows reparse point")
def test_a_junction_inside_a_container_is_neither_a_member_nor_followed(tmp_path):
    """Spec section 3.3: links are neither members nor followed, and a junction is one.

    `is_symlink()` is False for a junction, so until 0.8.0 the walk followed it:
    a junction inside a `.gdb` pointing outside the workspace put files from
    there into the digest (0.8.0 audit). The size the cap reads counts the same
    files the digest reads.
    """
    import subprocess

    from mapsmith.provenance import dataset_size

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_bytes(b"not part of the geodatabase")
    gdb = tmp_path / "data.gdb"
    gdb.mkdir()
    (gdb / "a.gdbtable").write_bytes(b"1")
    before = dataset_sha256(gdb)
    size_before = dataset_size(gdb)
    done = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(gdb / "jn"), str(outside)],
        capture_output=True, text=True, check=False,
    )
    assert done.returncode == 0, done.stderr
    assert (gdb / "jn" / "secret.txt").exists(), "the junction was not created"
    assert dataset_sha256(gdb) == before
    assert dataset_size(gdb) == size_before
