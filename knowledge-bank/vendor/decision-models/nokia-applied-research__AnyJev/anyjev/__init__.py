"""AnyJev: turn any causal LLM into a Jev-style decision model.

Typed decisions (choice / score / noul) with probabilities, read from the model's next-token logits
in one prefill. Two ways in:

- training-free, any open LLM: `Decider` reads the decision directly (`raw`), or with zero-label
  debiasing (`L0`, the default);
- self-distilled: `Tacit` runs AnyJev's own Tacit models, one forward per decision, and can send
  its least confident decisions to the model's own reasoning (`adaptive=True`).

Not affiliated with, endorsed by, or derived from TypeSafe AI or Jev.
"""
from anyjev.decider import Decider
from anyjev.question import Question
from anyjev.result import Decision, DecisionSet, LevelError
from anyjev.tacit import Tacit

__all__ = ["Question", "Decision", "DecisionSet", "Decider", "LevelError", "Tacit"]
try:  # single source of truth: the installed package metadata
    from importlib.metadata import version as _pkg_version

    __version__ = _pkg_version("anyjev")
except Exception:  # not installed (source checkout); keep in step with pyproject.toml
    __version__ = "0.3.0"
