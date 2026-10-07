"""Tests for PostGIS tools — read-only SQL guard and response shaping."""

from contextlib import asynccontextmanager

import pytest

from locusync.tools import postgis
from locusync.tools.postgis import _assert_read_only, run_spatial_query


class TestAssertReadOnly:
    def test_select_allowed(self):
        assert _assert_read_only("SELECT 1") is None
        assert _assert_read_only("  select * from t  ") is None

    def test_with_cte_allowed(self):
        assert _assert_read_only("WITH x AS (SELECT 1) SELECT * FROM x") is None

    def test_empty_rejected(self):
        assert _assert_read_only("") is not None
        assert _assert_read_only("   ") is not None

    @pytest.mark.parametrize(
        "sql",
        [
            "INSERT INTO t VALUES (1)",
            "UPDATE t SET a=1",
            "DELETE FROM t",
            "DROP TABLE t",
            "ALTER TABLE t ADD COLUMN c int",
            "TRUNCATE t",
            "CREATE TABLE t (id int)",
        ],
    )
    def test_writes_rejected(self, sql):
        assert _assert_read_only(sql) is not None

    def test_statement_batching_rejected(self):
        assert _assert_read_only("SELECT 1; DROP TABLE t") is not None

    def test_forbidden_keyword_in_cte_rejected(self):
        # A SELECT-prefixed query that still smuggles a write keyword.
        sneaky = "WITH x AS (DELETE FROM t RETURNING *) SELECT * FROM x"
        assert _assert_read_only(sneaky) is not None


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows
        self.last_query = None

    @asynccontextmanager
    async def transaction(self, readonly=False):
        assert readonly is True  # tools must use a READ ONLY transaction
        yield

    async def fetch(self, query):
        self.last_query = query
        return self._rows


class _FakePool:
    def __init__(self, rows):
        self.conn = _FakeConn(rows)

    @asynccontextmanager
    async def acquire(self):
        yield self.conn


@pytest.fixture
def fake_pool(monkeypatch):
    rows = [{"id": 1, "geojson": '{"type":"Point","coordinates":[0,0]}'}]
    pool = _FakePool(rows)

    async def _get_pool():
        return pool

    monkeypatch.setattr(postgis, "HAS_ASYNCPG", True)
    monkeypatch.setattr(postgis, "_get_pool", _get_pool)
    return pool


class TestRunSpatialQuery:
    @pytest.mark.asyncio
    async def test_rejects_write_without_db(self, fake_pool):
        result = await run_spatial_query("DELETE FROM t")
        assert result["success"] is False
        # The fake pool must never have been queried.
        assert fake_pool.conn.last_query is None

    @pytest.mark.asyncio
    async def test_success_shaping(self, fake_pool):
        result = await run_spatial_query("SELECT id, ST_AsGeoJSON(geom) AS geojson FROM t")
        assert result["success"] is True
        assert result["data"]["row_count"] == 1
        assert result["data"]["columns"] == ["id", "geojson"]
        assert result["metadata"]["source"] == "postgis"

    @pytest.mark.asyncio
    async def test_limit_capped(self, fake_pool):
        await run_spatial_query("SELECT * FROM t", limit=999999)
        # Effective limit is capped at MAX_ROWS in the wrapped query.
        assert f"LIMIT {postgis.MAX_ROWS}" in fake_pool.conn.last_query

    @pytest.mark.asyncio
    async def test_not_installed(self, monkeypatch):
        monkeypatch.setattr(postgis, "HAS_ASYNCPG", False)
        result = await run_spatial_query("SELECT 1")
        assert result["success"] is False
        assert "not installed" in result["error"].lower()
