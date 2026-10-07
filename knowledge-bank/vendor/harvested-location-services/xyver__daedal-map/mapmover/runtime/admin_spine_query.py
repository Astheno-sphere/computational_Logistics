"""Bounded two-stage point lookup for published country admin-spine layouts."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from functools import lru_cache
import os
import threading
import time

from shapely import from_wkb
from shapely.geometry import Point
import pandas as pd

from ..duckdb_helpers import is_cloud_mode, lease_query_connection, path_to_uri
from ..paths import COUNTRY_GEOMETRY_DIR, DATA_ROOT
from .geometry_catalog import load_geometry_catalog
from .geometry_storage_layout import country_admin_spine_root
from .published_artifacts import read_artifact_json
from .geometry_spine import geometry_spine_index_for_frame


META_COLUMNS = """
loc_id, parent_id, admin_level, name,
admin_0_loc_id, admin_1_loc_id, admin_2_loc_id, admin_3_loc_id,
admin_4_loc_id, admin_5_loc_id, admin_6_loc_id,
bbox_min_lon, bbox_min_lat, bbox_max_lon, bbox_max_lat
"""
META_COLUMN_NAMES = [part.strip() for part in META_COLUMNS.replace("\n", " ").split(",")]
ROUTE_INDEX_NAME = "loc_id_routes.parquet"
MAX_DIRECT_POINT_BRANCHES = 32
SPATIAL_JOIN_MIN_POINTS = max(
    1, int(os.environ.get("POINT_SPATIAL_JOIN_MIN_POINTS", "64")),
)
SPATIAL_JOIN_MAX_BANK_BYTES = max(
    0,
    int(float(os.environ.get("POINT_SPATIAL_JOIN_MAX_BANK_MB", "200")) * 1024 * 1024),
)
_SHALLOW_IDENTITY_CACHE: dict[tuple[str, int], pd.DataFrame] = {}
_SHALLOW_IDENTITY_CACHE_LOCK = threading.Lock()


def layout_root(iso3: str) -> Path:
    country = str(iso3 or "").strip().upper()
    profiles = [
        profile for profile in load_geometry_catalog().get("country_profiles") or []
        if isinstance(profile, dict) and str(profile.get("country_code") or "").upper() == country
        and str(profile.get("release_status") or "") in {"approved_for_publication", "published"}
    ]
    if len(profiles) == 1:
        try:
            clean_root = country_admin_spine_root(Path(DATA_ROOT), country, profiles[0])
            if is_cloud_mode() or all(
                (clean_root / name).is_file()
                for name in ("manifest.json", "admin_0_3.parquet", ROUTE_INDEX_NAME)
            ):
                return clean_root
        except ValueError:
            pass
        # The local authoring tree retains its admitted builder output. It is
        # not a Published compatibility path and is never selected in cloud.
        relative = str(profiles[0].get("query_layout_manifest") or "").replace("\\", "/")
        if relative.endswith("/runtime/admin_spine/manifest.json"):
            return Path(DATA_ROOT) / Path(relative).parent
    # Cloud activation is catalog-owned and fails closed.
    if is_cloud_mode():
        return Path(DATA_ROOT) / "__catalog_has_no_admitted_country_layout__" / country
    return Path(COUNTRY_GEOMETRY_DIR) / country / "admin_spine"


def layout_available(iso3: str) -> bool:
    root = layout_root(iso3)
    if not is_cloud_mode():
        return (root / "manifest.json").is_file() and (root / "admin_0_3.parquet").is_file()
    try:
        relative_root = root.relative_to(Path(DATA_ROOT)).as_posix()
    except ValueError:
        return False
    country = str(iso3).upper()
    if not (
        relative_root.startswith(f"geometry/countries/{country}/admin_spine/exact/")
    ):
        return False
    expected = relative_root + "/manifest.json"
    return _published_layout_manifest_available(str(iso3).upper(), expected)


def clear_admin_spine_query_cache() -> None:
    _published_layout_manifest_available.cache_clear()
    _layout_manifest_at_root.cache_clear()
    with _SHALLOW_IDENTITY_CACHE_LOCK:
        _SHALLOW_IDENTITY_CACHE.clear()


def prewarm_shallow_identity_index(iso3: str, maximum_level: int = 2) -> int:
    """Cache a country's bounded Admin0..N identity rows without geometry.

    This is intentionally separate from Display geometry prewarm. Dataset
    conversion needs only stable loc_ids and levels, so retaining polygon WKB
    here would waste both Railway memory and object-store bandwidth.
    """
    country = str(iso3 or "").strip().upper()
    level = max(0, min(3, int(maximum_level)))
    if not layout_available(country):
        return 0
    connection = _connection()
    try:
        frame = connection.execute(
            f"SELECT {META_COLUMNS} FROM read_parquet(?) "
            "WHERE admin_level <= ? ORDER BY admin_level, loc_id",
            [path_to_uri(layout_root(country) / "admin_0_3.parquet"), level],
        ).fetchdf()
    finally:
        connection.close()
    if frame.empty:
        return 0
    with _SHALLOW_IDENTITY_CACHE_LOCK:
        _SHALLOW_IDENTITY_CACHE[(country, level)] = frame
    return len(frame)


def cached_shallow_identity_rows(
    iso3: str,
    loc_ids: list[str],
    *,
    maximum_level: int,
    columns: list[str] | None = None,
) -> pd.DataFrame | None:
    """Return rows from a complete warm identity slice, or ``None`` if cold."""
    country = str(iso3 or "").strip().upper()
    requested = list(dict.fromkeys(str(value).strip() for value in loc_ids if str(value).strip()))
    with _SHALLOW_IDENTITY_CACHE_LOCK:
        eligible = [
            (level, frame) for (cached_country, level), frame in _SHALLOW_IDENTITY_CACHE.items()
            if cached_country == country and level >= int(maximum_level)
        ]
        if not eligible:
            return None
        frame = min(eligible, key=lambda item: item[0])[1]
        selected = frame[frame["loc_id"].isin(requested)].copy()
    projection = list(dict.fromkeys(["loc_id", *(columns or [])]))
    if columns is not None:
        selected = selected[[name for name in projection if name in selected.columns]]
    order = {loc_id: index for index, loc_id in enumerate(requested)}
    if selected.empty:
        return selected.reset_index(drop=True)
    selected["_requested_order"] = selected["loc_id"].map(order)
    return selected.sort_values("_requested_order").drop(columns=["_requested_order"]).reset_index(drop=True)


def shallow_identity_level_rows(iso3: str, admin_level: int) -> pd.DataFrame | None:
    """Read one shallow identity level without loading polygon WKB.

    Name resolution needs only the catalog-selected exact spine's identity
    columns. Keeping this read beside point resolution ensures hosted callers
    use the same admitted release and avoids routing a metadata lookup through
    the heavier generic geometry loader.
    """
    country = str(iso3 or "").strip().upper()
    level = int(admin_level)
    if level < 0 or level > 3 or not layout_available(country):
        return None

    with _SHALLOW_IDENTITY_CACHE_LOCK:
        eligible = [
            (maximum_level, frame)
            for (cached_country, maximum_level), frame in _SHALLOW_IDENTITY_CACHE.items()
            if cached_country == country and maximum_level >= level
        ]
        if eligible:
            frame = min(eligible, key=lambda item: item[0])[1]
            columns = [name for name in ("loc_id", "admin_level", "name") if name in frame.columns]
            return frame.loc[frame["admin_level"] == level, columns].copy().reset_index(drop=True)

    connection = _connection()
    try:
        return connection.execute(
            "SELECT loc_id, admin_level, name FROM read_parquet(?) "
            "WHERE admin_level = ? ORDER BY loc_id",
            [path_to_uri(layout_root(country) / "admin_0_3.parquet"), level],
        ).fetchdf()
    except Exception:
        return None
    finally:
        connection.close()


def _layout_manifest(iso3: str) -> dict[str, Any]:
    root = layout_root(iso3)
    return _layout_manifest_at_root(str(root), is_cloud_mode())


@lru_cache(maxsize=128)
def _layout_manifest_at_root(root_text: str, cloud_mode: bool) -> dict[str, Any]:
    root = Path(root_text)
    if not cloud_mode:
        path = root / "manifest.json"
        if not path.is_file():
            return {}
        try:
            import json
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    try:
        relative = root.relative_to(Path(DATA_ROOT)).as_posix()
        return read_artifact_json(f"{relative}/manifest.json", lane="active")
    except Exception:
        return {}


@lru_cache(maxsize=64)
def _published_layout_manifest_available(iso3: str, relative_path: str) -> bool:
    try:
        # Follow the runtime's selected immutable lane. Hosted production sets
        # active=published; release smoke may deliberately set active=staging.
        payload = read_artifact_json(relative_path, lane="active")
    except Exception:
        return False
    return bool(
        isinstance(payload, dict)
        and payload.get("status") == "PASS"
        and str(payload.get("country") or "").upper() == iso3
        and payload.get("layout_policy") == "national_admin_0_3_plus_admin_1_owned_deep"
    )


def _connection():
    return lease_query_connection()


def _metadata_with_geometry(connection, path: Path, lon: float, lat: float,
                            admin3: str = "") -> list[tuple]:
    """Return bbox candidates and their shapes in one object-store read.

    The old resolver queried a file once for metadata and then reopened the
    same file to fetch WKB for those candidate IDs.  On an unsorted remote
    shard the second ``loc_id IN`` query can scan nearly every row group again.
    Keep the bbox/owner predicate and exact Shapely test, but project WKB in
    this same read so the candidate scan is not duplicated.
    """
    owner_clause = "" if not admin3 else " AND admin_3_loc_id = ?"
    parameters: list[Any] = [path_to_uri(path), lon, lon, lat, lat]
    if admin3:
        parameters.append(admin3)
    return connection.execute(f"""
        SELECT {META_COLUMNS}, ST_AsWKB(geometry) AS geometry_wkb
        FROM read_parquet(?)
        WHERE bbox_max_lon >= ? AND bbox_min_lon <= ?
          AND bbox_max_lat >= ? AND bbox_min_lat <= ? {owner_clause}
        ORDER BY admin_level, loc_id
    """, parameters).fetchall()


def _metadata_with_geometry_bbox(
    connection,
    path: Path,
    points: list[dict[str, Any]],
    *,
    maximum_level: int | None = None,
    admin3: str = "",
    stage_timing_ms: dict[str, int] | None = None,
) -> pd.DataFrame:
    """Read exact point candidates without scanning the large WKB column first.

    A point-by-point DuckDB query is catastrophic for large MCP batches even
    when every individual read is selective. A shared envelope alone can also
    admit unrelated polygons between distant points, so multi-point batches
    retain an exact per-point bbox predicate after the pushdown envelope.
    Hosted geometry banks can be hundreds of MB while their metadata columns
    are tiny. A single coordinate uses a pushed-down one-pass exact read.
    Distributed batches first find candidate IDs with metadata only, then
    fetch WKB by those IDs from the same bank. No other geometry file is opened.
    """
    if not points:
        return pd.DataFrame(columns=[*META_COLUMN_NAMES, "geometry"])
    unique_points = list(dict.fromkeys(
        (float(point["lon"]), float(point["lat"])) for point in points
    ))
    # A few separated points are better served by independent pushdown scans
    # than by the correlated EXISTS plan, which reads all bbox metadata.
    # Keep this bounded: many UNION branches would multiply remote scans.
    if 1 < len(unique_points) <= MAX_DIRECT_POINT_BRANCHES:
        uri = path_to_uri(path)
        branches: list[str] = []
        parameters: list[Any] = []
        for lon, lat in unique_points:
            clauses = [
                "bbox_min_lon <= ?", "bbox_max_lon >= ?",
                "bbox_min_lat <= ?", "bbox_max_lat >= ?",
            ]
            branch_params: list[Any] = [uri, lon, lon, lat, lat]
            if maximum_level is not None:
                clauses.append("admin_level <= ?")
                branch_params.append(int(maximum_level))
            if admin3:
                clauses.append("admin_3_loc_id = ?")
                branch_params.append(admin3)
            branches.append(
                f"SELECT {META_COLUMNS}, ST_AsWKB(geometry) AS geometry "
                f"FROM read_parquet(?) WHERE {' AND '.join(clauses)}"
            )
            parameters.extend(branch_params)
        started = time.perf_counter()
        frame = connection.execute(" UNION ALL ".join(branches), parameters).fetchdf()
        if stage_timing_ms is not None:
            stage_timing_ms["direct_point_bank_ms"] = (
                stage_timing_ms.get("direct_point_bank_ms", 0)
                + int((time.perf_counter() - started) * 1000)
            )
            stage_timing_ms["bbox_candidate_count"] = (
                stage_timing_ms.get("bbox_candidate_count", 0) + len(frame)
            )
        return frame.drop_duplicates(subset="loc_id").sort_values(
            ["admin_level", "loc_id"]
        ).reset_index(drop=True) if not frame.empty else frame
    multiple = len(unique_points) > 1
    point_values = ", ".join("(?, ?)" for _ in unique_points) if multiple else ""
    parameters: list[Any] = (
        [coordinate for point in unique_points for coordinate in point]
        if multiple else []
    )
    uri = path_to_uri(path)
    parameters.append(uri)
    clauses = []
    if maximum_level is not None:
        clauses.append("admin_level <= ?")
        parameters.append(int(maximum_level))
    if admin3:
        clauses.append("admin_3_loc_id = ?")
        parameters.append(admin3)
    # DuckDB does not push a correlated EXISTS predicate into Parquet's row
    # group scan. Constant bounds do push down, avoiding an all-row metadata
    # read for the common single-point and tightly clustered requests.
    clauses.extend([
        "regions.bbox_min_lon <= ?", "regions.bbox_max_lon >= ?",
        "regions.bbox_min_lat <= ?", "regions.bbox_max_lat >= ?",
    ])
    if multiple:
        lons, lats = zip(*unique_points)
        parameters.extend([max(lons), min(lons), max(lats), min(lats)])
        clauses.append(
            "EXISTS (SELECT 1 FROM input_points AS point "
            "WHERE regions.bbox_max_lon >= point.lon "
            "AND regions.bbox_min_lon <= point.lon "
            "AND regions.bbox_max_lat >= point.lat "
            "AND regions.bbox_min_lat <= point.lat)"
        )
    else:
        lon, lat = unique_points[0]
        parameters.extend([lon, lon, lat, lat])
    point_cte = f"WITH input_points(lon, lat) AS (VALUES {point_values}) " if multiple else ""
    projection = META_COLUMNS if multiple else f"{META_COLUMNS}, ST_AsWKB(geometry) AS geometry"
    started = time.perf_counter()
    metadata = connection.execute(
        f"{point_cte}SELECT {projection} "
        f"FROM read_parquet(?) AS regions WHERE {' AND '.join(clauses)} "
        "ORDER BY admin_level, loc_id",
        parameters,
    ).fetchdf()
    if stage_timing_ms is not None:
        timing_key = "bbox_metadata_ms" if multiple else "direct_point_bank_ms"
        stage_timing_ms[timing_key] = stage_timing_ms.get(timing_key, 0) + int((time.perf_counter() - started) * 1000)
        stage_timing_ms["bbox_candidate_count"] = stage_timing_ms.get("bbox_candidate_count", 0) + len(metadata)
    if not multiple:
        return metadata
    if metadata.empty:
        metadata["geometry"] = pd.Series(dtype="object")
        return metadata
    ids = list(dict.fromkeys(str(value) for value in metadata["loc_id"]))
    placeholders = ", ".join("?" for _ in ids)
    started = time.perf_counter()
    shapes = connection.execute(
        f"SELECT loc_id, ST_AsWKB(geometry) AS geometry FROM read_parquet(?) "
        f"WHERE loc_id IN ({placeholders})",
        [uri, *ids],
    ).fetchdf()
    if stage_timing_ms is not None:
        stage_timing_ms["candidate_wkb_ms"] = stage_timing_ms.get("candidate_wkb_ms", 0) + int((time.perf_counter() - started) * 1000)
    if len(shapes) != len(ids) or shapes["loc_id"].duplicated().any():
        raise ValueError(f"{path} candidate geometry lookup did not return one shape per loc_id")
    return metadata.merge(shapes, on="loc_id", how="left", validate="many_to_one", sort=False)


def _spatial_join_point_matches(
    connection,
    path: Path,
    points: list[dict[str, Any]],
    *,
    maximum_level: int | None = None,
    admin3: str = "",
    stage_timing_ms: dict[str, int] | None = None,
) -> list[dict[int, dict[str, Any]]]:
    """Exact-match a point batch with DuckDB's native one-bank spatial join."""
    if not points:
        return []
    point_values = ", ".join("(?, ?, ?)" for _ in points)
    parameters: list[Any] = [
        coordinate
        for index, point in enumerate(points)
        for coordinate in (index, float(point["lon"]), float(point["lat"]))
    ]
    clauses: list[str] = []
    parameters.append(path_to_uri(path))
    if maximum_level is not None:
        clauses.append("regions.admin_level <= ?")
        parameters.append(int(maximum_level))
    if admin3:
        clauses.append("regions.admin_3_loc_id = ?")
        parameters.append(admin3)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    try:
        connection.execute("LOAD spatial")
    except Exception:
        connection.execute("INSTALL spatial")
        connection.execute("LOAD spatial")
    started = time.perf_counter()
    frame = connection.execute(
        f"WITH input_points(point_index, lon, lat) AS (VALUES {point_values}) "
        f"SELECT {META_COLUMNS}, points.point_index, "
        f"ST_Area(regions.geometry) AS match_area "
        f"FROM read_parquet(?) AS regions JOIN input_points AS points "
        f"ON ST_Covers(regions.geometry, ST_Point(points.lon, points.lat)){where}",
        parameters,
    ).fetchdf()
    if stage_timing_ms is not None:
        stage_timing_ms["spatial_join_bank_ms"] = stage_timing_ms.get("spatial_join_bank_ms", 0) + int((time.perf_counter() - started) * 1000)
        stage_timing_ms["spatial_join_match_count"] = stage_timing_ms.get("spatial_join_match_count", 0) + len(frame)
    results: list[dict[int, dict[str, Any]]] = [dict() for _ in points]
    if frame.empty:
        return results
    frame = frame.sort_values(["point_index", "admin_level", "match_area", "loc_id"])
    covering_ids = frame.groupby(["point_index", "admin_level"])["loc_id"].agg(
        lambda values: sorted({str(value) for value in values})
    ).to_dict()
    for row in frame.drop_duplicates(["point_index", "admin_level"]).to_dict("records"):
        point_index = int(row.pop("point_index"))
        level = int(row.get("admin_level", 0))
        row.pop("match_area", None)
        ids = covering_ids.get((point_index, level), [])
        if len(ids) > 1:
            row["__covering_loc_ids"] = ids
        results[point_index][level] = row
    return results


