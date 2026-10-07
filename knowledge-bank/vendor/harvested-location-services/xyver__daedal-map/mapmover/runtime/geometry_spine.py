"""Runtime geometry-spine helpers shared by API and MCP tools.

The private converters use reviewed geometry banks with a strict STRtree
point-overlay path. This module keeps the public runtime on the same shape:
parse each bank once, query many points, and choose the smallest covering
polygon without route-specific shortcuts.
"""
from __future__ import annotations

import json
import math
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Iterable

import pandas as pd
from shapely.geometry import Point, shape
from shapely.strtree import STRtree
from shapely.wkb import loads as load_wkb

try:
    import orjson

    def _json_loads(value: str) -> Any:
        return orjson.loads(value)

except ImportError:

    def _json_loads(value: str) -> Any:
        return json.loads(value)


@dataclass(frozen=True)
class RuntimeGeometryMatch:
    """One strict match from a runtime geometry bank."""

    row: pd.Series
    candidate_count: int
    candidate_loc_ids: tuple[str, ...] = ()


class RuntimeGeometrySpineIndex:
    """A DataFrame-backed polygon bank with strict point overlay behavior."""

    def __init__(
        self,
        frame: pd.DataFrame,
        *,
        loc_id_column: str = "loc_id",
        geometry_column: str = "geometry",
    ) -> None:
        self.loc_id_column = loc_id_column
        self.geometry_column = geometry_column
        self._frame = frame.reset_index(drop=True)
        self._geometries: list[Any] = []
        self._row_positions: list[int] = []
        self._geometry_ids: dict[int, int] = {}

        if geometry_column not in self._frame.columns:
            self._tree = None
            return

        for row_position, row in enumerate(self._frame.itertuples(index=False)):
            geom_value = getattr(row, geometry_column, None)
            if geom_value is None or (isinstance(geom_value, float) and math.isnan(geom_value)):
                continue
            try:
                if isinstance(geom_value, (bytes, bytearray, memoryview)):
                    geometry = load_wkb(bytes(geom_value))
                else:
                    geometry_payload = _json_loads(geom_value) if isinstance(geom_value, str) else geom_value
                    if not geometry_payload or geometry_payload.get("type") == "Point":
                        continue
                    geometry = shape(geometry_payload)
            except Exception:
                continue
            if geometry.is_empty:
                continue
            self._geometry_ids[id(geometry)] = len(self._geometries)
            self._geometries.append(geometry)
            self._row_positions.append(row_position)

        self._tree = STRtree(self._geometries) if self._geometries else None

    def _candidate_geometry_indexes(self, point: Point) -> Iterable[int]:
        if self._tree is None:
            return []
        raw_indexes = self._tree.query(point)
        indexes: list[int] = []
        for raw_index in raw_indexes:
            if isinstance(raw_index, (int,)):
                indexes.append(int(raw_index))
                continue
            try:
                indexes.append(int(raw_index))
                continue
            except (TypeError, ValueError):
                mapped_index = self._geometry_ids.get(id(raw_index))
                if mapped_index is not None:
                    indexes.append(mapped_index)
        return indexes

    def match_point(
        self,
        longitude: float | None,
        latitude: float | None,
        *,
        row_filter: Callable[[pd.Series], bool] | None = None,
    ) -> RuntimeGeometryMatch | None:
        if longitude is None or latitude is None or pd.isna(longitude) or pd.isna(latitude):
            return None
        point = Point(float(longitude), float(latitude))
        matches: list[tuple[float, str, int]] = []
        candidate_count = 0
        for geometry_index in self._candidate_geometry_indexes(point):
            geometry = self._geometries[geometry_index]
            if not geometry.covers(point):
                continue
            row_position = self._row_positions[geometry_index]
            row = self._frame.iloc[row_position]
            if row_filter is not None and not row_filter(row):
                continue
            candidate_count += 1
            loc_id = str(row.get(self.loc_id_column) or "")
            matches.append((float(geometry.area), loc_id, row_position))
        if not matches:
            return None
        matches.sort(key=lambda item: (item[0], item[1], item[2]))
        row_position = matches[0][2]
        return RuntimeGeometryMatch(
            row=self._frame.iloc[row_position], candidate_count=candidate_count,
            candidate_loc_ids=tuple(sorted({item[1] for item in matches})),
        )

    def match_points(
        self,
        points: Iterable[dict[str, Any]],
        *,
        row_filter: Callable[[pd.Series, dict[str, Any]], bool] | None = None,
    ) -> list[RuntimeGeometryMatch | None]:
        point_items = list(points)
        if self._tree is None or not point_items:
            return [None] * len(point_items)

        query_points: list[Point] = []
        query_to_item: list[int] = []
        for item_index, item in enumerate(point_items):
            try:
                lon = float(item.get("lon"))
                lat = float(item.get("lat"))
            except Exception:
                continue
            if pd.isna(lon) or pd.isna(lat):
                continue
            query_to_item.append(item_index)
            query_points.append(Point(lon, lat))
        if not query_points:
            return [None] * len(point_items)

        try:
            raw_pairs = self._tree.query(query_points, predicate="covered_by")
        except Exception:
            return [
                self.match_point(
                    item.get("lon"),
                    item.get("lat"),
                    row_filter=(lambda row, item=item: row_filter(row, item)) if row_filter is not None else None,
                )
                for item in point_items
            ]

        best: dict[int, tuple[float, str, int]] = {}
        counts: dict[int, int] = {}
        candidate_ids: dict[int, set[str]] = {}
        for query_index, geometry_index in zip(raw_pairs[0], raw_pairs[1]):
            item_index = query_to_item[int(query_index)]
            row_position = self._row_positions[int(geometry_index)]
            row = self._frame.iloc[row_position]
            if row_filter is not None and not row_filter(row, point_items[item_index]):
                continue
            counts[item_index] = counts.get(item_index, 0) + 1
            geometry = self._geometries[int(geometry_index)]
            candidate = (float(geometry.area), str(row.get(self.loc_id_column) or ""), row_position)
            candidate_ids.setdefault(item_index, set()).add(candidate[1])
            current = best.get(item_index)
            if current is None or candidate < current:
                best[item_index] = candidate

        results: list[RuntimeGeometryMatch | None] = [None] * len(point_items)
        for item_index, (_, _, row_position) in best.items():
            results[item_index] = RuntimeGeometryMatch(
                row=self._frame.iloc[row_position],
                candidate_count=counts.get(item_index, 0),
                candidate_loc_ids=tuple(sorted(candidate_ids.get(item_index, set()))),
            )
        return results


