"""When to stop reading cyclic shifts, with a guarantee that costs no labels.

L0 reads K cyclic shifts so that every option occupies every position once, which removes an additive
position bias exactly and makes the answer independent of the order the caller listed the options in.
Most items do not need all K: the leader is often decided after two or three, and reading the rest
changes nothing. The problem is knowing which items those are without looking at labels.

The trick is the choice of target. We do not try to certify *accuracy* -- that would need labels.
We certify **agreement with our own full-K answer**, which can be measured on any unlabelled states a
deployment already has: read all K shifts on a calibration batch once, record what full L0 said, then
find the smallest threshold whose disagreement rate clears the target. The user asks for "the decision
full L0 would have made, 99% of the time" and gets a mean shift count instead of K.

Two details decide whether this works.

**The statistic.** The natural one is the gap between the top two options, but a gap between
*probabilities* saturates at 1: once the marginal is peaked it carries no more information, which is
exactly the regime in which the rule must decide. The **log-odds margin** -- the same gap taken in log
space -- is unbounded and keeps separating "decided" from "overwhelmingly decided". Measured over four
(model, task) cells at K=18-20, a probability gap could not certify a 1% disagreement rate on two of
them at any threshold, while the log-odds margin certified all four
(`bench/results_layout/2026-09-27/margin_default.json`, research log entry 24).

**The certificate.** A threshold chosen on the calibration split's *point estimate* does not hold out:
300 states at a 1% target allow three disagreements, and fitting to exactly three overfits. Requiring a
Clopper-Pearson upper confidence bound to clear the target instead is what makes the number a
certificate; on the same four cells the held-out disagreement then came in at 0.000-0.008 against a 1%
target, where the point-estimate version came in at 0.013-0.025.

`DEFAULT_LOG_MARGIN` is the threshold to use before any calibration: the smallest value that certified
1% on all four cells at once. Calibrating per (model, question) is worth about 1.5x on top of it.
"""
from __future__ import annotations

from math import lgamma
from typing import Optional, Sequence, Tuple

import numpy as np

EPS = 1e-12

#: Certified on four (model, task) cells at K=18-20 (two 7-8B models, 900 unlabelled states each):
#: the smallest global log-odds margin whose Clopper-Pearson 95% upper bound on disagreement with the
#: full-K answer stays under 1%. It bought 1.9x-3.9x fewer shifts there. Outside that range -- very
#: small K, a very different model -- it is untested, so calibrate.
DEFAULT_LOG_MARGIN = 8.5


def log_margin(marginal: Sequence[float]) -> float:
    """Top-1 minus top-2 of a marginal, in log space.

    Invariant to the marginal's normalisation, so it can be read straight off `permute.marginalize`
    output: dividing both entries by the same total leaves their log difference alone."""
    p = np.sort(np.asarray(marginal, dtype=np.float64))[::-1]
    if p.size < 2:
        return float("inf")
    return float(np.log(max(p[0], EPS)) - np.log(max(p[1], EPS)))


def binom_cdf(k: int, n: int, p: float) -> float:
    """P[X <= k] for X ~ Binomial(n, p), summed in log space. Standard library plus numpy, because CI
    runs on numpy alone."""
    if n <= 0:
        return 1.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 1.0 if k >= n else 0.0
    k = min(k, n)
    ks = np.arange(0, k + 1)
    log_choose = np.asarray([lgamma(n + 1) - lgamma(int(i) + 1) - lgamma(n - int(i) + 1)
                             for i in ks])
    terms = log_choose + ks * np.log(p) + (n - ks) * np.log1p(-p)
    top = float(terms.max())
    return float(np.exp(top) * np.exp(terms - top).sum())


def cp_upper(k: int, n: int, delta: float = 0.05, iters: int = 60) -> float:
    """Clopper-Pearson upper confidence bound on a failure rate: the largest rate consistent with
    having seen `k` failures in `n` independent draws, at confidence 1 - `delta`."""
    if n <= 0:
        return 1.0
    if k >= n:
        return 1.0
    lo, hi = k / n, 1.0
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if binom_cdf(k, n, mid) > delta:
            lo = mid
        else:
            hi = mid
    return float(hi)


def stop_step(margins: Sequence[float], threshold: float, min_shifts: int) -> int:
    """How many shifts a rule with this threshold would have read.

    `margins[p]` is the running log-odds margin after p + 1 shifts. Returns a count in
    1..len(margins); len(margins) means it never stopped early."""
    m = np.asarray(margins, dtype=np.float64)
    ok = m >= threshold
    ok[: max(0, min_shifts - 1)] = False
    return int(np.argmax(ok) + 1) if bool(ok.any()) else int(m.size)


def choose_threshold(margins: np.ndarray, winners: np.ndarray, target: float = 0.01,
                     min_shifts: int = 2, delta: float = 0.05,
                     grid: Optional[Sequence[float]] = None) -> Tuple[Optional[float], dict]:
    """The cheapest threshold whose disagreement with the full-K answer is certified under `target`.

    margins: [N, K] running log-odds margin after 1..K shifts, in the order the shifts are read.
    winners: [N, K] running argmax (an option index) after 1..K shifts.

    Neither argument involves a label: the reference answer is `winners[:, -1]`, which is what reading
    every shift produced. Returns (threshold, info); the threshold is None when nothing in the grid
    can be certified, and the caller should then read every shift."""
    margins = np.asarray(margins, dtype=np.float64)
    winners = np.asarray(winners)
    n, k = margins.shape
    reference = winners[:, -1]
    if grid is None:
        grid = np.arange(0.0, 20.01, 0.25)
    for thr in grid:
        used = np.asarray([stop_step(margins[i], float(thr), min_shifts) for i in range(n)])
        pred = winners[np.arange(n), used - 1]
        bad = int(np.sum(pred != reference))
        bound = cp_upper(bad, n, delta)
        if bound <= target:
            return float(thr), {"n": n, "K": int(k), "target": target, "delta": delta,
                                "disagreements": bad, "bound": bound,
                                "mean_shifts": float(used.mean()),
                                "max_shifts": int(used.max()),
                                "shifts_saved": float(k - used.mean())}
    return None, {"n": n, "K": int(k), "target": target, "delta": delta,
                  "reason": "no threshold in the grid could be certified at this target"}