def _spatial_join_bank_eligible(iso3: str, path: Path, points: list[dict[str, Any]]) -> bool:
    """Use one exact spatial join for broad batches in bounded geometry banks."""
    unique = list(dict.fromkeys((float(item["lon"]), float(item["lat"])) for item in points))
    if len(unique) < SPATIAL_JOIN_MIN_POINTS:
        return False
    lons, lats = zip(*unique)
    if max(max(lons) - min(lons), max(lats) - min(lats)) < 2.0:
        return False
    root = layout_root(iso3)
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        return False
    manifest = _layout_manifest(iso3)
    outputs = manifest.get("outputs") or []
    sizes = [
        int(item.get("bytes") or 0) for item in outputs
        if isinstance(item, dict) and item.get("path") == relative
    ]
    return len(sizes) == 1 and 0 < sizes[0] <= SPATIAL_JOIN_MAX_BANK_BYTES


def _identity_rows(connection, path: Path, loc_ids: list[str]) -> list[dict[str, Any]]:
    """Read known identity rows without applying a spatial predicate.

    Explicit virtual ``NULL<n>`` ancestors have no bounding box or geometry,
    so they cannot participate in point containment.  Once a shaped
    descendant has identified one through its ancestry columns, this exact
    lookup recovers its stored metadata from the admitted layout bank.
    """
    requested = list(dict.fromkeys(str(value).strip() for value in loc_ids if str(value).strip()))
    if not requested:
        return []
    placeholders = ",".join("?" for _ in requested)
    rows = connection.execute(
        f"SELECT {META_COLUMNS} FROM read_parquet(?) "
        f"WHERE loc_id IN ({placeholders})",
        [path_to_uri(path), *requested],
    ).fetchall()
    return [_row_dict(row) for row in rows]


