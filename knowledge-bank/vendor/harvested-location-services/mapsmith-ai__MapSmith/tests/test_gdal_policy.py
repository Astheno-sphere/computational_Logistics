"""GDAL must not resolve indirection to the network when remote reads are off.

The path guard and the SQL scan check the string they are handed. GDAL does not:
a `.vrt` is a plain local path — no scheme, no `/vsi` prefix — and GDAL fetches
whatever its `<SrcDataSource>` names, in-process. Before `gdal_policy` existed,
reading such a file from *inside* a workspace sent HEAD and GET to an
attacker-named host, which contradicted the one promise SECURITY.md states as
testable.

These tests run in subprocesses on purpose: GDAL reads GDAL_SKIP/OGR_SKIP once,
when it registers drivers, so a change is only observable in a fresh process.
The assertion is always whether a request reached the loopback server — never
the error message, which differs by GDAL build.
"""

import http.server
import json
import os
import socket
import subprocess
import sys
import textwrap
import threading

import pytest

pytest.importorskip("pyogrio")

FEATURES = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"leaked": "SECRET-VALUE"},
            "geometry": {"type": "Point", "coordinates": [9.19, 45.46]},
        }
    ],
}


class _Server:
    """Loopback server that records every request it receives."""

    def __init__(self):
        body = json.dumps(FEATURES).encode()
        self.hits: list[str] = []
        hits = self.hits

        class Handler(http.server.BaseHTTPRequestHandler):
            def _reply(self, with_body):
                hits.append(f"{self.command} {self.path}")
                self.send_response(200)
                self.send_header("Content-Type", "application/geo+json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if with_body:
                    self.wfile.write(body)

            def do_GET(self):
                self._reply(True)

            def do_HEAD(self):
                self._reply(False)

            def log_message(self, *args):
                pass

        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        self.port = probe.getsockname()[1]
        probe.close()
        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    def stop(self):
        self._httpd.shutdown()


def gdal_policy_names():
    return ("GDAL_SKIP", "OGR_SKIP")


def _read_vrt_in_subprocess(vrt_path, allow_remote, workspace=None):
    """Import mapsmith (which installs the policy), then read the VRT."""
    code = textwrap.dedent(
        """
        import sys
        sys.path.insert(0, sys.argv[1])
        import mapsmith            # installs the GDAL driver policy
        import pyogrio
        try:
            pyogrio.read_dataframe(sys.argv[2])
            print("READ_OK")
        except Exception as exc:
            print(f"REFUSED {type(exc).__name__}")
        """
    )
    env = dict(os.environ)
    # the test process has imported mapsmith, so its own environment already
    # carries the policy; the child must start from a clean slate or it would be
    # testing what it inherited instead of what it decides
    for name in (
        *gdal_policy_names(),
        "MAPSMITH_ALLOW_REMOTE",
        "MAPSMITH_GDAL_POLICY",
        "MAPSMITH_WORKSPACE",
    ):
        env.pop(name, None)
    if allow_remote:
        env["MAPSMITH_ALLOW_REMOTE"] = "1"
    if workspace is not None:
        env["MAPSMITH_WORKSPACE"] = str(workspace)
    src = str(pytest.importorskip("mapsmith").__path__[0] + "/..")
    # check=False: a refusal is a legitimate outcome here, and the assertion is
    # what reached the listener rather than the child's exit code
    return subprocess.run(
        [sys.executable, "-c", code, src, str(vrt_path)],
        capture_output=True, text=True, env=env, timeout=120, check=False,
    ).stdout.strip()


def _write_vrt(tmp_path, source):
    vrt = tmp_path / "indirection.vrt"
    vrt.write_text(
        '<OGRVRTDataSource><OGRVRTLayer name="lyr">'
        f'<SrcDataSource relativeToVRT="0">{source}</SrcDataSource>'
        "</OGRVRTLayer></OGRVRTDataSource>",
        encoding="utf-8",
    )
    return vrt


def test_a_vrt_cannot_reach_the_network_by_default(tmp_path):
    server = _Server()
    try:
        vrt = _write_vrt(tmp_path, f"/vsicurl/http://127.0.0.1:{server.port}/x.geojson")
        _read_vrt_in_subprocess(vrt, allow_remote=False)
        assert server.hits == [], f"the indirection still reached the network: {server.hits}"
    finally:
        server.stop()


def test_the_opt_in_restores_indirection(tmp_path):
    """The capability is gated, not removed: with the switch on, GDAL resolves it."""
    server = _Server()
    try:
        vrt = _write_vrt(tmp_path, f"/vsicurl/http://127.0.0.1:{server.port}/x.geojson")
        _read_vrt_in_subprocess(vrt, allow_remote=True)
        assert server.hits, "the opt-in did not restore remote indirection"
    finally:
        server.stop()


def test_a_workspace_beats_the_opt_in(tmp_path):
    """The two layers used to disagree, and the weaker one won.

    `workspace.remote_reason` refuses remote forms under a workspace whatever
    MAPSMITH_ALLOW_REMOTE says, but `gdal_policy.apply` read the variable alone
    — so with both set, GDAL's indirection drivers came back and a .vrt *inside*
    the workspace fetched a URL, past every guard, in the configuration
    SECURITY.md calls the safest. Every other test here removes
    MAPSMITH_WORKSPACE from the child's environment, which is exactly why the
    combination went unnoticed.
    """
    server = _Server()
    try:
        vrt = _write_vrt(tmp_path, f"http://127.0.0.1:{server.port}/x.geojson")
        _read_vrt_in_subprocess(vrt, allow_remote=True, workspace=tmp_path)
        assert server.hits == [], (
            f"the opt-in lifted the policy under a workspace: {server.hits}"
        )
    finally:
        server.stop()


def test_ordinary_local_data_still_reads(tmp_path):
    """The policy must not cost the formats MapSmith exists to read."""
    plain = tmp_path / "plain.geojson"
    plain.write_text(json.dumps(FEATURES), encoding="utf-8")
    assert _read_vrt_in_subprocess(plain, allow_remote=False) == "READ_OK"


def test_the_skip_lists_are_comma_separated():
    """GDAL parses these as comma-separated lists. Space separation produces one
    token that matches no driver, so the policy would look installed — variables
    set, code run — and do nothing at all."""
    from mapsmith import gdal_policy

    merged = gdal_policy._merge("EXISTING", ("VRT", "WMS"))
    assert merged == "EXISTING,VRT,WMS"
    assert " " not in merged


def test_an_operators_own_skip_list_is_kept():
    from mapsmith import gdal_policy

    assert gdal_policy._merge("MBTiles,VRT", ("VRT", "WMS")) == "MBTiles,VRT,WMS"


def test_lifting_the_policy_leaves_what_the_operator_set(monkeypatch):
    """These variables are inherited: a container passes its whole environment
    down, so the opt-in has to be able to LIFT a policy a parent installed —
    without undoing a skip list the operator set for their own reasons."""
    from mapsmith import gdal_policy

    monkeypatch.delenv("MAPSMITH_ALLOW_REMOTE", raising=False)
    monkeypatch.setenv("GDAL_SKIP", "MBTiles")
    monkeypatch.delenv("OGR_SKIP", raising=False)
    monkeypatch.delenv(gdal_policy.SENTINEL, raising=False)

    gdal_policy.apply()
    assert "VRT" in os.environ["GDAL_SKIP"]
    assert "MBTiles" in os.environ["GDAL_SKIP"]
    assert os.environ[gdal_policy.SENTINEL] == "applied"

    monkeypatch.setenv("MAPSMITH_ALLOW_REMOTE", "1")
    gdal_policy.apply()
    assert os.environ.get("GDAL_SKIP") == "MBTiles", os.environ.get("GDAL_SKIP")
    assert "OGR_SKIP" not in os.environ
    assert gdal_policy.SENTINEL not in os.environ


def test_without_the_sentinel_nothing_is_touched(monkeypatch):
    """An operator's own skip list survives a MapSmith that never installed one."""
    from mapsmith import gdal_policy

    monkeypatch.setenv("MAPSMITH_ALLOW_REMOTE", "1")
    monkeypatch.setenv("GDAL_SKIP", "VRT")
    monkeypatch.delenv(gdal_policy.SENTINEL, raising=False)
    gdal_policy.apply()
    assert os.environ["GDAL_SKIP"] == "VRT"

# Every driver still visible once the policy is installed, reviewed by hand on
# 2026-08-22 (pyogrio 0.13 / GDAL 3.12.4). This list is not decoration: it is
# the only mechanism that catches a NEW driver. GDALG arrived in GDAL 3.11 —
# after the deny-list was written — and reopened the entire class 0.2.2 claims
# to close, readable from a plain local file inside the workspace, under any
# extension at all.
_REVIEWED = {
    "AIVector", "AVCBin", "AVCE00", "CSV", "DGN", "DXF", "EDIGEO", "EEDA",
    "ESRI Shapefile", "ESRIJSON", "FlatGeobuf", "GML", "GPKG", "GPSBabel", "GPX", "GTFS",
    "GeoJSON", "GeoJSONSeq", "GeoRSS", "Idrisi", "JML", "JSONFG", "KML", "LIBKML", "LVBAG",
    "MBTiles", "MEM", "MVT", "MapInfo File", "MapML", "MiraMonVector", "ODS", "OGR_GMT",
    "OGR_PDS", "OSM", "OpenFileGDB", "PDS4", "PGDUMP", "PMTiles", "S57", "SQLite", "SXF",
    "Selafin", "TopoJSON", "VDV", "VFK", "VICAR", "WAsP", "XLSX"
}


def test_no_new_driver_escapes_the_policy():
    """Fail when GDAL registers something nobody has reviewed yet.

    A deny-list over an evolving set is a list that is wrong between one
    upstream release and the next. This test does not stop a new driver from
    existing; it stops one from arriving UNLOOKED AT. When it fails there is a
    single question to answer — can this driver open another dataset, by
    network or by path? If it can, it belongs in the skip list; if it cannot,
    add it here with the date it was reviewed.
    """
    # In a clean subprocess, like the other tests here: GDAL reads GDAL_SKIP
    # when it registers drivers, and in the pytest process the geospatial stack
    # is already initialised by another test module before the policy applies.
    # An in-process check would measure import order, not the policy.
    pytest.importorskip("pyogrio")
    env = dict(os.environ)
    for name in (
        *gdal_policy_names(),
        "MAPSMITH_ALLOW_REMOTE",
        "MAPSMITH_GDAL_POLICY",
        "MAPSMITH_WORKSPACE",
    ):
        env.pop(name, None)
    visible = json.loads(
        subprocess.run(
            [
                sys.executable,
                "-c",
                "import mapsmith, pyogrio, json; print(json.dumps(sorted(pyogrio.list_drivers())))",
            ],
            capture_output=True, text=True, env=env, timeout=120, check=True,
        ).stdout
    )
    unreviewed = set(visible) - _REVIEWED
    assert not unreviewed, (
        f"GDAL registers drivers nobody has reviewed: {sorted(unreviewed)}. Any of them "
        "can be another indirection like GDALG: decide whether to skip it, or add "
        "it to _REVIEWED with the date."
    )


def test_a_gdalg_file_cannot_reach_the_network(tmp_path):
    """GDALG is the .vrt under another name, only worse: it is recognised by
    CONTENT, so the filename says nothing, and its command line can name a local
    path as readily as a URL. Measured before the fix: a file called
    `roads.geojson` inside the workspace issued HEAD and GET, and another read a
    dataset from OUTSIDE the workspace and handed back its rows.
    """
    server = _Server()
    try:
        bait = tmp_path / "recognised_by_content.geojson"
        bait.write_text(
            json.dumps({
                "type": "gdal_streamed_alg",
                "command_line": (
                    f"gdal vector convert http://127.0.0.1:{server.port}/x.geojson "
                    "--output-format=stream streamed_dataset"
                ),
            }),
            encoding="utf-8",
        )
        _read_vrt_in_subprocess(bait, allow_remote=False, workspace=tmp_path)
        assert server.hits == [], f"GDALG reached the network: {server.hits}"
    finally:
        server.stop()
