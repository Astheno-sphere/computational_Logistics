"""DuckDB connection sandbox: run_sql confinement when MAPSMITH_WORKSPACE is set.

SQL text can name any file, so the tool-boundary path jail cannot see it —
the engine connection itself must refuse anything outside the workspace.
These tests probe the real DuckDB behavior, including the corners the docs
leave open (prefix matching vs traversal), so a duckdb version bump that
weakens the sandbox fails CI here.
"""

import pytest

duckdb = pytest.importorskip("duckdb")

from mapsmith.engines import duckdb_engine


@pytest.fixture
def ws(monkeypatch, tmp_path):
    root = tmp_path / "ws"
    root.mkdir()
    monkeypatch.setenv("MAPSMITH_WORKSPACE", str(root))
    return root


def _plain_write_parquet(path, value: int) -> None:
    """Write a parquet OUTSIDE the sandbox, with a plain unrestricted connection."""
    con = duckdb.connect()
    con.execute(f"COPY (SELECT {value} AS v) TO '{str(path).replace(chr(92), '/')}' (FORMAT parquet)")
    con.close()


def test_io_inside_workspace_works(ws):
    con = duckdb_engine._connect()
    target = str(ws / "t.parquet").replace("\\", "/")
    con.execute(f"COPY (SELECT 42 AS v) TO '{target}' (FORMAT parquet)")
    assert con.sql(f"SELECT v FROM read_parquet('{target}')").fetchone()[0] == 42


def test_read_outside_workspace_refused(ws, tmp_path):
    outside = tmp_path / "outside.parquet"
    _plain_write_parquet(outside, 7)
    con = duckdb_engine._connect()
    with pytest.raises(duckdb.Error, match="(?i)permission"):
        con.sql(f"SELECT * FROM read_parquet('{str(outside).replace(chr(92), '/')}')").fetchall()


def test_write_outside_workspace_refused(ws, tmp_path):
    con = duckdb_engine._connect()
    target = str(tmp_path / "leak.parquet").replace("\\", "/")
    with pytest.raises(duckdb.Error, match="(?i)permission"):
        con.execute(f"COPY (SELECT 1 AS v) TO '{target}' (FORMAT parquet)")


def test_traversal_does_not_escape_the_prefix(ws, tmp_path):
    """allowed_directories matches by prefix: 'C:/ws/../evil' STARTS with
    'C:/ws/', so if DuckDB compared raw strings this would slip through."""
    evil = tmp_path / "evil.parquet"
    _plain_write_parquet(evil, 13)
    con = duckdb_engine._connect()
    sneaky = f"{str(ws).replace(chr(92), '/')}/../evil.parquet"
    with pytest.raises(duckdb.Error, match="(?i)permission"):
        con.sql(f"SELECT * FROM read_parquet('{sneaky}')").fetchall()


def test_sibling_prefix_is_not_inside(ws, tmp_path):
    evil_dir = tmp_path / (ws.name + "-evil")
    evil_dir.mkdir()
    evil = evil_dir / "evil.parquet"
    _plain_write_parquet(evil, 13)
    con = duckdb_engine._connect()
    with pytest.raises(duckdb.Error, match="(?i)permission"):
        con.sql(f"SELECT * FROM read_parquet('{str(evil).replace(chr(92), '/')}')").fetchall()