def _exact_candidate_rows(rows: list[tuple], lon: float, lat: float) -> list[tuple[tuple, bytes, float]]:
    """Apply the exact point-in-polygon check to shape-bearing candidates."""
    point = Point(lon, lat)
    matches = []
    for candidate in rows:
        if not candidate:
            continue
        row = tuple(candidate[:-1])
        geometry_wkb = candidate[-1]
        if geometry_wkb is None:
            continue
        geometry = from_wkb(bytes(geometry_wkb))
        if geometry.covers(point):
            matches.append((row, bytes(geometry_wkb), float(geometry.area)))
    return matches


def _row_dict(row: tuple) -> dict[str, Any]:
    return dict(zip(META_COLUMN_NAMES, row))


def _geometry_review(rows_by_level: dict[int, list[str]]) -> dict[str, Any] | None:
    """Flag distinct same-level Admin spine polygons covering one point."""
    conflicts = [
        {"admin_level": f"admin_{level}", "candidate_loc_ids": sorted(set(ids))}
        for level, ids in sorted(rows_by_level.items()) if len(set(ids)) > 1
    ]
    if not conflicts:
        return None
    return {
        "geometry_review_required": True,
        "geometry_review_notice": "Double-check boundary",
        "reason": "multiple_admin_matches_same_level",
        "conflicts": conflicts,
    }


