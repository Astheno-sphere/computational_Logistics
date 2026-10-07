from __future__ import annotations

import math
from collections.abc import Sequence

from ..utils.probability import validate_probabilities


def normalize_l1(probabilities: Sequence[float]) -> tuple[float, ...]:
    """Normalize non-negative values to sum to one, or return a uniform distribution."""

    values = validate_probabilities(probabilities)
    total = math.fsum(values)
    if total == 0:
        uniform = 1.0 / len(values)
        return tuple(uniform for _ in values)
    return tuple(probability / total for probability in values)
