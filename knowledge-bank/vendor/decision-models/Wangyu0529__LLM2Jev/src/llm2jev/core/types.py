from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypeAlias


JSONValue: TypeAlias = str | int | float | bool | None | Mapping[str, "JSONValue"] | Sequence["JSONValue"]
JSONContent: TypeAlias = str | Mapping[str, JSONValue] | Sequence[JSONValue]
State: TypeAlias = JSONContent