def resolve_point(
    iso3: str, lon: float, lat: float, *, target_admin_level: int | None = None,
) -> dict[str, Any] | None:
    """Resolve one point through the national Admin0-3 file and one owner file.

    ``target_admin_level`` bounds the work, it does not just filter the answer.
    The national ``admin_0_3.parquet`` already covers Admin 0-3, so a request
    that stops at or above Admin 3 never opens the deep per-Admin1 partition -
    the expensive read in this path. Callers asking for country, state, or
    county geography are the common case, and they now skip it entirely.
    """
    iso3 = str(iso3 or "").strip().upper()
    if not layout_available(iso3):
        return None
    root = layout_root(iso3)
    connection = _connection()
    try:
        shallow_candidates = _metadata_with_geometry(
            connection, root / "admin_0_3.parquet", lon, lat,
        )
        shallow = _exact_candidate_rows(shallow_candidates, lon, lat)
        if not shallow:
            return None
        shallow.sort(key=lambda item: (int(item[0][2]), -item[2], str(item[0][0])))
        shallow_by_level: dict[int, tuple[tuple, bytes, float]] = {}
        for item in shallow:
            shallow_by_level[int(item[0][2])] = item
        anchor = shallow[-1][0]
        admin1, admin3 = str(anchor[5] or ""), str(anchor[7] or "")
        deep: list[tuple[tuple, bytes, float]] = []
        deep_path = root / "deep" / f"{admin1}.parquet"
        needs_deep = target_admin_level is None or int(target_admin_level) > 3
        if needs_deep and admin1 and (is_cloud_mode() or deep_path.is_file()):
            deep_candidates = _metadata_with_geometry(
                connection, deep_path, lon, lat, admin3 if admin3 else "",
            )
            deep = _exact_candidate_rows(deep_candidates, lon, lat)
            deep.sort(key=lambda item: (int(item[0][2]), -item[2], str(item[0][0])))
        covering_by_level: dict[int, list[str]] = {}
        for item in [*shallow, *deep]:
            covering_by_level.setdefault(int(item[0][2]), []).append(str(item[0][0]))
        geometry_review = _geometry_review(covering_by_level)
        all_matches = [shallow_by_level[level] for level in sorted(shallow_by_level)] + deep
        by_level: dict[int, tuple[tuple, bytes, float]] = {}
        for item in all_matches:
            by_level[int(item[0][2])] = item
        ordered = [by_level[level] for level in sorted(by_level)]
        deepest_metadata = _row_dict(ordered[-1][0])
        missing_identity_ids = []
        for level in range(int(deepest_metadata.get("admin_level", 0)) + 1):
            loc_id = str(deepest_metadata.get(f"admin_{level}_loc_id") or "").strip()
            if not loc_id:
                continue
            if not any(str(item[0][0] or "").strip() == loc_id for item in ordered):
                missing_identity_ids.append(loc_id)
        if missing_identity_ids:
            identities_by_id: dict[str, dict[str, Any]] = {}
            for row in _identity_rows(connection, root / "admin_0_3.parquet", missing_identity_ids):
                identities_by_id[str(row.get("loc_id") or "").strip()] = row
            if admin1 and (is_cloud_mode() or deep_path.is_file()):
                remaining = [loc_id for loc_id in missing_identity_ids if loc_id not in identities_by_id]
                for row in _identity_rows(connection, deep_path, remaining):
                    identities_by_id[str(row.get("loc_id") or "").strip()] = row
            for loc_id in missing_identity_ids:
                row = identities_by_id.get(loc_id)
                if row is None:
                    raise ValueError(
                        f"admitted admin spine ancestry {loc_id!r} is absent from "
                        f"the {iso3} query-layout banks"
                    )
                row["identity_only"] = True
                ordered.append((tuple(row.get(name) for name in META_COLUMN_NAMES), None, 0.0))
            ordered.sort(key=lambda item: int(item[0][2]))
        final = ordered[-1]
        identity_ids = {
            loc_id for loc_id in missing_identity_ids if "-NULL" in loc_id
        }
        return {
            "country": iso3,
            "stack": [
                dict(_row_dict(item[0]), **({"identity_only": True} if str(item[0][0] or "").strip() in identity_ids else {}))
                for item in ordered
            ],
            "matched": _row_dict(final[0]),
            "geometry_wkb": final[1],
            "shallow_candidate_count": len(shallow_candidates),
            "deep_candidate_count": len(deep) if deep else 0,
            "query_layout": True,
            **({"geometry_review": geometry_review} if geometry_review else {}),
        }
    finally:
        connection.close()


