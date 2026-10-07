"""The rotation budget: the stopping certificate, and the canonical listing that makes it safe.

The two properties worth pinning are that the certificate is honest (it is a confidence bound, not a
point estimate, so it holds out) and that stopping early does not cost the guarantee L0 is documented
to give -- which it would, if the shifts were applied to the caller's listing instead of a canonical
one.
"""
import numpy as np
import pytest

from anyjev import Decider, Question
from anyjev.backends.fake import FakeBackend
from anyjev.calibrate.stopping import (
    DEFAULT_LOG_MARGIN,
    binom_cdf,
    choose_threshold,
    cp_upper,
    log_margin,
    stop_step,
)

OPTIONS = ["billing", "technical", "sales", "other", "legal", "shipping", "returns"]
TRUTH = {"card charged twice": "billing", "app crashes on launch": "technical",
         "bulk discount": "sales", "contract review": "legal",
         "parcel never arrived": "shipping", "send it back": "returns"}
STATES = list(TRUTH) * 6


def content(state, option):
    return 3.0 if TRUTH.get(state) == option else 0.0


# ---------------------------------------------------------------- the bound
def test_binomial_tail_and_clopper_pearson_agree_with_their_definitions():
    # P[X <= n] = 1, P[X <= 0] = (1-p)^n
    assert binom_cdf(10, 10, 0.3) == pytest.approx(1.0)
    assert binom_cdf(0, 10, 0.3) == pytest.approx(0.7 ** 10)
    # the upper bound is the p at which seeing k or fewer failures has probability exactly delta
    for k, n in ((0, 300), (3, 300), (7, 120)):
        assert binom_cdf(k, n, cp_upper(k, n, 0.05)) == pytest.approx(0.05, abs=1e-6)
    # zero failures out of n gives the closed form 1 - delta**(1/n)
    assert cp_upper(0, 300, 0.05) == pytest.approx(1 - 0.05 ** (1 / 300), abs=1e-6)
    # more evidence tightens it, and it is monotone in the failure count
    assert cp_upper(0, 600) < cp_upper(0, 300) < cp_upper(3, 300)


def test_the_bound_is_what_makes_the_threshold_hold_out():
    """Three failures in 300 is a 1.0% point estimate but a 2.6% upper bound, so a rule calibrated on
    the point estimate would be shipped as '1%' while really sitting at 2.6%."""
    assert 3 / 300 == pytest.approx(0.01)
    assert cp_upper(3, 300) > 0.02


# ---------------------------------------------------------------- the statistic
def test_log_margin_ignores_normalisation_and_orders_by_decisiveness():
    assert log_margin([0.6, 0.3, 0.1]) == pytest.approx(log_margin([6.0, 3.0, 1.0]))
    assert log_margin([0.98, 0.01, 0.01]) > log_margin([0.6, 0.3, 0.1])
    # once the marginal is peaked, a probability gap has almost nowhere left to go: these two are
    # 0.007 apart in gap and 2.3 apart in log margin, and the rule has to separate them
    a, b = [0.995, 0.0025, 0.0025], [0.9995, 0.00025, 0.00025]
    assert (max(b) - sorted(b)[-2]) - (max(a) - sorted(a)[-2]) < 0.01
    assert log_margin(b) - log_margin(a) > 2.0


def test_stop_step_respects_the_minimum_and_falls_back_to_the_full_budget():
    margins = [9.0, 9.0, 9.0, 9.0]
    assert stop_step(margins, threshold=1.0, min_shifts=1) == 1
    assert stop_step(margins, threshold=1.0, min_shifts=3) == 3
    assert stop_step([0.1, 0.2, 0.3], threshold=5.0, min_shifts=2) == 3   # never fires: read them all


# ---------------------------------------------------------------- choosing the threshold
def _planted(n=400, k=18, hard=0.1, seed=0):
    """Margins that grow with the shifts read, and a winner that only the hard items change late."""
    rng = np.random.default_rng(seed)
    margins = np.cumsum(rng.gamma(2.0, 1.2, (n, k)), axis=1) / np.arange(1, k + 1)
    winners = np.tile(rng.integers(0, k, (n, 1)), (1, k))
    flip = rng.random(n) < hard
    margins[flip] *= 0.15                       # the hard items never look decisive
    winners[flip, -1] = (winners[flip, -1] + 1) % k      # ...and their answer moves at the end
    return margins, winners


