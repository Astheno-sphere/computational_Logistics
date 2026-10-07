from typing import Any

from pydantic import BaseModel

__all__ = [
    "EnvRouterBenchmarkData",
]


class EnvRouterBenchmarkData(BaseModel):
    instruction: str
    context: dict[str, Any]
    readonly: bool
