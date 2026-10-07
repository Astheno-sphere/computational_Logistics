"""The level contract is enforceable: require= refuses probabilities below the asked level."""
import pytest

from anyjev import Decider, LevelError, Question
from anyjev.backends.fake import FakeBackend

OPTIONS = ["billing", "technical", "sales", "other"]
TRUTH = {"card declined": "billing", "app crashes": "technical", "bulk discount": "sales"}


def content(state, option):
    return 3.0 if TRUTH.get(state) == option else 0.0


def test_require_l0_refuses_raw():
    d = Decider(FakeBackend(content))
    q = Question.choice("Which handler?", OPTIONS, name="route")
    with pytest.raises(LevelError) as e:
        d.decide("card declined", [q], level="raw", require="L0")
    assert "route" in str(e.value)
    with pytest.raises(LevelError):
        d.decide_batch(list(TRUTH), q, level="raw", require="L0")


def test_require_passes_at_or_above_level():
    d = Decider(FakeBackend(content, temperature=0.3))
    q = Question.choice("Which handler?", OPTIONS, name="route")
    r = d.decide("card declined", [q], require="L0")
    assert r["route"].level == "L0"
    assert r["route"].require("raw") is r["route"]          # higher than asked is fine
    assert r.require("L0") is r


@pytest.mark.parametrize("level", ["L1", "L2", "L9"])
def test_require_rejects_unknown_level(level):
    d = Decider(FakeBackend(content))
    q = Question.choice("Which handler?", OPTIONS)
    with pytest.raises(ValueError):
        d.decide("x", [q], require=level)