def test_chosen_threshold_is_certified_and_cheaper_than_reading_every_shift():
    margins, winners = _planted()
    thr, info = choose_threshold(margins, winners, target=0.01, min_shifts=2)
    assert thr is not None
    assert info["bound"] <= 0.01                        # certified, not merely observed
    assert info["disagreements"] / info["n"] <= 0.01
    assert 2 <= info["mean_shifts"] < info["K"]         # and it actually saves something


def test_a_target_nothing_can_reach_returns_no_threshold_rather_than_a_bad_one():
    margins, winners = _planted(n=60, hard=0.5)
    thr, info = choose_threshold(margins, winners, target=1e-4, min_shifts=2)
    assert thr is None and "reason" in info             # the caller then reads every shift


def test_a_tighter_target_never_buys_a_cheaper_threshold():
    margins, winners = _planted()
    loose = choose_threshold(margins, winners, target=0.10)[1]["mean_shifts"]
    tight = choose_threshold(margins, winners, target=0.01)[1]["mean_shifts"]
    assert tight >= loose


# ---------------------------------------------------------------- end to end on the fake model
def test_canonical_listing_makes_the_decision_exactly_order_invariant_at_any_budget():
    """The property L0 is documented to give -- "the result no longer depends on how you listed the
    options" -- has to survive stopping early. It does, because the shifts are applied to a canonical
    listing, so two listings of the same options produce the same prompts."""
    q = Question.choice("Which handler?", OPTIONS, name="route")
    rev = Question.choice("Which handler?", list(reversed(OPTIONS)), name="route")
    for budget in (2, 3, len(OPTIONS)):
        a = Decider(FakeBackend(content, position_bias=[4.0] + [0] * 6), prior="none",
                    max_permutations=budget, adaptive_shifts=False, canonical_order=True)
        b = Decider(FakeBackend(content, position_bias=[4.0] + [0] * 6), prior="none",
                    max_permutations=budget, adaptive_shifts=False, canonical_order=True)
        for state in TRUTH:
            pa = a.decide(state, [q], level="L0")["route"]
            pb = b.decide(state, [rev], level="L0")["route"]
            # the same probability for the same option, whichever way it was listed
            assert pa.argmax == pb.argmax
            assert np.allclose(pa.probs, [pb.probs[rev.options.index(o)] for o in q.options],
                               atol=1e-12)
            assert pa.diagnostics["permutations"] == budget


def test_without_a_canonical_listing_a_partial_budget_is_not_invariant():
    """The control for the test above: this is what the guarantee costs when the caller's order
    reaches the model, and why `canonical_order` defaults to True."""
    q = Question.choice("Which handler?", OPTIONS, name="route")
    rev = Question.choice("Which handler?", list(reversed(OPTIONS)), name="route")
    a = Decider(FakeBackend(content, position_bias=[4.0] + [0] * 6), prior="none",
                max_permutations=2, adaptive_shifts=False, canonical_order=False)
    b = Decider(FakeBackend(content, position_bias=[4.0] + [0] * 6), prior="none",
                max_permutations=2, adaptive_shifts=False, canonical_order=False)
    diffs = []
    for state in TRUTH:
        pa = a.decide(state, [q], level="L0")["route"]
        pb = b.decide(state, [rev], level="L0")["route"]
        diffs.append(max(abs(pa.probs[i] - pb.probs[rev.options.index(o)])
                         for i, o in enumerate(q.options)))
    assert max(diffs) > 1e-6


def test_the_rotation_budget_is_opt_in_and_its_uncalibrated_threshold_errs_towards_reading_more():
    """Opt-in in 0.2 because every shipped table predates it. DEFAULT_LOG_MARGIN was certified on real
    models at K=18-20; on a question this small, with a synthetic model whose margins never approach it,
    it simply reads every shift -- the safe direction for an uncalibrated threshold, and the reason
    `calibrate_adaptive` exists."""
    q = Question.choice("Which handler?", OPTIONS, name="route")
    assert not Decider(FakeBackend(content)).adaptive_shifts      # off unless asked for
    assert not Decider(FakeBackend(content)).canonical_order
    d = Decider(FakeBackend(content, position_bias=[4.0] + [0] * 6), adaptive_shifts=True,
                canonical_order=True)
    assert d.adaptive_stat == "logit"
    assert d.adaptive_wave == 2          # tied-best locally, best on a served engine
    out = d.decide_batch(STATES, q, level="L0")
    assert all(o.diagnostics["adaptive"] for o in out)
    assert all(o.diagnostics["stop_threshold"] == DEFAULT_LOG_MARGIN for o in out)
    assert all(not o.diagnostics["stop_calibrated"] for o in out)
    assert d.stats["adaptive_shifts_total"] / d.stats["adaptive_items"] == q.k

    # a threshold this model can actually reach does save shifts, and keeps the same answers
    cheap = Decider(FakeBackend(content, position_bias=[4.0] + [0] * 6), adaptive_shifts=True,
                    adaptive_margin=2.0)
    got = cheap.decide_batch(STATES, q, level="L0")
    assert cheap.stats["adaptive_shifts_total"] / cheap.stats["adaptive_items"] < q.k
    assert min(o.diagnostics["shifts_used"] for o in got) >= 2
    assert np.mean([a.argmax == b.argmax for a, b in zip(got, out)]) >= 0.9


