"""Replay metadata catalog access helpers backed by ``ReplayReader``."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

from agentsociety2.storage.replay_reader import ReplayReader


def _loads_json(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (list, dict)):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="ignore")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return default
    return default


def _get_column_map(dataset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {column["column_name"]: column for column in dataset.get("columns", [])}


def _normalize_dataset_value(column: dict[str, Any] | None, value: Any) -> Any:
    if value is None:
        return None
    sqlite_type = str((column or {}).get("sqlite_type") or "").upper()
    if sqlite_type == "JSON":
        return jsonable_encoder(_loads_json(value, value))
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="ignore")
    return jsonable_encoder(value)


def normalize_dataset_row(
    dataset: dict[str, Any], row: dict[str, Any]
) -> dict[str, Any]:
    """Normalize a raw dataset row into a JSON-safe dict."""

    column_map = _get_column_map(dataset)
    return {
        key: _normalize_dataset_value(column_map.get(key), value)
        for key, value in row.items()
    }


def _translate_reader_error(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(
            status_code=404, detail=f"Dataset '{error.args[0]}' not found"
        )
    if isinstance(error, ValueError):
        return HTTPException(status_code=400, detail=str(error))
    return HTTPException(status_code=500, detail=str(error))


async def _to_thread_http(func, *args, **kwargs):
    try:
        return await asyncio.to_thread(func, *args, **kwargs)
    except HTTPException:
        raise
    except (KeyError, ValueError) as e:
        raise _translate_reader_error(e) from e


async def load_dataset_catalog(reader: ReplayReader) -> list[dict[str, Any]]:
    """Load all replay datasets with column metadata."""

    return await _to_thread_http(reader.load_dataset_catalog)


async def get_dataset_by_id(reader: ReplayReader, dataset_id: str) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(reader.get_dataset_by_id, dataset_id)
    except KeyError as e:
        raise HTTPException(
            status_code=404, detail=f"Dataset '{dataset_id}' not found"
        ) from e


async def find_dataset_by_capability(
    reader: ReplayReader,
    capability: str,
    *,
    kind: str | None = None,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            reader.find_dataset_by_capability, capability, kind=kind
        )
    except KeyError as e:
        raise HTTPException(
            status_code=404,
            detail=f"No replay dataset found for capability '{capability}'",
        ) from e


async def fetch_dataset_rows(
    reader: ReplayReader,
    dataset: dict[str, Any],
    *,
    order_by: str | None = None,
    desc: bool = False,
    step: int | None = None,
    entity_id: int | None = None,
    start_step: int | None = None,
    end_step: int | None = None,
    max_step: int | None = None,
    columns: list[str] | None = None,
    latest_per_entity: bool = False,
    limit: int | None = None,
    offset: int = 0,
) -> dict[str, Any]:
    """Fetch dataset rows with metadata-driven filtering and JSON-safe values."""

    return await _to_thread_http(
        reader.fetch_dataset_rows,
        dataset,
        order_by=order_by,
        desc=desc,
        step=step,
        entity_id=entity_id,
        start_step=start_step,
        end_step=end_step,
        max_step=max_step,
        columns=columns,
        latest_per_entity=latest_per_entity,
        limit=limit,
        offset=offset,
    )


async def count_dataset_rows(
    reader: ReplayReader,
    dataset: dict[str, Any],
    *,
    step: int | None = None,
    entity_id: int | None = None,
    start_step: int | None = None,
    end_step: int | None = None,
    max_step: int | None = None,
    latest_per_entity: bool = False,
) -> int:
    """Count dataset rows using the same filtering semantics as fetch_dataset_rows."""

    return await _to_thread_http(
        reader.count_dataset_rows,
        dataset,
        step=step,
        entity_id=entity_id,
        start_step=start_step,
        end_step=end_step,
        max_step=max_step,
        latest_per_entity=latest_per_entity,
    )


async def query_dataset_rows(
    reader: ReplayReader,
    dataset: dict[str, Any],
    *,
    page: int,
    page_size: int,
    order_by: str | None = None,
    desc: bool = False,
    step: int | None = None,
    entity_id: int | None = None,
    start_step: int | None = None,
    end_step: int | None = None,
    max_step: int | None = None,
    columns: list[str] | None = None,
    latest_per_entity: bool = False,
) -> dict[str, Any]:
    """Query rows from a dataset using metadata-driven filtering."""

    return await _to_thread_http(
        reader.query_dataset_rows,
        dataset,
        page=page,
        page_size=page_size,
        order_by=order_by,
        desc=desc,
        step=step,
        entity_id=entity_id,
        start_step=start_step,
        end_step=end_step,
        max_step=max_step,
        columns=columns,
        latest_per_entity=latest_per_entity,
    )


async def distinct_dataset_values(
    reader: ReplayReader,
    dataset: dict[str, Any],
    column: str,
    *,
    order: bool = True,
) -> list[Any]:
    return await _to_thread_http(reader.distinct_values, dataset, column, order=order)


async def count_dataset_distinct(
    reader: ReplayReader, dataset: dict[str, Any], column: str
) -> int:
    return await _to_thread_http(reader.count_distinct, dataset, column)


async def min_dataset_value(
    reader: ReplayReader, dataset: dict[str, Any], column: str
) -> Any:
    return await _to_thread_http(reader.min_value, dataset, column)


async def max_dataset_value(
    reader: ReplayReader, dataset: dict[str, Any], column: str
) -> Any:
    return await _to_thread_http(reader.max_value, dataset, column)