def resolve_points(
    iso3: str,
    points: list[dict[str, Any]],
    *,
    target_admin_level: int | None = None,
    admin_1_scope: str | None = None,
    stage_timing_ms: dict[str, int] | None = None,
) -> list[dict[str, Any]] | None:
    """Resolve a point batch using one physical bank per scope.

    ``None`` means the country has no admitted layout and callers may use a
    compatibility reader.  Once a layout is admitted, individual misses are
    authoritative empty stacks and must not trigger a second broad scan.
    """
    country = str(iso3 or "").strip().upper()
    point_items = list(points or [])
    if not layout_available(country):
        return None
    if not point_items:
        return []

    root = layout_root(country)
    target = None if target_admin_level is None else max(0, int(target_admin_level))
    shallow_maximum = 3 if target is None else min(3, target)
    connection = _connection()
    try:
        matches: list[dict[int, dict[str, Any]]] = [dict() for _ in point_items]
        shallow_path = root / "admin_0_3.parquet"
        if _spatial_join_bank_eligible(country, shallow_path, point_items):
            matches = _spatial_join_point_matches(
                connection, shallow_path, point_items,
                maximum_level=shallow_maximum, stage_timing_ms=stage_timing_ms,
            )
        else:
            shallow = _metadata_with_geometry_bbox(
                connection, shallow_path, point_items,
                maximum_level=shallow_maximum, stage_timing_ms=stage_timing_ms,
            )
            if not shallow.empty:
                for level in sorted(int(value) for value in shallow["admin_level"].dropna().unique()):
                    level_frame = shallow[shallow["admin_level"] == level].reset_index(drop=True)
                    index = geometry_spine_index_for_frame(level_frame)
                    level_matches = index.match_points(point_items) if index is not None else [None] * len(point_items)
                    for position, match in enumerate(level_matches):
                        if match is not None:
                            row = match.row.to_dict()
                            if len(match.candidate_loc_ids) > 1:
                                row["__covering_loc_ids"] = list(match.candidate_loc_ids)
                            matches[position][level] = row

        needs_deep = target is None or target > 3
        if needs_deep:
            by_owner: dict[str, list[tuple[int, dict[str, Any]]]] = {}
            missing_owner = False
            for position, point in enumerate(point_items):
                anchor = matches[position].get(3) or matches[position].get(2) or matches[position].get(1)
                owner = str((anchor or {}).get("admin_1_loc_id") or "")
                if owner:
                    by_owner.setdefault(owner, []).append((position, point))
                else:
                    missing_owner = True
            expected_owner = str(admin_1_scope or "").strip()
            observed_owners = sorted(by_owner)
            if expected_owner and (missing_owner or observed_owners != [expected_owner]):
                error = {
                    "code": "deep_admin_1_scope_mismatch",
                    "message": (
                        "Every point in an Admin 4+ request must resolve inside the "
                        "single declared admin_1_scope. Split the input by Admin 1."
                    ),
                    "admin_1_scope": expected_owner,
                    "observed_admin_1_scopes": observed_owners,
                }
                return [
                    {
                        "country": country,
                        "stack": [levels[level] for level in sorted(levels)],
                        "matched": levels[max(levels)] if levels else None,
                        "query_layout": True,
                        "error": error,
                    }
                    for levels in matches
                ]
            for owner, owned in by_owner.items():
                deep_path = root / "deep" / f"{owner}.parquet"
                if not is_cloud_mode() and not deep_path.is_file():
                    continue
                owned_points = [point for _, point in owned]
                if _spatial_join_bank_eligible(country, deep_path, owned_points):
                    deep_matches = _spatial_join_point_matches(
                        connection, deep_path, owned_points,
                        maximum_level=target, stage_timing_ms=stage_timing_ms,
                    )
                    for owned_position, level_matches in enumerate(deep_matches):
                        original_position = owned[owned_position][0]
                        matches[original_position].update(level_matches)
                    continue
                deep = _metadata_with_geometry_bbox(
                    connection, deep_path, owned_points,
                    maximum_level=target, stage_timing_ms=stage_timing_ms,
                )
                if deep.empty:
                    continue
                for level in sorted(int(value) for value in deep["admin_level"].dropna().unique()):
                    level_frame = deep[deep["admin_level"] == level].reset_index(drop=True)
                    index = geometry_spine_index_for_frame(level_frame)
                    level_matches = index.match_points(owned_points) if index is not None else [None] * len(owned_points)
                    for owned_position, match in enumerate(level_matches):
                        if match is not None:
                            original_position = owned[owned_position][0]
                            row = match.row.to_dict()
                            if len(match.candidate_loc_ids) > 1:
                                row["__covering_loc_ids"] = list(match.candidate_loc_ids)
                            matches[original_position][level] = row

        outputs: list[dict[str, Any]] = []
        missing_identity_ids: set[str] = set()
        for levels in matches:
            if not levels:
                continue
            deepest = levels[max(levels)]
            for level in range(int(deepest.get("admin_level", 0)) + 1):
                loc_id = str(deepest.get(f"admin_{level}_loc_id") or "").strip()
                if loc_id and not any(str(row.get("loc_id") or "") == loc_id for row in levels.values()):
                    missing_identity_ids.add(loc_id)

        identities: dict[str, dict[str, Any]] = {}
        if missing_identity_ids:
            for row in _identity_rows(connection, root / "admin_0_3.parquet", sorted(missing_identity_ids)):
                identities[str(row.get("loc_id") or "")] = row
            remaining = missing_identity_ids - set(identities)
            by_owner_ids: dict[str, list[str]] = {}
            for loc_id in remaining:
                parts = loc_id.split("-")
                if len(parts) >= 2:
                    by_owner_ids.setdefault("-".join(parts[:2]), []).append(loc_id)
            for owner, loc_ids in by_owner_ids.items():
                path = root / "deep" / f"{owner}.parquet"
                if is_cloud_mode() or path.is_file():
                    for row in _identity_rows(connection, path, loc_ids):
                        identities[str(row.get("loc_id") or "")] = row

        for levels in matches:
            geometry_review = _geometry_review({
                level: row.get("__covering_loc_ids", [str(row.get("loc_id") or "")])
                for level, row in levels.items()
            })
            for row in levels.values():
                row.pop("__covering_loc_ids", None)
            ordered = [levels[level] for level in sorted(levels)]
            if ordered:
                deepest = ordered[-1]
                for level in range(int(deepest.get("admin_level", 0)) + 1):
                    loc_id = str(deepest.get(f"admin_{level}_loc_id") or "").strip()
                    if loc_id and not any(str(row.get("loc_id") or "") == loc_id for row in ordered):
                        identity = identities.get(loc_id)
                        if identity is not None:
                            ordered.append(dict(identity, identity_only=True))
                ordered.sort(key=lambda row: int(row.get("admin_level", 0)))
            outputs.append({
                "country": country,
                "stack": ordered,
                "matched": ordered[-1] if ordered else None,
                "query_layout": True,
                **({"geometry_review": geometry_review} if geometry_review else {}),
            })
        return outputs
    finally:
        connection.close()


