"""PostGIS tools — run spatial SQL against a persistent PostGIS database.

These tools unlock dataset-scale spatial work that the in-memory tools can't do:
persistent storage, indexed spatial joins, and arbitrary SQL analysis.

Safety model:
  * Queries are **read-only**. Only a single ``SELECT``/``WITH`` statement is
    accepted (``_assert_read_only``), and it runs inside a ``READ ONLY``
    transaction, so DDL/DML is rejected at two layers.
  * A row cap (``LIMIT``) is always applied.

Configuration: set ``POSTGIS_DSN`` (e.g. ``postgresql://user:pass@host:5432/db``).
The ``asyncpg`` driver is an optional dependency (``pip install '.[postgis]'``).
"""

import logging
import re
from typing import Any

from locusync.config import get_config
from locusync.utils import make_error_response, make_success_response

logger = logging.getLogger(__name__)

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:  # pragma: no cover - exercised only without the extra
    asyncpg = None
    HAS_ASYNCPG = False
    logger.info("asyncpg not available. PostGIS tools will be disabled.")


_READ_ONLY_PREFIX = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
# Block obvious write/DDL keywords as a belt-and-braces check on top of the
# READ ONLY transaction (e.g. a CTE that wraps an INSERT ... RETURNING).
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|"
    r"vacuum|reindex|call|do)\b",
    re.IGNORECASE,
)

MAX_ROWS = 10000


def _assert_read_only(sql: str) -> str | None:
    """Return an error message if ``sql`` is not a single read-only statement."""
    if not sql or not sql.strip():
        return "SQL query cannot be empty"

    stripped = sql.strip().rstrip(";")
    # Reject statement batching (a second ';' separates statements).
    if ";" in stripped:
        return "Only a single statement is allowed (no ';' separators)"
    if not _READ_ONLY_PREFIX.match(stripped):
        return "Only read-only SELECT/WITH queries are allowed"
    if _FORBIDDEN.search(stripped):
        return "Query contains a forbidden (write/DDL) keyword"
    return None


_pool: Any = None


async def _get_pool() -> Any:
    """Return a lazily created asyncpg connection pool."""
    global _pool
    if _pool is None:
        dsn = get_config().postgis_dsn
        if not dsn:
            raise RuntimeError("POSTGIS_DSN is not configured")
        _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    return _pool


async def reset_pool() -> None:
    """Close and drop the pool (used by tests / shutdown)."""
    global _pool
    if _pool is not None:
        await _pool.close()
    _pool = None


async def run_spatial_query(sql: str, limit: int = 1000) -> dict[str, Any]:
    """Run a read-only spatial SQL query and return rows.

    Geometry columns should be wrapped in ``ST_AsGeoJSON(geom)`` in the SELECT
    to get GeoJSON strings back.

    Args:
        sql: A single ``SELECT``/``WITH`` statement.
        limit: Maximum rows to return (capped at ``MAX_ROWS``).
    """
    if not HAS_ASYNCPG:
        return make_error_response(
            "PostGIS support is not installed. Install with: pip install '.[postgis]'"
        )

    error = _assert_read_only(sql)
    if error:
        return make_error_response(error)

    limit = max(1, min(limit, MAX_ROWS))

    try:
        pool = await _get_pool()
    except Exception as e:
        logger.error(f"PostGIS connection failed: {e}")
        return make_error_response(f"Cannot connect to PostGIS: {e}")

    try:
        async with pool.acquire() as conn:  # noqa: SIM117 - transaction needs conn
            # READ ONLY transaction: any write attempt errors at the DB level.
            async with conn.transaction(readonly=True):
                wrapped = f"SELECT * FROM ({sql.rstrip(';')}) AS _q LIMIT {limit}"
                rows = await conn.fetch(wrapped)

        records = [dict(r) for r in rows]
        data = {
            "rows": records,
            "row_count": len(records),
            "columns": list(records[0].keys()) if records else [],
        }
        metadata = {
            "source": "postgis",
            "truncated": len(records) >= limit,
            "limit": limit,
        }
        return make_success_response(data, metadata)

    except Exception as e:
        logger.exception(f"PostGIS query failed: {e}")
        return make_error_response(f"Query failed: {e}")


async def list_spatial_tables() -> dict[str, Any]:
    """List spatial tables registered in PostGIS ``geometry_columns``."""
    if not HAS_ASYNCPG:
        return make_error_response(
            "PostGIS support is not installed. Install with: pip install '.[postgis]'"
        )
    try:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT f_table_schema AS schema, f_table_name AS table, "
                "f_geometry_column AS geometry_column, srid, type "
                "FROM geometry_columns ORDER BY f_table_schema, f_table_name"
            )
        tables = [dict(r) for r in rows]
        return make_success_response(
            {"tables": tables, "count": len(tables)}, {"source": "postgis"}
        )
    except Exception as e:
        logger.exception(f"Failed to list spatial tables: {e}")
        return make_error_response(f"Cannot list spatial tables: {e}")
