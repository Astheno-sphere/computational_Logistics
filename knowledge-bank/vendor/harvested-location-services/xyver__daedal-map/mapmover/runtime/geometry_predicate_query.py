"""Shared predicate-first reads for admitted geometry query layouts.

Layout admission guarantees the named columns. Runtime readers therefore push
the requested projection and predicate directly into DuckDB instead of paying
for a separate remote schema query before every selective read.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from ..duckdb_helpers import (
    lease_query_connection,
    parquet_available,
    path_to_uri,
    quote_ident,
    run_df,
)


BBOX_COLUMNS = ("bbox_min_lon", "bbox_min_lat", "bbox_max_lon", "bbox_max_lat")


def stable_hash_shard(value: str, shard_count: int) -> str:
    """Return a stable zero-padded SHA-256 modulo shard identifier."""
    count = int(shard_count)
    if count < 1:
        raise ValueError("shard_count must be positive")
    digest = hashlib.sha256(str(value).encode("utf-8")).digest()
    width = max(2, len(str(count - 1)))
    return f"{int.from_bytes(digest, 'big') % count:0{width}d}"


def read_bbox_candidates(
    path: Path,
    lon: float,
    lat: float,
    *,
    columns: Iterable[str],
) -> pd.DataFrame:
    """Read rows whose admitted WGS84 bounds can contain one point."""
    selected = list(dict.fromkeys([*columns, *BBOX_COLUMNS]))
    if not parquet_available(path):
        return pd.DataFrame(columns=selected)
    projection = ", ".join(quote_ident(column) for column in selected)
    return run_df(
        f"SELECT {projection} FROM read_parquet(?) "
        "WHERE bbox_min_lon <= ? AND bbox_max_lon >= ? "
        "AND bbox_min_lat <= ? AND bbox_max_lat >= ?",
        [path_to_uri(path), float(lon), float(lon), float(lat), float(lat)],
    )


def read_bbox_candidates_for_points(
    path: Path,
    points: Iterable[dict[str, Any]],
    *,
    columns: Iterable[str],
) -> pd.DataFrame:
    """Read bbox candidates for a point batch in one pushed-down scan."""
    point_rows: list[tuple[int, float, float]] = []
    for position, point in enumerate(points):
        try:
            point_rows.append((position, float(point["lon"]), float(point["lat"])))
        except (KeyError, TypeError, ValueError):
            continue
    selected = list(dict.fromkeys([*columns, *BBOX_COLUMNS]))
    result_columns = ["point_position", *selected]
    if not point_rows or not parquet_available(path):
        return pd.DataFrame(columns=result_columns)
    values_sql = ", ".join("(?, ?, ?)" for _ in point_rows)
    parameters: list[Any] = [path_to_uri(path)]
    for position, lon, lat in point_rows:
        parameters.extend([position, lon, lat])
    projection = ", ".join(f"candidate.{quote_ident(column)}" for column in selected)
    return run_df(
        "WITH candidate AS (SELECT * FROM read_parquet(?)), "
        f"query_point(point_position, lon, lat) AS (VALUES {values_sql}) "
        f"SELECT query_point.point_position, {projection} "
        "FROM candidate JOIN query_point ON "
        "candidate.bbox_min_lon <= query_point.lon "
        "AND candidate.bbox_max_lon >= query_point.lon "
        "AND candidate.bbox_min_lat <= query_point.lat "
        "AND candidate.bbox_max_lat >= query_point.lat",
        parameters,
    )


def read_geojson_containment_for_points(
    path: Path,
    points: Iterable[dict[str, Any]],
    *,
    columns: Iterable[str],
) -> pd.DataFrame:
    """Exact-match a point batch against one compact GeoJSON geometry bank.

    The admitted bank still uses its bbox columns to prune pairs, but DuckDB
    performs the final point-in-polygon predicate in the same file scan. This
    avoids returning broad bbox candidates to Python for shape parsing.
    """
    point_rows: list[tuple[int, float, float]] = []
    for position, point in enumerate(points):
        try:
            point_rows.append((position, float(point["lon"]), float(point["lat"])))
        except (KeyError, TypeError, ValueError):
            continue
    selected = list(dict.fromkeys([*columns, *BBOX_COLUMNS]))
    result_columns = ["point_position", *selected]
    if not point_rows or not parquet_available(path):
        return pd.DataFrame(columns=result_columns)

    values_sql = ", ".join("(?, ?, ?)" for _ in point_rows)
    parameters: list[Any] = [path_to_uri(path)]
    for position, lon, lat in point_rows:
        parameters.extend([position, lon, lat])
    projection = ", ".join(f"candidate.{quote_ident(column)}" for column in selected)
    sql = (
        "WITH candidate AS (SELECT * FROM read_parquet(?)), "
        f"query_point(point_position, lon, lat) AS (VALUES {values_sql}) "
        f"SELECT query_point.point_position, {projection} "
        "FROM candidate JOIN query_point ON "
        "candidate.bbox_min_lon <= query_point.lon "
        "AND candidate.bbox_max_lon >= query_point.lon "
        "AND candidate.bbox_min_lat <= query_point.lat "
        "AND candidate.bbox_max_lat >= query_point.lat "
        "AND ST_Covers(ST_GeomFromGeoJSON(candidate.geometry), "
        "ST_Point(query_point.lon, query_point.lat))"
    )
    with lease_query_connection() as connection:
        try:
            connection.execute("LOAD spatial")
        except Exception:
            connection.execute("INSTALL spatial")
            connection.execute("LOAD spatial")
        return connection.execute(sql, parameters).fetchdf()


def read_rows_by_ids(
    path: Path | None,
    values: Iterable[str],
    *,
    id_column: str,
    columns: Iterable[str],
) -> pd.DataFrame:
    """Read a projected set of admitted geometry rows by exact identifier."""
    requested = sorted({str(value) for value in values if str(value)})
    selected = list(dict.fromkeys([id_column, *columns]))
    if path is None or not requested or not parquet_available(path):
        return pd.DataFrame(columns=selected)
    projection = ", ".join(quote_ident(column) for column in selected)
    placeholders = ", ".join("?" for _ in requested)
    return run_df(
        f"SELECT {projection} FROM read_parquet(?) "
        f"WHERE {quote_ident(id_column)} IN ({placeholders})",
        [path_to_uri(path), *requested],
    )


def read_hash_sharded_rows(
    shard_paths: Mapping[str, Path],
    values: Iterable[str],
    *,
    shard_count: int,
    id_column: str,
    columns: Iterable[str],
) -> pd.DataFrame:
    """Read every routed shard once through one DuckDB query."""
    by_shard: dict[str, set[str]] = {}
    for value in {str(item) for item in values if str(item)}:
        by_shard.setdefault(stable_hash_shard(value, shard_count), set()).add(value)
    selected = list(dict.fromkeys([id_column, *columns]))
    routed = [
        (shard, shard_paths.get(shard))
        for shard in sorted(by_shard)
        if shard_paths.get(shard) is not None
        and parquet_available(shard_paths[shard])
    ]
    requested = sorted({value for shard, _path in routed for value in by_shard[shard]})
    if not routed or not requested:
        return pd.DataFrame(columns=selected)

    # DuckDB accepts parameterized path lists. Keeping every selected shard in
    # one read_parquet relation avoids leasing and scheduling one query per
    # hash bucket while preserving the invariant that no shard is listed twice.
    path_placeholders = ", ".join("?" for _ in routed)
    value_placeholders = ", ".join("?" for _ in requested)
    projection = ", ".join(quote_ident(column) for column in selected)
    return run_df(
        f"SELECT {projection} FROM read_parquet([{path_placeholders}], union_by_name=true) "
        f"WHERE {quote_ident(id_column)} IN ({value_placeholders})",
        [*[path_to_uri(path) for _shard, path in routed], *requested],
    ).reset_index(drop=True)
