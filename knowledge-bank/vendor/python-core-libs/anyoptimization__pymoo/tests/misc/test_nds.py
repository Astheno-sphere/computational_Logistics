import numpy as np
import pytest
import moocore

from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting, find_non_dominated


CASES = {
    'empty':      np.zeros((0, 2)),
    'single':     np.array([[1.0, 2.0]]),
    'duplicates': np.array([[1.0, 2.0], [1.0, 2.0], [1.0, 2.0]]),
    'all_nd':     np.array([[1.0, 3.0], [2.0, 2.0], [3.0, 1.0]]),
    'all_dom':    np.array([[1.0, 1.0], [2.0, 2.0], [3.0, 3.0]]),
    'mixed':      np.array([[1.0, 3.0], [2.0, 2.0], [2.0, 2.0], [3.0, 1.0], [4.0, 4.0]]),
    'random_2d':  np.random.RandomState(1).rand(50, 2),
    'random_3d':  np.random.RandomState(1).rand(50, 3),
    'random_5d':  np.random.RandomState(1).rand(50, 5),
}


@pytest.mark.parametrize('F', CASES.values(), ids=CASES.keys())
def test_find_non_dominated(F):
    pymoo = find_non_dominated(F)
    mc = np.array([], dtype=int) if len(F) == 0 else np.where(moocore.is_nondominated(F, keep_weakly=True))[0]
    np.testing.assert_array_equal(np.sort(pymoo), np.sort(mc))


@pytest.mark.parametrize('F', CASES.values(), ids=CASES.keys())
def test_non_dominated_sorting_ranks(F):
    if len(F) == 0:
        assert NonDominatedSorting().do(F) == []
        return
    _, pymoo_ranks = NonDominatedSorting().do(F, return_rank=True)
    mc_ranks = moocore.pareto_rank(F)
    np.testing.assert_array_equal(pymoo_ranks, mc_ranks)


def test_nds_n_stop_if_ranked():
    F = np.random.RandomState(1).rand(100, 3)
    fronts = NonDominatedSorting().do(F, n_stop_if_ranked=20)
    assert sum(len(f) for f in fronts) >= 20


def test_nds_only_first_front():
    F = np.random.RandomState(1).rand(50, 3)
    front0 = NonDominatedSorting().do(F, only_non_dominated_front=True)
    all_fronts = NonDominatedSorting().do(F)
    np.testing.assert_array_equal(np.sort(front0), np.sort(all_fronts[0]))


def reference_ranks(F):
    # naive O(N^2 M) non-dominated ranking, correct at any dimension
    n = len(F)
    ranks = np.full(n, -1)
    remaining = set(range(n))
    r = 0
    while remaining:
        idx = list(remaining)
        front = [
            i
            for i in idx
            if not any(
                j != i and np.all(F[j] <= F[i]) and np.any(F[j] < F[i]) for j in idx
            )
        ]
        for i in front:
            ranks[i] = r
            remaining.discard(i)
        r += 1
    return ranks


def test_nds_above_moocore_objective_limit():
    # moocore's native pareto_rank supports at most 255 objectives; above that
    # pymoo must fall back to its own implementation instead of failing
    rng = np.random.default_rng(1)
    base = rng.random((30, 3))
    F = np.hstack([base, np.zeros((30, 300 - 3))])

    _, ranks = NonDominatedSorting().do(F, return_rank=True)
    np.testing.assert_array_equal(ranks, reference_ranks(F))


def test_find_non_dominated_above_moocore_objective_limit():
    rng = np.random.default_rng(2)
    base = rng.random((30, 3))
    F = np.hstack([base, np.zeros((30, 300 - 3))])

    expected = np.where(reference_ranks(F) == 0)[0]
    np.testing.assert_array_equal(np.sort(find_non_dominated(F)), expected)
