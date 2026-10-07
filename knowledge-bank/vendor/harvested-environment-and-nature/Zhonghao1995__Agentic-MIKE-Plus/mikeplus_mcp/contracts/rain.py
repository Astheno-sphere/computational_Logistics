"""Rainfall input contract (pure): a timestamped CSV -> a clean intensity series.

MIKE+ rainfall boundaries take a .dfs0 of *Rainfall Intensity* (mm/h, mean-step-
backward) — the same shape as DHI's own example files. This module does the
parsing/validation/unit conversion so the mikeio-writing worker stays trivial.
"""
from __future__ import annotations

import pandas as pd

INTENSITY_UNITS = {"mm/h", "mm/hr", "mm per hour"}
DEPTH_UNITS = {"mm", "mm/step", "mm per step"}


def load_rain_csv(csv_path: str, time_col: str | None = None, value_col: str | None = None) -> pd.Series:
    """Read a CSV into a float Series indexed by datetime (sorted, deduplicated).

    ``time_col`` / ``value_col`` default to the first and second columns.
    """
    df = pd.read_csv(csv_path)
    if df.shape[1] < 2:
        raise ValueError("rain CSV needs at least two columns (time, value)")
    tcol = time_col or df.columns[0]
    vcol = value_col or df.columns[1]
    for c in (tcol, vcol):
        if c not in df.columns:
            raise ValueError(f"column {c!r} not in CSV (have {list(df.columns)})")
    t = pd.to_datetime(df[tcol], errors="raise")
    v = pd.to_numeric(df[vcol], errors="coerce")
    s = pd.Series(v.to_numpy(dtype=float), index=pd.DatetimeIndex(t), name="Rainfall")
    s = s[~s.index.duplicated(keep="first")].sort_index()
    if s.isna().any():
        raise ValueError(f"{int(s.isna().sum())} non-numeric rainfall value(s) in column {vcol!r}")
    if (s < 0).any():
        raise ValueError("negative rainfall values")
    if len(s) < 2:
        raise ValueError("need at least two time steps")
    return s


def to_intensity(s: pd.Series, unit: str = "mm/h") -> tuple[pd.Series, dict]:
    """Return an intensity series in mm/h plus a small provenance dict.

    ``unit='mm'`` means depth per step: converted with each step's own duration
    (the last step reuses the previous duration).
    """
    u = unit.strip().lower()
    dt_s = pd.Series(s.index, index=s.index).diff().shift(-1).dt.total_seconds()
    dt_s.iloc[-1] = dt_s.iloc[-2] if len(dt_s) > 1 else dt_s.iloc[-1]
    if (dt_s <= 0).any():
        raise ValueError("time steps must be strictly increasing")
    if u in INTENSITY_UNITS:
        inten = s.astype(float)
        depth_mm = float((inten * dt_s / 3600.0).sum())
        conv = "none"
    elif u in DEPTH_UNITS:
        inten = s.astype(float) * 3600.0 / dt_s
        depth_mm = float(s.sum())
        conv = "depth per step (mm) -> intensity (mm/h)"
    else:
        raise ValueError(f"unsupported rain unit {unit!r}; use 'mm/h' (intensity) or 'mm' (depth per step)")
    info = {
        "input_unit": unit,
        "conversion": conv,
        "n_steps": int(len(inten)),
        "start": str(inten.index[0]),
        "end": str(inten.index[-1]),
        "timestep_s": float(dt_s.iloc[0]),
        "uniform_step": bool(dt_s.iloc[:-1].nunique() == 1),
        "total_depth_mm": round(depth_mm, 3),
        "peak_intensity_mm_h": round(float(inten.max()), 3),
        "peak_time": str(inten.idxmax()),
    }
    return inten.rename("Rainfall"), info
