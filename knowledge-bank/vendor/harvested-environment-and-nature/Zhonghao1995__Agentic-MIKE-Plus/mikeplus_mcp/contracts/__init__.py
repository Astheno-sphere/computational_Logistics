"""Engine-agnostic contracts — the 'narrow waist'.

schema / units / plot_style / compare / topology / rain / manifest / inp are
deliberately kept pure (no mikeplus/mikeio imports at module top) so they can be
reused by any engine adapter (MIKE+, SWMM, LSTM), imported anywhere, and
unit-tested without a license.
"""