def test_the_same_file_is_readable_without_a_workspace(monkeypatch, tmp_path):
    """Counterpart to the ST_Read test above: the file is fine, it is the
    sandbox that refuses it. Without this, that test could pass on a typo."""
    import geopandas as gpd
    from shapely.geometry import Point

    target = tmp_path / "readable.gpkg"
    gpd.GeoDataFrame({"id": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326").to_file(target)

    monkeypatch.delenv("MAPSMITH_WORKSPACE", raising=False)
    con = duckdb_engine._connect()
    sql_path = str(target).replace(chr(92), "/")
    assert con.sql(f"SELECT count(*) FROM ST_Read('{sql_path}')").fetchone()[0] == 1


def test_extension_install_and_load_refused(ws):
    con = duckdb_engine._connect()
    with pytest.raises(duckdb.Error):
        con.execute("INSTALL httpfs")
    with pytest.raises(duckdb.Error):
        con.execute("LOAD httpfs")


def test_configuration_is_locked(ws):
    con = duckdb_engine._connect()
    with pytest.raises(duckdb.Error):
        con.execute("SET enable_external_access = true")
    with pytest.raises(duckdb.Error):
        con.execute("SET allowed_directories = ['/']")
    with pytest.raises(duckdb.Error):
        con.execute("SET memory_limit = '100GB'")


def test_gdal_vsi_paths_refused(ws):
    con = duckdb_engine._connect()
    with pytest.raises(duckdb.Error):
        con.sql("SELECT * FROM ST_Read('/vsicurl/https://example.invalid/x.shp')").fetchall()


def test_st_read_cannot_reach_a_real_file_outside_the_workspace(ws, tmp_path):
    """ST_Read goes through GDAL, so it needs its own check — and it has to use
    a file that really exists, or the test would pass on the read error alone."""
    import geopandas as gpd
    from shapely.geometry import Point

    outside = tmp_path / "outside.gpkg"
    gpd.GeoDataFrame({"id": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326").to_file(outside)
    assert outside.exists()

    target = str(outside).replace(chr(92), "/")
    con = duckdb_engine._connect()
    with pytest.raises(duckdb.Error):
        # surfaces as a GDAL open failure: the driver is denied by the
        # filesystem layer rather than by DuckDB's own path check
        con.sql(f"SELECT * FROM ST_Read('{target}')").fetchall()


def test_no_workspace_means_no_sandbox(monkeypatch, tmp_path):
    monkeypatch.delenv("MAPSMITH_WORKSPACE", raising=False)
    con = duckdb_engine._connect()
    target = str(tmp_path / "free.parquet").replace("\\", "/")
    con.execute(f"COPY (SELECT 1 AS v) TO '{target}' (FORMAT parquet)")
    assert con.sql(f"SELECT v FROM read_parquet('{target}')").fetchone()[0] == 1


def test_run_sql_end_to_end_inside_workspace(ws):
    out = str(ws / "result.parquet")
    result = duckdb_engine.run_sql("SELECT 5 AS v", output_path=out)
    assert result["row_count"] == 1
    assert (ws / "result.parquet").exists()


# --- hardening that applies even without a workspace -----------------------

def test_community_extensions_and_autoload_are_off_without_a_workspace(monkeypatch):
    """Unconfined file access without a workspace is deliberate; escalation to
    shell commands and to DuckDB's own network filesystems is not. `shellfs`
    runs a shell command for a filename ending in '|', and autoload pulls
    httpfs on demand — both reachable from one LLM-written statement under
    DuckDB's defaults.

    This says nothing about GDAL, which brings its own HTTP client and stays
    reachable in this mode on purpose — see
    test_gdal_network_reads_are_available_without_a_workspace, which is where
    that price is pinned down."""
    monkeypatch.delenv("MAPSMITH_WORKSPACE", raising=False)
    con = duckdb_engine._connect()

    settings = dict(
        con.sql(
            "SELECT name, value FROM duckdb_settings() WHERE name IN "
            "('allow_community_extensions', 'autoload_known_extensions', "
            "'autoinstall_known_extensions')"
        ).fetchall()
    )
    assert settings == {
        "allow_community_extensions": "false",
        "autoload_known_extensions": "false",
        "autoinstall_known_extensions": "false",
    }

    # the settings are locked, so SQL cannot turn autoload back on
    with pytest.raises(duckdb.Error):
        con.execute("SET autoload_known_extensions = true")
    with pytest.raises(duckdb.Error):
        con.execute("INSTALL shellfs FROM community")

    # Loading a *signed core* extension explicitly is still allowed (only
    # enable_external_access would stop it, and that would take local file
    # access with it), so the egress it would open is closed one level down,
    # with disabled_filesystems.
    #
    # DuckDB does not report that setting back (it reads as an empty string),
    # and whether `LOAD httpfs` fails with "not found" or the read fails with
    # "disabled" depends on the machine's extension cache. So: assert the
    # property the user cares about — SQL cannot read a URL — and make the
    # stronger claim only where the cache allows it, instead of writing a test
    # whose verdict depends on which machine runs it.
    with pytest.raises(duckdb.Error):
        con.execute("SET disabled_filesystems = ''")  # the block cannot be lifted

    url = "https://raw.githubusercontent.com/duckdb/duckdb/main/README.md"
    try:
        con.execute("LOAD httpfs")
    except duckdb.Error:
        loaded = False  # not in this machine's cache: nothing to load it with
    else:
        loaded = True
    with pytest.raises(duckdb.Error) as failure:
        con.sql(f"SELECT count(*) FROM read_csv('{url}')").fetchall()
    if loaded:
        # httpfs is present, so the refusal must come from the filesystem block
        assert "disabled" in str(failure.value).lower(), str(failure.value)


def _geojson_server():
    """A loopback HTTP server serving one GeoJSON, recording every request.

    Loopback only: these tests must never depend on the internet, and the
    recorded requests are the point — a refusal that still fired the request
    would be a beacon, which is not a refusal.
    """
    import http.server
    import json
    import threading

    payload = json.dumps({
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {"secret": "internal"},
                      "geometry": {"type": "Point", "coordinates": [9.19, 45.46]}}],
    }).encode()
    hits: list[str] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def _reply(self, body):
            hits.append(f"{self.command} {self.path}")
            self.send_response(200)
            self.send_header("Content-Type", "application/geo+json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            if body:
                self.wfile.write(payload)

        def do_GET(self):
            self._reply(True)

        def do_HEAD(self):
            self._reply(False)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/remote.geojson"
    return server, url, hits


def test_the_tool_refuses_remote_sql_by_default(monkeypatch):
    """The default posture after #21: no network from agent-written SQL.

    GDAL brings its own HTTP client, so `/vsicurl` reaches an endpoint and hands
    its content back in the tool result — SSRF with the host's network position,
    from one statement. DuckDB's `disabled_filesystems` does not cover it and
    `enable_external_access=false` would take local files with it, so the
    refusal lives at the tool boundary. Zero requests is the assertion that
    matters: a refusal that had already fired the request would still leak.
    """
    server, url, hits = _geojson_server()
    monkeypatch.delenv("MAPSMITH_WORKSPACE", raising=False)
    monkeypatch.delenv("MAPSMITH_ALLOW_REMOTE", raising=False)
    try:
        with pytest.raises(ValueError, match="MAPSMITH_ALLOW_REMOTE"):
            duckdb_engine.run_sql(f"SELECT secret FROM ST_Read('/vsicurl/{url}')")
        assert hits == [], f"the refusal still reached the network: {hits}"
    finally:
        server.shutdown()


def test_the_operator_can_switch_remote_sql_on(monkeypatch):
    """Cloud-native data stays possible: the capability is gated, not removed."""
    server, url, hits = _geojson_server()
    monkeypatch.delenv("MAPSMITH_WORKSPACE", raising=False)
    monkeypatch.setenv("MAPSMITH_ALLOW_REMOTE", "1")
    try:
        out = duckdb_engine.run_sql(f"SELECT secret FROM ST_Read('/vsicurl/{url}')")
        assert out["rows"] == [["internal"]], out
        assert hits, "no request reached the loopback server"
    finally:
        server.shutdown()


def test_the_boundary_is_run_sql_not_the_connection(monkeypatch):
    """Worth knowing for anyone auditing this: the raw connection is still
    capable of a GDAL network read without a workspace, and that is deliberate —
    `enable_external_access=false` is the only DuckDB-level switch that would
    stop it and it would take local file access with it. The refusal is
    therefore at the tool boundary, which is the only place agent-written SQL
    enters. A future engine that runs agent SQL without going through
    `workspace.refuse_remote_in_sql` reopens the hole, and this test is here to
    say so out loud rather than leave it implied."""
    server, url, hits = _geojson_server()
    monkeypatch.delenv("MAPSMITH_WORKSPACE", raising=False)
    monkeypatch.delenv("MAPSMITH_ALLOW_REMOTE", raising=False)
    try:
        con = duckdb_engine._connect()
        rows = con.sql(f"SELECT secret FROM ST_Read('/vsicurl/{url}')").fetchall()
        assert rows == [("internal",)], rows
        assert hits, "no request reached the loopback server"
    finally:
        server.shutdown()


def test_a_workspace_stops_gdal_from_reaching_the_network(ws):
    """The same statement under a workspace: refused, and silent.

    Zero requests is the assertion that matters. A refusal that had already
    fired the HTTP request would still leak whatever the agent put in the URL,
    and would still let it probe the host's network position.
    """
    server, url, hits = _geojson_server()
    try:
        con = duckdb_engine._connect()
        with pytest.raises(duckdb.Error):
            con.sql(f"SELECT * FROM ST_Read('/vsicurl/{url}')").fetchall()
        assert hits == [], f"the refusal still reached the network: {hits}"
    finally:
        server.shutdown()


def test_spatial_still_works_without_a_workspace(tmp_path, monkeypatch):
    """The hardening must not cost the one extension we actually use."""
    monkeypatch.delenv("MAPSMITH_WORKSPACE", raising=False)
    con = duckdb_engine._connect()
    assert con.sql("SELECT ST_AsText(ST_Point(1, 2)) AS wkt").fetchone()[0] == "POINT (1 2)"

    target = str(tmp_path / "free.parquet").replace("\\", "/")
    con.execute(f"COPY (SELECT 1 AS v) TO '{target}' (FORMAT parquet)")
    assert con.sql(f"SELECT v FROM read_parquet('{target}')").fetchone()[0] == 1


def test_run_sql_itself_refuses_to_install_an_extension():
    """Through the tool, not the policy function.

    Written after making the same mistake this suite spent a day fixing: the
    first tests for this called `sql_policy.refuse_extension_loading_in_sql`
    directly, so deleting the call from `run_sql` left every one of them green.
    A test of a policy function proves the function raises; only a test of the
    operation proves anything is asking it.

    The statement is the one an audit used to make this tool return the host's
    real cloud credentials.
    """
    import pytest as _pytest

    with _pytest.raises(ValueError, match="(?i)extension"):
        duckdb_engine.run_sql(
            "INSTALL aws; LOAD aws; SELECT * FROM load_aws_credentials()"
        )


def test_run_sql_still_answers_a_spatial_question():
    """The other half: `spatial` must keep working.

    MapSmith loads it through the Python API before the configuration is locked,
    so no statement has to ask for it — but a policy that broke ST_Area would be
    a worse defect than the one it fixed, and nothing else in this file would
    have noticed.
    """
    result = duckdb_engine.run_sql(
        "SELECT ST_Area(ST_GeomFromText('POLYGON((0 0,10 0,10 10,0 10,0 0))')) AS a"
    )
    assert result["rows"][0][0] == 100.0


def test_run_sql_refuses_the_two_spellings_that_walked_past_the_first_policy():
    """Through the tool, on the vectors an audit actually used.

    Both reached the real INSTALL/LOAD in DuckDB against the first version of
    this policy: one downloaded a 22 MB native extension binary over HTTPS, the
    other made `run_sql` return this machine's real cloud access key id. The
    suite was green throughout, because every test vector used a canonical
    spelling.
    """
    import pytest as _pytest

    for query in (
        "LOAD $$httpfs$$; LOAD $$aws$$; SELECT * FROM load_aws_credentials()",
        "INSTALL $$inet$$",
        "SELECT '--' AS x; LOAD aws; SELECT 1",
    ):
        with _pytest.raises(ValueError, match="(?i)extension"):
            duckdb_engine.run_sql(query)


def test_run_sql_does_not_refuse_a_column_called_load():
    """The other direction, through the tool.

    `load` is an everyday column name — sediment load, nutrient load, traffic
    load — and the scanning version refused all of these as loading an extension
    called "FROM", "DESC" or "IS".
    """
    for query in (
        "SELECT 1 AS load",
        "SELECT * FROM (SELECT 3 AS load) t ORDER BY load DESC",
        "SELECT * FROM (SELECT NULL AS load) t WHERE load IS NULL",
    ):
        duckdb_engine.run_sql(query)
