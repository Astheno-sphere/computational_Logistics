"""Tests for the pure-numpy IGD helper in pymoo.util.misc."""

import numpy as np
import pytest
from moocore import igd as moocore_igd

from pymoo.util.misc import igd


@pytest.mark.parametrize("n_ref", [1, 3, 10, 50])
@pytest.mark.parametrize("n_pts", [1, 5, 20])
@pytest.mark.parametrize("n_dim", [1, 2, 5, 31])  # moocore caps dimensions at 31
def test_igd_matches_moocore(n_ref, n_pts, n_dim):
    rng = np.random.default_rng(n_ref * 1000 + n_pts * 10 + n_dim)
    F = rng.random((n_pts, n_dim))
    ref = rng.random((n_ref, n_dim))

    expected = moocore_igd(F, ref=ref)
    actual = igd(F, ref)

    np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-12)


def test_igd_identical_sets_is_zero():
    F = np.arange(48, dtype=float).reshape(1, 48)
    np.testing.assert_allclose(igd(F, F), 0.0, atol=1e-12)


def test_igd_reference_subset_of_F_is_zero():
    # every reference point coincides with a point in F -> IGD == 0
    F = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]])
    ref = np.array([[0.0, 0.0], [2.0, 2.0]])
    np.testing.assert_allclose(igd(F, ref), 0.0, atol=1e-12)


def test_igd_column_mismatch_raises():
    with pytest.raises(ValueError):
        igd(np.zeros((3, 4)), np.zeros((3, 5)))


def test_igd_high_dim_survives_where_moocore_cap_would_break():
    # moocore.igd has a hard MOOCORE_DIMENSION_MAX=31 cap enforced only by a
    # compile-time assume; the numpy helper must handle far more columns.
    rng = np.random.default_rng(0)
    F = rng.random((5, 500))
    ref = rng.random((7, 500))

    D = np.sqrt(((ref[:, None, :] - F[None, :, :]) ** 2).sum(axis=2))
    expected = float(np.mean(np.min(D, axis=1)))

    np.testing.assert_allclose(igd(F, ref), expected, rtol=1e-12)
