"""The choose threshold is backed by a measurement, and cannot outgrow it."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))

import choice_at_scale

from mapsmith import catalog

# A loss this small is inside what one request more or less changes (1 of ~118).
NO_LOSS = 1.0


def test_choosable_is_not_above_the_largest_size_measured_without_loss():
    """Raising `CHOOSABLE` hands a caller bigger sets to choose from, and that is
    free only as far as the measured choice holds.

    The bound is the largest set size the data file actually measured with no
    loss against 30 -- the size itself, not the top of a bucket around it. The
    first version of this test took the top of a "31-40" bucket that held only
    sets of 34, so it allowed 40 on a measurement of 34 and could not fail
    (found by the geo review, 2026-09-29).
    """
    paired = choice_at_scale.score()["paired"]
    assert paired, "the measurement produced no paired comparison: the data file is broken"
    free = choice_at_scale.SIZES[0]
    for size in choice_at_scale.SIZES[1:]:
        row = paired.get(size)
        if row is None or row["loss_points"] > NO_LOSS:
            break
        free = size
    assert catalog.CHOOSABLE <= free, (
        f"CHOOSABLE is {catalog.CHOOSABLE}, but the choice measurement shows no loss only "
        f"up to {free} candidates; re-measure with benchmarks/choice_at_scale.py first"
    )


def test_the_measurement_covers_every_request_at_every_size():
    result = choice_at_scale.score()
    assert set(result["right_by_size"]) == set(choice_at_scale.SIZES)
    assert result["requests"] >= 100
    for row in result["paired"].values():
        assert row["pairs"] >= 100, "most requests must be compared with themselves"