def load_rows_by_loc_ids(iso3: str, loc_ids: list[str], columns: list[str] | None = None) -> pd.DataFrame:
    """Load exact rows from an admitted country query layout.

    This is the shape-fetch counterpart to :func:`resolve_point`.  Keeping it
    on the same layout seam lets ``get_geometry`` retrieve the loc_id returned
    by point resolution without falling back to a legacy country bank.
    """
    iso3 = str(iso3 or "").strip().upper()
    requested = list(dict.fromkeys(str(value).strip() for value in loc_ids if str(value).strip()))
    if not requested or not layout_available(iso3):
        return pd.DataFrame()
    projection = list(dict.fromkeys(["loc_id", *(columns or [])]))
    # DuckDB's spatial GEOMETRY logical type cannot be converted directly to
    # a pandas/NumPy column. Runtime geometry loaders use WKB, so normalize the
    # shape at the SQL boundary while preserving every other field.
    select_clause = (
        "* EXCLUDE (geometry), ST_AsWKB(geometry) AS geometry"
        if columns is None
        else ", ".join(f'"{name}"' for name in projection)
    )
    root = layout_root(iso3)
    manifest = _layout_manifest(iso3)
    route_spec = manifest.get("route_index") or {}
    route_index_required = bool(route_spec.get("path") == ROUTE_INDEX_NAME)
    route_rows: dict[str, tuple[int, str]] = {}
    route_path = root / ROUTE_INDEX_NAME
    if route_index_required or route_path.is_file():
        route_connection = _connection()
        try:
            placeholders = ",".join("?" for _ in requested)
            rows = route_connection.execute(
                f"SELECT loc_id, admin_level, admin_1_loc_id FROM read_parquet(?) "
                f"WHERE loc_id IN ({placeholders})",
                [path_to_uri(route_path), *requested],
            ).fetchall()
            route_rows = {
                str(loc_id): (int(admin_level), str(owner or ""))
                for loc_id, admin_level, owner in rows
            }
        except Exception:
            if route_index_required:
                return pd.DataFrame()
            route_rows = {}
        finally:
            route_connection.close()
    requests_by_path: dict[Path, dict[int, list[str]]] = {}
    for loc_id in requested:
        route = route_rows.get(loc_id)
        if route is not None:
            admin_level, owner_loc_id = route
        elif route_index_required:
            # A modern layout's explicit routing table is authoritative. An
            # unknown ID must not be guessed from punctuation.
            continue
        else:
            parts = loc_id.split("-")
            admin_level = len(parts) - 1
            owner_loc_id = "-".join(parts[:2])
        if admin_level <= 3:
            path = root / "admin_0_3.parquet"
        else:
            path = root / "deep" / f"{owner_loc_id}.parquet"
        requests_by_path.setdefault(path, {}).setdefault(admin_level, []).append(loc_id)
    connection = _connection()
    try:
        frames = []
        for path, requests_by_level in requests_by_path.items():
            if not path.is_file() and not is_cloud_mode():
                continue
            predicates = []
            parameters: list[Any] = [path_to_uri(path)]
            for admin_level, path_loc_ids in sorted(requests_by_level.items()):
                placeholders = ",".join("?" for _ in path_loc_ids)
                predicates.append(f"(admin_level = ? AND loc_id IN ({placeholders}))")
                parameters.extend([admin_level, *path_loc_ids])
            frame = connection.execute(
                f"SELECT {select_clause} FROM read_parquet(?) WHERE {' OR '.join(predicates)}",
                parameters,
            ).fetchdf()
            if not frame.empty:
                frames.append(frame)
        if not frames:
            return pd.DataFrame()
        result = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["loc_id"], keep="first")
        order = {loc_id: index for index, loc_id in enumerate(requested)}
        result["_requested_order"] = result["loc_id"].map(order)
        return result.sort_values("_requested_order").drop(columns=["_requested_order"]).reset_index(drop=True)
    finally:
        connection.close()