_INDEX_CACHE_MAX_ITEMS = 16
_index_cache: OrderedDict[tuple[int, int, tuple[str, ...]], RuntimeGeometrySpineIndex] = OrderedDict()
_index_cache_lock = threading.Lock()


def _cache_key(frame: pd.DataFrame) -> tuple[int, int, tuple[str, ...]]:
    return (id(frame), len(frame), tuple(str(column) for column in frame.columns))


def geometry_spine_index_for_frame(frame: pd.DataFrame | None) -> RuntimeGeometrySpineIndex | None:
    """Return a cached runtime geometry-spine index for a loaded geometry frame."""
    if frame is None or frame.empty:
        return None
    key = _cache_key(frame)
    with _index_cache_lock:
        cached = _index_cache.get(key)
        if cached is not None:
            _index_cache.move_to_end(key)
            return cached
    index = RuntimeGeometrySpineIndex(frame)
    with _index_cache_lock:
        _index_cache[key] = index
        _index_cache.move_to_end(key)
        while len(_index_cache) > _INDEX_CACHE_MAX_ITEMS:
            _index_cache.popitem(last=False)
    return index


def match_point_in_frame(frame: pd.DataFrame | None, lon: float, lat: float) -> pd.Series | None:
    """Compatibility helper for single point lookups."""
    index = geometry_spine_index_for_frame(frame)
    match = index.match_point(lon, lat) if index is not None else None
    return match.row if match is not None else None
