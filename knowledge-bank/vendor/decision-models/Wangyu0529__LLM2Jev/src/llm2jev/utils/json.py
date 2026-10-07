from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypeVar, cast


T = TypeVar("T")


def is_json_value(value: object) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and is_json_value(item) for key, item in value.items())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return all(is_json_value(item) for item in value)
    return False


def is_json_content(value: object) -> bool:
    return isinstance(value, str) or (
        isinstance(value, Mapping) and is_json_value(value)
    ) or (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes, bytearray))
        and is_json_value(value)
    )


def copy_json_content(value: T) -> T:
    """Recursively copy JSON containers while preserving scalar values."""

    if isinstance(value, Mapping):
        return cast(T, {key: copy_json_content(item) for key, item in value.items()})
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return cast(T, [copy_json_content(item) for item in value])
    return value