def load_route_rows_by_loc_ids(iso3: str, loc_ids: list[str]) -> pd.DataFrame:
    """Resolve admin identities from the compact country route index only.

    Identification and joins need existence, level, and deep-shard ownership;
    they do not need to reopen polygon banks.  The route index is part of the
    admitted query-layout closure and is authoritative for modern layouts.
    """
    country = str(iso3 or "").strip().upper()
    requested = list(dict.fromkeys(
        str(value).strip() for value in loc_ids if str(value).strip()
    ))
    if not requested or not layout_available(country):
        return pd.DataFrame(columns=["loc_id", "admin_level", "admin_1_loc_id"])
    route_path = layout_root(country) / ROUTE_INDEX_NAME
    manifest = _layout_manifest(country)
    route_required = bool((manifest.get("route_index") or {}).get("path") == ROUTE_INDEX_NAME)
    if not route_required and not route_path.is_file() and not is_cloud_mode():
        return pd.DataFrame(columns=["loc_id", "admin_level", "admin_1_loc_id"])
    connection = _connection()
    try:
        placeholders = ",".join("?" for _ in requested)
        frame = connection.execute(
            f"SELECT loc_id, admin_level, admin_1_loc_id FROM read_parquet(?) "
            f"WHERE loc_id IN ({placeholders})",
            [path_to_uri(route_path), *requested],
        ).fetchdf()
        if frame.empty:
            return frame
        order = {loc_id: index for index, loc_id in enumerate(requested)}
        frame["_requested_order"] = frame["loc_id"].map(order)
        return frame.sort_values("_requested_order").drop(
            columns=["_requested_order"]
        ).reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["loc_id", "admin_level", "admin_1_loc_id"])
    finally:
        connection.close()


