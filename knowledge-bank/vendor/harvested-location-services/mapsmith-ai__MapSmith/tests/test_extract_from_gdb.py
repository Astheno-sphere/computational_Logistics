"""extract_layer from a file geodatabase, which the catalog has always promised.

Until 0.7.1 the input digest opened the path as a file, and a `.gdb` is a
directory: the operation died before writing anything. The digest now follows
the specification's rule for directory containers (section 3.3, draft.9), and
the record names the container and the layer read.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

from mapsmith.engines.vector import extract_layer

sys.path.insert(0, str(Path(__file__).parent / "data"))
import manifest_spec_multi_file_digest as reference
import manifest_spec_validator as validator


def _gdb(tmp_path: Path) -> Path:
    gdb = tmp_path / "src.gdb"
    try:
        gpd.GeoDataFrame({"n": [1, 2]}, geometry=[Point(0, 0), Point(1, 1)],
                         crs="EPSG:32633").to_file(gdb, layer="wells", driver="OpenFileGDB")
        gpd.GeoDataFrame({"n": [3]}, geometry=[Point(5, 5)],
                         crs="EPSG:32633").to_file(gdb, layer="roads", driver="OpenFileGDB")
    except Exception as exc:  # noqa: BLE001 -- GDAL builds without the OpenFileGDB writer
        pytest.skip(f"this GDAL cannot write a file geodatabase: {exc}")
    return gdb


def test_a_layer_is_extracted_from_a_file_geodatabase_with_its_digest(tmp_path):
    gdb = _gdb(tmp_path)
    out = tmp_path / "wells.parquet"
    extract_layer(str(gdb), "wells", str(out))
    assert len(gpd.read_parquet(out)) == 2
    record = json.loads(Path(f"{out}.provenance.json").read_text(encoding="utf-8"))
    (entry,) = record["inputs"]
    assert entry["path"].endswith("src.gdb")
    assert entry["layer"] == "wells"
    # Against the specification's reference, not the function that wrote it.
    assert entry["sha256"] == reference.dataset_sha256(gdb)
    assert validator.problems(record) == []


def test_an_operation_reading_a_single_layer_geodatabase_records_the_layer(tmp_path):
    """The layer read is recorded even when the caller did not name it.

    A single-layer `.gdb` handed to any operation is read as its only layer,
    and until 0.8.0 the input carried no `layer`: the lineage walk then met the
    record of that very layer beside the container and stopped with "records
    claim this container's digest, but for other layers" (0.8.0 review).
    """
    import json

    import geopandas as gpd
    from shapely.geometry import Point

    from mapsmith.engines import vector
    from mapsmith.lineage import lineage

    gdb = tmp_path / "one.gdb"
    try:
        gpd.GeoDataFrame({"n": [1]}, geometry=[Point(500000, 5000000)],
                         crs="EPSG:32633").to_file(gdb, layer="wells", driver="OpenFileGDB")
    except Exception as exc:  # noqa: BLE001 -- GDAL builds without the OpenFileGDB writer
        pytest.skip(f"no OpenFileGDB writer: {exc}")
    from mapsmith.provenance import dataset_sha256

    # The record a third party, or a per-engine emitter, writes for that layer.
    (tmp_path / "one.gdb.wells.provenance.json").write_text(json.dumps({
        "spec_version": "1.0.0-draft.10", "operation": "x", "parameters": {}, "inputs": [],
        "output": {"path": "one.gdb", "sha256": dataset_sha256(gdb), "layer": "wells"},
        "engine": {"name": "t", "version": "1"},
        "verification": [{"name": "result_not_empty", "passed": True, "detail": "1"}],
        "started_at": "2026-10-05T08:00:00Z", "finished_at": "2026-10-05T08:00:01Z",
    }), encoding="utf-8")
    out = tmp_path / "buffered.parquet"
    result = vector.buffer(str(gdb), 10.0, str(out))
    manifest = json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))
    assert manifest["inputs"][0].get("layer") == "wells"
    walk = lineage(str(out), scan_root=str(tmp_path))
    assert [step["operation"] for step in walk["steps"]] == ["buffer_layer", "x"], walk["stops"]
