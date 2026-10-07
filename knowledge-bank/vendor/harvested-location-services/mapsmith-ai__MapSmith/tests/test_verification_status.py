"""The panel must not present an unverifiable output as a verified one (#17).

"All critical checks passed" is vacuously true when no critical check ran.
That is exactly the `run_sql` case — SQL is opaque to static analysis, so its
only check is non-critical and its manifest records no inputs — and it would
put a green tick on the one output in the architecture whose geometry could
have come from the model.
"""

import json

import geopandas as gpd
import pytest
from shapely.geometry import Point

from mapsmith import preview


def _manifest(tmp_path, checks, *, inputs=None, repairs=None, operation="buffer_layer"):
    """Write a dataset plus the manifest the panel will read."""
    target = tmp_path / "layer.parquet"
    gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(0, 0).buffer(1)], crs="EPSG:32632"
    ).to_parquet(target)
    (tmp_path / "layer.parquet.provenance.json").write_text(
        json.dumps({
            "operation": operation,
            "engine": {"name": "geopandas"},
            "inputs": inputs if inputs is not None else [{"path": "in.parquet"}],
            "verification": checks,
            "repairs": repairs or [],
            "finished_at": "2026-08-20T12:00:00Z",
        }),
        encoding="utf-8",
    )
    return str(target)


def test_a_failed_non_critical_check_is_not_verified(tmp_path):
    """The exact shape of a run_sql manifest whose only check failed."""
    path = _manifest(
        tmp_path,
        [{"name": "crs_present", "passed": False, "critical": False,
          "detail": "no geo metadata"}],
        inputs=[],
        operation="run_sql",
    )
    summary = preview.provenance_summary(path)
    assert summary["status"] == "unchecked"
    assert summary["verified"] is False
    assert summary["inputs_recorded"] is False
    assert summary["checks_critical"] == 0


def test_a_passing_non_critical_check_is_still_not_verified(tmp_path):
    """Passing a check nobody considers load-bearing is not verification."""
    path = _manifest(
        tmp_path,
        [{"name": "crs_present", "passed": True, "critical": False,
          "detail": "EPSG:32632"}],
        inputs=[],
        operation="run_sql",
    )
    assert preview.provenance_summary(path)["status"] == "unchecked"


def test_passing_critical_checks_are_verified(tmp_path):
    path = _manifest(tmp_path, [
        {"name": "crs_present", "passed": True, "critical": True, "detail": "EPSG:32632"},
        {"name": "result_not_empty", "passed": False, "critical": False, "detail": "1/1 empty"},
    ])
    summary = preview.provenance_summary(path)
    assert summary["status"] == "verified"
    assert summary["verified"] is True
    assert summary["checks_critical"] == 1


def test_a_failed_critical_check_is_a_failure_not_an_absence(tmp_path):
    path = _manifest(tmp_path, [
        {"name": "crs_present", "passed": True, "critical": True, "detail": "EPSG:32632"},
        {"name": "geometry_valid", "passed": False, "critical": True, "detail": "1/1 invalid"},
    ])
    summary = preview.provenance_summary(path)
    assert summary["status"] == "failed"
    assert summary["verified"] is False


def test_an_empty_check_list_is_unchecked(tmp_path):
    assert preview.provenance_summary(_manifest(tmp_path, []))["status"] == "unchecked"


def test_repairs_are_surfaced_to_the_panel(tmp_path):
    """MapSmith rewriting the user's geometry has to reach the card."""
    path = _manifest(
        tmp_path,
        [{"name": "geometry_valid", "passed": True, "critical": True, "detail": "all valid"}],
        repairs=[{"check": "geometry_valid", "action": "make_valid()", "resolved": True}],
    )
    summary = preview.provenance_summary(path)
    assert summary["status"] == "verified"
    assert summary["repairs"] == 1


def test_the_panel_renders_all_three_states(tmp_path):
    """The badge text and the CSS token for each state must exist in the panel,
    or a state would render unstyled or unlabelled."""
    from mapsmith import ui

    for token in ("verified ✓", "verification failed", "not verifiable"):
        assert token in ui.MAP_HTML
    for css in ("--warn:", ".warn {"):
        assert css in ui.MAP_HTML
    # the token must be defined in both themes, not only the default one
    assert ui.MAP_HTML.count("--warn:") >= 2


@pytest.mark.parametrize("missing", ["verification", "inputs", "repairs"])
def test_older_manifests_do_not_crash_the_panel(tmp_path, missing):
    """0.1.0 manifests have no repairs field; a manifest could also be
    truncated. The panel must degrade, not raise."""
    target = tmp_path / "layer.parquet"
    gpd.GeoDataFrame({"id": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326").to_parquet(target)
    manifest = {
        "operation": "buffer_layer",
        "engine": {"name": "geopandas"},
        "inputs": [{"path": "in.parquet"}],
        "verification": [{"name": "crs_present", "passed": True, "critical": True}],
        "repairs": [],
    }
    del manifest[missing]
    (tmp_path / "layer.parquet.provenance.json").write_text(json.dumps(manifest), encoding="utf-8")

    summary = preview.provenance_summary(str(target))
    assert summary is not None
    assert summary["status"] in ("verified", "unchecked", "failed")