def query_descendant_scope(
    iso3: str,
    parent_loc_id: str,
    target_admin_level: int,
    *,
    bbox: tuple[float, float, float, float] | None = None,
    limit: int | None = 100,
    offset: int = 0,
    count_only: bool = False,
) -> dict[str, Any] | None:
    """Page descendants with one scan of the authoritative geometry bank.

    The route index identifies the parent's level and Admin1 owner. The actual
    result query then touches exactly one geometry Parquet: the national
    Admin0-3 bank, or one Admin1-owned deep bank. Country-wide deep requests
    deliberately return ``None`` because they span multiple physical banks.
    """
    country = str(iso3 or "").strip().upper()
    parent = str(parent_loc_id or "").strip()
    target = int(target_admin_level)
    if not parent or not layout_available(country):
        return None

    root = layout_root(country)
    route_path = root / ROUTE_INDEX_NAME
    connection = _connection()
    try:
        route = connection.execute(
            "SELECT admin_level, admin_1_loc_id FROM read_parquet(?) WHERE loc_id = ? LIMIT 1",
            [path_to_uri(route_path), parent],
        ).fetchone()
        if route is None:
            return {"rows": [], "total_count": 0, "single_bank": True}
        parent_level = int(route[0])
        owner = str(route[1] or "").strip()
        if target <= parent_level:
            return {"rows": [], "total_count": 0, "single_bank": True}
        if target <= 3:
            bank_path = root / "admin_0_3.parquet"
        elif parent_level >= 1 and owner:
            bank_path = root / "deep" / f"{owner}.parquet"
        else:
            return None
        if not is_cloud_mode() and not bank_path.is_file():
            return {"rows": [], "total_count": 0, "single_bank": True}

        ancestry_column = f"admin_{parent_level}_loc_id"
        clauses = ["admin_level = ?", f'"{ancestry_column}" = ?']
        parameters: list[Any] = [path_to_uri(bank_path), target, parent]
        if bbox is not None:
            min_lon, min_lat, max_lon, max_lat = bbox
            clauses.extend([
                "bbox_max_lon >= ?", "bbox_min_lon <= ?",
                "bbox_max_lat >= ?", "bbox_min_lat <= ?",
            ])
            parameters.extend([min_lon, max_lon, min_lat, max_lat])
        where_clause = " AND ".join(clauses)
        page_limit = None if limit is None else max(0, int(limit))
        if count_only or page_limit == 0:
            total = int(connection.execute(
                f"SELECT count(*) FROM read_parquet(?) WHERE {where_clause}",
                parameters,
            ).fetchone()[0])
            return {"rows": [], "total_count": total, "single_bank": True}

        page_offset = max(0, int(offset))
        page_parameters = [*parameters]
        page_clause = ""
        if page_limit is not None:
            page_clause += " LIMIT ?"
            page_parameters.append(page_limit)
        if page_offset:
            page_clause += " OFFSET ?"
            page_parameters.append(page_offset)
        frame = connection.execute(
            f"SELECT {META_COLUMNS}, count(*) OVER () AS __total_count "
            f"FROM read_parquet(?) WHERE {where_clause} ORDER BY loc_id{page_clause}",
            page_parameters,
        ).fetchdf()
        if frame.empty:
            # OFFSET beyond the final row loses the window count; use one small
            # count query only for that uncommon pagination edge case.
            total = 0
            if page_offset:
                total = int(connection.execute(
                    f"SELECT count(*) FROM read_parquet(?) WHERE {where_clause}",
                    parameters,
                ).fetchone()[0])
            return {"rows": [], "total_count": total, "single_bank": True}
        total = int(frame["__total_count"].iloc[0])
        rows = frame.drop(columns=["__total_count"]).to_dict("records")
        return {"rows": rows, "total_count": total, "single_bank": True}
    finally:
        connection.close()
