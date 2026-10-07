"""Baseline-vs-scenario comparison of result series (engine-agnostic, pure).

Two pandas Series (indexed by datetime) or two result frames go in; a small,
canonical delta record comes out. Keep this module free of mikeio/mikeplus so it
can be unit-tested and reused for SWMM/LSTM results.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .schema import parse_column
from .units import unit_for


def align(a: pd.Series, b: pd.Series) -> tuple[pd.Series, pd.Series, str]:
    """Put two series on one time index.

    Uses the exact common timestamps when the two series share (nearly) the same
    time base; otherwise interpolates ``b`` (in time) onto ``a``'s index. Returns
    ``(a, b, how)`` with ``how`` = ``'exact'`` or ``'interpolated'``.
    """
    a = a.dropna()
    b = b.dropna()
    common = a.index.intersection(b.index)
    if len(common) >= 2 and len(common) >= 0.9 * max(len(a), len(b)):
        return a.loc[common], b.loc[common], "exact"
    if len(a) < 2 or len(b) < 2:
        raise ValueError("series too short to align (need >= 2 points each)")
    union = a.index.union(b.index)
    bi = b.reindex(union).interpolate(method="time").reindex(a.index)
    lo, hi = b.index.min(), b.index.max()
    mask = (a.index >= lo) & (a.index <= hi)   # never extrapolate beyond b's span
    return a[mask], bi[mask], "interpolated"


def _volume(s: pd.Series) -> float:
    """Trapezoidal integral of a rate series (per-second) over its own time axis."""
    if len(s) < 2:
        return 0.0
    # seconds since the first step (resolution-agnostic: ns/us/s indexes all work)
    t = (s.index - s.index[0]).total_seconds().to_numpy(dtype=float)
    y = s.to_numpy(dtype=float)
    return float(np.sum(0.5 * (y[1:] + y[:-1]) * np.diff(t)))


def compare_series(a: pd.Series, b: pd.Series, quantity: str,
                   label_a: str = "baseline", label_b: str = "scenario") -> dict:
    """Canonical delta record for one element (b relative to a)."""
    aa, bb, how = align(a, b)
    if len(aa) < 2:
        raise ValueError("no overlapping time steps between the two series")
    unit = unit_for(quantity)
    av, bv = aa.to_numpy(dtype=float), bb.to_numpy(dtype=float)

    peak_a, peak_b = float(np.nanmax(av)), float(np.nanmax(bv))
    t_pa, t_pb = aa.idxmax(), bb.idxmax()
    diff = bv - av
    i_max = int(np.nanargmax(np.abs(diff)))
    denom = float(np.nansum((av - np.nanmean(av)) ** 2))
    nse = 1.0 - float(np.nansum(diff ** 2)) / denom if denom > 0 else None

    out = {
        "quantity": quantity,
        "unit": unit,
        "label_a": label_a,
        "label_b": label_b,
        "aligned": how,
        "n_points": int(len(aa)),
        "peak_a": round(peak_a, 6),
        "peak_b": round(peak_b, 6),
        "delta_peak": round(peak_b - peak_a, 6),
        "delta_peak_pct": _pct(peak_b - peak_a, peak_a),
        "peak_time_a": str(t_pa),
        "peak_time_b": str(t_pb),
        "peak_time_shift_min": round((t_pb - t_pa).total_seconds() / 60.0, 2),
        "mean_a": round(float(np.nanmean(av)), 6),
        "mean_b": round(float(np.nanmean(bv)), 6),
        "max_abs_diff": round(float(abs(diff[i_max])), 6),
        "max_abs_diff_time": str(aa.index[i_max]),
        "rmse": round(float(math.sqrt(np.nanmean(diff ** 2))), 6),
        "nse_b_vs_a": None if nse is None else round(nse, 4),
    }
    if unit.endswith("/s"):   # a rate -> integrate to a volume (m3/s -> m3)
        va, vb = _volume(aa), _volume(bb)
        out.update({
            "volume_a": round(va, 3),
            "volume_b": round(vb, 3),
            "delta_volume": round(vb - va, 3),
            "delta_volume_pct": _pct(vb - va, va),
            "volume_unit": unit[:-2],   # 'm3/s' -> 'm3'
        })
    return out


def compare_frames(df_a: pd.DataFrame, df_b: pd.DataFrame, quantity: str,
                   top_n: int = 10, tol: float = 1e-6) -> dict:
    """Peak change per element for one quantity, across every column both frames share.

    Answers "where did the change matter?" after a parameter edit. Peaks are taken on
    each frame's own time axis (no alignment needed for a max).
    """
    cols_a = {str(c): c for c in df_a.columns if str(c).split(":", 1)[0] == quantity}
    cols_b = {str(c): c for c in df_b.columns if str(c).split(":", 1)[0] == quantity}
    shared = [c for c in cols_a if c in cols_b]
    if not shared:
        raise ValueError(f"no shared {quantity!r} columns between the two results")

    rows = []
    for c in shared:
        pa = float(df_a[cols_a[c]].max())
        pb = float(df_b[cols_b[c]].max())
        if math.isnan(pa) or math.isnan(pb):
            continue
        meta = parse_column(c)
        rows.append({
            "element_id": meta["element_id"],
            "chainage": meta["chainage"],
            "peak_a": round(pa, 6),
            "peak_b": round(pb, 6),
            "delta_peak": round(pb - pa, 6),
            "delta_peak_pct": _pct(pb - pa, pa),
        })
    deltas = np.array([r["delta_peak"] for r in rows], dtype=float)
    rows.sort(key=lambda r: -abs(r["delta_peak"]))
    return {
        "quantity": quantity,
        "unit": unit_for(quantity),
        "n_shared": len(rows),
        "n_only_a": len(cols_a) - len(shared),
        "n_only_b": len(cols_b) - len(shared),
        "n_increased": int((deltas > tol).sum()),
        "n_decreased": int((deltas < -tol).sum()),
        "n_unchanged": int((np.abs(deltas) <= tol).sum()),
        "top": rows[:top_n],
    }


def _pct(delta: float, base: float):
    if base is None or base == 0 or math.isnan(base):
        return None
    return round(100.0 * delta / abs(base), 2)