def test_calibrate_adaptive_needs_no_labels_and_its_certificate_holds_on_held_out_states():
    q = Question.choice("Which handler?", OPTIONS, name="route")
    cal, held = STATES[:24] * 6, STATES[24:]        # see the test below on why 24 is not enough
    d = Decider(FakeBackend(content, position_bias=[3.0, 1.0] + [0] * 5), prior="none",
                adaptive_shifts=True, canonical_order=True)
    cert = d.calibrate_adaptive(q, cal, target=0.05)          # states only -- no labels passed
    assert cert["threshold"] is not None and cert["bound"] <= 0.05
    assert cert["mean_shifts"] <= q.k and cert["n"] == len(cal)

    full = Decider(FakeBackend(content, position_bias=[3.0, 1.0] + [0] * 5), prior="none",
                   adaptive_shifts=False)
    stopped = d.decide_batch(held, q, level="L0")
    reference = full.decide_batch(held, q, level="L0")
    agree = np.mean([s.argmax == r.argmax for s, r in zip(stopped, reference)])
    assert agree >= 0.95
    assert all(s.diagnostics["stop_calibrated"] for s in stopped)


def test_too_few_states_cannot_certify_a_tight_target_at_all():
    """Even with zero observed disagreements, 24 states only bound the rate at 12%: the floor is
    1 - delta**(1/n). Asking for 5% from 24 states must fail rather than pretend."""
    assert cp_upper(0, 24) > 0.05
    q = Question.choice("Which handler?", OPTIONS, name="route")
    d = Decider(FakeBackend(content), prior="none", adaptive_shifts=True)
    cert = d.calibrate_adaptive(q, STATES[:24], target=0.05)
    assert cert["threshold"] is None
    assert d.decide(STATES[0], [q], level="L0")["route"].diagnostics["shifts_used"] == q.k


def test_a_pinned_margin_still_wins_and_the_old_statistic_is_still_reachable():
    q = Question.choice("Which handler?", OPTIONS, name="route")
    d = Decider(FakeBackend(content), adaptive_shifts=True, adaptive_stat="prob",
                adaptive_margin=0.5)
    out = d.decide(STATES[0], [q], level="L0")["route"]
    assert out.diagnostics["stop_stat"] == "prob"
    assert out.diagnostics["stop_threshold"] == 0.5


def test_waves_make_one_backend_call_per_wave_and_agree_with_reading_one_at_a_time():
    q = Question.choice("Which handler?", OPTIONS, name="route")
    one = Decider(FakeBackend(content, position_bias=[4.0] + [0] * 6), prior="none",
                  adaptive_shifts=True, adaptive_wave=1)
    wide = Decider(FakeBackend(content, position_bias=[4.0] + [0] * 6), prior="none",
                   adaptive_shifts=True, adaptive_wave=q.k)                 # one wave: every shift in a single call
    a = one.decide_batch(STATES, q, level="L0")
    b = wide.decide_batch(STATES, q, level="L0")
    assert wide.stats["backend_calls"] < one.stats["backend_calls"]
    assert all(x.diagnostics["shifts_used"] <= y.diagnostics["shifts_used"] for x, y in zip(a, b))
    assert np.mean([x.argmax == y.argmax for x, y in zip(a, b)]) >= 0.9


def test_bad_adaptive_configuration_is_refused():
    be = FakeBackend(content)
    for kwargs in ({"adaptive_stat": "gap"}, {"adaptive_target": 0.0}, {"adaptive_target": 1.0},
                   {"adaptive_wave": 0}, {"adaptive_margin": -1.0}, {"adaptive_min_shifts": 0}):
        with pytest.raises(ValueError):
            Decider(be, **kwargs)
