"""Provenance manifest (pure Python)."""
import hashlib

from mikeplus_mcp.contracts import manifest as mf


def test_file_info_hashes_existing_and_flags_missing(tmp_path):
    p = tmp_path / "a.res1d"
    p.write_bytes(b"hello")
    info = mf.file_info(p)
    assert info["exists"] is True
    assert info["bytes"] == 5
    assert info["sha256"] == hashlib.sha256(b"hello").hexdigest()

    gone = mf.file_info(tmp_path / "nope.res1d")
    assert gone == {"path": str(tmp_path / "nope.res1d"), "exists": False, "bytes": None, "sha256": None}


def test_build_manifest_keeps_run_qa_fields_and_drops_noise(tmp_path):
    model = tmp_path / "m.sqlite"
    model.write_bytes(b"db")
    run = {"ok": True, "status": "completed_with_warnings", "warnings": ["w"], "errors": [],
           "elapsed_s": 12.5, "active_simulation": "Sim1", "result_files": ["x.res1d"],
           "_log_tail": "noise that must not be stored"}
    doc = mf.build_manifest(case="c1", model=str(model), inputs=[str(model)],
                            results=["missing.res1d"], run=run, edits=[{"table": "msm_Link"}],
                            tool_calls=[{"tool": "mike_run", "ok": True}], notes="n", version="0.1.0")
    assert doc["schema"] == mf.SCHEMA
    assert doc["engine"] == "mikeplus" and doc["case"] == "c1"
    assert doc["model"]["sha256"] == hashlib.sha256(b"db").hexdigest()
    assert doc["run"]["status"] == "completed_with_warnings"
    assert "_log_tail" not in doc["run"]
    assert doc["edits"] == [{"table": "msm_Link"}]
    assert doc["environment"]["mikeplus_mcp"] == "0.1.0"
    assert mf.missing_files(doc) == ["missing.res1d"]


def test_build_manifest_with_nothing_is_still_well_formed():
    doc = mf.build_manifest()
    assert doc["model"] is None
    assert doc["inputs"] == [] and doc["results"] == [] and doc["figures"] == []
    assert doc["run"] == {}
    assert mf.missing_files(doc) == []
