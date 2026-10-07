"""Guard the hand-written API reference against silently going out of date.

The Sphinx ``api/algorithms.rst`` page lists each algorithm with a manual
``.. autoclass::`` entry. Historically it drifted badly (9 of ~40 algorithms
listed), so a new algorithm could ship invisible to the documentation. This test
asserts the page lists every algorithm in the canonical portfolio (the same lists
the deterministic + golden suites parametrize over), so the omission fails CI.
"""

import re
from pathlib import Path

from tests.algorithms.test_deterministic_moo import MULTI_OBJECTIVE_ALGORITHM_CLASSES
from tests.algorithms.test_deterministic_soo import ALL_SINGLE_OBJECTIVE_ALGORITHMS

ALGORITHMS_RST = Path(__file__).parent.parent / "docs" / "source" / "api" / "algorithms.rst"

ALL_ALGORITHMS = ALL_SINGLE_OBJECTIVE_ALGORITHMS + MULTI_OBJECTIVE_ALGORITHM_CLASSES


def _documented_paths():
    text = ALGORITHMS_RST.read_text()
    return set(re.findall(r"^\.\.\s+autoclass::\s+(\S+)", text, flags=re.MULTILINE))


def test_every_algorithm_is_documented():
    documented = _documented_paths()
    expected = {f"{a.__module__}.{a.__qualname__}" for a in ALL_ALGORITHMS}

    missing = sorted(expected - documented)
    assert not missing, (
        f"algorithms missing an autoclass entry in {ALGORITHMS_RST.name}: {missing}. "
        f"Add a `.. autoclass:: <import path>` block for each."
    )
