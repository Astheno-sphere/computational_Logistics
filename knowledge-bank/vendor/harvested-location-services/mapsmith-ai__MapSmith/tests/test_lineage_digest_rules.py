"""get_lineage across the draft.9 digest rule, and on layers of one container.

Records written up to 0.7.1 digest a shapefile as its `.shp` alone; records
written now digest it as the listing of its data files (spec section 3.3). A
walker that compared every record against the new rule would call unchanged
data edited and stop every chain at the boundary. And a container's digest
identifies the container, not the layer (spec section 6), so a hop into a
container must match the layer too.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "data"))

import manifest_spec_validator as validator

from mapsmith.lineage import lineage
from mapsmith.provenance import SPEC_VERSION, dataset_sha256

PASSED = [{"name": "result_not_empty", "passed": True, "detail": "1 row", "critical": True}]


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def shapefile(folder: Path, stem: str, content: bytes) -> Path:
    for ext in (".shp", ".shx", ".dbf", ".prj"):
        (folder / f"{stem}{ext}").write_bytes(content + ext.encode())
    return folder / f"{stem}.shp"


def record(output_path: str, output_sha: str, inputs: list[dict], spec: str, layer=None) -> dict:
    out = {"path": output_path, "sha256": output_sha}
    if layer is not None:
        out["layer"] = layer
    rec = {
        "spec_version": spec,
        "operation": "op",
        "parameters": {},
        "inputs": inputs,
        "output": out,
        "engine": {"name": "test", "version": "1.0"},
        "verification": PASSED,
        "started_at": "2026-09-27T08:00:00Z",
        "finished_at": "2026-09-27T08:00:01Z",
    }
    assert not validator.problems(rec)
    return rec


def write(path: Path, rec: dict) -> None:
    path.write_text(json.dumps(rec), encoding="utf-8")


def test_a_record_from_071_still_matches_its_unchanged_shapefile(tmp_path):
    shp = shapefile(tmp_path, "roads", b"r")
    write(Path(f"{shp}.provenance.json"),
          record("roads.shp", sha_file(shp), [], "1.0.0-draft.8"))
    result = lineage(shp, scan_root=tmp_path)
    assert result["root"]["manifest_beside"] == "matched"
    # The .shp is confirmed; the attributes and the CRS were never in that
    # record's digest, so the walk does not vouch for them.
    assert [step["claim"] for step in result["steps"]] == ["reverified_shp_only"]
    assert result["verified"] is False


def test_a_record_from_071_does_not_vouch_for_attributes_edited_after_it(tmp_path):
    shp = shapefile(tmp_path, "roads", b"r")
    write(Path(f"{shp}.provenance.json"),
          record("roads.shp", sha_file(shp), [], "1.0.0-draft.8"))
    (tmp_path / "roads.dbf").write_bytes(b"attributes rewritten after the run")
    result = lineage(shp, scan_root=tmp_path)
    assert [step["claim"] for step in result["steps"]] == ["reverified_shp_only"]
    assert result["verified"] is False


def test_a_chain_crosses_the_rule_boundary(tmp_path):
    # Upstream: a shapefile written by 0.7.1 (legacy digest). Downstream: a
    # record written now, whose input digest is the listing of that shapefile.
    source = tmp_path / "source.gpkg"
    source.write_bytes(b"source")
    shp = shapefile(tmp_path, "roads", b"r")
    write(Path(f"{shp}.provenance.json"), record(
        "roads.shp", sha_file(shp),
        [{"path": "source.gpkg", "sha256": sha_file(source)}], "1.0.0-draft.8"))
    final = tmp_path / "final.parquet"
    final.write_bytes(b"final")
    write(Path(f"{final}.provenance.json"), record(
        "final.parquet", sha_file(final),
        [{"path": "roads.shp", "sha256": dataset_sha256(shp)}], SPEC_VERSION))
    result = lineage(final, scan_root=tmp_path)
    assert len(result["steps"]) == 2, result["stopped_at"]
    assert [step["claim"] for step in result["steps"]] == ["reverified", "reverified_shp_only"]
    assert result["complete"] is True
    assert result["verified"] is False  # the upstream record vouches for the .shp alone
    assert [stop["sha256"] for stop in result["stopped_at"]] == [sha_file(source)]


def test_a_hop_into_a_container_matches_the_layer(tmp_path):
    gdb = tmp_path / "out.gdb"
    gdb.mkdir()
    (gdb / "a00000001.gdbtable").write_bytes(b"both layers live here")
    container = dataset_sha256(gdb)
    for layer, op in (("wells", "buffer_wells"), ("roads", "buffer_roads")):
        rec = record("out.gdb", container, [], SPEC_VERSION, layer=layer)
        rec["operation"] = op
        write(tmp_path / f"out.gdb.{layer}.provenance.json", rec)

    def downstream(name: str, layer):
        target = tmp_path / f"{name}.parquet"
        target.write_bytes(name.encode())
        inp = {"path": "out.gdb", "sha256": container}
        if layer:
            inp["layer"] = layer
        write(Path(f"{target}.provenance.json"),
              record(target.name, sha_file(target), [inp], SPEC_VERSION))
        return target

    from_roads = lineage(downstream("from_roads", "roads"), scan_root=tmp_path)
    assert [s["operation"] for s in from_roads["steps"]] == ["op", "buffer_roads"]

    unnamed = lineage(downstream("unnamed", None), scan_root=tmp_path)
    assert [s["operation"] for s in unnamed["steps"]] == ["op"]
    assert [stop["reason"] for stop in unnamed["stopped_at"]] == ["other_layer"]
    assert unnamed["complete"] is False


def _two_layer_container(tmp_path):
    """out.gdb with two layers, each written by its own operation from its own source."""
    gdb = tmp_path / "out.gdb"
    gdb.mkdir()
    (gdb / "a00000001.gdbtable").write_bytes(b"both layers live here")
    container = dataset_sha256(gdb)
    for layer in ("wells", "roads"):
        src = tmp_path / f"{layer}_source.gpkg"
        src.write_bytes(layer.encode())
        rec = record("out.gdb", container,
                     [{"path": src.name, "sha256": sha_file(src)}], SPEC_VERSION, layer=layer)
        rec["operation"] = f"write_{layer}"
        write(tmp_path / f"out.gdb.{layer}.provenance.json", rec)
    return gdb, container


def test_a_layer_record_is_rechecked_against_its_container(tmp_path):
    # Section 3.1 puts a layer's record beside the container, not beside a file
    # named after the layer: stripping the suffix alone found nothing, and every
    # hop into a geodatabase read as a claim about a missing output.
    _, container = _two_layer_container(tmp_path)
    target = tmp_path / "final.parquet"
    target.write_bytes(b"final")
    write(Path(f"{target}.provenance.json"), record(
        target.name, sha_file(target),
        [{"path": "out.gdb", "sha256": container, "layer": "roads"}], SPEC_VERSION))
    result = lineage(target, scan_root=tmp_path)
    (hop,) = [s for s in result["steps"] if s["operation"] == "write_roads"]
    assert hop["claim"] == "reverified"
    assert hop["output"]["layer"] == "roads"
    # Two records claim the container, one claims the layer: not a competition.
    assert "competing_claims" not in hop
    assert result["verified"] is True and result["complete"] is True


def test_two_layers_of_one_container_on_two_branches_are_two_histories(tmp_path):
    _, container = _two_layer_container(tmp_path)
    target = tmp_path / "joined.parquet"
    target.write_bytes(b"joined")
    write(Path(f"{target}.provenance.json"), record(
        target.name, sha_file(target),
        [{"path": "out.gdb", "sha256": container, "layer": "roads"},
         {"path": "out.gdb", "sha256": container, "layer": "wells"}], SPEC_VERSION))
    result = lineage(target, scan_root=tmp_path)
    assert sorted(s["operation"] for s in result["steps"]) == ["op", "write_roads", "write_wells"]
    assert not any("subtree_shown_at" in s for s in result["steps"])
    assert len(result["stopped_at"]) == 2
    assert result["summary"].startswith("3 operations recovered back to 2 original")


def test_a_container_walked_without_a_layer_does_not_say_nobody_claims_it(tmp_path):
    gdb, _ = _two_layer_container(tmp_path)
    result = lineage(gdb, scan_root=tmp_path)
    assert result["steps"] == []
    assert [stop["reason"] for stop in result["stopped_at"]] == ["other_layer"]
    assert "No manifest claims" not in result["summary"]


def test_later_means_semver_precedence():
    from mapsmith.provenance import declares_listing_rule

    later = ["1.0.0-draft.9", "1.0.0-draft.10", "1.0.0", "1.0.0-rc.1", "1.1.0-draft.1", "1.2.0"]
    earlier = ["1.0.0-draft.8", "1.0.0-draft.2", "1.0.0-alpha", "not-a-version", None,
               "1.0.0-draft.09"]
    assert all(declares_listing_rule({"spec_version": v}) for v in later)
    assert not any(declares_listing_rule({"spec_version": v}) for v in earlier)


def test_the_history_of_one_layer_starts_from_the_geodatabase(tmp_path):
    source = tmp_path / "source.gpkg"
    source.write_bytes(b"source")
    gdb = tmp_path / "out.gdb"
    gdb.mkdir()
    (gdb / "a00000001.gdbtable").write_bytes(b"two layers")
    container = dataset_sha256(gdb)
    for layer, op in (("wells", "buffer_wells"), ("roads", "buffer_roads")):
        rec = record("out.gdb", container,
                     [{"path": "source.gpkg", "sha256": sha_file(source)}], SPEC_VERSION, layer=layer)
        rec["operation"] = op
        write(tmp_path / f"out.gdb.{layer}.provenance.json", rec)

    result = lineage(gdb, scan_root=tmp_path, layer="roads")
    assert result["root"]["manifest_beside"] == "matched"
    assert [s["operation"] for s in result["steps"]] == ["buffer_roads"]
    assert result["complete"] is True


def test_a_layer_for_a_plain_file_is_refused(tmp_path):
    f = tmp_path / "a.parquet"
    f.write_bytes(b"x")
    with pytest.raises(ValueError, match="not a directory container"):
        lineage(f, scan_root=tmp_path, layer="roads")


def test_shapefiles_off_the_chain_are_not_hashed(tmp_path, monkeypatch):
    """Indexing reads JSON; a shapefile is hashed only when a hop needs it.

    Until 0.8.0 every lineage call hashed every shapefile record's output while
    indexing, whatever the chain asked about -- tens of gigabytes on a
    workspace of large shapefiles (0.8.0 review and audit). Three shapefiles
    unrelated to a parquet chain must now cost nothing.
    """
    monkeypatch.chdir(tmp_path)
    import mapsmith.lineage as lineage_module

    calls = []
    real = lineage_module.shapefile_digests
    monkeypatch.setattr(
        lineage_module, "shapefile_digests", lambda path: calls.append(path) or real(path)
    )
    for n in range(3):
        shp = shapefile(tmp_path, f"other{n}", b"x" * (n + 1))
        write(Path(str(shp) + ".provenance.json"),
              record(shp.name, dataset_sha256(shp), [], SPEC_VERSION))
    src = tmp_path / "a.parquet"
    src.write_bytes(b"a")
    out = tmp_path / "b.parquet"
    out.write_bytes(b"b")
    write(Path(str(src) + ".provenance.json"), record("a.parquet", sha_file(src), [], SPEC_VERSION))
    write(Path(str(out) + ".provenance.json"),
          record("b.parquet", sha_file(out), [{"path": "a.parquet", "sha256": sha_file(src)}],
                 SPEC_VERSION))
    result = lineage(str(out), scan_root=str(tmp_path))
    assert len(result["steps"]) == 2
    assert calls == [], f"hashed shapefiles that are not on the chain: {calls}"


@pytest.mark.parametrize("layer", ["a:b", "roads\x00", "x\ny"])
def test_a_layer_naming_a_stream_or_holding_control_characters_is_refused(tmp_path, layer):
    gdb = tmp_path / "data.gdb"
    gdb.mkdir()
    (gdb / "a.gdbtable").write_bytes(b"1")
    with pytest.raises(ValueError, match="control character"):
        lineage(str(gdb), scan_root=str(tmp_path), layer=layer)
