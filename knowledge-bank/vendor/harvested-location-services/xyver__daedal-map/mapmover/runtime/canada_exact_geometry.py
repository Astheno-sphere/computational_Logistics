"""Memory-bounded exact Canada point containment over component shards."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import shapely

from ..duckdb_helpers import lease_query_connection, parquet_columns, path_to_uri
from ..paths import DATA_ROOT


ROOT = (
    DATA_ROOT / "geometry" / "countries" / "CAN" / "representations" /
    "statcan_2021" / "predicate_exact"
)


def canada_query_exact_enabled() -> bool:
    return str(os.getenv("CANADA_QUERY_EXACT_ENABLED", "")).strip().lower() in {
        "1", "true", "yes", "on",
    }


def _partition(level: int, province: str | None = None) -> tuple[Path, Path]:
    stem = "CAN" if level < 2 else f"CAN-{province}"
    root = ROOT / f"admin_{level}"
    return root / f"{stem}.index.parquet", root / f"{stem}.parquet"


def _sql_uri(path: Path) -> str:
    return path_to_uri(path).replace("'", "''")


def _match_partition(connection, points: list[dict], level: int, province: str | None) -> dict[int, dict]:
    if not points:
        return {}
    index_path, geometry_path = _partition(level, province)
    values = ", ".join("(?, ?, ?)" for _ in points)
    params: list[Any] = []
    for point in points:
        params.extend([int(point["index"]), float(point["lon"]), float(point["lat"])])
    candidates = connection.execute(
        f"""WITH points(point_index, lon, lat) AS (VALUES {values})
            SELECT points.point_index, components.component_row_id
            FROM points
            JOIN read_parquet('{_sql_uri(index_path)}') AS components
              ON components.min_x <= points.lon AND components.max_x >= points.lon
             AND components.min_y <= points.lat AND components.max_y >= points.lat
            ORDER BY points.point_index, components.component_row_id""",
        params,
    ).fetchall()
    component_ids = sorted({int(row[1]) for row in candidates})
    if not component_ids:
        return {}
    placeholders = ", ".join("?" for _ in component_ids)
    available = parquet_columns(geometry_path)
    optional = ["name", "source_system", "source_vintage", "source_id"]
    optional_sql = ", ".join(
        name if name in available else f"NULL AS {name}" for name in optional
    )
    cursor = connection.execute(
        f"""SELECT component_row_id, loc_id, parent_id, admin_level,
                   {optional_sql}, geometry
            FROM read_parquet('{_sql_uri(geometry_path)}')
            WHERE component_row_id IN ({placeholders})""",
        component_ids,
    )
    columns = [item[0] for item in cursor.description]
    components = {int(row[0]): dict(zip(columns, row)) for row in cursor.fetchall()}
    points_by_index = {int(point["index"]): point for point in points}
    matches: dict[int, list[dict]] = {}
    for point_index, component_id in candidates:
        row = components.get(int(component_id))
        point = points_by_index[int(point_index)]
        if row and shapely.covers(
            shapely.from_wkb(bytes(row["geometry"])),
            shapely.Point(float(point["lon"]), float(point["lat"])),
        ):
            cleaned = {key: value for key, value in row.items() if key != "geometry"}
            matches.setdefault(int(point_index), []).append(cleaned)
    # Shared official edges can legitimately cover both neighbors. Preserve a
    # deterministic choice until the public contract grows an ambiguity array.
    return {
        point_index: sorted(rows, key=lambda row: str(row["loc_id"]))[0]
        for point_index, rows in matches.items()
    }


def resolve_canada_query_exact_points(
    points: list[dict], *, target_admin_level: int | None = None,
) -> list[dict]:
    """Resolve a Canada-scoped batch without hydrating full feature polygons."""
    target = 5 if target_admin_level is None else max(0, min(5, int(target_admin_level)))
    normalized: list[dict] = []
    results: list[dict | None] = [None] * len(points or [])
    for index, point in enumerate(points or []):
        try:
            normalized.append({"index": index, "lon": float(point["lon"]), "lat": float(point["lat"])})
        except (KeyError, TypeError, ValueError):
            results[index] = {"error": "invalid point"}

    connection = lease_query_connection()
    matches_by_point: dict[int, dict[int, dict]] = {item["index"]: {} for item in normalized}
    try:
        for level in range(0, min(target, 1) + 1):
            for index, row in _match_partition(connection, normalized, level, None).items():
                matches_by_point[index][level] = row
        for level in range(2, target + 1):
            by_province: dict[str, list[dict]] = {}
            for point in normalized:
                admin1 = matches_by_point[point["index"]].get(1)
                loc_id = str((admin1 or {}).get("loc_id") or "")
                province = loc_id.split("-")[1] if loc_id.startswith("CAN-") else ""
                if province:
                    by_province.setdefault(province, []).append(point)
            for province, province_points in by_province.items():
                for index, row in _match_partition(connection, province_points, level, province).items():
                    matches_by_point[index][level] = row
    finally:
        connection.close()

    missing_name_ids = sorted({
        str(row.get("loc_id"))
        for levels in matches_by_point.values() for row in levels.values()
        if row.get("loc_id") and not row.get("name")
    })
    if missing_name_ids:
        from .reference_graph import identities

        names = {
            str(row.get("loc_id")): row.get("name")
            for row in identities(missing_name_ids)
        }
        for levels in matches_by_point.values():
            for row in levels.values():
                if not row.get("name"):
                    row["name"] = names.get(str(row.get("loc_id")))

    for point in normalized:
        index = point["index"]
        levels = matches_by_point[index]
        deepest_level = max(levels, default=-1)
        deepest = levels.get(deepest_level)
        if deepest is None or deepest_level != target:
            results[index] = {
                "point": {"lon": point["lon"], "lat": point["lat"]},
                "country": {"loc_id": "CAN", "name": "Canada"},
                "target_admin_level": f"admin_{target}",
                "resolution_fidelity": "query_exact_predicate_components",
                "error": {
                    "code": "no_match_at_target_admin_level",
                    "message": f"Point did not match an exact admin_{target} component in CAN",
                },
            }
            continue
        stack = [
            {
                "loc_id": row.get("loc_id"), "name": row.get("name"),
                "admin_level": level, "vintage": row.get("source_vintage"),
            }
            for level, row in sorted(levels.items())
        ]
        results[index] = {
            "point": {"lon": point["lon"], "lat": point["lat"]},
            "country": {"loc_id": "CAN", "name": "Canada"},
            "matched": {
                "loc_id": deepest.get("loc_id"), "name": deepest.get("name"),
                "admin_level": deepest_level, "country_name": "Canada", "iso3": "CAN",
            },
            "stack": stack,
            "resolution_mode": "query_exact_single_vintage",
            "resolution_fidelity": "query_exact_predicate_components",
            "target_admin_level": f"admin_{target}",
            "deeper_available": target < 5,
            "available_deeper_admin_levels": [f"admin_{level}" for level in range(target + 1, 6)],
        }
    return [result or {"error": "point did not resolve"} for result in results]
