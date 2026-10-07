from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import TypeVar


K = TypeVar("K")


def validate_probability(value: float, field: str = "probability") -> float:
    """Validate and return one finite probability."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number from 0 to 1")
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{field} must be a number from 0 to 1")
    return float(value)


def validate_probabilities(probabilities: Sequence[float]) -> tuple[float, ...]:
    """Validate a non-empty sequence of probabilities."""

    values = tuple(probabilities)
    if not values:
        raise ValueError("probabilities must not be empty")
    return tuple(validate_probability(value, "probability") for value in values)


def copy_probability_distribution(
    probabilities: Mapping[K, float],
) -> dict[K, float]:
    """Copy and validate a non-empty probability distribution."""

    copied = {
        key: validate_probability(probability, f"probability for {key!r}")
        for key, probability in probabilities.items()
    }
    if not copied:
        raise ValueError("probabilities must not be empty")
    if not math.isclose(math.fsum(copied.values()), 1.0, abs_tol=1e-6):
        raise ValueError("probabilities must sum to 1")
    return copied

